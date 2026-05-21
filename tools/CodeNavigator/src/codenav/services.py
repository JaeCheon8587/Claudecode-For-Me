"""Shared service layer for CLI and web UI."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from codenav import indexer, parser_cs, search as search_mod, store

_EXCLUDE_DIRS = {
    ".cache",
    ".claire",
    ".codenav",
    ".git",
    ".pytest_cache",
    ".worktrees",
    "bin",
    "obj",
    "node_modules",
    "packages",
    "TestResults",
}


def collect_cs_files(root: Path) -> list[Path]:
    results = []
    for path in root.rglob("*.cs"):
        if any(part in _EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name.endswith((".g.cs", ".AssemblyAttributes.cs", ".AssemblyInfo.cs")):
            continue
        results.append(path)
    return results


def detect_solution(root: Path) -> str:
    slns = sorted(root.glob("*.sln"), key=lambda path: path.name.lower())
    return slns[0].stem if slns else ""


def detect_solution_for_file(root: Path, file: Path) -> str:
    """Return the closest ancestor .sln name for a source file."""
    root_resolved = root.resolve()
    current = file.resolve().parent

    while True:
        slns = sorted(current.glob("*.sln"), key=lambda path: path.name.lower())
        if slns:
            return slns[0].stem
        if current == root_resolved or current.parent == current:
            break
        current = current.parent

    return detect_solution(root_resolved)


def detect_project(file: Path) -> str:
    for parent in file.parents:
        csproj = list(parent.glob("*.csproj"))
        if csproj:
            return csproj[0].stem
    return ""


def resolve_index_path(root: Path, file: str | Path) -> Path:
    """Resolve a stored index path back to an absolute filesystem path."""
    path = Path(file)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def storage_path(root: Path, file: str | Path) -> str:
    """Return the path format stored in the DB."""
    path = Path(file)
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except (OSError, ValueError):
        return str(file)


def display_path(root: Path, file: str | Path) -> str:
    """Return a root-relative display path when possible."""
    return storage_path(root, file)


def normalize_index_paths(root: Path) -> int:
    """Migrate existing in-root absolute file/folder values to relative storage."""
    conn = store.open_db(root)
    changed = 0
    try:
        rows = conn.execute("SELECT id, file, folder, class_name FROM classes").fetchall()
        for row in rows:
            new_file = storage_path(root, row["file"])
            new_folder = storage_path(root, row["folder"])
            if new_file == row["file"] and new_folder == row["folder"]:
                continue
            duplicate = conn.execute(
                "SELECT id FROM classes WHERE file=? AND class_name=? AND id<>?",
                (new_file, row["class_name"], row["id"]),
            ).fetchone()
            if duplicate:
                store.delete_entry(conn, row["id"])
                changed += 1
                continue
            conn.execute(
                "UPDATE classes SET file=?, folder=? WHERE id=?",
                (new_file, new_folder, row["id"]),
            )
            changed += 1
        conn.commit()
        return changed
    finally:
        conn.close()


def get_status(root: Path) -> dict[str, Any]:
    conn = store.open_db(root)
    try:
        return store.get_stats(conn, root)
    finally:
        conn.close()


def search_index(
    root: Path,
    query: str,
    *,
    limit: int = 10,
    solution: str | None = None,
    project: str | None = None,
    scope: str = "class",
) -> list[dict[str, Any]]:
    conn = store.open_db(root, readonly=True)
    try:
        return search_mod.search(
            conn,
            query,
            limit=limit,
            solution=solution,
            project=project,
            scope=scope,
        )
    finally:
        conn.close()


def run_reindex(
    root: Path,
    *,
    full: bool = False,
    files: list[str] | None = None,
    changed: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    normalized_count = normalize_index_paths(root)
    conn = store.open_db(root)
    deleted_files: list[str] = []
    deleted_count = 0

    if full:
        file_paths = collect_cs_files(root)
        indexed_files = {storage_path(root, path) for path in file_paths}
        stale_indexed_files = conn.execute(
            "SELECT DISTINCT file FROM classes WHERE source_type='auto'"
        ).fetchall()
        for row in stale_indexed_files:
            if row["file"] not in indexed_files:
                deleted_count += store.delete_file(conn, row["file"], source_type="auto")
    elif files:
        file_paths = [Path(item) for item in files]
    elif changed:
        try:
            result_mod = subprocess.run(
                ["git", "diff", "--name-only", "--cached", "--diff-filter=ACMRT"],
                capture_output=True,
                text=True,
                cwd=root,
                check=False,
            )
            file_paths = [root / line for line in result_mod.stdout.splitlines() if line.endswith(".cs")]
            result_del = subprocess.run(
                ["git", "diff", "--name-only", "--cached", "--diff-filter=D"],
                capture_output=True,
                text=True,
                cwd=root,
                check=False,
            )
            deleted_files = [storage_path(root, root / line) for line in result_del.stdout.splitlines() if line.endswith(".cs")]
        except FileNotFoundError as exc:
            conn.close()
            return {"ok": False, "code": 1, "error": str(exc), "message": "git not found"}
    else:
        conn.close()
        return {"ok": False, "code": 1, "message": "Specify --full, --files, or --changed"}

    for deleted_file in deleted_files:
        deleted_count += store.delete_file(conn, deleted_file)

    written = 0
    skipped = 0
    failed_files: list[str] = []
    claude_calls = 0

    for file in file_paths:
        file_resolved = resolve_index_path(root, file)
        if not file_resolved.exists():
            continue
        solution = detect_solution_for_file(root, file_resolved)
        project = detect_project(file_resolved)
        classes = parser_cs.parse_cs_file(file_resolved, solution=solution, project=project)

        current_names = {cls.class_name for cls in classes}
        file_str = storage_path(root, file_resolved)
        existing = conn.execute("SELECT class_name FROM classes WHERE file=?", (file_str,)).fetchall()
        for row in existing:
            if row["class_name"] not in current_names:
                store.delete_file(conn, file_str)
                break

        if not classes:
            continue

        entries = parser_cs.classes_to_index_entries(classes, file_resolved, solution=solution, project=project)
        for entry in entries:
            entry["file"] = storage_path(root, entry["file"])
            entry["folder"] = storage_path(root, entry["folder"])
        entries, calls = indexer.enrich_entries(entries, verbose=verbose)
        claude_calls += calls

        for entry in entries:
            if entry.get("_ai_failed"):
                entry["stale"] = 1
                entry.setdefault("description", "")
                store.upsert_class(conn, entry)
                failed_files.append(entry["file"])
                continue
            if store.upsert_class(conn, entry):
                written += 1
            else:
                skipped += 1

    conn.close()
    code = 0 if not failed_files else 2
    return {
        "ok": code in (0, 2),
        "code": code,
        "written": written,
        "skipped": skipped,
        "stale_count": len(failed_files),
        "failed_files": failed_files,
        "claude_calls": claude_calls,
        "deleted_count": deleted_count,
        "normalized_count": normalized_count,
        "message": (
            f"Reindex done: {written} written, {skipped} skipped (unchanged), "
            f"{len(failed_files)} stale. Claude calls: {claude_calls}."
        ),
    }


def delete_file_index(root: Path, file: str, *, confirm: bool) -> dict[str, Any]:
    root = root.resolve()
    normalize_index_paths(root)
    resolved = storage_path(root, resolve_index_path(root, file))
    conn = store.open_db(root)
    try:
        count = store.count_file_classes(conn, resolved)
        if count == 0:
            return {"file": resolved, "deleted": 0, "dry_run": not confirm}
        if not confirm:
            return {"file": resolved, "would_delete": count, "dry_run": True}
        deleted = store.delete_file(conn, resolved)
        return {"file": resolved, "deleted": deleted, "dry_run": False}
    finally:
        conn.close()


def list_entries(root: Path, **filters: Any) -> list[dict[str, Any]]:
    conn = store.open_db(root)
    try:
        return store.list_entries(conn, **filters)
    finally:
        conn.close()


def get_entry(root: Path, entry_id: int) -> dict[str, Any] | None:
    conn = store.open_db(root)
    try:
        return store.get_entry(conn, entry_id)
    finally:
        conn.close()


def distinct_filter_values(root: Path) -> dict[str, list[str]]:
    conn = store.open_db(root)
    try:
        return {
            "solution": store.distinct_values(conn, "solution"),
            "project": store.distinct_values(conn, "project"),
            "namespace": store.distinct_values(conn, "namespace"),
            "kind": store.distinct_values(conn, "kind"),
            "source_type": store.distinct_values(conn, "source_type"),
        }
    finally:
        conn.close()


def parse_tags_text(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.replace("\n", ",").split(",")]
    return [part for part in parts if part]


def save_manual_metadata(root: Path, entry_id: int, *, description: str, tags_text: str) -> bool:
    conn = store.open_db(root)
    try:
        return store.save_manual_metadata(conn, entry_id, description=description.strip(), tags=parse_tags_text(tags_text))
    finally:
        conn.close()


def create_manual_entry(root: Path, payload: dict[str, str]) -> int:
    conn = store.open_db(root)
    try:
        raw_file = payload["file"].strip()
        file_path = Path(raw_file)
        resolved_file = file_path.resolve() if file_path.is_absolute() else (root / file_path).resolve()
        raw_folder = payload.get("folder", "").strip()
        resolved_folder = Path(raw_folder).resolve() if raw_folder and Path(raw_folder).is_absolute() else ((root / raw_folder).resolve() if raw_folder else resolved_file.parent)
        return store.create_manual_entry(
            conn,
            {
                "solution": payload.get("solution", "").strip(),
                "project": payload.get("project", "").strip(),
                "namespace": payload.get("namespace", "").strip(),
                "folder": storage_path(root, resolved_folder),
                "file": storage_path(root, resolved_file),
                "class_name": payload.get("class_name", "").strip(),
                "kind": payload.get("kind", "class").strip() or "class",
                "description": payload.get("description", "").strip(),
                "tags": parse_tags_text(payload.get("tags", "")),
                "methods": [],
            },
        )
    finally:
        conn.close()


def delete_manual_entry(root: Path, entry_id: int) -> bool:
    conn = store.open_db(root)
    try:
        entry = store.get_entry(conn, entry_id)
        if not entry or entry["source_type"] != "manual":
            return False
        return store.delete_entry(conn, entry_id)
    finally:
        conn.close()
