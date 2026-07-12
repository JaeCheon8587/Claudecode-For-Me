from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


CONTRACT_VERSION = 5
SSOT_TYPES = ("PRD", "FC", "FRD", "ADR", "ADR-CATALOG", "ARCHITECTURE")
ROLE_MODEL = {
    "judge": "opus",
    "editor": "sonnet",
    "reviewer": "opus",
    "auditor": "opus",
}
ROLE_TEMPLATE = {
    "judge": "skills/ssot-write/templates/document-judge-input.md",
    "editor": "skills/ssot-write/templates/document-editor-input.md",
    "reviewer": "skills/ssot-write/templates/document-reviewer-input.md",
    "auditor": "skills/ssot-write/templates/cross-auditor-input.md",
}
ROLE_STATUS = {
    "judge": {"READY", "BLOCKED", "FAIL"},
    "editor": {"PASS", "BLOCKED", "FAIL"},
    "reviewer": {"PASS", "FAIL", "BLOCKED"},
    "auditor": {"PASS", "FAIL", "BLOCKED"},
}
RESULT_FIELDS = {
    "contract_version", "dispatch_id", "stage", "role", "mode", "status",
    "artifact", "failure_class", "question_id", "question", "changed",
    "affected_paths",
}
TARGET_ACTIONS = {"CREATE", "UPDATE"}


class ContractError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _normalize_rel(value: str) -> str:
    return Path(value.replace("\\", "/")).as_posix().lstrip("./")


def _resolve_under(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractError(f"Path escapes root: {value}") from exc
    return path


def _repo_rel(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"Path is outside repo: {path}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"Required JSON missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _process_path(value: str | Path) -> Path:
    return Path(value).resolve()


def _state_path(process: Path) -> Path:
    return process / "state.json"


def _load_state(process: Path) -> dict[str, Any]:
    state = _read_json(_state_path(process))
    if state.get("contract_version") != CONTRACT_VERSION:
        raise ContractError(
            f"Contract version mismatch: expected {CONTRACT_VERSION}, "
            f"found {state.get('contract_version')}"
        )
    return state


def _append_event(process: Path, event: dict[str, Any]) -> None:
    row = {"at": _now(), **event}
    with (process / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _save_state(process: Path, state: dict[str, Any], event: dict[str, Any] | None = None) -> None:
    state["updated_at"] = _now()
    _write_json(_state_path(process), state)
    if event:
        _append_event(process, event)
    _render_views(process, state)


def _scan_docs(repo: Path, app: str) -> dict[str, str]:
    root = repo / "Docs" / app
    if not root.is_dir():
        raise ContractError(f"Docs app directory missing: {root}")
    return {
        path.relative_to(repo).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*.md"))
        if path.is_file()
    }


def _snapshot(process: Path, state: dict[str, Any], label: str) -> None:
    manifest = _scan_docs(Path(state["repo_root"]), state["app"])
    _write_json(process / "snapshots" / f"{label}.json", manifest)


def _snapshot_changed(process: Path, state: dict[str, Any], label: str) -> list[str]:
    before = _read_json(process / "snapshots" / f"{label}.json")
    after = _scan_docs(Path(state["repo_root"]), state["app"])
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _write_patch(process: Path, state: dict[str, Any]) -> list[str]:
    repo = Path(state["repo_root"])
    original = _read_json(process / "snapshots" / "original.json")
    current = _scan_docs(repo, state["app"])
    changed = sorted(path for path in set(original) | set(current) if original.get(path) != current.get(path))
    lines: list[str] = []
    baseline = process / "baseline"
    for rel in changed:
        old_path = baseline / rel
        new_path = repo / rel
        old = old_path.read_text(encoding="utf-8").splitlines(True) if old_path.is_file() else []
        new = new_path.read_text(encoding="utf-8").splitlines(True) if new_path.is_file() else []
        lines.extend(difflib.unified_diff(old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    (process / "changes.patch").write_text("".join(lines), encoding="utf-8")
    state["changed_paths"] = changed
    return changed


def _create_original_snapshot(process: Path, state: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    root = repo / "Docs" / state["app"]
    baseline = process / "baseline"
    for source in root.rglob("*.md"):
        if source.is_file():
            target = baseline / source.relative_to(repo)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    _snapshot(process, state, "original")


def _task_source(repo: Path, task_rel: str) -> dict[str, Any]:
    text = (repo / task_rel).read_text(encoding="utf-8")
    status_match = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
    status = status_match.group(1).strip() if status_match else "UNSPECIFIED"
    ids = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_-]+-(?:ADR|FRD|TASK)-\d{3}\b", text)))
    headings = [m.group(1).strip() for m in re.finditer(r"^#{2,3}\s+(.+)$", text, re.MULTILINE)]
    return {
        "contract_version": CONTRACT_VERSION,
        "task": task_rel,
        "status": status,
        "referenced_ids": ids,
        "headings": headings,
        "high_signal_terms": _high_signal_terms(text),
    }


def _high_signal_terms(text: str) -> list[str]:
    """Extract exact technical terms suitable for conservative document routing."""
    terms: set[str] = set()
    for code in re.findall(r"`([^`\r\n]{3,100})`", text):
        terms.update(re.findall(r"[A-Za-z][A-Za-z0-9_.-]{3,}|[A-Z][A-Z0-9_]{3,}", code))
    terms.update(re.findall(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b", text))
    terms.update(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+\b", text))
    ignored = {
        "TASK", "MASTER", "UPDATE", "CREATE", "SKIP", "READY", "PASS", "FAIL",
        "TODO", "NONE", "NULL", "TRUE", "FALSE", "COUNT", "STRING",
        "DATA", "DESCRIPTION", "REGION", "SUMMARY", "TARGET", "VALUE", "VALUES",
        "COLUMNS", "EXTRACT", "CLONE", "INFRASTRUCTURE", "TESTS",
    }

    def distinctive(term: str) -> bool:
        if term.upper() in ignored:
            return False
        if "_" in term:
            return True
        capitals = sum(1 for char in term if char.isupper())
        return capitals >= 2

    return sorted(
        term for term in terms
        if len(term) >= 4 and distinctive(term) and not term.isdigit()
    )


def _relationship_targets(text: str, app: str) -> list[tuple[str, str]]:
    adr_pattern = rf"{re.escape(app)}-ADR-\d{{3}}"
    edges: list[tuple[str, str]] = []
    for match in re.finditer(
        rf"Superseded\s*(?:\(\s*)?by\s*[:：]?\s*`?({adr_pattern})`?\s*\)?",
        text,
        re.IGNORECASE,
    ):
        edges.append((_canonical_adr(app, match.group(1)), "superseded-by"))
    for match in re.finditer(
        r"^\|\s*(?:Superseded By|대체 ADR|승계 ADR)\s*\|\s*([^|]+)\|",
        text,
        re.MULTILINE | re.IGNORECASE,
    ):
        edges.extend((_canonical_adr(app, value), "structured-superseded-by") for value in re.findall(adr_pattern, match.group(1), re.IGNORECASE))
    return edges


def _supersedes_predecessors(text: str, app: str) -> list[tuple[str, str]]:
    adr_pattern = rf"{re.escape(app)}-ADR-\d{{3}}"
    values: list[tuple[str, str]] = []
    patterns = (
        r"\*\*supersedes\*\*\s*[:：]\s*([^\r\n]+)",
        r"^\|\s*Supersedes\s*\|\s*([^|]+)\|",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
            values.extend((_canonical_adr(app, value), "supersedes") for value in re.findall(adr_pattern, match.group(1), re.IGNORECASE))
    return values


def _canonical_adr(app: str, value: str) -> str:
    match = re.search(r"ADR-(\d{3})", value, re.IGNORECASE)
    if not match:
        raise ContractError(f"Invalid ADR identifier: {value}")
    return f"{app}-ADR-{match.group(1)}"


def _resolve_authority(repo: Path, app: str, source: dict[str, Any]) -> dict[str, Any]:
    """Build authority facts without asking an LLM to infer graph structure."""
    root = repo / "Docs" / app / "ADR"
    statuses: dict[str, str] = {}
    superseded_by: dict[str, list[str]] = {}
    evidence: list[dict[str, str]] = []
    for path in sorted(root.glob(f"{app}-ADR-*.md")) if root.is_dir() else []:
        text = path.read_text(encoding="utf-8")
        adr_id = path.stem
        match = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        statuses[adr_id] = match.group(1).strip() if match else "UNSPECIFIED"
        for target, source_kind in _relationship_targets(text, app):
            if target != adr_id:
                superseded_by.setdefault(adr_id, []).append(target)
                evidence.append({"from": adr_id, "to": target, "path": _repo_rel(repo, path), "source": source_kind})
        for predecessor, source_kind in _supersedes_predecessors(text, app):
            if predecessor != adr_id:
                superseded_by.setdefault(predecessor, []).append(adr_id)
                evidence.append({"from": predecessor, "to": adr_id, "path": _repo_rel(repo, path), "source": source_kind})
    referenced = [
        _canonical_adr(app, item)
        for item in source.get("referenced_ids", [])
        if "-ADR-" in item.upper()
    ]
    normalized_edges = {key: sorted(set(value)) for key, value in superseded_by.items()}

    def chain(start: str) -> list[str]:
        ordered: list[str] = []
        pending = [start]
        seen: set[str] = set()
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            ordered.append(current)
            pending.extend(normalized_edges.get(current, []))
        return ordered

    return {
        "contract_version": CONTRACT_VERSION,
        "basis_candidates": referenced,
        "statuses": statuses,
        "superseded_by": normalized_edges,
        "relationship_evidence": sorted(evidence, key=lambda row: (row["from"], row["to"], row["path"])),
        "chains": {basis: chain(basis) for basis in referenced},
        "resolver": "runner",
    }


def _candidate_paths(repo: Path, app: str, kind: str) -> list[str]:
    root = repo / "Docs" / app
    patterns = {
        "PRD": [root / f"{app}-PRD.md"],
        "FC": [root / f"{app}-FC.md"],
        "FRD": sorted((root / "FRD").glob(f"{app}-FRD-*.md")),
        "ADR": sorted((root / "ADR").glob(f"{app}-ADR-*.md")),
        "ADR-CATALOG": [root / f"{app}-ADR-CATALOG.md"],
        "ARCHITECTURE": [root / f"{app}-ARCHITECTURE.md"],
    }[kind]
    return [_repo_rel(repo, path) for path in patterns if path.is_file()]


def _route_candidate_paths(
    repo: Path, all_paths: list[str], source: dict[str, Any], kind: str
) -> tuple[list[str], str, dict[str, list[str]]]:
    if kind not in {"FRD", "ADR"} or len(all_paths) <= 1:
        return all_paths, "all", {}
    referenced = set(source.get("referenced_ids", []))
    terms = source.get("high_signal_terms", [])
    matched: dict[str, list[str]] = {}
    for rel in all_paths:
        path = repo / rel
        text = path.read_text(encoding="utf-8")
        hits = [term for term in terms if term.casefold() in text.casefold()]
        if path.stem.casefold() in {item.casefold() for item in referenced}:
            hits.insert(0, path.stem)
        if hits:
            matched[rel] = sorted(set(hits))
    selected = sorted(matched)
    if not selected:
        return all_paths, "fallback-all-no-match", {}
    if len(selected) * 4 >= len(all_paths) * 3:
        return all_paths, "fallback-all-broad-match", matched
    return selected, "high-signal", matched


def _classify_ssot_path(app: str, rel: str) -> str | None:
    rel = _normalize_rel(rel)
    exact = {
        f"Docs/{app}/{app}-PRD.md": "PRD",
        f"Docs/{app}/{app}-FC.md": "FC",
        f"Docs/{app}/{app}-ADR-CATALOG.md": "ADR-CATALOG",
        f"Docs/{app}/{app}-ARCHITECTURE.md": "ARCHITECTURE",
    }
    if rel in exact:
        return exact[rel]
    if re.fullmatch(rf"Docs/{re.escape(app)}/FRD/{re.escape(app)}-FRD-\d{{3}}\.md", rel):
        return "FRD"
    if re.fullmatch(rf"Docs/{re.escape(app)}/ADR/{re.escape(app)}-ADR-\d{{3}}\.md", rel):
        return "ADR"
    return None


def _collect_candidates(repo: Path, app: str, source: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for index, kind in enumerate(SSOT_TYPES, 1):
        all_paths = _candidate_paths(repo, app, kind)
        selected, selection_mode, matched_terms = _route_candidate_paths(repo, all_paths, source, kind)
        rows.append({
            "candidate_id": f"CAND-{index:03d}",
            "ssot_type": kind,
            "paths": selected,
            "all_path_count": len(all_paths),
            "selection_mode": selection_mode,
            "matched_terms": matched_terms,
        })
    return {"contract_version": CONTRACT_VERSION, "candidates": rows}


def _render_views(process: Path, state: dict[str, Any]) -> None:
    stages = state.get("stage_results", {})
    rows = "\n".join(
        f"| {name} | {value.get('owner')} | {value.get('status')} | {value.get('result') or 'none'} |"
        for name, value in stages.items()
    )
    build = f"""# ssot-write Orchestration Build\n\nGenerated by runner. Do not edit manually.\n\n- Contract: v{CONTRACT_VERSION}\n- Pattern: source → per-document judge → compile → per-file editor → per-file review → cross audit\n- Process: `{state['process_rel']}`\n\n## Ownership\n\n| Unit | Owner | Responsibility |\n|---|---|---|\n| source/candidates/plan | runner | extract, collect, compile |\n| document judgment | judge | one SSOT type only |\n| document edit | editor | one path only |\n| document review | reviewer | one changed path only |\n| cross audit | auditor | relationships only |\n"""
    progress = f"""# ssot-write Orchestration Progress\n\nGenerated by runner. Do not edit manually.\n\n- Run status: {state['run_status']}\n- Current stage: {state['current_stage']}\n- Next role: {state.get('next_role') or 'none'}\n- Dispatch sequence: {state['dispatch_seq']}\n\n| Stage | Owner | Status | Result |\n|---|---|---|---|\n{rows}\n"""
    (process / "ssot-write-orchestration-build.md").write_text(build, encoding="utf-8")
    (process / "ssot-write-orchestration-progress.md").write_text(progress, encoding="utf-8")
    (process / "ssot-write-build.md").write_text(build.replace("Orchestration ", ""), encoding="utf-8")
    (process / "ssot-write-progress.md").write_text(progress.replace("Orchestration ", ""), encoding="utf-8")


def init_run(repo: Path, task: str, app: str, process: Path | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    task_rel = _normalize_rel(task)
    task_path = _resolve_under(repo, task_rel)
    expected_prefix = f"Docs/{app}/TASK/"
    if not task_path.is_file() or not task_rel.lower().startswith(expected_prefix.lower()):
        raise ContractError(f"Invalid TASK path for {app}: {task}")
    process = (process or repo / ".process" / task_path.stem).resolve()
    if _state_path(process).is_file():
        _load_state(process)
        return {"action": "resume", "process": str(process), "contract_version": CONTRACT_VERSION}
    process.mkdir(parents=True, exist_ok=True)
    source = _task_source(repo, task_rel)
    candidates = _collect_candidates(repo, app, source)
    _write_json(process / "source.json", source)
    _write_json(process / "authority.json", _resolve_authority(repo, app, source))
    _write_json(process / "candidates.json", candidates)
    _write_json(process / "decision.json", {"contract_version": CONTRACT_VERSION, "decisions": []})
    state = {
        "contract_version": CONTRACT_VERSION,
        "repo_root": str(repo), "task": task_rel, "app": app,
        "process_rel": _repo_rel(repo, process),
        "run_status": "running", "current_stage": "judge", "next_role": "judge", "next_mode": "judge",
        "dispatch_seq": 0, "active_dispatch": None,
        "candidate_queue": [row["candidate_id"] for row in candidates["candidates"]],
        "candidate_index": 0, "judgments": {}, "editor_queue": [], "editor_index": 0,
        "review_queue": [], "review_index": 0, "approved_changed_paths": [], "changed_paths": [],
        "audit_iteration": 0, "repair_attempts": 0, "rejudge_attempts": 0,
        "blocking_question_id": None, "blocking_question": None,
        "last_result": None, "last_failure_class": "NONE",
        "stage_results": {
            "source": {"owner": "runner", "status": "done", "result": "READY"},
            "judge": {"owner": "judge", "status": "pending", "result": None},
            "compile": {"owner": "runner", "status": "pending", "result": None},
            "edit": {"owner": "editor", "status": "pending", "result": None},
            "review": {"owner": "reviewer", "status": "pending", "result": None},
            "audit": {"owner": "auditor", "status": "pending", "result": None},
            "finalize": {"owner": "runner", "status": "pending", "result": None},
        },
        "created_at": _now(), "updated_at": _now(),
    }
    _create_original_snapshot(process, state)
    (process / "events.jsonl").write_text("", encoding="utf-8")
    _save_state(process, state, {"event": "init", "stage": "source", "result": "READY"})
    return {"action": "initialized", "process": str(process), "contract_version": CONTRACT_VERSION}


def _candidate(state: dict[str, Any], process: Path, candidate_id: str) -> dict[str, Any]:
    data = _read_json(process / "candidates.json")
    for row in data["candidates"]:
        if row["candidate_id"] == candidate_id:
            return row
    raise ContractError(f"Unknown candidate: {candidate_id}")


def _dispatch_spec(process: Path, state: dict[str, Any]) -> dict[str, Any]:
    role = state["next_role"]
    stage = state["current_stage"]
    mode = state["next_mode"]
    if role not in ROLE_MODEL:
        raise ContractError(f"No dispatch role: {role}")
    state["dispatch_seq"] += 1
    dispatch_id = f"{stage}-{state['dispatch_seq']:03d}"
    spec: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION, "dispatch_id": dispatch_id,
        "stage": stage, "role": role, "model": ROLE_MODEL[role], "mode": mode,
        "template": str((_plugin_root() / ROLE_TEMPLATE[role]).resolve()),
        "repo_root": state["repo_root"], "task": state["task"], "app": state["app"],
        "process": str(process), "source": str(process / "source.json"),
        "authority": str(process / "authority.json"),
        "candidates": str(process / "candidates.json"), "plan": str(process / "ssot-write-plan.json"),
        "patch": str(process / "changes.patch"), "result_path": str(process / "results" / f"{dispatch_id}.json"),
        "authorized_paths": [], "approved_changed_paths": list(state["approved_changed_paths"]),
        "affected_path": None, "candidate_id": None, "ssot_type": None,
    }
    if role == "judge":
        candidate_id = state["candidate_queue"][state["candidate_index"]]
        candidate = _candidate(state, process, candidate_id)
        spec.update({
            "candidate_id": candidate_id, "ssot_type": candidate["ssot_type"],
            "candidate_paths": candidate["paths"],
            "candidate_selection": {
                "mode": candidate.get("selection_mode"),
                "selected_count": len(candidate["paths"]),
                "all_path_count": candidate.get("all_path_count", len(candidate["paths"])),
                "matched_terms": candidate.get("matched_terms", {}),
            },
            "artifact": str(process / "judgments" / f"{candidate_id}.json"),
        })
    elif role == "editor":
        path = state["editor_queue"][state["editor_index"]]
        spec.update({"affected_path": path, "authorized_paths": [path],
                     "artifact": str(process / "editor-notes" / f"{dispatch_id}.md")})
    elif role == "reviewer":
        path = state["review_queue"][state["review_index"]]
        spec.update({"affected_path": path,
                     "artifact": str(process / "reviews" / f"{dispatch_id}.md")})
    else:
        spec["artifact"] = str(process / "ssot-write-audit.md")
    label = f"dispatch-{dispatch_id}"
    _snapshot(process, state, label)
    spec["snapshot_label"] = label
    rejection = state.pop("last_rejection", None)
    if rejection:
        spec["last_rejection"] = rejection
    state["active_dispatch"] = spec
    state["stage_results"][stage]["status"] = "doing"
    return spec


def next_action(process: Path) -> dict[str, Any]:
    process = _process_path(process)
    state = _load_state(process)
    if state["run_status"] == "done":
        return {"action": "done", "process": str(process), "report_path": str(process / "final-report.txt"),
                "response_mode": "verbatim", "allow_additional_text": False}
    if state["run_status"] == "blocked":
        return {"action": "ask_user", "question_id": state["blocking_question_id"],
                "question": state["blocking_question"]}
    if state.get("active_dispatch"):
        return {"action": "dispatch", **state["active_dispatch"]}
    spec = _dispatch_spec(process, state)
    _save_state(process, state, {"event": "dispatch", "stage": spec["stage"], "result": "pending"})
    return {"action": "dispatch", **spec}


def _validate_result(result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    unknown = set(result) - RESULT_FIELDS
    missing = RESULT_FIELDS - set(result)
    if unknown or missing:
        raise ContractError(f"Result fields mismatch: unknown={sorted(unknown)}, missing={sorted(missing)}")
    if result["contract_version"] != CONTRACT_VERSION:
        raise ContractError("Result contract version mismatch")
    for key in ("dispatch_id", "stage", "role", "mode"):
        if result[key] != dispatch[key]:
            raise ContractError(f"Result {key} mismatch")
    if result["status"] not in ROLE_STATUS[result["role"]]:
        raise ContractError(f"Invalid status for {result['role']}: {result['status']}")
    failure = result["failure_class"]
    if result["status"] == "FAIL" and result["role"] in {"reviewer", "auditor"}:
        if failure not in {"EXECUTION", "PLAN"}:
            raise ContractError("Review FAIL requires EXECUTION or PLAN")
    elif failure != "NONE":
        raise ContractError("Only review FAIL may use a failure class")
    if result["status"] == "BLOCKED":
        if not result["question_id"] or not result["question"]:
            raise ContractError("BLOCKED requires question fields")
    elif result["question_id"] is not None or result["question"] is not None:
        raise ContractError("Non-BLOCKED question fields must be null")
    if not isinstance(result["changed"], list) or not isinstance(result["affected_paths"], list):
        raise ContractError("changed and affected_paths must be lists")


def _validate_judgment(process: Path, state: dict[str, Any], dispatch: dict[str, Any]) -> dict[str, Any]:
    value = _read_json(Path(dispatch["artifact"]))
    fields = {"contract_version", "candidate_id", "ssot_type", "decision", "targets", "reason", "evidence"}
    if set(value) != fields:
        raise ContractError(f"Judgment fields mismatch: {sorted(set(value) ^ fields)}")
    if value["contract_version"] != CONTRACT_VERSION or value["candidate_id"] != dispatch["candidate_id"]:
        raise ContractError("Judgment identity mismatch")
    if value["ssot_type"] != dispatch["ssot_type"] or value["decision"] not in {"SKIP", "CHANGE", "BLOCKED"}:
        raise ContractError("Invalid judgment type or decision")
    if not isinstance(value["reason"], str) or not value["reason"].strip():
        raise ContractError("Judgment reason must be non-empty")
    if not isinstance(value["evidence"], list) or not all(isinstance(item, str) for item in value["evidence"]):
        raise ContractError("Judgment evidence must be a string list")
    targets = value["targets"]
    if not isinstance(targets, list):
        raise ContractError("Judgment targets must be a list")
    if (value["decision"] == "CHANGE") != bool(targets):
        raise ContractError("CHANGE requires targets; SKIP/BLOCKED prohibit targets")
    repo = Path(state["repo_root"])
    app_prefix = f"Docs/{state['app']}/"
    normalized: list[dict[str, str]] = []
    for target in targets:
        if not isinstance(target, dict) or set(target) != {"action", "path", "edit_scope", "reason"}:
            raise ContractError("Invalid judgment target schema")
        action = target["action"]
        path = _repo_rel(repo, _resolve_under(repo, target["path"]))
        if action not in TARGET_ACTIONS or not path.lower().startswith(app_prefix.lower()) or "/TASK/" in path.upper():
            raise ContractError(f"Invalid judgment target: {target}")
        if _classify_ssot_path(state["app"], path) != dispatch["ssot_type"]:
            raise ContractError(
                f"Judge for {dispatch['ssot_type']} cannot target another SSOT type: {path}"
            )
        target_path = repo / path
        if action == "UPDATE" and not target_path.is_file():
            raise ContractError(f"UPDATE target missing: {path}")
        if action == "CREATE" and target_path.exists():
            raise ContractError(f"CREATE target exists: {path}")
        normalized.append({**target, "path": path})
    value["targets"] = normalized
    return value


def _compile_plan(process: Path, state: dict[str, Any]) -> None:
    rows = []
    targets: list[dict[str, str]] = []
    path_actions: dict[str, str] = {}
    for candidate_id in state["candidate_queue"]:
        judgment = state["judgments"][candidate_id]
        action = "SKIP" if judgment["decision"] == "SKIP" else (
            judgment["targets"][0]["action"] if len({t["action"] for t in judgment["targets"]}) == 1 else "MIXED"
        )
        rows.append({"ssot_type": judgment["ssot_type"], "action": action,
                     "targets": judgment["targets"], "reason": judgment["reason"], "evidence": judgment["evidence"]})
        for target in judgment["targets"]:
            previous = path_actions.get(target["path"])
            if previous is not None:
                raise ContractError(f"Duplicate target across judgments: {target['path']}")
            path_actions[target["path"]] = target["action"]
            targets.append(target)
    paths = sorted({target["path"] for target in targets})
    plan = {
        "contract_version": CONTRACT_VERSION, "result": "READY", "matrix": rows,
        "authorized_paths": paths, "task_disposition": "ACTIVE",
        "ssot_result": "APPLY" if paths else "NOOP", "downstream": "WORK_PACKET",
        "compiled_by": "runner",
    }
    _write_json(process / "ssot-write-plan.json", plan)
    lines = ["# ssot-write Impact", "", "Compiled by runner from isolated judgments.", "",
             "| SSOT | Action | Targets |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['ssot_type']} | {row['action']} | {', '.join(t['path'] for t in row['targets']) or 'none'} |")
    (process / "ssot-write-impact.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    state["stage_results"]["compile"] = {"owner": "runner", "status": "done", "result": "READY"}
    state["editor_queue"] = paths
    state["editor_index"] = 0
    if paths:
        state.update({"current_stage": "edit", "next_role": "editor", "next_mode": "apply"})
    else:
        changed = _write_patch(process, state)
        if not set(changed).issubset(set(state["approved_changed_paths"])):
            raise ContractError("No-op compile contains changes without a successful editor")
        _prepare_review_or_audit(process, state)


def _prepare_review_or_audit(process: Path, state: dict[str, Any]) -> None:
    state["review_queue"] = list(state["changed_paths"])
    state["review_index"] = 0
    if state["review_queue"]:
        state.update({"current_stage": "review", "next_role": "reviewer", "next_mode": "review"})
    else:
        _prepare_audit(process, state)


def _run_checks(process: Path, state: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    helper = repo / "scripts" / "docs_helpers.py"
    if not helper.is_file():
        helper = _plugin_root() / "scripts" / "docs_helpers.py"
    check = {"contract_version": CONTRACT_VERSION, "status": "UNAVAILABLE"}
    if helper.is_file():
        before = _scan_docs(repo, state["app"])
        completed = subprocess.run([sys.executable, str(helper), "check", "--repo", str(repo), "--app", state["app"]],
                                   text=True, capture_output=True, encoding="utf-8", errors="replace")
        after = _scan_docs(repo, state["app"])
        mutated = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        check = {"contract_version": CONTRACT_VERSION, "status": "PASS" if completed.returncode == 0 else "FAIL",
                 "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
                 "mutated_paths": mutated}
        if mutated:
            check["status"] = "FAIL"
    _write_json(process / "checks" / "docs-helper.json", check)
    adr_status = _run_adr_status_check(process, state)
    state["mechanical_checks"] = {"docs_helper": check, "adr_status": adr_status}


def _run_adr_status_check(process: Path, state: dict[str, Any]) -> dict[str, Any]:
    repo = Path(state["repo_root"])
    app = state["app"]
    catalog = repo / "Docs" / app / f"{app}-ADR-CATALOG.md"
    catalog_text = catalog.read_text(encoding="utf-8") if catalog.is_file() else ""
    section = ""
    catalog_status: dict[str, str] = {}
    for line in catalog_text.splitlines():
        heading = re.match(r"^##\s+(.+)$", line.strip())
        if heading:
            section = heading.group(1).strip()
            continue
        if not line.lstrip().startswith("|"):
            continue
        first_cell = line.strip().strip("|").split("|", 1)[0]
        match = re.search(rf"\b{re.escape(app)}-ADR-\d{{3}}\b", first_cell)
        if match:
            normalized = "Superseded" if "Superseded" in section or "Deprecated" in section else (
                "Accepted" if "Accepted" in section else "Proposed" if "Proposed" in section else section
            )
            catalog_status[match.group(0)] = normalized
    ids = set(_read_json(process / "authority.json").get("basis_candidates", []))
    plan = _read_json(process / "ssot-write-plan.json")
    for row in plan.get("matrix", []):
        if row.get("ssot_type") == "ADR":
            for target in row.get("targets", []):
                match = re.search(rf"\b{re.escape(app)}-ADR-\d{{3}}\b", target.get("path", ""))
                if match:
                    ids.add(match.group(0))
    checked = []
    failures = []
    for adr_id in sorted(ids):
        path = repo / "Docs" / app / "ADR" / f"{adr_id}.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        match = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        file_status = match.group(1).strip() if match else None
        listed = catalog_status.get(adr_id)
        result = "PASS" if _status_class(file_status) and _status_class(file_status) == _status_class(listed) else "FAIL"
        row = {"adr": adr_id, "file_status": file_status, "catalog_status": listed, "result": result}
        checked.append(row)
        if result == "FAIL": failures.append(row)
    evidence = {"contract_version": CONTRACT_VERSION, "status": "FAIL" if failures else "PASS",
                "checked": checked, "failures": failures}
    _write_json(process / "checks" / "adr-status.json", evidence)
    return evidence


def _status_class(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if "accepted" in lowered:
        return "Accepted"
    if "superseded" in lowered or "deprecated" in lowered:
        return "Superseded"
    if "proposed" in lowered:
        return "Proposed"
    if "rejected" in lowered:
        return "Rejected"
    if "reverted" in lowered:
        return "Reverted"
    return value.strip()


def _prepare_audit(process: Path, state: dict[str, Any]) -> None:
    changed = _write_patch(process, state)
    if not set(changed).issubset(set(state["approved_changed_paths"])):
        raise ContractError("Audit input contains changes without a successful editor")
    _run_checks(process, state)
    state["audit_iteration"] += 1
    state.update({"current_stage": "audit", "next_role": "auditor", "next_mode": "cross-audit"})


def _block(process: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    state.update({"run_status": "blocked", "blocking_question_id": result["question_id"],
                  "blocking_question": result["question"], "last_result": "BLOCKED"})
    state["stage_results"][state["current_stage"]].update({"status": "blocked", "result": "BLOCKED"})


def _finalize(process: Path, state: dict[str, Any]) -> None:
    paths = state["changed_paths"]
    report = "\n".join((
        "UPDATE/CREATE " + (", ".join(paths) if paths else "none"),
        f"Process: {state['process_rel'].rstrip('/')}/", "Audit: PASS", "Next: work-packet-write",
    )) + "\n"
    (process / "final-report.txt").write_text(report, encoding="utf-8")
    state.update({"run_status": "done", "current_stage": "done", "next_role": None,
                  "next_mode": None, "last_result": "PASS", "last_failure_class": "NONE"})
    state["stage_results"]["finalize"] = {"owner": "runner", "status": "done", "result": "PASS"}


def _accept_judge(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    judgment = _validate_judgment(process, state, dispatch)
    if result["status"] == "BLOCKED":
        if judgment["decision"] != "BLOCKED":
            raise ContractError("BLOCKED result requires BLOCKED judgment")
        _block(process, state, result)
        return
    if result["status"] != "READY" or judgment["decision"] == "BLOCKED":
        raise ContractError("Judge result and judgment disagree")
    state["judgments"][dispatch["candidate_id"]] = judgment
    state["candidate_index"] += 1
    if state["candidate_index"] < len(state["candidate_queue"]):
        state.update({"current_stage": "judge", "next_role": "judge", "next_mode": "judge"})
    else:
        state["stage_results"]["judge"] = {"owner": "judge", "status": "done", "result": "READY"}
        _compile_plan(process, state)


def _accept_editor(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    actual = _snapshot_changed(process, state, dispatch["snapshot_label"])
    expected = [dispatch["affected_path"]]
    declared = sorted(_normalize_rel(item) for item in result["changed"])
    if result["status"] == "BLOCKED":
        if actual:
            raise ContractError("BLOCKED editor left changes")
        _block(process, state, result)
        return
    if result["status"] != "PASS" or actual != expected or declared != expected:
        raise ContractError(f"Editor must change exactly one authorized path: expected={expected}, actual={actual}, declared={declared}")
    approved = set(state["approved_changed_paths"])
    approved.update(actual)
    state["approved_changed_paths"] = sorted(approved)
    state["editor_index"] += 1
    if state["editor_index"] < len(state["editor_queue"]):
        return
    changed = _write_patch(process, state)
    if not set(changed).issubset(set(state["approved_changed_paths"])):
        raise ContractError("Cumulative patch exceeds approved editor paths")
    state["stage_results"]["edit"] = {"owner": "editor", "status": "done", "result": "PASS"}
    (process / "ssot-write-action.md").write_text(
        "# ssot-write Action\n\nEdited one path per dispatch:\n\n" + "\n".join(f"- `{p}`" for p in changed) + "\n",
        encoding="utf-8",
    )
    _prepare_review_or_audit(process, state)


def _accept_reviewer(process: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    if result["status"] == "BLOCKED":
        _block(process, state, result)
        return
    if result["status"] == "FAIL":
        affected = sorted({_normalize_rel(p) for p in result["affected_paths"]})
        if result["failure_class"] != "EXECUTION" or affected != [state["review_queue"][state["review_index"]]]:
            raise ContractError("Document review FAIL must identify its one path as EXECUTION")
        if state["repair_attempts"] >= 2:
            raise ContractError("Document repair limit exceeded")
        state["repair_attempts"] += 1
        state["editor_queue"] = affected
        state["editor_index"] = 0
        state.update({"current_stage": "edit", "next_role": "editor", "next_mode": "repair"})
        return
    state["review_index"] += 1
    if state["review_index"] < len(state["review_queue"]):
        return
    state["stage_results"]["review"] = {"owner": "reviewer", "status": "done", "result": "PASS"}
    _prepare_audit(process, state)


def _accept_auditor(process: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    if result["status"] == "BLOCKED":
        _block(process, state, result)
        return
    if result["status"] == "PASS":
        checks = state.get("mechanical_checks", {})
        if checks.get("docs_helper", {}).get("status") not in {"PASS", "UNAVAILABLE"}:
            raise ContractError("Cross-audit PASS requires successful docs helper evidence")
        if checks.get("adr_status", {}).get("status") != "PASS":
            raise ContractError("Cross-audit PASS requires successful ADR status evidence")
        state["stage_results"]["audit"] = {"owner": "auditor", "status": "done", "result": "PASS"}
        _finalize(process, state)
        return
    if result["failure_class"] == "PLAN":
        if state["rejudge_attempts"] >= 2:
            raise ContractError("Rejudge limit exceeded")
        state["rejudge_attempts"] += 1
        state["candidate_index"] = 0
        state["judgments"] = {}
        state.update({"current_stage": "judge", "next_role": "judge", "next_mode": "rejudge"})
    else:
        affected = sorted({_normalize_rel(p) for p in result["affected_paths"]})
        if not affected or not set(affected).issubset(set(state["approved_changed_paths"])):
            raise ContractError("Execution audit FAIL requires approved affected_paths")
        if state["repair_attempts"] >= 2:
            raise ContractError("Document repair limit exceeded")
        state["repair_attempts"] += 1
        state["editor_queue"] = affected
        state["editor_index"] = 0
        state.update({"current_stage": "edit", "next_role": "editor", "next_mode": "repair"})


def _record_rejection(process: Path, state: dict[str, Any], result_path: Path, error: ContractError) -> None:
    dispatch = state.get("active_dispatch") or {}
    dispatch_id = dispatch.get("dispatch_id", "unknown")
    counts = state.setdefault("rejection_counts", {})
    attempt = int(counts.get(dispatch_id, 0)) + 1
    counts[dispatch_id] = attempt
    rejected = process / "results" / "rejected"
    rejected.mkdir(parents=True, exist_ok=True)
    if result_path.is_file():
        (rejected / f"{dispatch_id}-attempt-{attempt}.json").write_bytes(result_path.read_bytes())
    metadata = {"contract_version": CONTRACT_VERSION, "dispatch_id": dispatch_id, "attempt": attempt,
                "error_code": "CONTRACT_ERROR", "message": str(error), "rejected_at": _now()}
    _write_json(rejected / f"{dispatch_id}-attempt-{attempt}-error.json", metadata)
    state["last_rejection"] = metadata
    if state.get("active_dispatch"):
        state["active_dispatch"]["last_rejection"] = metadata
    if attempt >= 3:
        state.update({"run_status": "blocked", "blocking_question_id": f"REJECTION-{dispatch_id}",
                      "blocking_question": f"Dispatch {dispatch_id} produced three invalid results"})
    _save_state(process, state, {"event": "result_rejected", "stage": dispatch.get("stage"),
                                 "result": "REJECTED", "dispatch_id": dispatch_id, "attempt": attempt})


def accept_result(process: Path, result_path: Path) -> dict[str, Any]:
    process = _process_path(process)
    state = _load_state(process)
    dispatch = state.get("active_dispatch")
    if not dispatch:
        raise ContractError("No active dispatch")
    try:
        result = _read_json(result_path.resolve())
        _validate_result(result, dispatch)
        if result["role"] != "editor":
            changed = _snapshot_changed(process, state, dispatch["snapshot_label"])
            if changed:
                raise ContractError(f"Read-only role modified permanent docs: {changed}")
        artifact = _resolve_under(Path(state["repo_root"]), result["artifact"])
        if artifact.resolve() != Path(dispatch["artifact"]).resolve() or not artifact.is_file():
            raise ContractError("Result artifact does not match dispatch")
        if result["role"] == "judge":
            _accept_judge(process, state, result, dispatch)
        elif result["role"] == "editor":
            _accept_editor(process, state, result, dispatch)
        elif result["role"] == "reviewer":
            _accept_reviewer(process, state, result)
        else:
            _accept_auditor(process, state, result)
        state["active_dispatch"] = None
        state["last_result"] = result["status"]
        state["last_failure_class"] = result["failure_class"]
        _save_state(process, state, {"event": "result", "stage": result["stage"], "result": result["status"]})
        return {"action": "accepted", "status": result["status"], "process": str(process)}
    except ContractError as exc:
        _record_rejection(process, state, result_path.resolve(), exc)
        raise


def resolve_block(process: Path, conflict_id: str, answer: str | None = None, choice: str | None = None) -> dict[str, Any]:
    process = _process_path(process)
    state = _load_state(process)
    if state["run_status"] != "blocked" or conflict_id != state["blocking_question_id"]:
        raise ContractError("Conflict does not match blocked state")
    decisions = _read_json(process / "decision.json")
    decisions["decisions"].append({"conflict_id": conflict_id, "answer": choice or answer, "resolved_at": _now()})
    _write_json(process / "decision.json", decisions)
    state.update({"run_status": "running", "blocking_question_id": None, "blocking_question": None,
                  "active_dispatch": None})
    _save_state(process, state, {"event": "resolve", "stage": state["current_stage"], "result": "READY"})
    return {"action": "resolved", "process": str(process)}


def status(process: Path) -> dict[str, Any]:
    return _load_state(_process_path(process))


def render(process: Path) -> dict[str, Any]:
    process = _process_path(process)
    state = _load_state(process)
    _render_views(process, state)
    return {"action": "rendered", "process": str(process)}


def report(process: Path) -> str:
    process = _process_path(process)
    state = _load_state(process)
    if state["run_status"] != "done":
        raise ContractError("Run is not done")
    expected = "\n".join((
        "UPDATE/CREATE " + (", ".join(state["changed_paths"]) if state["changed_paths"] else "none"),
        f"Process: {state['process_rel'].rstrip('/')}/", "Audit: PASS", "Next: work-packet-write",
    ))
    actual = (process / "final-report.txt").read_text(encoding="utf-8").rstrip("\n")
    if actual != expected:
        raise ContractError("final-report.txt does not match runner state")
    return actual


def _emit_json(value: Any) -> None:
    try:
        print(json.dumps(value, ensure_ascii=False))
    except UnicodeEncodeError:
        print(json.dumps(value, ensure_ascii=True))


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init")
    init.add_argument("--repo", type=Path, required=True); init.add_argument("--task", required=True)
    init.add_argument("--app", required=True); init.add_argument("--process", type=Path)
    for name in ("next", "status", "render", "report"):
        command = sub.add_parser(name); command.add_argument("--process", type=Path, required=True)
    accept = sub.add_parser("accept-result"); accept.add_argument("--process", type=Path, required=True); accept.add_argument("--result", type=Path, required=True)
    resolve = sub.add_parser("resolve"); resolve.add_argument("--process", type=Path, required=True); resolve.add_argument("--conflict", required=True); resolve.add_argument("--answer"); resolve.add_argument("--choice")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            process = args.process
            if process is not None and not process.is_absolute(): process = args.repo / process
            _emit_json(init_run(args.repo, args.task, args.app, process))
        elif args.cmd == "next": _emit_json(next_action(args.process))
        elif args.cmd == "accept-result": _emit_json(accept_result(args.process, args.result))
        elif args.cmd == "resolve": _emit_json(resolve_block(args.process, args.conflict, args.answer, args.choice))
        elif args.cmd == "status": _emit_json(status(args.process))
        elif args.cmd == "render": _emit_json(render(args.process))
        elif args.cmd == "report": print(report(args.process))
    except ContractError as exc:
        print(json.dumps({"error": "CONTRACT_ERROR", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0
