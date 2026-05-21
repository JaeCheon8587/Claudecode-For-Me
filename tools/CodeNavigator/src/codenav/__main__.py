"""codenav CLI entry point."""

import argparse
import json
import sys
from pathlib import Path

from codenav import services, app as web_app


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    stats = services.get_status(root)
    print(f"DB      : {stats['db_path']}")
    print(f"Classes : {stats['total_classes']}")
    print(f"Manual  : {stats['manual_classes']}")
    print(f"Stale   : {stats['stale_classes']}")
    print(f"LastIdx : {stats['last_indexed'] or 'never'}")
    if stats["stale_files"]:
        print("Stale files:")
        for file in stats["stale_files"]:
            print(f"  {file}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    try:
        results = services.search_index(
            root,
            args.query,
            limit=args.limit,
            solution=args.solution or None,
            project=args.project or None,
            scope=args.scope,
        )
    except Exception:
        print("No index. Run: codenav reindex --full", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print("No results.")
        return 0
    for result in results:
        print(f"[{result['score']:.2f}] {result['project'] or result['solution']} / {result['namespace']} / {result['class']}")
        print(f"       {result['file']}")
        print(f"       {result['description']}")
        print(f"       tags: {', '.join(result['tags'])}")
        if args.scope == "method" and result.get("methods"):
            for method in result["methods"][:5]:
                print(f"         • {method['name']}: {method.get('description', '')}")
        print()
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    result = services.run_reindex(
        root,
        full=args.full,
        files=args.files,
        changed=args.changed,
        verbose=args.verbose,
    )
    if result.get("deleted_count") and args.verbose:
        print(f"  [DELETE] removed {result['deleted_count']} classes from deleted files", file=sys.stderr)
    print(result["message"], file=sys.stderr)
    if result.get("error"):
        print(result["error"], file=sys.stderr)
    return int(result["code"])


def cmd_delete(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    result = services.delete_file_index(root, args.file, confirm=args.yes)
    if result.get("deleted", 0) == 0 and result.get("would_delete", 0) == 0:
        if args.json:
            print(json.dumps(result))
        else:
            print(f"No indexed classes for file: {result['file']}")
        return 0
    if not args.yes:
        if args.json:
            print(json.dumps(result))
        else:
            print(f"[dry-run] Would delete {result['would_delete']} class(es) for {result['file']}. Re-run with --yes to confirm.")
        return 0
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Deleted {result['deleted']} class(es) for {result['file']}")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    web_app.run_ui_server(root, host=args.host, port=args.port)
    return 0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="codenav", description="CodeNavigator CLI")
    parser.add_argument("--root", default="", help="Repo root (default: cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show index stats")

    sp = sub.add_parser("search", help="Search classes by keyword")
    sp.add_argument("query", help="Keyword query (e.g. '데이터 수집')")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--scope", choices=["class", "method"], default="class")
    sp.add_argument("--solution", default="")
    sp.add_argument("--project", default="")
    sp.add_argument("--json", action="store_true", help="Output as JSON array")

    rp = sub.add_parser("reindex", help="Index / update class descriptions")
    rp.add_argument("--full", action="store_true", help="Reindex entire repo")
    rp.add_argument("--files", nargs="+", metavar="FILE", help="Specific files")
    rp.add_argument("--changed", action="store_true", help="Staged .cs files (git diff --cached)")
    rp.add_argument("--verbose", action="store_true")

    dp = sub.add_parser("delete", help="Delete indexed classes for a file")
    dp.add_argument("--file", required=True, help="C# file path (absolute or relative to --root)")
    dp.add_argument("--yes", action="store_true", help="Actually delete (default: dry-run)")
    dp.add_argument("--json", action="store_true", help="Output as JSON")

    up = sub.add_parser("ui", help="Run local web UI")
    up.add_argument("--host", default="127.0.0.1")
    up.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    dispatch = {
        "status": cmd_status,
        "search": cmd_search,
        "reindex": cmd_reindex,
        "delete": cmd_delete,
        "ui": cmd_ui,
    }
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
