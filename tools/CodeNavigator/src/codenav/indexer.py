"""AI-driven description+tags generator via Claude Code CLI subprocess."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_SKILL_PATH = Path(__file__).parent.parent.parent / ".claude" / "skills" / "codenav-indexer" / "SKILL.md"
_MOCK_ENV = "CODENAV_INDEXER_MOCK"
_MAX_RETRIES = 1


def _claude_exe() -> str | None:
    """Resolve claude binary path (handles Windows .cmd shim)."""
    return shutil.which("claude")


def _call_claude(class_info: str, retries: int = _MAX_RETRIES) -> dict[str, Any] | None:
    if os.environ.get(_MOCK_ENV) == "fail":
        return None

    exe = _claude_exe()
    if exe is None:
        return None

    if not _SKILL_PATH.exists():
        return None

    cmd = [
        exe,
        "-p",
        "--output-format", "json",
        "--append-system-prompt-file", str(_SKILL_PATH),
    ]
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                input=class_info,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
            )
            outer = json.loads(result.stdout.strip())
            inner_text = outer.get("result") or outer.get("response", "")
            # Strip markdown code fences if model wrapped output
            if inner_text.startswith("```"):
                lines = inner_text.splitlines()
                inner_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            parsed = json.loads(inner_text)
            if "description" in parsed and "tags" in parsed:
                return parsed
        except FileNotFoundError:
            return None  # binary disappeared mid-run; no retry
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            if attempt < retries:
                continue
    return None


def generate_description(
    class_name: str,
    namespace: str,
    methods: list[dict],
    xml_summary: str = "",
    file: str = "",
) -> dict[str, Any] | None:
    """Call Claude CLI to generate description + tags for a single class."""
    method_names = ", ".join(m["name"] for m in methods[:15])
    info_lines = [
        f"Class: {class_name}",
        f"Namespace: {namespace}",
        f"File: {file}",
    ]
    if xml_summary:
        info_lines.append(f"XML Summary: {xml_summary}")
    if method_names:
        info_lines.append(f"Methods: {method_names}")

    return _call_claude("\n".join(info_lines))


def enrich_entries(
    entries: list[dict[str, Any]],
    *,
    verbose: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Fill description+tags for entries that have no description yet. Returns (entries, claude_call_count)."""
    call_count = 0
    for entry in entries:
        if entry.get("description"):
            continue
        result = generate_description(
            entry["class_name"],
            entry.get("namespace", ""),
            entry.get("methods", []),
            entry.get("xml_summary", ""),
            entry.get("file", ""),
        )
        call_count += 1
        if result:
            tags = result.get("tags", entry.get("tags", []))
            if not isinstance(tags, list):
                tags = [str(tags)]
            entry["description"] = result.get("description", "")
            entry["tags"] = tags
            if verbose:
                print(f"  [AI] {entry['class_name']}: {entry['description'][:60]}...", file=sys.stderr)
        else:
            if verbose:
                print(f"  [STALE] {entry['class_name']}: AI call failed", file=sys.stderr)
            entry["_ai_failed"] = True
    return entries, call_count
