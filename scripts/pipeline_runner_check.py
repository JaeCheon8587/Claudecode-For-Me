#!/usr/bin/env python3
"""Validate pipeline-runner build/progress contracts."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


BUILD_REQUIRED_HEADINGS = (
    "## Input",
    "## Scale Assessment",
    "## Routing Decision",
    "## Step Parameters",
    "## Approval",
    "## Risk Notes",
)
PROGRESS_REQUIRED_HEADINGS = (
    "## Current State",
    "## Step Status",
    "## Output Registry",
    "## Decisions / Deviations",
    "## Append-only Log",
    "## Final Output",
)
BUILD_REQUIRED_HEADERS = (
    "| Axis | Score | Evidence |",
    "| Order | Skill | Input | Required Params | Expected Output | Gate | Next Input |",
)
PROGRESS_REQUIRED_HEADERS = (
    "| Order | Skill | Status | Input | Output | Notes |",
)
APPROVAL_STATUSES = {"pending", "approved", "rejected"}
CURRENT_STATUSES = {"pending", "in-progress", "done", "blocked"}
STEP_STATUSES = {"pending", "doing", "done", "blocked", "skipped"}
EMPTY_VALUES = {"", "pending", "none", "n/a", "not run", "skipped"}


@dataclass
class Check:
    ok: bool
    code: str
    message: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _line_value(text: str, key: str) -> str | None:
    pattern = re.compile(rf"^-\s*{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _has_placeholder(text: str) -> bool:
    return bool(re.search(r"\{\{[^}]+\}\}", text))


def _table_rows_after_header(text: str, header: str) -> list[list[str]]:
    lines = text.splitlines()
    rows: list[list[str]] = []
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        for row in lines[index + 2 :]:
            stripped = row.strip()
            if not stripped.startswith("|"):
                break
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            rows.append(cells)
        break
    return rows


def _strip_md(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value.strip()


def _looks_like_path(value: str) -> bool:
    value = _strip_md(value)
    return (
        "/" in value
        or "\\" in value
        or value.endswith(".md")
        or value.startswith(".process")
        or value.startswith(".worktree")
        or value.startswith(".review")
    )


def _candidate_paths(value: str) -> list[str]:
    raw = _strip_md(value)
    candidates = re.findall(r"`([^`]+)`", value)
    candidates.extend(re.findall(r"(?<!\w)([A-Za-z0-9_./\\-]+\.(?:md|csproj|cs|json))", raw))
    candidates.extend(re.findall(r"(?<!\w)(\.(?:process|worktree|review)[A-Za-z0-9_./\\-]*)", raw))
    if _looks_like_path(raw):
        candidates.append(raw)
    out: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip().rstrip(".,;)")
        if cleaned and cleaned.lower() not in EMPTY_VALUES and cleaned not in out:
            out.append(cleaned)
    return out


def check_template(process: Path) -> list[Check]:
    build = process / "pipeline-build.md"
    progress = process / "pipeline-progress.md"
    checks: list[Check] = []

    for path, label in ((build, "BUILD"), (progress, "PROGRESS")):
        if path.is_file():
            checks.append(Check(True, f"{label}_FILE", f"{path} exists"))
        else:
            checks.append(Check(False, f"{label}_FILE", f"{path} missing"))

    if not build.is_file() or not progress.is_file():
        return checks

    build_text = _read(build)
    progress_text = _read(progress)

    for heading in BUILD_REQUIRED_HEADINGS:
        checks.append(Check(heading in build_text, "BUILD_HEADING", heading))
    for heading in PROGRESS_REQUIRED_HEADINGS:
        checks.append(Check(heading in progress_text, "PROGRESS_HEADING", heading))
    for header in BUILD_REQUIRED_HEADERS:
        checks.append(Check(header in build_text, "BUILD_HEADER", header))
    for header in PROGRESS_REQUIRED_HEADERS:
        checks.append(Check(header in progress_text, "PROGRESS_HEADER", header))

    checks.append(Check(not _has_placeholder(build_text), "BUILD_PLACEHOLDER", "no {{...}} placeholders"))
    checks.append(Check(not _has_placeholder(progress_text), "PROGRESS_PLACEHOLDER", "no {{...}} placeholders"))
    return checks


def check_approval(process: Path) -> list[Check]:
    checks = check_template(process)
    build = process / "pipeline-build.md"
    progress = process / "pipeline-progress.md"
    if not build.is_file() or not progress.is_file():
        return checks

    build_text = _read(build)
    progress_text = _read(progress)
    status = _line_value(build_text, "Status")
    checks.append(Check(status in APPROVAL_STATUSES, "APPROVAL_STATUS_ALLOWED", f"Status={status}"))
    checks.append(Check(status == "approved", "APPROVAL_APPROVED", "Approval Status must be approved before Phase 4"))

    approved_by = _line_value(build_text, "Approved By")
    approved_at = _line_value(build_text, "Approved At")
    checks.append(Check(bool(approved_by and approved_by != "pending"), "APPROVED_BY", f"Approved By={approved_by}"))
    checks.append(Check(bool(approved_at and approved_at != "pending"), "APPROVED_AT", f"Approved At={approved_at}"))

    current = _line_value(progress_text, "Status")
    checks.append(Check(current in CURRENT_STATUSES, "CURRENT_STATUS_ALLOWED", f"Current Status={current}"))
    return checks


def check_progress(process: Path, allow_doing: bool = False) -> list[Check]:
    checks = check_template(process)
    progress = process / "pipeline-progress.md"
    if not progress.is_file():
        return checks

    text = _read(progress)
    current = _line_value(text, "Status")
    checks.append(Check(current in CURRENT_STATUSES, "CURRENT_STATUS_ALLOWED", f"Current Status={current}"))

    rows = _table_rows_after_header(text, "| Order | Skill | Status | Input | Output | Notes |")
    checks.append(Check(bool(rows), "STEP_ROWS", "Step Status rows exist"))
    for row in rows:
        if len(row) < 6:
            checks.append(Check(False, "STEP_ROW_SHAPE", "Step row must have 6 cells"))
            continue
        skill = row[1]
        status = row[2]
        checks.append(Check(status in STEP_STATUSES, "STEP_STATUS_ALLOWED", f"{skill}={status}"))
        if status == "doing" and not allow_doing:
            checks.append(Check(False, "STEP_STATUS_DOING", f"{skill} still doing"))
    return checks


def check_outputs(process: Path, repo: Path) -> list[Check]:
    checks = check_progress(process)
    progress = process / "pipeline-progress.md"
    if not progress.is_file():
        return checks

    text = _read(progress)
    rows = _table_rows_after_header(text, "| Order | Skill | Status | Input | Output | Notes |")
    for row in rows:
        if len(row) < 6:
            continue
        skill, status, output = row[1], row[2], row[4]
        if status == "done":
            normalized = _strip_md(output).lower()
            checks.append(Check(normalized not in EMPTY_VALUES, "STEP_OUTPUT_PRESENT", f"{skill} output present"))
            for candidate in _candidate_paths(output):
                path = (repo / candidate).resolve()
                checks.append(Check(path.exists(), "STEP_OUTPUT_EXISTS", f"{skill} output exists: {candidate}"))

    registry_match = re.search(r"## Output Registry(?P<body>.*?)(?:\n## |\Z)", text, re.DOTALL)
    if registry_match:
        body = registry_match.group("body")
        for line in body.splitlines():
            if not line.strip().startswith("- "):
                continue
            _, _, value = line.partition(":")
            cleaned = _strip_md(value)
            if cleaned.lower() in EMPTY_VALUES:
                continue
            for candidate in _candidate_paths(cleaned):
                path = (repo / candidate).resolve()
                checks.append(Check(path.exists(), "REGISTRY_OUTPUT_EXISTS", f"registry output exists: {candidate}"))
    else:
        checks.append(Check(False, "OUTPUT_REGISTRY", "Output Registry section missing"))

    final_match = re.search(r"## Final Output(?P<body>.*?)(?:\n## |\Z)", text, re.DOTALL)
    checks.append(Check(bool(final_match), "FINAL_OUTPUT", "Final Output section exists"))
    return checks


def emit(checks: list[Check]) -> int:
    failed = 0
    encoding = sys.stdout.encoding or "utf-8"

    def safe_print(text: str) -> None:
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))

    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        if not check.ok:
            failed += 1
        safe_print(f"{status} {check.code} {check.message}")
    safe_print(f"Summary: {len(checks) - failed} PASS, {failed} FAIL")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("template", "approval", "progress", "outputs"):
        sp = sub.add_parser(name)
        sp.add_argument("--process", required=True, type=Path)
        if name == "progress":
            sp.add_argument("--allow-doing", action="store_true")
        if name == "outputs":
            sp.add_argument("--repo", type=Path, default=Path("."))

    args = parser.parse_args(argv)
    process = args.process
    if not process.is_dir():
        print(f"ERROR process dir missing: {process}", file=sys.stderr)
        return 2

    if args.cmd == "template":
        return emit(check_template(process))
    if args.cmd == "approval":
        return emit(check_approval(process))
    if args.cmd == "progress":
        return emit(check_progress(process, allow_doing=args.allow_doing))
    if args.cmd == "outputs":
        return emit(check_outputs(process, repo=args.repo))
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
