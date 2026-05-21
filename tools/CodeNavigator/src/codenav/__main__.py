"""codenav CLI entry point.

Commands:
    codenav status
    codenav search <query> [--limit N] [--scope class|method] [--solution S] [--project P] [--json]
    codenav reindex [--files f1 f2 ...] [--full] [--root DIR] [--verbose]
    codenav delete --file <path> [--yes] [--json]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from codenav import store, search as search_mod, parser_cs, indexer


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    conn = store.open_db(root)
    stats = store.get_stats(conn, root)
    print(f"DB      : {stats['db_path']}")
    print(f"Classes : {stats['total_classes']}")
    print(f"Stale   : {stats['stale_classes']}")
    print(f"LastIdx : {stats['last_indexed'] or 'never'}")
    if stats["stale_files"]:
        print("Stale files:")
        for f in stats["stale_files"]:
            print(f"  {f}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    try:
        conn = store.open_db(root, readonly=True)
    except Exception:
        print("No index. Run: codenav reindex --full", file=sys.stderr)
        return 1

    results = search_mod.search(
        conn,
        args.query,
        limit=args.limit,
        solution=args.solution or None,
        project=args.project or None,
        scope=args.scope,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print("No results.")
        for r in results:
            print(f"[{r['score']:.2f}] {r['project'] or r['solution']} / {r['namespace']} / {r['class']}")
            print(f"       {r['file']}")
            print(f"       {r['description']}")
            print(f"       tags: {', '.join(r['tags'])}")
            if args.scope == "method" and r.get("methods"):
                for m in r["methods"][:5]:
                    print(f"         • {m['name']}: {m.get('description','')}")
            print()
    return 0


_EXCLUDE_DIRS = {".codenav", ".git", "bin", "obj", "node_modules", "packages", "TestResults"}


def _collect_cs_files(root: Path) -> list[Path]:
    results = []
    for p in root.rglob("*.cs"):
        if any(part in _EXCLUDE_DIRS for part in p.parts):
            continue
        # Skip generated files
        if p.name.endswith((".g.cs", ".AssemblyAttributes.cs", ".AssemblyInfo.cs")):
            continue
        results.append(p)
    return results


def _detect_solution(root: Path) -> str:
    slns = list(root.glob("*.sln")) + list(root.glob("**/*.sln"))
    return slns[0].stem if slns else ""


def _detect_project(file: Path) -> str:
    for p in file.parents:
        csproj = list(p.glob("*.csproj"))
        if csproj:
            return csproj[0].stem
    return ""


def cmd_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    conn = store.open_db(root)
    solution = _detect_solution(root)
    verbose = args.verbose

    deleted_files: list[str] = []

    if args.full:
        files = _collect_cs_files(root)
        if verbose:
            print(f"Full reindex: {len(files)} .cs files found", file=sys.stderr)
    elif args.files:
        files = [Path(f) for f in args.files]
    elif args.changed:
        try:
            result_mod = subprocess.run(
                ["git", "diff", "--name-only", "--cached", "--diff-filter=ACMRT"],
                capture_output=True, text=True, cwd=root,
            )
            files = [root / f for f in result_mod.stdout.splitlines() if f.endswith(".cs")]
            result_del = subprocess.run(
                ["git", "diff", "--name-only", "--cached", "--diff-filter=D"],
                capture_output=True, text=True, cwd=root,
            )
            deleted_files = [str((root / f).resolve()) for f in result_del.stdout.splitlines() if f.endswith(".cs")]
            if verbose:
                print(f"Changed (staged): {len(files)} .cs files, {len(deleted_files)} deleted", file=sys.stderr)
        except FileNotFoundError:
            print("git not found", file=sys.stderr)
            return 1
    else:
        print("Specify --full, --files, or --changed", file=sys.stderr)
        return 1

    # Remove deleted files from index
    deleted_count = 0
    for df in deleted_files:
        deleted_count += store.delete_file(conn, df)
    if deleted_count and verbose:
        print(f"  [DELETE] removed {deleted_count} classes from deleted files", file=sys.stderr)

    written = 0
    skipped = 0
    failed_files: list[str] = []
    claude_calls = 0

    for file in files:
        file_resolved = file.resolve()
        if not file_resolved.exists():
            if verbose:
                print(f"  [SKIP] not found: {file}", file=sys.stderr)
            continue
        project = _detect_project(file_resolved)
        classes = parser_cs.parse_cs_file(file_resolved, solution=solution, project=project)

        # Remove orphaned classes (class renamed/deleted within the file)
        current_names = {c.class_name for c in classes}
        file_str = str(file_resolved)
        existing = conn.execute(
            "SELECT class_name FROM classes WHERE file=?", (file_str,)
        ).fetchall()
        for row in existing:
            if row["class_name"] not in current_names:
                store.delete_file(conn, file_str)
                break  # delete_file removes all; re-insert all classes below

        if not classes:
            continue
        entries = parser_cs.classes_to_index_entries(classes, file_resolved, solution=solution, project=project)
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

    print(
        f"Reindex done: {written} written, {skipped} skipped (unchanged), "
        f"{len(failed_files)} stale. Claude calls: {claude_calls}.",
        file=sys.stderr,
    )
    return 0 if not failed_files else 2


def cmd_delete(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    file = str(Path(args.file).resolve())
    conn = store.open_db(root)
    try:
        n = store.count_file_classes(conn, file)
        if n == 0:
            if args.json:
                print(json.dumps({"file": file, "deleted": 0, "dry_run": not args.yes}))
            else:
                print(f"No indexed classes for file: {file}")
            return 0
        if not args.yes:
            if args.json:
                print(json.dumps({"file": file, "would_delete": n, "dry_run": True}))
            else:
                print(f"[dry-run] Would delete {n} class(es) for {file}. Re-run with --yes to confirm.")
            return 0
        deleted = store.delete_file(conn, file)
        if args.json:
            print(json.dumps({"file": file, "deleted": deleted, "dry_run": False}))
        else:
            print(f"Deleted {deleted} class(es) for {file}")
        return 0
    finally:
        conn.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="codenav", description="CodeNavigator CLI")
    parser.add_argument("--root", default="", help="Repo root (default: cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # status
    sub.add_parser("status", help="Show index stats")

    # search
    sp = sub.add_parser("search", help="Search classes by keyword")
    sp.add_argument("query", help="Keyword query (e.g. '데이터 수집')")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--scope", choices=["class", "method"], default="class")
    sp.add_argument("--solution", default="")
    sp.add_argument("--project", default="")
    sp.add_argument("--json", action="store_true", help="Output as JSON array")

    # reindex
    rp = sub.add_parser("reindex", help="Index / update class descriptions")
    rp.add_argument("--full", action="store_true", help="Reindex entire repo")
    rp.add_argument("--files", nargs="+", metavar="FILE", help="Specific files")
    rp.add_argument("--changed", action="store_true", help="Staged .cs files (git diff --cached)")
    rp.add_argument("--verbose", action="store_true")

    # delete
    dp = sub.add_parser("delete", help="Delete indexed classes for a file")
    dp.add_argument("--file", required=True, help="C# file path (absolute or relative to --root)")
    dp.add_argument("--yes", action="store_true", help="Actually delete (default: dry-run)")
    dp.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    dispatch = {"status": cmd_status, "search": cmd_search, "reindex": cmd_reindex, "delete": cmd_delete}
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
