#!/usr/bin/env python3
"""Create pipeline-runner build/progress files from fixed templates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
TEMPLATE_DIR = ROOT / "skills" / "pipeline-runner" / "templates"
AXES = (
    ("SCOPE", "변경 범위"),
    ("SSOT", "SSOT 영향도"),
    ("CONTRACT", "데이터/API/계약 영향도"),
    ("VALIDATION", "테스트/검증 난이도"),
    ("RISK", "실패 리스크"),
    ("DEPENDENCY", "의존성/불확실성"),
    ("SPLIT", "작업 분할 필요성"),
)


def slug_from_requirement(path: Path) -> str:
    stem = path.stem
    return stem.removeprefix("requirement-") or stem


def load_json_arg(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    candidate = Path(raw)
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(raw)


def score_values(scores: dict[str, Any], key: str) -> tuple[str, str]:
    value = scores.get(key) or scores.get(key.lower()) or {}
    if isinstance(value, list) and len(value) >= 2:
        return str(value[0]), str(value[1])
    if isinstance(value, dict):
        return str(value.get("score", "pending")), str(value.get("evidence", "pending"))
    return "pending", "pending"


def pipeline_skills(pipeline: str) -> list[str]:
    return [part.strip() for part in pipeline.split("->") if part.strip()]


def default_steps(pipeline: str, requirement: str) -> list[dict[str, str]]:
    skills = pipeline_skills(pipeline)
    steps: list[dict[str, str]] = []
    previous_output = requirement
    for index, skill in enumerate(skills, start=1):
        expected = "pending"
        params = "none"
        gate = "pending"
        next_input = "pending"
        if skill == "task-write":
            params = f"--from {requirement}"
            expected = "TASK path + task-write process dir"
            gate = "progress/handoff SUCCESS + Critic SUCCESS"
            next_input = "TASK path"
        elif skill == "ssot-write":
            expected = "SSOT paths + ssot process dir"
            gate = "consistency audit pass or AUDIT_BLOCKED"
            next_input = "TASK path + ssot process dir"
        elif skill == "work-packet-write":
            params = "--process <ssot-process-dir>"
            expected = "Work Packet path"
            gate = "Work Packet Ready"
            next_input = "Work Packet path"
        elif skill == "forge-scope":
            expected = "forge worktree + branch"
            gate = "build/test pass"
            next_input = "forge slug"
        elif skill == "ddr-loop":
            expected = "conformance result"
            gate = "conformance >= 99 or cap recorded"
            next_input = "forge branch"
        elif skill == "branch-review":
            expected = "review report"
            gate = "Recommendation recorded"
            next_input = "final report"
        steps.append(
            {
                "order": str(index),
                "skill": skill,
                "input": previous_output,
                "params": params,
                "output": expected,
                "gate": gate,
                "next": next_input,
                "status": "pending",
                "notes": "waiting for approval",
            }
        )
        previous_output = next_input
    return steps


def normalize_steps(raw: Any, pipeline: str, requirement: str) -> list[dict[str, str]]:
    if not raw:
        return default_steps(pipeline, requirement)
    out: list[dict[str, str]] = []
    for index, step in enumerate(raw, start=1):
        out.append(
            {
                "order": str(step.get("order", index)),
                "skill": str(step.get("skill", "pending")),
                "input": str(step.get("input", "pending")),
                "params": str(step.get("params", step.get("required_params", "none"))),
                "output": str(step.get("output", step.get("expected_output", "pending"))),
                "gate": str(step.get("gate", "pending")),
                "next": str(step.get("next", step.get("next_input", "pending"))),
                "status": str(step.get("status", "pending")),
                "notes": str(step.get("notes", "waiting for approval")),
            }
        )
    return out


def table_escape(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()


def step_parameter_rows(steps: list[dict[str, str]]) -> str:
    rows = []
    for step in steps:
        rows.append(
            "| {order} | {skill} | {input} | {params} | {output} | {gate} | {next} |".format(
                order=table_escape(step["order"]),
                skill=table_escape(step["skill"]),
                input=table_escape(step["input"]),
                params=table_escape(step["params"]),
                output=table_escape(step["output"]),
                gate=table_escape(step["gate"]),
                next=table_escape(step["next"]),
            )
        )
    return "\n".join(rows) or "| 1 | pending | pending | none | pending | pending | pending |"


def step_status_rows(steps: list[dict[str, str]]) -> str:
    rows = []
    for step in steps:
        rows.append(
            "| {order} | {skill} | {status} | {input} | {output} | {notes} |".format(
                order=table_escape(step["order"]),
                skill=table_escape(step["skill"]),
                status=table_escape(step["status"]),
                input=table_escape(step["input"]),
                output="pending",
                notes=table_escape(step["notes"]),
            )
        )
    return "\n".join(rows) or "| 1 | pending | pending | pending | pending | waiting for approval |"


def replace_all(template: str, replacements: dict[str, str]) -> str:
    out = template
    for key, value in replacements.items():
        out = out.replace("{{" + key + "}}", value)
    missing = sorted(set(re.findall(r"\{\{([^}]+)\}\}", out)))
    if missing:
        raise ValueError(f"unreplaced placeholders: {', '.join(missing)}")
    return out


def run_template_check(process: Path) -> int:
    sys.path.insert(0, str(SCRIPT_DIR))
    from pipeline_runner_check import check_template, emit  # type: ignore

    return emit(check_template(process))


def cmd_init(args: argparse.Namespace) -> int:
    requirement = Path(args.requirement)
    slug = args.name or slug_from_requirement(requirement)
    process = args.process_dir or Path(".process") / f"pipeline-{slug}"
    if process.exists() and not args.force:
        print(f"ERROR process dir already exists: {process}", file=sys.stderr)
        return 2

    scores = load_json_arg(args.scores_json, {})
    steps = normalize_steps(load_json_arg(args.steps_json, None), args.pipeline, str(requirement))
    replacements = {
        "SLUG": slug,
        "REQUIREMENT_PATH": str(requirement),
        "SOURCE_REQUEST": args.source_request or str(requirement),
        "APP": args.app or "unknown",
        "TOTAL_SCORE": str(args.total_score),
        "SIZE_BAND": args.size,
        "FORCED_CONDITIONS": args.forced_conditions,
        "SELECTED_PIPELINE": args.pipeline,
        "STEP_PARAMETER_ROWS": step_parameter_rows(steps),
        "STEP_STATUS_ROWS": step_status_rows(steps),
        "LAST_UPDATED": args.date or date.today().isoformat(),
        "RISK_NOTES": args.risk_notes,
    }
    for prefix, axis in AXES:
        score, evidence = score_values(scores, axis)
        replacements[f"{prefix}_SCORE"] = score
        replacements[f"{prefix}_EVIDENCE"] = evidence

    build_template = (TEMPLATE_DIR / "pipeline-build.md").read_text(encoding="utf-8")
    progress_template = (TEMPLATE_DIR / "pipeline-progress.md").read_text(encoding="utf-8")
    build = replace_all(build_template, replacements)
    progress = replace_all(progress_template, replacements)

    process.mkdir(parents=True, exist_ok=True)
    (process / "pipeline-build.md").write_text(build, encoding="utf-8")
    (process / "pipeline-progress.md").write_text(progress, encoding="utf-8")

    print(f"CREATE {process / 'pipeline-build.md'}")
    print(f"CREATE {process / 'pipeline-progress.md'}")
    return run_template_check(process)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init")
    init.add_argument("--requirement", required=True)
    init.add_argument("--app", default="unknown")
    init.add_argument("--name")
    init.add_argument("--source-request")
    init.add_argument("--pipeline", required=True)
    init.add_argument("--total-score", default="pending")
    init.add_argument("--size", default="pending")
    init.add_argument("--forced-conditions", default="none")
    init.add_argument("--risk-notes", default="none")
    init.add_argument("--scores-json")
    init.add_argument("--steps-json")
    init.add_argument("--process-dir", type=Path)
    init.add_argument("--date")
    init.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
