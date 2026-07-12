from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


CONTRACT_VERSION = 6
SSOT_TYPES = ("PRD", "FC", "FRD", "ADR", "ADR-CATALOG", "ARCHITECTURE")
ROLE_MODEL = {
    "thinker": "opus",
    "plan_critic": "opus",
    "editor": "sonnet",
    "outcome_critic": "opus",
}
ROLE_TEMPLATE = {
    "thinker": "skills/ssot-write/templates/change-thinker-input.md",
    "plan_critic": "skills/ssot-write/templates/plan-critic-input.md",
    "editor": "skills/ssot-write/templates/staged-editor-input.md",
    "outcome_critic": "skills/ssot-write/templates/outcome-critic-input.md",
}
ROLE_STATUS = {
    "thinker": {"READY", "BLOCKED"},
    "plan_critic": {"PASS", "FAIL", "BLOCKED"},
    "editor": {"PASS", "BLOCKED"},
    "outcome_critic": {"PASS", "FAIL", "BLOCKED"},
}
RESULT_FIELDS = {
    "contract_version", "dispatch_id", "stage", "role", "mode", "status",
    "artifact", "failure_class", "question_id", "question", "changed",
    "affected_paths", "input_digest", "actual_model",
}
TARGET_ACTIONS = {"CREATE", "UPDATE"}
DISPOSITIONS = {"ACTIVE", "NOOP", "OBSOLETE", "REWRITE_REQUIRED", "BLOCKED"}
TERMINAL_RESULTS = {
    "DONE", "NOOP", "OBSOLETE", "REWRITE_REQUIRED", "USER_REJECTED",
    "PLAN_REJECTED", "VERIFY_FAILED", "CONTRACT_BLOCKED",
    "COMMIT_FAILED_ROLLED_BACK", "RECOVERY_REQUIRED",
}
MAX_REJECTIONS = 3
MAX_PLAN_REVISIONS = 2
MAX_REPAIRS_PER_PATH = 2
TASK_LINK_PATTERN = re.compile(r"(?:\[[^\]]*\]\([^)]*/TASK/[^)]*\)|\b[A-Z][A-Z0-9]*-TASK-\d{3}\b)", re.IGNORECASE)


class ContractError(RuntimeError):
    def __init__(self, message: str, code: str = "CONTRACT_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _value_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        raise ContractError(f"Path escapes root: {value}", "PATH_ESCAPE") from exc
    return path


def _repo_rel(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"Path is outside repo: {path}", "PATH_ESCAPE") from exc


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"Required JSON missing: {path}", "MISSING_JSON")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid JSON: {path}: {exc}", "INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}", "INVALID_JSON")
    return value


def _read_bound_json(path: Path, expected_sha256: str, code: str) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"Bound JSON missing: {path}", code)
    try:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ContractError(f"Bound JSON changed after approval: {path}", code)
        value = json.loads(raw.decode("utf-8"))
    except ContractError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid bound JSON: {path}: {exc}", code) from exc
    if not isinstance(value, dict):
        raise ContractError(f"Bound JSON root must be an object: {path}", code)
    return value


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def _write_text(path: Path, value: str) -> None:
    _atomic_write_bytes(path, value.encode("utf-8"))


def _process_path(value: str | Path) -> Path:
    return Path(value).resolve()


def _state_path(process: Path) -> Path:
    return process / "state.json"


def _load_state(process: Path) -> dict[str, Any]:
    state = _read_json(_state_path(process))
    if state.get("contract_version") != CONTRACT_VERSION:
        raise ContractError(
            f"Contract version mismatch: expected {CONTRACT_VERSION}, found {state.get('contract_version')}",
            "CONTRACT_VERSION_MISMATCH",
        )
    return state


@contextmanager
def _advisory_file_lock(path: Path, error_code: str) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    locked = False
    try:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError) as exc:
            raise ContractError(f"Advisory lock is held: {path}", error_code) from exc
        locked = True
        yield
    finally:
        if locked:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except (OSError, ImportError):
                pass
        stream.close()


@contextmanager
def _process_lock(process: Path) -> Iterator[None]:
    process.mkdir(parents=True, exist_ok=True)
    with _advisory_file_lock(process / ".runner.lock", "PROCESS_LOCKED"):
        yield


def _append_event(process: Path, event: dict[str, Any]) -> None:
    row = {"at": _now(), **event}
    with (process / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _save_state(process: Path, state: dict[str, Any], event: dict[str, Any] | None = None) -> None:
    state["state_revision"] = int(state.get("state_revision", 0)) + 1
    state["updated_at"] = _now()
    _write_json(_state_path(process), state)
    if event:
        _append_event(process, event)
    _render_views(process, state)


def _scan_docs(repo: Path, app: str) -> dict[str, str]:
    root = repo / "Docs" / app
    if not root.is_dir():
        raise ContractError(f"Docs app directory missing: {root}", "DOCS_APP_MISSING")
    return {
        path.relative_to(repo).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*.md"))
        if path.is_file()
    }


def _scan_helper_surface(root: Path) -> dict[str, str]:
    docs = root / "Docs"
    if not docs.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(docs.rglob("*"))
        if path.is_file()
    }


def _versioned_and_untracked_paths(repo: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        completed = None
    if completed is None or completed.returncode != 0:
        return [
            path for path in repo.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(repo).parts
        ]
    paths: list[Path] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            rel = raw.decode("utf-8")
        except UnicodeDecodeError:
            rel = raw.decode(sys.getfilesystemencoding(), errors="replace")
        path = repo / rel
        if path.is_file():
            paths.append(path)
    return paths


def _protected_manifest(repo: Path, app: str, process: Path) -> dict[str, str]:
    candidates = set(_versioned_and_untracked_paths(repo))
    docs_root = repo / "Docs"
    if docs_root.is_dir():
        candidates.update(path for path in docs_root.rglob("*") if path.is_file())
    manifest: dict[str, str] = {}
    for path in sorted(candidates):
        try:
            path.resolve().relative_to(process.resolve())
            continue
        except ValueError:
            pass
        manifest[_repo_rel(repo, path)] = _sha256(path)
    return manifest


def _control_manifest(process: Path, dispatch: dict[str, Any]) -> dict[str, str]:
    """Snapshot runner-owned process files, excluding this role's exact outputs."""
    allowed = {
        Path(os.path.abspath(dispatch["artifact"])),
        Path(os.path.abspath(dispatch["result_path"])),
    }
    if dispatch.get("staged_path"):
        allowed.add(Path(os.path.abspath(dispatch["staged_path"])))
    guard = process / "snapshots" / f"{dispatch['snapshot_label']}-control.json"
    allowed.add(Path(os.path.abspath(guard)))
    allowed.add(Path(os.path.abspath(process / ".runner.lock")))
    allowed.add(Path(os.path.abspath(process / "state.json")))
    manifest: dict[str, str] = {}
    for path in sorted(process.rglob("*")):
        if not path.is_file() or Path(os.path.abspath(path)) in allowed:
            continue
        manifest[path.relative_to(process).as_posix()] = _sha256(path)
    return manifest


def _guarded_state_sha(state: dict[str, Any]) -> str:
    value = dict(state)
    value.pop("control_guard_sha256", None)
    return _value_sha(value)


def _snapshot_control(process: Path, dispatch: dict[str, Any], state: dict[str, Any]) -> None:
    guard = process / "snapshots" / f"{dispatch['snapshot_label']}-control.json"
    payload = {
        "contract_version": CONTRACT_VERSION,
        "dispatch_id": dispatch["dispatch_id"],
        "state_sha256": _guarded_state_sha(state),
        "manifest": _control_manifest(process, dispatch),
    }
    _write_json(guard, payload)
    state["control_guard_sha256"] = _sha256(guard)
    _write_json(_state_path(process), state)


def _control_changes(process: Path, dispatch: dict[str, Any], state: dict[str, Any]) -> list[str]:
    guard = process / "snapshots" / f"{dispatch['snapshot_label']}-control.json"
    if not guard.is_file() or _sha256(guard) != state.get("control_guard_sha256"):
        return [guard.relative_to(process).as_posix()]
    payload = _read_json(guard)
    if (
        payload.get("dispatch_id") != dispatch["dispatch_id"]
        or payload.get("state_sha256") != _guarded_state_sha(state)
        or not isinstance(payload.get("manifest"), dict)
    ):
        return ["state.json"]
    before = payload["manifest"]
    after = _control_manifest(process, dispatch)
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _snapshot_protected(process: Path, state: dict[str, Any], label: str) -> None:
    manifest = _protected_manifest(Path(state["repo_root"]), state["app"], process)
    _write_json(process / "snapshots" / f"{label}-protected.json", manifest)


def _protected_changes(process: Path, state: dict[str, Any], label: str) -> list[str]:
    before = _read_json(process / "snapshots" / f"{label}-protected.json")
    after = _protected_manifest(Path(state["repo_root"]), state["app"], process)
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _scan_staging(process: Path) -> dict[str, str]:
    root = process / "staging"
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _snapshot_staging(process: Path, label: str) -> None:
    _write_json(process / "snapshots" / f"{label}-staging.json", _scan_staging(process))


def _staging_changes(process: Path, label: str) -> list[str]:
    before = _read_json(process / "snapshots" / f"{label}-staging.json")
    after = _scan_staging(process)
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _create_baseline(process: Path, state: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    root = repo / "Docs" / state["app"]
    baseline = process / "baseline"
    for source in root.rglob("*.md"):
        if source.is_file():
            target = baseline / source.relative_to(repo)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    manifest = _scan_docs(repo, state["app"])
    _write_json(process / "snapshots" / "original.json", manifest)
    state["baseline_manifest_sha"] = _value_sha(manifest)


def _high_signal_terms(text: str) -> list[str]:
    terms: set[str] = set()
    for code in re.findall(r"`([^`\r\n]{3,100})`", text):
        terms.update(re.findall(r"[A-Za-z][A-Za-z0-9_.-]{3,}|[A-Z][A-Z0-9_]{3,}", code))
    terms.update(re.findall(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b", text))
    terms.update(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+\b", text))
    ignored = {
        "TASK", "MASTER", "UPDATE", "CREATE", "SKIP", "READY", "PASS", "FAIL",
        "TODO", "NONE", "NULL", "TRUE", "FALSE", "COUNT", "STRING", "DATA",
        "DESCRIPTION", "REGION", "SUMMARY", "TARGET", "VALUE", "VALUES", "TESTS",
    }
    return sorted(term for term in terms if len(term) >= 4 and term.upper() not in ignored)


def _task_source(repo: Path, task_rel: str) -> dict[str, Any]:
    task = repo / task_rel
    text = task.read_text(encoding="utf-8")
    status_match = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
    ids = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_-]+-(?:ADR|FRD|TASK)-\d{3}\b", text)))
    headings = [m.group(1).strip() for m in re.finditer(r"^#{2,3}\s+(.+)$", text, re.MULTILINE)]
    return {
        "contract_version": CONTRACT_VERSION,
        "task": task_rel,
        "task_sha256": _sha256(task),
        "status": status_match.group(1).strip() if status_match else "UNSPECIFIED",
        "referenced_ids": ids,
        "headings": headings,
        "high_signal_terms": _high_signal_terms(text),
    }


def _canonical_adr(app: str, value: str) -> str:
    match = re.search(r"ADR-(\d{3})", value, re.IGNORECASE)
    if not match:
        raise ContractError(f"Invalid ADR identifier: {value}", "INVALID_ADR_ID")
    return f"{app}-ADR-{match.group(1)}"


def _relationship_targets(text: str, app: str) -> list[tuple[str, str]]:
    adr_pattern = rf"{re.escape(app)}-ADR-\d{{3}}"
    edges: list[tuple[str, str]] = []
    for match in re.finditer(
        rf"Superseded\s*(?:\(\s*)?by\s*[:：]?\s*`?({adr_pattern})`?\s*\)?",
        text, re.IGNORECASE,
    ):
        edges.append((_canonical_adr(app, match.group(1)), "superseded-by"))
    for match in re.finditer(
        r"^\|\s*(?:Superseded By|대체 ADR|승계 ADR)\s*\|\s*([^|]+)\|",
        text, re.MULTILINE | re.IGNORECASE,
    ):
        edges.extend(
            (_canonical_adr(app, value), "structured-superseded-by")
            for value in re.findall(adr_pattern, match.group(1), re.IGNORECASE)
        )
    return edges


def _supersedes_predecessors(text: str, app: str) -> list[tuple[str, str]]:
    adr_pattern = rf"{re.escape(app)}-ADR-\d{{3}}"
    values: list[tuple[str, str]] = []
    for pattern in (r"\*\*supersedes\*\*\s*[:：]\s*([^\r\n]+)", r"^\|\s*Supersedes\s*\|\s*([^|]+)\|"):
        for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
            values.extend(
                (_canonical_adr(app, value), "supersedes")
                for value in re.findall(adr_pattern, match.group(1), re.IGNORECASE)
            )
    return values


def _resolve_authority(repo: Path, app: str, source: dict[str, Any]) -> dict[str, Any]:
    root = repo / "Docs" / app / "ADR"
    statuses: dict[str, str] = {}
    superseded_by: dict[str, list[str]] = {}
    evidence: list[dict[str, str]] = []
    for path in sorted(root.glob(f"{app}-ADR-*.md")) if root.is_dir() else []:
        text = path.read_text(encoding="utf-8")
        adr_id = path.stem
        status = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        statuses[adr_id] = status.group(1).strip() if status else "UNSPECIFIED"
        for target, source_kind in _relationship_targets(text, app):
            if target != adr_id:
                superseded_by.setdefault(adr_id, []).append(target)
                evidence.append({"from": adr_id, "to": target, "path": _repo_rel(repo, path), "source": source_kind})
        for predecessor, source_kind in _supersedes_predecessors(text, app):
            if predecessor != adr_id:
                superseded_by.setdefault(predecessor, []).append(adr_id)
                evidence.append({"from": predecessor, "to": adr_id, "path": _repo_rel(repo, path), "source": source_kind})
    normalized = {key: sorted(set(values)) for key, values in superseded_by.items()}

    def chain(start: str) -> list[str]:
        pending = [start]
        seen: set[str] = set()
        ordered: list[str] = []
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            ordered.append(current)
            pending.extend(normalized.get(current, []))
        return ordered

    referenced = [
        _canonical_adr(app, item) for item in source.get("referenced_ids", [])
        if "-ADR-" in item.upper()
    ]
    terminals = {
        basis: [node for node in chain(basis) if not normalized.get(node)]
        for basis in referenced
    }
    conflicts = [basis for basis, values in terminals.items() if len(values) != 1]
    return {
        "contract_version": CONTRACT_VERSION,
        "basis_candidates": referenced,
        "statuses": statuses,
        "superseded_by": normalized,
        "relationship_evidence": sorted(evidence, key=lambda row: (row["from"], row["to"], row["path"])),
        "chains": {basis: chain(basis) for basis in referenced},
        "terminal_candidates": terminals,
        "conflicts": conflicts,
        "resolver": "runner",
    }


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


def _document_index(repo: Path, app: str, source: dict[str, Any]) -> dict[str, Any]:
    root = repo / "Docs" / app
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        rel = _repo_rel(repo, path)
        kind = _classify_ssot_path(app, rel)
        if not kind:
            continue
        text = path.read_text(encoding="utf-8")
        title = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        status = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        ids = sorted(set(re.findall(rf"\b(?:{re.escape(app)}-(?:ADR|FRD)-\d{{3}}|F\d{{3}})\b", text)))
        hits = [term for term in source.get("high_signal_terms", []) if term.casefold() in text.casefold()]
        rows.append({
            "path": rel,
            "ssot_type": kind,
            "title": title.group(1).strip() if title else path.stem,
            "status": status.group(1).strip() if status else None,
            "ids": ids,
            "matched_terms": sorted(set(hits)),
            "sha256": _sha256(path),
        })
    return {"contract_version": CONTRACT_VERSION, "documents": rows, "all_path_count": len(rows)}


def _render_views(process: Path, state: dict[str, Any]) -> None:
    stages = state.get("stage_results", {})
    rows = "\n".join(
        f"| {name} | {value.get('owner')} | {value.get('status')} | {value.get('result') or 'none'} |"
        for name, value in stages.items()
    )
    contract_path = process / "approved-contract.json"
    matrix: list[str] = []
    relation_rows: list[str] = []
    disposition = state.get("disposition") or "pending"
    downstream = state.get("downstream") or "pending"
    if contract_path.is_file():
        try:
            expected = state.get("approved_contract_sha256")
            contract = _read_bound_json(contract_path, expected, "APPROVED_CONTRACT_TAMPERED") if expected else _read_json(contract_path)
            disposition = contract.get("disposition", disposition)
            for action in contract.get("actions", []):
                matrix.append(f"| {action['ssot_type']} | {action['action']} | `{action['path']}` | {action['reason']} |")
            for skip in contract.get("skips", []):
                matrix.append(f"| {skip['ssot_type']} | SKIP | none | {skip['reason']} |")
            for relation in contract.get("relations", []):
                authority = ", ".join(relation.get("authority_ids", [])) or "none"
                relation_rows.append(
                    f"| {relation['relation_id']} | {relation['kind']} | {authority} | "
                    f"{relation['outcome']} | {relation['requirement']} |"
                )
        except (ContractError, KeyError, TypeError):
            matrix = ["| unknown | BLOCKED | none | approved contract hash/schema mismatch |"]
            relation_rows = ["| unknown | BLOCKED | none | none | approved contract unavailable |"]
    matrix_text = "\n".join(matrix) if matrix else "| pending | pending | none | pending |"
    relations_text = "\n".join(relation_rows) if relation_rows else "| none | none | none | none | none |"
    build = f"""# ssot-write Orchestration Build

Generated by Contract v{CONTRACT_VERSION} runner. Do not edit manually.

- Process: `{state['process_rel']}`
- Pattern: think → plan critique → stage → checks → outcome critique → runner commit
- Task disposition: `{disposition}`
- Downstream: `{downstream}`

## Ownership

| Unit | Owner | Responsibility |
|---|---|---|
| source/index/authority/state | runner | deterministic evidence and transitions |
| change proposal | Opus thinker | one global semantic proposal |
| plan critique | fresh Opus critic | falsify proposal before writes |
| staged document | Sonnet editor | one process-owned staging path |
| mechanical checks/commit | runner | verify and journaled commit/rollback |
| outcome critique | fresh Opus critic | falsify final staged outcome |

## Confirmed SSOT Action Matrix

| SSOT | Action | Target | Reason |
|---|---|---|---|
{matrix_text}

## Input Precedence and Downstream Constraints

| Relation ID | Kind | Authority | Outcome | Work Packet instruction |
|---|---|---|---|---|
{relations_text}
"""
    progress = f"""# ssot-write Orchestration Progress

Generated by Contract v{CONTRACT_VERSION} runner. Do not edit manually.

- Run status: {state['run_status']}
- Current stage: {state['current_stage']}
- Terminal result: {state.get('terminal_result') or 'none'}
- Next role: {state.get('next_role') or 'none'}
- State revision: {state.get('state_revision', 0)}
- Dispatch sequence: {state['dispatch_seq']}

| Stage | Owner | Status | Result |
|---|---|---|---|
{rows}
"""
    _write_text(process / "ssot-write-orchestration-build.md", build)
    _write_text(process / "ssot-write-orchestration-progress.md", progress)
    _write_text(process / "ssot-write-build.md", build.replace("Orchestration ", ""))
    _write_text(process / "ssot-write-progress.md", progress.replace("Orchestration ", ""))


def init_run(repo: Path, task: str, app: str, process: Path | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    task_rel = _normalize_rel(task)
    task_path = _resolve_under(repo, task_rel)
    expected_prefix = f"Docs/{app}/TASK/"
    if not task_path.is_file() or not task_rel.lower().startswith(expected_prefix.lower()):
        raise ContractError(f"Invalid TASK path for {app}: {task}", "INVALID_TASK_PATH")
    process = (process or repo / ".process" / task_path.stem).resolve()
    _repo_rel(repo, process)
    if _state_path(process).is_file():
        state = _load_state(process)
        if state["repo_root"] != str(repo) or state["task"] != task_rel or state["app"] != app:
            raise ContractError("Existing process identity does not match init arguments", "PROCESS_IDENTITY_MISMATCH")
        return {"action": "resume", "process": str(process), "contract_version": CONTRACT_VERSION}
    process.mkdir(parents=True, exist_ok=True)
    with _process_lock(process):
        source = _task_source(repo, task_rel)
        authority = _resolve_authority(repo, app, source)
        index = _document_index(repo, app, source)
        _write_json(process / "source.json", source)
        _write_json(process / "authority.json", authority)
        _write_json(process / "document-index.json", index)
        _write_json(process / "decision.json", {"contract_version": CONTRACT_VERSION, "decisions": []})
        state: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "state_revision": 0,
            "run_id": f"{task_path.stem}-{hashlib.sha256(str(process).encode()).hexdigest()[:10]}",
            "repo_root": str(repo), "task": task_rel, "app": app,
            "process_rel": _repo_rel(repo, process),
            "run_status": "running", "current_stage": "think",
            "terminal_result": None, "next_role": "thinker", "next_mode": "propose",
            "dispatch_seq": 0, "active_dispatch": None,
            "control_guard_sha256": None,
            "plan_revisions": 0, "repair_attempts": {}, "outcome_iterations": 0,
            "proposal_path": None, "proposal_sha256": None,
            "critique_path": None, "critique_sha256": None,
            "approved_contract_sha256": None, "disposition": None, "downstream": None,
            "editor_queue": [], "editor_index": 0, "staged_hashes": {},
            "commit_recovery_pending": False,
            "blocking_question_id": None, "blocking_question": None,
            "blocking_kind": None, "resume_after_block": None,
            "last_result": None, "last_failure_class": "NONE",
            "stage_results": {
                "source": {"owner": "runner", "status": "done", "result": "READY"},
                "think": {"owner": "thinker", "status": "pending", "result": None},
                "plan_critique": {"owner": "plan_critic", "status": "pending", "result": None},
                "edit": {"owner": "editor", "status": "pending", "result": None},
                "check": {"owner": "runner", "status": "pending", "result": None},
                "outcome_review": {"owner": "outcome_critic", "status": "pending", "result": None},
                "commit": {"owner": "runner", "status": "pending", "result": None},
                "finalize": {"owner": "runner", "status": "pending", "result": None},
            },
            "created_at": _now(), "updated_at": _now(),
        }
        _create_baseline(process, state)
        baseline_root = _overlay_root(process, state)
        baseline_helper = _execute_docs_helper(baseline_root, state)
        if baseline_helper.get("raw_class") == "MUTATED":
            raise ContractError("Baseline docs helper modified its isolated validation tree", "HELPER_MUTATED_DOCS")
        if baseline_helper.get("raw_class") == "INFRA_FAIL":
            raise ContractError(
                f"Baseline docs helper could not establish a stable result: {baseline_helper.get('reason')}",
                "HELPER_INFRA_FAILURE",
            )
        _write_json(process / "checks" / "baseline-docs-helper.json", baseline_helper)
        _write_text(process / "events.jsonl", "")
        _save_state(process, state, {"event": "init", "stage": "source", "result": "READY"})
    return {"action": "initialized", "process": str(process), "contract_version": CONTRACT_VERSION}


def _template_for_type(repo: Path, kind: str) -> str | None:
    names = {
        "PRD": ("Docs/.templates/App/APP-PRD-TEMPLATE.md", "docs/.templates/PRD-TEMPLATE.md"),
        "FC": ("Docs/.templates/App/APP-FC-TEMPLATE.md", "docs/.templates/FC-TEMPLATE.md"),
        "FRD": ("Docs/.templates/App/FRD/APP-FRD-001-TEMPLATE.md", "docs/.templates/FRD-TEMPLATE.md"),
        "ADR": ("Docs/.templates/App/ADR/APP-ADR-001-TEMPLATE.md", "docs/.templates/ADR-TEMPLATE.md"),
        "ADR-CATALOG": ("Docs/.templates/App/APP-ADR-CATALOG-TEMPLATE.md",),
        "ARCHITECTURE": ("Docs/.templates/App/APP-ARCHITECTURE-TEMPLATE.md", "docs/.templates/ARCHITECTURE-TEMPLATE.md"),
    }[kind]
    for base in (repo, _plugin_root()):
        for rel in names:
            candidate = base / rel
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def _input_files(process: Path, state: dict[str, Any], role: str) -> list[Path]:
    repo = Path(state["repo_root"])
    common = [repo / state["task"], process / "source.json", process / "authority.json", process / "document-index.json", process / "decision.json"]
    if role == "thinker":
        for optional in (state.get("critique_path"), state.get("outcome_review_path")):
            if optional:
                common.append(Path(optional))
    elif role == "plan_critic":
        common.append(Path(state["proposal_path"]))
    elif role == "editor":
        common.append(process / "approved-contract.json")
    else:
        common.extend([process / "approved-contract.json", process / "changes.patch", process / "checks" / "summary.json"])
        common.extend(path for path in (process / "staging").rglob("*") if path.is_file())
    return [path for path in common if path.is_file()]


def _validate_dispatch_freshness(dispatch: dict[str, Any]) -> None:
    template = Path(dispatch["template"])
    if not template.is_file() or _sha256(template) != dispatch["template_sha256"]:
        raise ContractError("Dispatch template changed after dispatch", "STALE_DISPATCH")
    for value, expected in dispatch.get("input_hashes", {}).items():
        path = Path(value)
        if not path.is_file() or _sha256(path) != expected:
            raise ContractError(f"Dispatch input changed after dispatch: {path}", "STALE_DISPATCH")


def _dispatch_spec(process: Path, state: dict[str, Any]) -> dict[str, Any]:
    role = state["next_role"]
    stage = state["current_stage"]
    mode = state["next_mode"]
    if role not in ROLE_MODEL:
        raise ContractError(f"No dispatch role: {role}", "NO_DISPATCH_ROLE")
    state["dispatch_seq"] += 1
    dispatch_id = f"{stage}-{state['dispatch_seq']:03d}"
    template = (_plugin_root() / ROLE_TEMPLATE[role]).resolve()
    if not template.is_file():
        raise ContractError(f"Role template missing: {template}", "TEMPLATE_MISSING")
    input_hashes = {str(path): _sha256(path) for path in _input_files(process, state, role)}
    spec: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "dispatch_id": dispatch_id, "stage": stage, "role": role,
        "model": ROLE_MODEL[role], "mode": mode,
        "template": str(template), "template_sha256": _sha256(template),
        "repo_root": state["repo_root"], "task": state["task"], "app": state["app"],
        "process": str(process), "source": str(process / "source.json"),
        "authority": str(process / "authority.json"),
        "document_index": str(process / "document-index.json"),
        "decision": str(process / "decision.json"),
        "approved_contract": str(process / "approved-contract.json"),
        "patch": str(process / "changes.patch"), "checks": str(process / "checks" / "summary.json"),
        "input_hashes": input_hashes,
        "affected_path": None, "staged_path": None, "document_template": None,
        "authorized_paths": [], "feedback_paths": [],
    }
    if role == "thinker":
        spec["artifact"] = str(process / "proposals" / f"{dispatch_id}.json")
        spec["feedback_paths"] = [path for path in (state.get("critique_path"), state.get("outcome_review_path")) if path]
    elif role == "plan_critic":
        spec["proposal"] = state["proposal_path"]
        spec["proposal_sha256"] = state["proposal_sha256"]
        spec["artifact"] = str(process / "critiques" / f"{dispatch_id}.json")
    elif role == "editor":
        path = state["editor_queue"][state["editor_index"]]
        kind = _classify_ssot_path(state["app"], path)
        spec.update({
            "affected_path": path,
            "staged_path": str((process / "staging" / path).resolve()),
            "authorized_paths": [str((process / "staging" / path).resolve())],
            "document_template": _template_for_type(Path(state["repo_root"]), kind or "FRD"),
            "artifact": str(process / "editor-notes" / f"{dispatch_id}.md"),
            "feedback_paths": [str(process / "checks" / "summary.json"), state.get("outcome_review_path")],
        })
        spec["feedback_paths"] = [path for path in spec["feedback_paths"] if path and Path(path).is_file()]
    else:
        spec["artifact"] = str(process / "reviews" / f"{dispatch_id}.json")
        spec["staging_root"] = str(process / "staging")
        spec["contract_sha256"] = state["approved_contract_sha256"]
    spec["result_path"] = str(process / "results" / f"{dispatch_id}.json")
    digest_basis = {
        "dispatch_id": dispatch_id, "stage": stage, "role": role, "mode": mode,
        "template_sha256": spec["template_sha256"], "input_hashes": input_hashes,
        "affected_path": spec["affected_path"], "authorized_paths": spec["authorized_paths"],
    }
    spec["input_digest"] = _value_sha(digest_basis)
    rejection = state.pop("last_rejection", None)
    if rejection:
        spec["last_rejection"] = rejection
    label = f"dispatch-{dispatch_id}"
    _snapshot_protected(process, state, label)
    _snapshot_staging(process, label)
    spec["snapshot_label"] = label
    packet = process / "dispatches" / f"{dispatch_id}.json"
    prompt = process / "dispatches" / f"{dispatch_id}.md"
    spec["dispatch_packet"] = str(packet)
    spec["prompt_path"] = str(prompt)
    _write_json(packet, spec)
    _write_text(prompt, (
        f"# ssot-write Contract v{CONTRACT_VERSION} dispatch\n\n"
        f"Read `{template}` completely, then read `{packet}` and execute that one role. "
        "Use only packet paths, write the exact artifact and result_path, and do not ask the main orchestrator to interpret the task.\n"
    ))
    state["active_dispatch"] = spec
    state["stage_results"][stage]["status"] = "doing"
    return spec


def next_action(process: Path) -> dict[str, Any]:
    process = _process_path(process)
    with _process_lock(process):
        state = _load_state(process)
        if state["run_status"] == "committing":
            _recover_interrupted_commit(process, state)
            _save_state(process, state, {
                "event": "commit_recovery", "stage": "commit",
                "result": state.get("terminal_result") or "pending",
            })
            if state["run_status"] == "committing":
                return {
                    "action": "retry", "process": str(process),
                    "reason": state.get("last_failure_class") or "COMMIT_LOCKED",
                    "retry_after_seconds": 1,
                }
        if state["run_status"] == "terminal":
            return {
                "action": "done", "process": str(process),
                "terminal_result": state["terminal_result"],
                "report_path": str(process / "final-report.txt"),
                "response_mode": "verbatim", "allow_additional_text": False,
            }
        if state["run_status"] == "waiting_user":
            return {"action": "ask_user", "question_id": state["blocking_question_id"], "question": state["blocking_question"]}
        source = _read_json(process / "source.json")
        task_path = Path(state["repo_root"]) / state["task"]
        if not state.get("active_dispatch") and (
            not task_path.is_file() or _sha256(task_path) != source.get("task_sha256")
        ):
            _finalize(process, state, "VERIFY_FAILED", "SOURCE_CHANGED")
            _save_state(process, state, {"event": "source_changed", "stage": state["current_stage"], "result": "VERIFY_FAILED"})
            return {
                "action": "done", "process": str(process),
                "terminal_result": state["terminal_result"],
                "report_path": str(process / "final-report.txt"),
                "response_mode": "verbatim", "allow_additional_text": False,
            }
        if state.get("active_dispatch"):
            return {"action": "dispatch", **state["active_dispatch"]}
        spec = _dispatch_spec(process, state)
        _save_state(process, state, {"event": "dispatch", "stage": spec["stage"], "result": "pending", "dispatch_id": spec["dispatch_id"]})
        _snapshot_control(process, spec, state)
        return {"action": "dispatch", **spec}


def _validate_result(result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    unknown = set(result) - RESULT_FIELDS
    missing = RESULT_FIELDS - set(result)
    if unknown or missing:
        raise ContractError(f"Result fields mismatch: unknown={sorted(unknown)}, missing={sorted(missing)}", "RESULT_SCHEMA")
    if result["contract_version"] != CONTRACT_VERSION:
        raise ContractError("Result contract version mismatch", "RESULT_VERSION")
    for key in ("dispatch_id", "stage", "role", "mode", "input_digest"):
        if result[key] != dispatch[key]:
            raise ContractError(f"Result {key} mismatch", "STALE_DISPATCH" if key == "input_digest" else "RESULT_IDENTITY")
    if result["status"] not in ROLE_STATUS[result["role"]]:
        raise ContractError(f"Invalid status for {result['role']}: {result['status']}", "RESULT_STATUS")
    expected_failure = "NONE"
    if result["status"] == "FAIL":
        expected_failure = result["failure_class"]
        allowed = {"PLAN"} if result["role"] == "plan_critic" else {"PLAN", "EXECUTION"}
        if expected_failure not in allowed:
            raise ContractError("FAIL uses an invalid failure class", "RESULT_FAILURE_CLASS")
    elif result["failure_class"] != "NONE":
        raise ContractError("Only FAIL may use a failure class", "RESULT_FAILURE_CLASS")
    if result["status"] == "BLOCKED":
        if not isinstance(result["question_id"], str) or not result["question_id"].strip() or not isinstance(result["question"], str) or not result["question"].strip():
            raise ContractError("BLOCKED requires question fields", "RESULT_QUESTION")
    elif result["question_id"] is not None or result["question"] is not None:
        raise ContractError("Non-BLOCKED question fields must be null", "RESULT_QUESTION")
    if not isinstance(result["actual_model"], str) or not result["actual_model"].strip():
        raise ContractError("actual_model must be a non-empty string", "RESULT_MODEL")
    if (
        not isinstance(result["changed"], list)
        or not all(isinstance(item, str) for item in result["changed"])
        or not isinstance(result["affected_paths"], list)
        or not all(isinstance(item, str) for item in result["affected_paths"])
    ):
        raise ContractError("changed and affected_paths must be string lists", "RESULT_PATHS")


def _validate_path(repo: Path, app: str, path_value: str, kind: str) -> str:
    path = _repo_rel(repo, _resolve_under(repo, path_value))
    if _classify_ssot_path(app, path) != kind:
        raise ContractError(f"Target path/type mismatch: {kind}: {path}", "TARGET_TYPE_MISMATCH")
    if "/TASK/" in path.upper():
        raise ContractError(f"TASK path cannot be targeted: {path}", "TARGET_TASK_PROHIBITED")
    return path


def _validate_proposal(path: Path, state: dict[str, Any], dispatch: dict[str, Any]) -> dict[str, Any]:
    value = _read_json(path)
    fields = {"contract_version", "proposal_id", "disposition", "facts", "actions", "skips", "relations", "risk_flags", "questions"}
    if set(value) != fields:
        raise ContractError(f"Proposal fields mismatch: {sorted(set(value) ^ fields)}", "PROPOSAL_SCHEMA")
    if value["contract_version"] != CONTRACT_VERSION or value["proposal_id"] != dispatch["dispatch_id"]:
        raise ContractError("Proposal identity mismatch", "PROPOSAL_IDENTITY")
    if not isinstance(value["disposition"], str) or value["disposition"] not in DISPOSITIONS:
        raise ContractError("Invalid proposal disposition", "PROPOSAL_DISPOSITION")
    for key in ("facts", "actions", "skips", "relations", "risk_flags", "questions"):
        if not isinstance(value[key], list):
            raise ContractError(f"Proposal {key} must be a list", "PROPOSAL_SCHEMA")
    if not all(isinstance(item, str) and item.strip() for item in value["risk_flags"]):
        raise ContractError("risk_flags must contain non-empty strings", "PROPOSAL_SCHEMA")
    if value["disposition"] == "BLOCKED":
        if value["actions"] or len(value["questions"]) != 1 or not isinstance(value["questions"][0], str) or not value["questions"][0].strip():
            raise ContractError("BLOCKED proposal requires one string question and no actions", "PROPOSAL_BLOCKED")
        return value
    if value["questions"]:
        raise ContractError("Non-BLOCKED proposal cannot contain questions", "PROPOSAL_QUESTION")
    fact_ids: set[str] = set()
    for fact in value["facts"]:
        if not isinstance(fact, dict) or set(fact) != {"fact_id", "statement", "evidence"}:
            raise ContractError("Invalid fact schema", "PROPOSAL_FACT")
        if (
            not isinstance(fact["fact_id"], str) or not fact["fact_id"].strip()
            or fact["fact_id"] in fact_ids
            or not isinstance(fact["statement"], str) or not fact["statement"].strip()
            or not isinstance(fact["evidence"], list)
            or not all(isinstance(item, str) and item.strip() for item in fact["evidence"])
        ):
            raise ContractError("Invalid or duplicate fact", "PROPOSAL_FACT")
        fact_ids.add(fact["fact_id"])
    relation_ids: set[str] = set()
    repo = Path(state["repo_root"])
    relation_fields = {
        "relation_id", "kind", "source_path", "target_path", "feature_id",
        "authority_ids", "outcome", "requirement", "verification",
    }
    for relation in value["relations"]:
        if not isinstance(relation, dict) or set(relation) != relation_fields:
            raise ContractError("Invalid relation schema", "PROPOSAL_RELATION")
        relation_id = relation["relation_id"]
        if not isinstance(relation_id, str) or not relation_id or relation_id in relation_ids:
            raise ContractError("Invalid or duplicate relation_id", "PROPOSAL_RELATION")
        relation_ids.add(relation_id)
        if not isinstance(relation["kind"], str) or relation["kind"] not in {"FC_FRD_TRACE", "ADR_DISPOSITION", "SEMANTIC"}:
            raise ContractError("Invalid relation kind", "PROPOSAL_RELATION")
        if not isinstance(relation["verification"], str) or relation["verification"] not in {"MECHANICAL", "SEMANTIC"}:
            raise ContractError("Invalid relation verification", "PROPOSAL_RELATION")
        for key in ("source_path", "target_path"):
            if relation[key] is not None:
                if not isinstance(relation[key], str) or not relation[key].strip():
                    raise ContractError("Relation paths must be non-empty strings or null", "PROPOSAL_RELATION")
                normalized = _repo_rel(repo, _resolve_under(repo, relation[key]))
                if not normalized.startswith(f"Docs/{state['app']}/"):
                    raise ContractError("Relation path is outside the App", "PROPOSAL_RELATION")
                relation[key] = normalized
        if not isinstance(relation["authority_ids"], list) or not all(isinstance(item, str) for item in relation["authority_ids"]):
            raise ContractError("authority_ids must be strings", "PROPOSAL_RELATION")
        if relation["feature_id"] is not None and (not isinstance(relation["feature_id"], str) or not relation["feature_id"].strip()):
            raise ContractError("feature_id must be a non-empty string or null", "PROPOSAL_RELATION")
        if not isinstance(relation["outcome"], str) or not relation["outcome"].strip():
            raise ContractError("Relation outcome is required", "PROPOSAL_RELATION")
        if not isinstance(relation["requirement"], str) or not relation["requirement"].strip():
            raise ContractError("Relation requirement is required", "PROPOSAL_RELATION")
    action_fields = {"action_id", "ssot_type", "action", "path", "edit_scope", "reason", "fact_ids", "relation_ids"}
    action_ids: set[str] = set()
    action_types: set[str] = set()
    action_paths: set[str] = set()
    for action in value["actions"]:
        if not isinstance(action, dict) or set(action) != action_fields:
            raise ContractError("Invalid action schema", "PROPOSAL_ACTION")
        if not isinstance(action["action_id"], str) or not action["action_id"].strip() or action["action_id"] in action_ids:
            raise ContractError("Invalid or duplicate action_id", "PROPOSAL_ACTION")
        action_ids.add(action["action_id"])
        kind = action["ssot_type"]
        if not isinstance(kind, str) or kind not in SSOT_TYPES or not isinstance(action["action"], str) or action["action"] not in TARGET_ACTIONS:
            raise ContractError("Invalid action type", "PROPOSAL_ACTION")
        if not isinstance(action["path"], str) or not action["path"].strip():
            raise ContractError("Action path must be a non-empty string", "PROPOSAL_ACTION")
        path_value = _validate_path(repo, state["app"], action["path"], kind)
        path_key = path_value.casefold()
        if path_key in action_paths:
            raise ContractError(f"Duplicate action path: {path_value}", "PROPOSAL_ACTION")
        action_paths.add(path_key)
        action["path"] = path_value
        target = repo / path_value
        if action["action"] == "UPDATE" and not target.is_file():
            raise ContractError(f"UPDATE target missing: {path_value}", "PROPOSAL_ACTION")
        if action["action"] == "CREATE" and target.exists():
            raise ContractError(f"CREATE target exists: {path_value}", "PROPOSAL_ACTION")
        if not isinstance(action["edit_scope"], str) or not action["edit_scope"].strip() or not isinstance(action["reason"], str) or not action["reason"].strip():
            raise ContractError("Action edit_scope and reason are required", "PROPOSAL_ACTION")
        if (
            not isinstance(action["fact_ids"], list)
            or not all(isinstance(item, str) for item in action["fact_ids"])
            or not isinstance(action["relation_ids"], list)
            or not all(isinstance(item, str) for item in action["relation_ids"])
        ):
            raise ContractError("Action fact_ids and relation_ids must be string lists", "PROPOSAL_ACTION")
        if not set(action["fact_ids"]).issubset(fact_ids) or not set(action["relation_ids"]).issubset(relation_ids):
            raise ContractError("Action references unknown facts or relations", "PROPOSAL_ACTION")
        action_types.add(kind)
    skip_fields = {"ssot_type", "reason", "reused_authorities"}
    skip_types: set[str] = set()
    for skip in value["skips"]:
        if not isinstance(skip, dict) or set(skip) != skip_fields:
            raise ContractError("Invalid skip schema", "PROPOSAL_SKIP")
        kind = skip["ssot_type"]
        if not isinstance(kind, str) or kind not in SSOT_TYPES or kind in skip_types or not isinstance(skip["reason"], str) or not skip["reason"].strip():
            raise ContractError("Invalid or duplicate skip", "PROPOSAL_SKIP")
        if not isinstance(skip["reused_authorities"], list) or not all(isinstance(item, str) for item in skip["reused_authorities"]):
            raise ContractError("reused_authorities must be a string list", "PROPOSAL_SKIP")
        skip_types.add(kind)
    if action_types & skip_types or action_types | skip_types != set(SSOT_TYPES):
        raise ContractError("Proposal must cover all six SSOT types exactly once", "PROPOSAL_COVERAGE")
    if value["disposition"] == "ACTIVE" and not value["actions"]:
        raise ContractError("ACTIVE disposition requires actions", "PROPOSAL_DISPOSITION")
    if value["disposition"] == "NOOP" and value["actions"]:
        raise ContractError("NOOP prohibits actions", "PROPOSAL_DISPOSITION")
    if value["disposition"] in {"OBSOLETE", "REWRITE_REQUIRED"} and value["actions"]:
        raise ContractError(f"{value['disposition']} prohibits actions", "PROPOSAL_DISPOSITION")
    for frd_action in [row for row in value["actions"] if row["ssot_type"] == "FRD" and row["action"] == "CREATE"]:
        matches = [
            relation for relation in value["relations"]
            if relation["kind"] == "FC_FRD_TRACE" and relation["target_path"] == frd_action["path"]
        ]
        if len(matches) != 1:
            raise ContractError("Each FRD CREATE requires one matching FC_FRD_TRACE relation", "PLAN_INVARIANT_FAILED")
        relation = matches[0]
        fc_actions = [
            row for row in value["actions"]
            if row["ssot_type"] == "FC" and row["path"] == relation["source_path"]
        ]
        if not fc_actions or relation["relation_id"] not in frd_action["relation_ids"] or relation["relation_id"] not in fc_actions[0]["relation_ids"]:
            raise ContractError("FC_FRD_TRACE must bind both FC and created FRD actions", "PLAN_INVARIANT_FAILED")
    adr_skip = next((row for row in value["skips"] if row["ssot_type"] == "ADR"), None)
    if adr_skip and adr_skip["reused_authorities"] and any(row["ssot_type"] == "FRD" for row in value["actions"]):
        covered = {
            item for relation in value["relations"] if relation["kind"] == "ADR_DISPOSITION"
            for item in relation["authority_ids"]
        }
        if not set(adr_skip["reused_authorities"]).issubset(covered):
            raise ContractError("Reused ADR authorities require an ADR_DISPOSITION relation", "PLAN_INVARIANT_FAILED")
    return value


def _validate_critique(path: Path, proposal_sha: str, dispatch: dict[str, Any]) -> dict[str, Any]:
    value = _read_json(path)
    fields = {"contract_version", "critique_id", "proposal_sha256", "verdict", "defects", "risk_level", "question_id", "question"}
    if set(value) != fields:
        raise ContractError("Critique fields mismatch", "CRITIQUE_SCHEMA")
    if value["contract_version"] != CONTRACT_VERSION or value["critique_id"] != dispatch["dispatch_id"]:
        raise ContractError("Critique identity mismatch", "CRITIQUE_IDENTITY")
    if value["proposal_sha256"] != proposal_sha:
        raise ContractError("Critique is not bound to the current proposal", "STALE_INPUT")
    if not isinstance(value["verdict"], str) or value["verdict"] not in {"APPROVE", "REJECT", "BLOCKED"} or not isinstance(value["defects"], list):
        raise ContractError("Invalid critique verdict", "CRITIQUE_SCHEMA")
    if not isinstance(value["risk_level"], str) or value["risk_level"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ContractError("Invalid critique risk_level", "CRITIQUE_SCHEMA")
    defect_fields = {"defect_id", "class", "affected_paths", "description", "evidence"}
    for defect in value["defects"]:
        if not isinstance(defect, dict) or set(defect) != defect_fields:
            raise ContractError("Invalid critique defect", "CRITIQUE_SCHEMA")
        if (
            not isinstance(defect["defect_id"], str) or not defect["defect_id"].strip()
            or not isinstance(defect["class"], str) or defect["class"] not in {"PLAN", "AUTHORITY"}
            or not isinstance(defect["affected_paths"], list) or not all(isinstance(item, str) for item in defect["affected_paths"])
            or not isinstance(defect["description"], str) or not defect["description"].strip()
            or not isinstance(defect["evidence"], list) or not all(isinstance(item, str) and item.strip() for item in defect["evidence"])
        ):
            raise ContractError("Invalid critique defect", "CRITIQUE_SCHEMA")
    if value["verdict"] == "APPROVE" and value["defects"]:
        raise ContractError("APPROVE prohibits defects", "CRITIQUE_SCHEMA")
    if value["verdict"] == "REJECT" and not value["defects"]:
        raise ContractError("REJECT requires defects", "CRITIQUE_SCHEMA")
    if value["verdict"] == "BLOCKED":
        if value["defects"] or not isinstance(value["question_id"], str) or not value["question_id"].strip() or not isinstance(value["question"], str) or not value["question"].strip():
            raise ContractError("BLOCKED critique requires one question and no defects", "CRITIQUE_SCHEMA")
    elif value["question_id"] is not None or value["question"] is not None:
        raise ContractError("Non-BLOCKED critique question fields must be null", "CRITIQUE_SCHEMA")
    return value


def _validate_outcome(path: Path, contract_sha: str, dispatch: dict[str, Any]) -> dict[str, Any]:
    value = _read_json(path)
    fields = {"contract_version", "review_id", "contract_sha256", "verdict", "failure_class", "defects", "question_id", "question"}
    if set(value) != fields:
        raise ContractError("Outcome review fields mismatch", "OUTCOME_SCHEMA")
    if value["contract_version"] != CONTRACT_VERSION or value["review_id"] != dispatch["dispatch_id"]:
        raise ContractError("Outcome review identity mismatch", "OUTCOME_IDENTITY")
    if value["contract_sha256"] != contract_sha:
        raise ContractError("Outcome review is not bound to the approved contract", "STALE_INPUT")
    if not isinstance(value["verdict"], str) or value["verdict"] not in {"PASS", "FAIL", "BLOCKED"}:
        raise ContractError("Invalid outcome verdict", "OUTCOME_SCHEMA")
    if not isinstance(value["failure_class"], str) or value["failure_class"] not in {"NONE", "PLAN", "EXECUTION"}:
        raise ContractError("Invalid outcome failure class", "OUTCOME_SCHEMA")
    if not isinstance(value["defects"], list):
        raise ContractError("Outcome defects must be a list", "OUTCOME_SCHEMA")
    if value["verdict"] == "PASS" and (value["failure_class"] != "NONE" or value["defects"]):
        raise ContractError("PASS prohibits defects", "OUTCOME_SCHEMA")
    defect_fields = {"defect_id", "class", "affected_paths", "description", "evidence"}
    for defect in value["defects"]:
        if not isinstance(defect, dict) or set(defect) != defect_fields:
            raise ContractError("Invalid outcome defect", "OUTCOME_SCHEMA")
        if (
            not isinstance(defect["defect_id"], str) or not defect["defect_id"].strip()
            or not isinstance(defect["class"], str) or defect["class"] not in {"PLAN", "EXECUTION"}
            or not isinstance(defect["affected_paths"], list) or not all(isinstance(item, str) for item in defect["affected_paths"])
            or not isinstance(defect["description"], str) or not defect["description"].strip()
            or not isinstance(defect["evidence"], list) or not all(isinstance(item, str) and item.strip() for item in defect["evidence"])
        ):
            raise ContractError("Invalid outcome defect", "OUTCOME_SCHEMA")
    if value["verdict"] == "FAIL" and not value["defects"]:
        raise ContractError("FAIL requires defects", "OUTCOME_SCHEMA")
    if value["verdict"] == "BLOCKED":
        if value["failure_class"] != "NONE" or value["defects"] or not isinstance(value["question_id"], str) or not value["question_id"].strip() or not isinstance(value["question"], str) or not value["question"].strip():
            raise ContractError("BLOCKED outcome requires one question and no defects", "OUTCOME_SCHEMA")
    elif value["question_id"] is not None or value["question"] is not None:
        raise ContractError("Non-BLOCKED outcome question fields must be null", "OUTCOME_SCHEMA")
    return value


def _risk_reasons(proposal: dict[str, Any], authority: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if proposal["disposition"] in {"OBSOLETE", "REWRITE_REQUIRED"}:
        reasons.append(f"task-disposition:{proposal['disposition']}")
    if any(action["action"] == "CREATE" for action in proposal["actions"]):
        reasons.append("creates-permanent-ssot")
    if any(action["ssot_type"] == "ADR" for action in proposal["actions"]):
        reasons.append("changes-adr-authority")
    if len(proposal["actions"]) >= 4:
        reasons.append("four-or-more-targets")
    if authority.get("conflicts"):
        reasons.append("authority-graph-conflict")
    reasons.extend(f"proposal:{flag}" for flag in proposal.get("risk_flags", []))
    return sorted(set(reasons))


def _block(state: dict[str, Any], result: dict[str, Any], kind: str, resume: dict[str, Any]) -> None:
    state.update({
        "run_status": "waiting_user",
        "blocking_question_id": result["question_id"],
        "blocking_question": result["question"],
        "blocking_kind": kind,
        "resume_after_block": resume,
        "last_result": "BLOCKED",
    })
    state["stage_results"][state["current_stage"]].update({"status": "blocked", "result": "BLOCKED"})


def _freeze_contract(process: Path, state: dict[str, Any]) -> None:
    proposal = _read_bound_json(
        Path(state["proposal_path"]), state["proposal_sha256"], "STALE_APPROVAL"
    )
    _read_bound_json(
        Path(state["critique_path"]), state["critique_sha256"], "STALE_APPROVAL"
    )
    contract = {
        **proposal,
        "contract_version": CONTRACT_VERSION,
        "proposal_sha256": state["proposal_sha256"],
        "critique_sha256": state["critique_sha256"],
        "approved_at": _now(),
        "compiled_by": "runner",
    }
    contract.pop("proposal_id", None)
    _write_json(process / "approved-contract.json", contract)
    contract_sha = _sha256(process / "approved-contract.json")
    state["approved_contract_sha256"] = contract_sha
    state["disposition"] = contract["disposition"]
    state["downstream"] = "WORK_PACKET" if contract["disposition"] in {"ACTIVE", "NOOP"} else (
        "TASK_WRITE" if contract["disposition"] == "REWRITE_REQUIRED" else "NONE"
    )
    _write_text(process / "ssot-write-impact.md", (
        "# ssot-write Impact\n\n"
        f"- Approved contract: `{contract_sha}`\n"
        f"- Disposition: `{contract['disposition']}`\n"
        f"- Actions: {len(contract['actions'])}\n"
        f"- Relations: {len(contract['relations'])}\n"
    ))
    if contract["disposition"] != "ACTIVE":
        terminal = "NOOP" if contract["disposition"] == "NOOP" else contract["disposition"]
        _finalize(process, state, terminal, "PASS" if terminal in {"NOOP", "OBSOLETE"} else terminal)
        return
    staging = process / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    repo = Path(state["repo_root"])
    for action in contract["actions"]:
        staged = staging / action["path"]
        staged.parent.mkdir(parents=True, exist_ok=True)
        if action["action"] == "UPDATE":
            shutil.copy2(repo / action["path"], staged)
    state["editor_queue"] = [action["path"] for action in contract["actions"]]
    state["editor_index"] = 0
    state.update({"current_stage": "edit", "next_role": "editor", "next_mode": "apply"})


def _proposal_action_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {action["path"]: action for action in contract["actions"]}


def _approved_contract(process: Path, state: dict[str, Any]) -> dict[str, Any]:
    expected = state.get("approved_contract_sha256")
    if not isinstance(expected, str) or not expected:
        raise ContractError("Approved contract hash is missing", "APPROVED_CONTRACT_TAMPERED")
    return _read_bound_json(
        process / "approved-contract.json", expected, "APPROVED_CONTRACT_TAMPERED"
    )


def _status_class(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    for name in ("accepted", "superseded", "deprecated", "proposed", "rejected", "reverted"):
        if name in lowered:
            return "Superseded" if name == "deprecated" else name.title()
    return value.strip()


def _run_adr_status_check(root: Path, app: str, contract: dict[str, Any]) -> dict[str, Any]:
    ids: set[str] = set()
    for action in contract["actions"]:
        if action["ssot_type"] == "ADR":
            ids.add(Path(action["path"]).stem)
    for relation in contract["relations"]:
        ids.update(relation["authority_ids"])
    catalog = root / "Docs" / app / f"{app}-ADR-CATALOG.md"
    catalog_text = catalog.read_text(encoding="utf-8") if catalog.is_file() else ""
    section = ""
    catalog_status: dict[str, str] = {}
    for line in catalog_text.splitlines():
        heading = re.match(r"^##\s+(.+)$", line.strip())
        if heading:
            section = heading.group(1).strip()
            continue
        first_cell = line.strip().strip("|").split("|", 1)[0] if line.lstrip().startswith("|") else ""
        match = re.search(rf"\b{re.escape(app)}-ADR-\d{{3}}\b", first_cell)
        if match:
            normalized = "Superseded" if "Superseded" in section or "Deprecated" in section else (
                "Accepted" if "Accepted" in section else "Proposed" if "Proposed" in section else section
            )
            catalog_status[match.group(0)] = normalized
    checked: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for adr_id in sorted(ids):
        path = root / "Docs" / app / "ADR" / f"{adr_id}.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        match = re.search(r"^\|\s*상태\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        file_status = match.group(1).strip() if match else None
        listed = catalog_status.get(adr_id)
        result = "PASS" if _status_class(file_status) and _status_class(file_status) == _status_class(listed) else "FAIL"
        row = {"adr": adr_id, "file_status": file_status, "catalog_status": listed, "result": result}
        checked.append(row)
        if result == "FAIL":
            failures.append(row)
    return {"contract_version": CONTRACT_VERSION, "status": "FAIL" if failures else "PASS", "checked": checked, "failures": failures}


def _overlay_root(process: Path, state: dict[str, Any]) -> Path:
    root = process / "validation-root"
    if root.exists():
        shutil.rmtree(root)
    repo = Path(state["repo_root"])
    shutil.copytree(repo / "Docs", root / "Docs")
    for rel in _scan_staging(process):
        source = process / "staging" / rel
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def _execute_docs_helper(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    helper = Path(state["repo_root"]) / "scripts" / "docs_helpers.py"
    if not helper.is_file():
        helper = _plugin_root() / "scripts" / "docs_helpers.py"
    if not helper.is_file():
        return {
            "status": "FAIL", "raw_class": "INFRA_FAIL", "reason": "helper unavailable",
            "helper_path": None, "helper_sha256": None, "failures": [], "mutated_paths": [],
        }
    helper_path = str(helper.resolve())
    helper_sha256 = _sha256(helper)
    before = _scan_helper_surface(root)
    try:
        completed = subprocess.run(
            [sys.executable, str(helper), "check", "--repo", str(root), "--app", state["app"]],
            text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL", "raw_class": "INFRA_FAIL", "reason": "helper timeout",
            "helper_path": helper_path, "helper_sha256": helper_sha256,
            "failures": [], "mutated_paths": [],
        }
    except OSError as exc:
        return {
            "status": "FAIL", "raw_class": "INFRA_FAIL", "reason": f"helper execution failed: {exc}",
            "helper_path": helper_path, "helper_sha256": helper_sha256,
            "failures": [], "mutated_paths": [],
        }
    after = _scan_helper_surface(root)
    mutated = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    output_lines = [*completed.stdout.splitlines(), *completed.stderr.splitlines()]
    failures = sorted(line.strip() for line in output_lines if line.lstrip().startswith("FAIL "))
    stable_failure_pattern = re.compile(
        rf"^FAIL\s+(\S+)\s+((?:Docs|docs)/{re.escape(state['app'])}/\S+)(?:\s|$)",
        re.IGNORECASE,
    )
    failure_identities = []
    for line in failures:
        match = stable_failure_pattern.match(line)
        failure_identities.append(
            f"{match.group(1)}|{_normalize_rel(match.group(2)).casefold()}" if match else None
        )
    summary_pattern = re.compile(r"^Summary:\s*(\d+)\s+PASS,\s*(\d+)\s+WARN,\s*(\d+)\s+FAIL$")
    summaries = [summary_pattern.fullmatch(line.strip()) for line in completed.stdout.splitlines()]
    summaries = [match for match in summaries if match]
    reason = None
    if mutated:
        raw_class = "MUTATED"
        reason = "helper modified validation Docs"
    elif len(summaries) != 1:
        raw_class = "INFRA_FAIL"
        reason = "helper emitted no unique parseable Summary"
    else:
        _, _, fail_count = (int(value) for value in summaries[0].groups())
        expected_exit = 1 if fail_count else 0
        if fail_count != len(failures):
            raw_class = "INFRA_FAIL"
            reason = "Summary FAIL count does not match stable failure lines"
        elif fail_count and any(identity is None for identity in failure_identities):
            raw_class = "INFRA_FAIL"
            reason = "helper FAIL lacks a stable check-id and App-relative path"
        elif completed.returncode != expected_exit:
            raw_class = "INFRA_FAIL"
            reason = "helper exit code contradicts Summary"
        elif completed.stderr.strip():
            raw_class = "INFRA_FAIL"
            reason = "helper emitted unexpected stderr"
        else:
            raw_class = "KNOWN_FAIL" if fail_count else "CLEAN"
    return {
        "status": "PASS" if raw_class == "CLEAN" else "FAIL",
        "raw_class": raw_class,
        "reason": reason,
        "helper_path": helper_path,
        "helper_sha256": helper_sha256,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "failures": failures,
        "failure_identities": failure_identities,
        "mutated_paths": mutated,
    }


def _relation_checks(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for relation in contract["relations"]:
        if relation["kind"] == "FC_FRD_TRACE":
            source_path = relation["source_path"]
            target_path = relation["target_path"]
            feature = relation["feature_id"]
            if not source_path or not target_path or not feature:
                failures.append({"code": "FC_FRD_TRACE_SCHEMA", "paths": [p for p in (source_path, target_path) if p], "relation_id": relation["relation_id"]})
                continue
            source = root / source_path
            target = root / target_path
            source_text = source.read_text(encoding="utf-8") if source.is_file() else ""
            target_text = target.read_text(encoding="utf-8") if target.is_file() else ""
            rows = [line for line in source_text.splitlines() if re.match(rf"^\|\s*{re.escape(feature)}\s*\|", line)]
            joined = "\n".join(rows)
            markers = [Path(target_path).stem, "§17", "§18"]
            if not target.is_file() or feature not in target_text or any(marker not in joined for marker in markers):
                failures.append({"code": "FC_FRD_TRACE_MISSING", "paths": [source_path, target_path], "relation_id": relation["relation_id"], "required": markers})
        elif relation["kind"] == "ADR_DISPOSITION" and relation["outcome"] == "REUSE_EXISTING":
            source_path = relation["source_path"]
            if source_path:
                source = root / source_path
                text = source.read_text(encoding="utf-8") if source.is_file() else ""
                adr_lines = "\n".join(line for line in text.splitlines() if re.match(r"^\|\s*ADR(?:-CATALOG)?\s*\|", line, re.IGNORECASE))
                if re.search(r"검토\s*필요|\bTBD\b|미정", adr_lines, re.IGNORECASE):
                    failures.append({"code": "STALE_ADR_PLACEHOLDER", "paths": [source_path], "relation_id": relation["relation_id"]})
                if relation["authority_ids"] and not any(adr_id in text for adr_id in relation["authority_ids"]):
                    failures.append({"code": "ADR_REUSE_EVIDENCE_MISSING", "paths": [source_path], "relation_id": relation["relation_id"]})
    return {"contract_version": CONTRACT_VERSION, "status": "FAIL" if failures else "PASS", "failures": failures}


def _run_checks(process: Path, state: dict[str, Any]) -> dict[str, Any]:
    contract = _approved_contract(process, state)
    root = _overlay_root(process, state)
    action_paths = [action["path"] for action in contract["actions"]]
    task_citations: list[str] = []
    missing: list[str] = []
    for path in action_paths:
        staged = process / "staging" / path
        if not staged.is_file():
            missing.append(path)
            continue
        if TASK_LINK_PATTERN.search(staged.read_text(encoding="utf-8")):
            task_citations.append(path)
    relation = _relation_checks(root, contract)
    helper_result = _execute_docs_helper(root, state)
    baseline_helper = _read_json(process / "checks" / "baseline-docs-helper.json")
    current_helper_failures = Counter(helper_result.get("failures", []))
    baseline_helper_failures = Counter(baseline_helper.get("failures", []))
    new_helper_failures = sorted((current_helper_failures - baseline_helper_failures).elements())
    helper_version_matches = (
        helper_result.get("helper_path") == baseline_helper.get("helper_path")
        and helper_result.get("helper_sha256") == baseline_helper.get("helper_sha256")
    )
    current_class = helper_result.get("raw_class")
    baseline_class = baseline_helper.get("raw_class")
    known_preexisting_only = (
        baseline_class == "KNOWN_FAIL"
        and current_class == "KNOWN_FAIL"
        and not new_helper_failures
    )
    helper_result["baseline_status"] = baseline_helper.get("status")
    helper_result["baseline_raw_class"] = baseline_class
    helper_result["helper_version_matches"] = helper_version_matches
    helper_result["new_failures"] = new_helper_failures
    helper_result["effective_status"] = "PASS" if (
        helper_version_matches
        and (current_class == "CLEAN" or known_preexisting_only)
    ) else "FAIL"
    adr = _run_adr_status_check(root, state["app"], contract)
    checks = {
        "contract_version": CONTRACT_VERSION,
        "contract_sha256": state["approved_contract_sha256"],
        "staging_manifest": _scan_staging(process),
        "missing_staged_paths": missing,
        "task_citation_paths": task_citations,
        "relations": relation,
        "docs_helper": helper_result,
        "adr_status": adr,
    }
    checks["status"] = "PASS" if (
        not missing and not task_citations and relation["status"] == "PASS"
        and helper_result["effective_status"] == "PASS" and adr["status"] == "PASS"
    ) else "FAIL"
    _write_json(process / "checks" / "summary.json", checks)
    state["mechanical_checks"] = checks
    state["stage_results"]["check"] = {"owner": "runner", "status": "done", "result": checks["status"]}
    return checks


def _write_staged_patch(process: Path, state: dict[str, Any]) -> None:
    contract = _approved_contract(process, state)
    baseline = process / "baseline"
    staging = process / "staging"
    lines: list[str] = []
    for action in contract["actions"]:
        rel = action["path"]
        old_path = baseline / rel
        new_path = staging / rel
        old = old_path.read_text(encoding="utf-8").splitlines(True) if old_path.is_file() else []
        new = new_path.read_text(encoding="utf-8").splitlines(True) if new_path.is_file() else []
        lines.extend(difflib.unified_diff(old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    _write_text(process / "changes.patch", "".join(lines))


def _schedule_repairs(process: Path, state: dict[str, Any], affected: list[str], feedback: str) -> None:
    attempts = state.setdefault("repair_attempts", {})
    for path in affected:
        count = int(attempts.get(path, 0)) + 1
        if count > MAX_REPAIRS_PER_PATH:
            _finalize(process, state, "VERIFY_FAILED", "VERIFY_FAILED")
            return
        attempts[path] = count
    state["editor_queue"] = affected
    state["editor_index"] = 0
    state["repair_feedback"] = feedback
    state.update({"current_stage": "edit", "next_role": "editor", "next_mode": "repair"})


def _prepare_outcome(process: Path, state: dict[str, Any]) -> None:
    _write_staged_patch(process, state)
    checks = _run_checks(process, state)
    if checks["status"] != "PASS":
        helper = checks["docs_helper"]
        if helper.get("raw_class") in {"INFRA_FAIL", "MUTATED"} or not helper.get("helper_version_matches", False):
            _finalize(process, state, "VERIFY_FAILED", "DOCS_HELPER_UNSTABLE")
            return
        affected: set[str] = set(checks["missing_staged_paths"] + checks["task_citation_paths"])
        for failure in checks["relations"]["failures"]:
            affected.update(failure.get("paths", []))
        contract_paths = {action["path"] for action in _approved_contract(process, state)["actions"]}
        affected = {path for path in affected if path in contract_paths} or contract_paths
        _schedule_repairs(process, state, sorted(affected), str(process / "checks" / "summary.json"))
        return
    state["outcome_iterations"] += 1
    state.update({"current_stage": "outcome_review", "next_role": "outcome_critic", "next_mode": "verify"})


def _accept_thinker(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    proposal = _validate_proposal(Path(dispatch["artifact"]), state, dispatch)
    if result["status"] == "BLOCKED":
        if proposal["disposition"] != "BLOCKED":
            raise ContractError("BLOCKED result requires BLOCKED proposal", "PROPOSAL_BLOCKED")
        if proposal["questions"][0] != result["question"]:
            raise ContractError("BLOCKED proposal and result question disagree", "PROPOSAL_BLOCKED")
        _block(state, result, "authority", {"stage": "think", "role": "thinker", "mode": "revise"})
        return
    if proposal["disposition"] == "BLOCKED":
        raise ContractError("READY result cannot use BLOCKED proposal", "PROPOSAL_BLOCKED")
    normalized = process / "proposals" / f"{dispatch['dispatch_id']}.normalized.json"
    _write_json(normalized, proposal)
    state["proposal_path"] = str(normalized)
    state["proposal_sha256"] = _sha256(normalized)
    state["stage_results"]["think"] = {"owner": "thinker", "status": "done", "result": "READY"}
    state.update({"current_stage": "plan_critique", "next_role": "plan_critic", "next_mode": "challenge"})


def _accept_plan_critic(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    critique = _validate_critique(Path(dispatch["artifact"]), state["proposal_sha256"], dispatch)
    expected_status = {"APPROVE": "PASS", "REJECT": "FAIL", "BLOCKED": "BLOCKED"}[critique["verdict"]]
    if result["status"] != expected_status:
        raise ContractError("Plan critic result and artifact disagree", "CRITIQUE_RESULT")
    if critique["verdict"] == "BLOCKED" and (
        result["question_id"] != critique["question_id"] or result["question"] != critique["question"]
    ):
        raise ContractError("Plan critic question and result disagree", "CRITIQUE_RESULT")
    state["critique_path"] = dispatch["artifact"]
    state["critique_sha256"] = _sha256(Path(dispatch["artifact"]))
    if result["status"] == "BLOCKED" or critique["verdict"] == "BLOCKED":
        _block(state, result, "authority", {"stage": "think", "role": "thinker", "mode": "revise"})
        return
    if result["status"] == "FAIL" or critique["verdict"] == "REJECT":
        if result["failure_class"] != "PLAN":
            raise ContractError("Plan critique rejection must use PLAN", "CRITIQUE_RESULT")
        if state["plan_revisions"] >= MAX_PLAN_REVISIONS:
            _finalize(process, state, "PLAN_REJECTED", "PLAN_REJECTED")
            return
        state["plan_revisions"] += 1
        state.update({"current_stage": "think", "next_role": "thinker", "next_mode": "revise"})
        return
    if result["status"] != "PASS" or critique["verdict"] != "APPROVE":
        raise ContractError("Plan critic result and artifact disagree", "CRITIQUE_RESULT")
    state["stage_results"]["plan_critique"] = {"owner": "plan_critic", "status": "done", "result": "PASS"}
    proposal = _read_json(Path(state["proposal_path"]))
    risks = _risk_reasons(proposal, _read_json(process / "authority.json"))
    if critique.get("risk_level") == "HIGH":
        risks = sorted(set([*risks, "plan-critic-high-risk"]))
    if risks:
        contract_sha = state["proposal_sha256"]
        question_id = f"RISK-{contract_sha[:12]}"
        paths = [action["path"] for action in proposal["actions"]]
        pseudo = {
            "question_id": question_id,
            "question": f"Approve high-risk SSOT contract {contract_sha[:12]}? disposition={proposal['disposition']}; paths={paths}; risks={risks}",
        }
        _block(state, pseudo, "risk_approval", {"action": "freeze_contract", "proposal_sha256": contract_sha})
        return
    _freeze_contract(process, state)


def _accept_editor(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    live_changes = _protected_changes(process, state, dispatch["snapshot_label"])
    if live_changes:
        raise ContractError(f"Editor modified protected live files: {live_changes}", "LIVE_WRITE_PROHIBITED")
    actual = _staging_changes(process, dispatch["snapshot_label"])
    expected = [dispatch["affected_path"]]
    declared = sorted(_normalize_rel(item) for item in result["changed"])
    if result["status"] == "BLOCKED":
        if actual:
            raise ContractError("BLOCKED editor left staging changes", "EDITOR_BLOCKED_DIRTY")
        _block(state, result, "execution", {"stage": "edit", "role": "editor", "mode": dispatch["mode"]})
        return
    if actual != expected or declared != expected:
        raise ContractError(f"Editor must change exactly one staging path: expected={expected}, actual={actual}, declared={declared}", "EDITOR_PATH_SCOPE")
    staged = process / "staging" / dispatch["affected_path"]
    if staged.is_symlink():
        raise ContractError("Editor staging output cannot be a symlink", "EDITOR_PATH_SCOPE")
    if not staged.is_file():
        raise ContractError("Editor did not create the staged file", "EDITOR_OUTPUT_MISSING")
    state.setdefault("staged_hashes", {})[dispatch["affected_path"]] = _sha256(staged)
    state["editor_index"] += 1
    if state["editor_index"] < len(state["editor_queue"]):
        return
    state["stage_results"]["edit"] = {"owner": "editor", "status": "done", "result": "PASS"}
    _write_text(process / "ssot-write-action.md", "# ssot-write Action\n\nStaged paths:\n\n" + "\n".join(f"- `{path}`" for path in state["editor_queue"]) + "\n")
    _prepare_outcome(process, state)


def _accept_outcome(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    review = _validate_outcome(Path(dispatch["artifact"]), state["approved_contract_sha256"], dispatch)
    if result["status"] != review["verdict"] or result["failure_class"] != review["failure_class"]:
        raise ContractError("Outcome result and artifact disagree", "OUTCOME_RESULT")
    if review["verdict"] == "BLOCKED" and (
        result["question_id"] != review["question_id"] or result["question"] != review["question"]
    ):
        raise ContractError("Outcome question and result disagree", "OUTCOME_RESULT")
    state["outcome_review_path"] = dispatch["artifact"]
    if result["status"] == "BLOCKED" or review["verdict"] == "BLOCKED":
        _block(state, result, "verification", {"stage": "outcome_review", "role": "outcome_critic", "mode": "verify"})
        return
    if result["status"] == "FAIL" or review["verdict"] == "FAIL":
        failure = review["failure_class"]
        if failure == "PLAN":
            if state["plan_revisions"] >= MAX_PLAN_REVISIONS:
                _finalize(process, state, "PLAN_REJECTED", "PLAN_REJECTED")
                return
            state["plan_revisions"] += 1
            staging = process / "staging"
            if staging.exists():
                shutil.rmtree(staging)
            state.update({"current_stage": "think", "next_role": "thinker", "next_mode": "revise"})
            return
        affected: set[str] = set()
        for defect in review["defects"]:
            if defect["class"] == "EXECUTION":
                affected.update(_normalize_rel(path) for path in defect["affected_paths"])
        allowed = {action["path"] for action in _approved_contract(process, state)["actions"]}
        if not affected or not affected.issubset(allowed):
            raise ContractError("Outcome EXECUTION failure must identify approved paths", "OUTCOME_AFFECTED_PATHS")
        _schedule_repairs(process, state, sorted(affected), dispatch["artifact"])
        return
    if result["status"] != "PASS" or review["verdict"] != "PASS":
        raise ContractError("Outcome result and artifact disagree", "OUTCOME_RESULT")
    checks = _read_json(process / "checks" / "summary.json")
    if checks.get("status") != "PASS":
        raise ContractError("Outcome PASS cannot override failed mechanical checks", "MECHANICAL_GATE_FAILED")
    state["stage_results"]["outcome_review"] = {"owner": "outcome_critic", "status": "done", "result": "PASS"}
    state["stage_results"]["commit"] = {"owner": "runner", "status": "doing", "result": None}
    state.update({
        "run_status": "committing", "current_stage": "commit",
        "next_role": None, "next_mode": None,
    })


def _receipt(process: Path, state: dict[str, Any], result: dict[str, Any], dispatch: dict[str, Any]) -> None:
    receipt = {
        "contract_version": CONTRACT_VERSION,
        "dispatch_id": dispatch["dispatch_id"],
        "requested_model": dispatch["model"], "actual_model": result["actual_model"],
        "template_sha256": dispatch["template_sha256"],
        "input_digest": dispatch["input_digest"],
        "artifact_sha256": _sha256(Path(dispatch["artifact"])),
        "result_sha256": _sha256(Path(dispatch["result_path"])),
        "accepted_at": _now(),
    }
    _write_json(process / "receipts" / f"{dispatch['dispatch_id']}.json", receipt)


def _run_live_postcheck(repo: Path, state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    relation = _relation_checks(repo, contract)
    adr = _run_adr_status_check(repo, state["app"], contract)
    return {"status": "PASS" if relation["status"] == "PASS" and adr["status"] == "PASS" else "FAIL", "relations": relation, "adr_status": adr}


def _commit(process: Path, state: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    lock = repo / ".process" / f".ssot-write-{state['app']}.commit.lock"
    try:
        with _advisory_file_lock(lock, "COMMIT_LOCKED"):
            _commit_locked(process, state)
    except ContractError as exc:
        if exc.code != "COMMIT_LOCKED":
            _finalize(process, state, "VERIFY_FAILED", exc.code)
            return
        state["commit_recovery_pending"] = True
        state["last_result"] = "pending"
        state["last_failure_class"] = "COMMIT_LOCKED"


def _commit_locked(process: Path, state: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    contract = _approved_contract(process, state)
    original = _read_json(process / "snapshots" / "original.json")
    current = _scan_docs(repo, state["app"])
    if current != original:
        _finalize(process, state, "VERIFY_FAILED", "COMMIT_CONFLICT")
        return
    backup = process / "commit-backup"
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    for action in contract["actions"]:
        rel = action["path"]
        target = _resolve_under(repo, rel)
        staged = _resolve_under(process / "staging", rel)
        if staged.is_symlink() or not staged.is_file():
            _finalize(process, state, "VERIFY_FAILED", "STAGING_CHANGED_BEFORE_COMMIT")
            return
        after_sha256 = _sha256(staged)
        if state.get("staged_hashes", {}).get(rel) != after_sha256:
            _finalize(process, state, "VERIFY_FAILED", "STAGING_CHANGED_BEFORE_COMMIT")
            return
        before_sha256 = _sha256(target) if target.is_file() else None
        temp = target.with_name(f".{target.name}.{state['run_id']}.tmp")
        saved = backup / rel
        entries.append({
            "path": rel,
            "action": action["action"],
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
            "backup_path": saved.relative_to(process).as_posix(),
            "temp_path": _repo_rel(repo, temp),
            "phase": "PREPARING",
        })
    journal: dict[str, Any] = {
        "contract_sha256": state["approved_contract_sha256"],
        "started_at": _now(), "entries": entries, "status": "PREPARING",
    }
    _write_json(process / "commit-journal.json", journal)
    try:
        for entry in entries:
            rel = entry["path"]
            target = _resolve_under(repo, rel)
            staged = _resolve_under(process / "staging", rel)
            saved = _resolve_under(process, entry["backup_path"])
            temp = _resolve_under(repo, entry["temp_path"])
            if entry["before_sha256"] is not None:
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                _fsync_file(saved)
                if _sha256(saved) != entry["before_sha256"]:
                    raise ContractError(f"Backup verification failed: {rel}", "BACKUP_VERIFY_FAILED")
            target.parent.mkdir(parents=True, exist_ok=True)
            if temp.exists() or temp.is_symlink():
                temp.unlink()
            shutil.copy2(staged, temp)
            _fsync_file(temp)
            if _sha256(temp) != entry["after_sha256"]:
                raise ContractError(f"Prepared temp verification failed: {rel}", "TEMP_VERIFY_FAILED")
            entry["phase"] = "PREPARED"
        journal["status"] = "PREPARED"
        _write_json(process / "commit-journal.json", journal)
        for entry in entries:
            target = _resolve_under(repo, entry["path"])
            temp = _resolve_under(repo, entry["temp_path"])
            journal["status"] = "COMMITTING"
            entry["phase"] = "REPLACING"
            _write_json(process / "commit-journal.json", journal)
            _replace_commit_target(temp, target)
            if not target.is_file() or _sha256(target) != entry["after_sha256"]:
                raise ContractError(f"Committed target verification failed: {entry['path']}", "COMMIT_VERIFY_FAILED")
            entry["phase"] = "APPLIED"
            _write_json(process / "commit-journal.json", journal)
        post = _run_live_postcheck(repo, state, contract)
        if post["status"] != "PASS":
            raise ContractError("Post-commit mechanical verification failed", "POSTCOMMIT_FAILED")
    except Exception as exc:
        rollback_errors = _rollback_journal(process, state, journal, str(exc))
        terminal = "RECOVERY_REQUIRED" if rollback_errors else "COMMIT_FAILED_ROLLED_BACK"
        _finalize(process, state, terminal, terminal)
        return
    journal.update({"status": "COMMITTED", "finished_at": _now()})
    _write_json(process / "commit-journal.json", journal)
    state["changed_paths"] = [action["path"] for action in contract["actions"]]
    state["commit_manifest"] = entries
    _write_json(process / "commit-manifest.json", {"contract_version": CONTRACT_VERSION, "entries": entries, "status": "COMMITTED"})
    state["stage_results"]["commit"] = {"owner": "runner", "status": "done", "result": "PASS"}
    _finalize(process, state, "DONE", "PASS")


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _rollback_journal(process: Path, state: dict[str, Any], journal: dict[str, Any], error: str) -> list[str]:
    repo = Path(state["repo_root"])
    journal["status"] = "ROLLING_BACK"
    journal["error"] = error
    _write_json(process / "commit-journal.json", journal)
    rollback_errors: list[str] = []
    for entry in reversed(journal.get("entries", [])):
        rel = entry.get("path")
        try:
            if not isinstance(rel, str):
                raise ContractError("Journal path is invalid", "JOURNAL_INVALID")
            target = _resolve_under(repo, rel)
            before_sha256 = entry.get("before_sha256")
            after_sha256 = entry.get("after_sha256")
            current_sha256 = _sha256(target) if target.is_file() else None
            if current_sha256 == before_sha256:
                pass
            elif current_sha256 == after_sha256:
                if before_sha256 is None:
                    target.unlink()
                else:
                    saved = _resolve_under(process, entry["backup_path"])
                    if not saved.is_file() or _sha256(saved) != before_sha256:
                        raise ContractError(f"Rollback backup is missing or corrupt: {rel}", "BACKUP_VERIFY_FAILED")
                    rollback_temp = target.with_name(f".{target.name}.{state['run_id']}.rollback.tmp")
                    if rollback_temp.exists() or rollback_temp.is_symlink():
                        rollback_temp.unlink()
                    shutil.copy2(saved, rollback_temp)
                    _fsync_file(rollback_temp)
                    _replace_commit_target(rollback_temp, target)
                    if _sha256(target) != before_sha256:
                        raise ContractError(f"Rollback verification failed: {rel}", "ROLLBACK_VERIFY_FAILED")
            else:
                raise ContractError(f"Live target has third-party content: {rel}", "RECOVERY_CONFLICT")
            temp = _resolve_under(repo, entry["temp_path"])
            if temp.exists() or temp.is_symlink():
                temp.unlink()
            entry["phase"] = "ROLLED_BACK"
            _write_json(process / "commit-journal.json", journal)
        except (OSError, ContractError, KeyError, TypeError) as exc:
            if isinstance(rel, str):
                rollback_errors.append(rel)
            else:
                rollback_errors.append("<invalid-journal-entry>")
            entry["rollback_error"] = str(exc)
            _write_json(process / "commit-journal.json", journal)
    journal.update({
        "status": "RECOVERY_REQUIRED" if rollback_errors else "ROLLED_BACK",
        "rollback_errors": rollback_errors, "finished_at": _now(),
    })
    _write_json(process / "commit-journal.json", journal)
    return rollback_errors


def _finish_committed_journal(process: Path, state: dict[str, Any], journal: dict[str, Any]) -> None:
    repo = Path(state["repo_root"])
    original = _read_json(process / "snapshots" / "original.json")
    expected = dict(original)
    for entry in journal.get("entries", []):
        if not isinstance(entry.get("path"), str) or not isinstance(entry.get("after_sha256"), str):
            _finalize(process, state, "RECOVERY_REQUIRED", "RECOVERY_REQUIRED")
            return
        expected[entry["path"]] = entry["after_sha256"]
    if _scan_docs(repo, state["app"]) != expected:
        _finalize(process, state, "RECOVERY_REQUIRED", "RECOVERY_REQUIRED")
        return
    contract = _approved_contract(process, state)
    if _run_live_postcheck(repo, state, contract)["status"] != "PASS":
        _finalize(process, state, "RECOVERY_REQUIRED", "RECOVERY_REQUIRED")
        return
    state["changed_paths"] = [entry["path"] for entry in journal["entries"]]
    state["commit_manifest"] = journal["entries"]
    _write_json(process / "commit-manifest.json", {
        "contract_version": CONTRACT_VERSION, "entries": journal["entries"], "status": "COMMITTED",
    })
    state["stage_results"]["commit"] = {"owner": "runner", "status": "done", "result": "PASS"}
    _finalize(process, state, "DONE", "PASS")


def _validate_commit_journal(process: Path, state: dict[str, Any], journal: dict[str, Any]) -> None:
    if journal.get("contract_sha256") != state.get("approved_contract_sha256"):
        raise ContractError("Commit journal contract hash mismatch", "JOURNAL_INVALID")
    if journal.get("status") not in {
        "PREPARING", "PREPARED", "COMMITTING", "ROLLING_BACK",
        "ROLLED_BACK", "COMMITTED", "RECOVERY_REQUIRED",
    } or not isinstance(journal.get("entries"), list):
        raise ContractError("Commit journal status or entries are invalid", "JOURNAL_INVALID")
    contract = _approved_contract(process, state)
    original = _read_json(process / "snapshots" / "original.json")
    actions = {action["path"]: action for action in contract["actions"]}
    entries = journal["entries"]
    if len(entries) != len(actions):
        raise ContractError("Commit journal action coverage mismatch", "JOURNAL_INVALID")
    repo = Path(state["repo_root"])
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ContractError("Commit journal entry is invalid", "JOURNAL_INVALID")
        rel = entry["path"]
        action = actions.get(rel)
        target = _resolve_under(repo, rel)
        expected_temp = _repo_rel(repo, target.with_name(f".{target.name}.{state['run_id']}.tmp"))
        if (
            action is None or rel in seen
            or entry.get("action") != action["action"]
            or entry.get("before_sha256") != original.get(rel)
            or entry.get("after_sha256") != state.get("staged_hashes", {}).get(rel)
            or entry.get("backup_path") != f"commit-backup/{rel}"
            or entry.get("temp_path") != expected_temp
            or entry.get("phase") not in {"PREPARING", "PREPARED", "REPLACING", "APPLIED", "ROLLED_BACK"}
        ):
            raise ContractError(f"Commit journal entry mismatch: {rel}", "JOURNAL_INVALID")
        seen.add(rel)


def _recover_interrupted_commit(process: Path, state: dict[str, Any]) -> None:
    journal_path = process / "commit-journal.json"
    if not journal_path.is_file():
        _commit(process, state)
        return
    journal = _read_json(journal_path)
    try:
        _validate_commit_journal(process, state, journal)
    except ContractError:
        _finalize(process, state, "RECOVERY_REQUIRED", "RECOVERY_REQUIRED")
        return
    status = journal.get("status")
    if status == "COMMITTED":
        _finish_committed_journal(process, state, journal)
        return
    if status == "RECOVERY_REQUIRED":
        _finalize(process, state, "RECOVERY_REQUIRED", "RECOVERY_REQUIRED")
        return
    repo = Path(state["repo_root"])
    lock = repo / ".process" / f".ssot-write-{state['app']}.commit.lock"
    try:
        with _advisory_file_lock(lock, "COMMIT_LOCKED"):
            errors = _rollback_journal(process, state, journal, "interrupted commit recovered on resume")
    except ContractError as exc:
        if exc.code != "COMMIT_LOCKED":
            raise
        state["commit_recovery_pending"] = True
        state["last_result"] = "pending"
        state["last_failure_class"] = "COMMIT_LOCKED"
        return
    terminal = "RECOVERY_REQUIRED" if errors else "COMMIT_FAILED_ROLLED_BACK"
    _finalize(process, state, terminal, terminal)


def _replace_commit_target(temp: Path, target: Path) -> None:
    """Narrow fault-injection seam for journaled multi-file commit tests."""
    os.replace(temp, target)


def _finalize(process: Path, state: dict[str, Any], terminal: str, audit: str) -> None:
    if terminal not in TERMINAL_RESULTS:
        raise ContractError(f"Invalid terminal result: {terminal}", "TERMINAL_RESULT")
    paths = state.get("changed_paths", []) if terminal == "DONE" else []
    next_step = "work-packet-write" if terminal in {"DONE", "NOOP"} else (
        "task-write" if terminal == "REWRITE_REQUIRED" else "STOP"
    )
    report = "\n".join((
        "UPDATE/CREATE " + (", ".join(paths) if paths else "none"),
        f"Process: {state['process_rel'].rstrip('/')}/",
        f"Audit: {audit}",
        f"Next: {next_step}",
    )) + "\n"
    _write_text(process / "final-report.txt", report)
    state.update({
        "run_status": "terminal", "terminal_result": terminal,
        "current_stage": "done", "next_role": None, "next_mode": None,
        "last_result": audit, "last_failure_class": "NONE" if audit == "PASS" else audit,
        "final_audit": audit, "final_next": next_step,
        "commit_recovery_pending": False,
    })
    state["stage_results"]["finalize"] = {"owner": "runner", "status": "done", "result": terminal}


def _record_rejection(process: Path, state: dict[str, Any], result_path: Path, error: ContractError) -> None:
    dispatch = state.get("active_dispatch") or {}
    dispatch_id = dispatch.get("dispatch_id", "unknown")
    counts = state.setdefault("rejection_counts", {})
    attempt = int(counts.get(dispatch_id, 0)) + 1
    counts[dispatch_id] = attempt
    rejected = process / "results" / "rejected"
    rejected.mkdir(parents=True, exist_ok=True)
    if result_path.is_file():
        _atomic_write_bytes(rejected / f"{dispatch_id}-attempt-{attempt}.json", result_path.read_bytes())
    metadata = {
        "contract_version": CONTRACT_VERSION, "dispatch_id": dispatch_id,
        "attempt": attempt, "error_code": error.code, "message": str(error), "rejected_at": _now(),
    }
    _write_json(rejected / f"{dispatch_id}-attempt-{attempt}-error.json", metadata)
    state["last_rejection"] = metadata
    if state.get("active_dispatch"):
        state["active_dispatch"]["last_rejection"] = metadata
    if error.code == "STALE_DISPATCH":
        state["active_dispatch"] = None
    if attempt >= MAX_REJECTIONS:
        _finalize(process, state, "CONTRACT_BLOCKED", "CONTRACT_BLOCKED")
    _save_state(process, state, {"event": "result_rejected", "stage": dispatch.get("stage"), "result": "REJECTED", "dispatch_id": dispatch_id, "error_code": error.code})
    if state.get("active_dispatch") and state.get("run_status") != "terminal":
        _snapshot_control(process, state["active_dispatch"], state)


def accept_result(process: Path, result_path: Path) -> dict[str, Any]:
    process = _process_path(process)
    with _process_lock(process):
        state = _load_state(process)
        dispatch = state.get("active_dispatch")
        if not dispatch:
            raise ContractError("No active dispatch", "NO_ACTIVE_DISPATCH")
        resolved_result = result_path.resolve()
        try:
            expected_result = _resolve_under(process, dispatch["result_path"])
            if Path(dispatch["result_path"]).is_symlink() or resolved_result != expected_result:
                raise ContractError("Result path does not match dispatched result_path", "RESULT_PATH_MISMATCH")
            result = _read_json(resolved_result)
            _validate_result(result, dispatch)
            _validate_dispatch_freshness(dispatch)
            live_changes = _protected_changes(process, state, dispatch["snapshot_label"])
            if live_changes:
                raise ContractError(f"Role modified protected live files: {live_changes}", "LIVE_WRITE_PROHIBITED")
            control_changes = _control_changes(process, dispatch, state)
            if control_changes:
                raise ContractError(f"Role modified runner control files: {control_changes}", "PROCESS_TAMPERED")
            artifact = _resolve_under(Path(state["repo_root"]), result["artifact"])
            expected_artifact = _resolve_under(process, dispatch["artifact"])
            if artifact.is_symlink() or artifact.resolve() != expected_artifact or not artifact.is_file():
                raise ContractError("Result artifact does not match dispatch", "ARTIFACT_MISMATCH")
            if result["role"] == "thinker":
                _accept_thinker(process, state, result, dispatch)
            elif result["role"] == "plan_critic":
                _accept_plan_critic(process, state, result, dispatch)
            elif result["role"] == "editor":
                _accept_editor(process, state, result, dispatch)
            else:
                _accept_outcome(process, state, result, dispatch)
            _receipt(process, state, result, dispatch)
            state["active_dispatch"] = None
            if state["run_status"] != "terminal":
                state["last_result"] = result["status"]
                state["last_failure_class"] = result["failure_class"]
            _save_state(process, state, {"event": "result", "stage": result["stage"], "result": result["status"], "dispatch_id": result["dispatch_id"]})
            if state["run_status"] == "committing":
                _commit(process, state)
                _save_state(process, state, {
                    "event": "commit", "stage": "commit",
                    "result": state.get("terminal_result") or "pending",
                })
            return {"action": "accepted", "status": result["status"], "process": str(process)}
        except ContractError as exc:
            _record_rejection(process, state, resolved_result, exc)
            raise


def resolve_block(process: Path, conflict_id: str, answer: str | None = None, choice: str | None = None) -> dict[str, Any]:
    process = _process_path(process)
    with _process_lock(process):
        state = _load_state(process)
        if state["run_status"] != "waiting_user" or conflict_id != state["blocking_question_id"]:
            raise ContractError("Conflict does not match blocked state", "CONFLICT_MISMATCH")
        response = (choice or answer or "").strip()
        if not response:
            raise ContractError("A non-empty conflict answer is required", "CONFLICT_ANSWER_REQUIRED")
        kind = state["blocking_kind"]
        resume = state["resume_after_block"] or {}
        approving_risk = kind == "risk_approval" and response.upper() in {"APPROVE", "YES", "Y", "승인", "진행"}
        if approving_risk:
            if resume.get("proposal_sha256") != state.get("proposal_sha256"):
                raise ContractError("Approval is stale for the current proposal", "STALE_APPROVAL")
            _read_bound_json(
                Path(state["proposal_path"]), state["proposal_sha256"], "STALE_APPROVAL"
            )
            _read_bound_json(
                Path(state["critique_path"]), state["critique_sha256"], "STALE_APPROVAL"
            )
        decisions = _read_json(process / "decision.json")
        decisions["decisions"].append({
            "conflict_id": conflict_id, "question": state["blocking_question"],
            "answer": response, "contract_sha256": state.get("proposal_sha256"), "resolved_at": _now(),
        })
        _write_json(process / "decision.json", decisions)
        state.update({
            "run_status": "running", "blocking_question_id": None,
            "blocking_question": None, "blocking_kind": None,
            "resume_after_block": None, "active_dispatch": None,
        })
        if kind == "risk_approval":
            if not approving_risk:
                _finalize(process, state, "USER_REJECTED", "USER_REJECTED")
            else:
                _freeze_contract(process, state)
        else:
            state.update({
                "current_stage": resume.get("stage", "think"),
                "next_role": resume.get("role", "thinker"),
                "next_mode": resume.get("mode", "revise"),
            })
        _save_state(process, state, {"event": "resolve", "stage": state["current_stage"], "result": "READY", "conflict_id": conflict_id})
        return {"action": "resolved", "process": str(process)}


def status(process: Path) -> dict[str, Any]:
    return _load_state(_process_path(process))


def render(process: Path) -> dict[str, Any]:
    process = _process_path(process)
    with _process_lock(process):
        state = _load_state(process)
        _render_views(process, state)
    return {"action": "rendered", "process": str(process)}


def report(process: Path) -> str:
    process = _process_path(process)
    state = _load_state(process)
    if state["run_status"] != "terminal":
        raise ContractError("Run is not terminal", "RUN_NOT_TERMINAL")
    report_path = process / "final-report.txt"
    if not report_path.is_file():
        raise ContractError("final-report.txt missing", "REPORT_MISSING")
    if state["terminal_result"] == "DONE":
        manifest = _read_json(process / "commit-manifest.json")
        repo = Path(state["repo_root"])
        for entry in manifest["entries"]:
            target = repo / entry["path"]
            if not target.is_file() or _sha256(target) != entry["after_sha256"]:
                raise ContractError(f"Committed output changed after finalization: {entry['path']}", "REPORT_OUTPUT_TAMPERED")
    expected = "\n".join((
        "UPDATE/CREATE " + (
            ", ".join(state.get("changed_paths", []))
            if state["terminal_result"] == "DONE" and state.get("changed_paths") else "none"
        ),
        f"Process: {state['process_rel'].rstrip('/')}/",
        f"Audit: {state.get('final_audit')}",
        f"Next: {state.get('final_next')}",
    ))
    actual = report_path.read_text(encoding="utf-8").rstrip("\n")
    if actual != expected:
        raise ContractError("final-report.txt does not match terminal state", "REPORT_TAMPERED")
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
    init.add_argument("--repo", type=Path, required=True)
    init.add_argument("--task", required=True)
    init.add_argument("--app", required=True)
    init.add_argument("--process", type=Path)
    for name in ("next", "status", "render", "report"):
        command = sub.add_parser(name)
        command.add_argument("--process", type=Path, required=True)
    accept = sub.add_parser("accept-result")
    accept.add_argument("--process", type=Path, required=True)
    accept.add_argument("--result", type=Path, required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--process", type=Path, required=True)
    resolve.add_argument("--conflict", required=True)
    resolve.add_argument("--answer")
    resolve.add_argument("--choice")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            process = args.process
            if process is not None and not process.is_absolute():
                process = args.repo / process
            _emit_json(init_run(args.repo, args.task, args.app, process))
        elif args.cmd == "next":
            _emit_json(next_action(args.process))
        elif args.cmd == "accept-result":
            _emit_json(accept_result(args.process, args.result))
        elif args.cmd == "resolve":
            _emit_json(resolve_block(args.process, args.conflict, args.answer, args.choice))
        elif args.cmd == "status":
            _emit_json(status(args.process))
        elif args.cmd == "render":
            _emit_json(render(args.process))
        elif args.cmd == "report":
            print(report(args.process))
    except ContractError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
