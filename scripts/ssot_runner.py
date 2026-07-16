#!/usr/bin/env python3
"""Legacy-only entry point for Contract v5-v8 ssot-write processes.

New ssot-write runs are orchestrated by the skill and its three named agents.
This module exists only to resume a process whose state.json already declares
an old contract_version. It must never initialize a new process.
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
    raise RuntimeError(
        "LEGACY_RUNNER_REQUIRES_EXISTING_PROCESS: "
        "new ssot-write runs must use the ssot-write skill"
    )


_configure_stdio = _v8._configure_stdio
_emit_json = _v8._emit_json


if __name__ == "__main__":
    try:
        implementation = _implementation(sys.argv[1:])
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    implementation._configure_stdio()
    raise SystemExit(implementation.main())
