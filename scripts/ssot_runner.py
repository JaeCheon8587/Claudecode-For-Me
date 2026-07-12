#!/usr/bin/env python3
"""Stable CLI entry point for ssot-write runners.

New runs use Contract v8. Existing Contract v5, v6, and v7 processes remain
resumable and are never migrated in place because their state and artifact
contracts differ from v8.
"""

import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from ssot_runner_v8 import *  # noqa: F401,F403
import ssot_runner_v8 as _v8


def _argument(argv: list[str], name: str) -> str | None:
    try:
        return argv[argv.index(name) + 1]
    except (ValueError, IndexError):
        return None


def _process_from_argv(argv: list[str]) -> Path | None:
    value = _argument(argv, "--process")
    if value:
        path = Path(value)
        repo = _argument(argv, "--repo")
        if not path.is_absolute() and repo:
            path = Path(repo) / path
        return path.resolve()
    if argv and argv[0] == "init":
        repo = _argument(argv, "--repo")
        task = _argument(argv, "--task")
        if repo and task:
            return (Path(repo) / ".process" / Path(task).stem).resolve()
    return None


def _implementation(argv: list[str]):
    process = _process_from_argv(argv)
    state_path = process / "state.json" if process else None
    if state_path and state_path.is_file():
        try:
            version = json.loads(state_path.read_text(encoding="utf-8")).get("contract_version")
        except (OSError, json.JSONDecodeError):
            version = None
        if version == 5:
            import ssot_runner_v5 as v5
            return v5
        if version == 6:
            import ssot_runner_v6 as v6
            return v6
        if version == 7:
            import ssot_runner_v7 as v7
            return v7
        if version == 8:
            return _v8
    return _v8


_configure_stdio = _v8._configure_stdio
_emit_json = _v8._emit_json


if __name__ == "__main__":
    implementation = _implementation(sys.argv[1:])
    implementation._configure_stdio()
    raise SystemExit(implementation.main())
