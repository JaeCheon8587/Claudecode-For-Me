"""AI-driven `// ---` frontmatter block generator for C# class declarations.

Scans .cs files under root, finds classes without XML doc and without existing
frontmatter, asks Claude CLI to generate description + tags for each, then
inserts a `// ---` YAML block directly above the class declaration.

Safety:
- Defaults to dry-run; --apply required to write.
- Refuses to run on dirty git working tree unless --allow-dirty.
- Per-invocation cap via --limit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import parser_cs

_SKILL_PATH = (
    Path(__file__).parent.parent.parent
    / ".claude"
    / "skills"
    / "codenav-frontmatter-gen"
    / "SKILL.md"
)
_MOCK_ENV = "CODENAV_FRONTMATTER_MOCK"
_BATCH_SIZE = 10
_CLAUDE_TIMEOUT = 120

_CLASS_DECL_RE = re.compile(
    r"""
    (?P<indent>[ \t]*)
    (?:(?:public|internal|protected|private|static|abstract|sealed|partial)[ \t]+)*
    (?:class|struct|interface|record)[ \t]+
    (?P<name>\w+)
    """,
    re.VERBOSE,
)


@dataclass
class Target:
    file: Path
    class_name: str
    namespace: str
    kind: str
    decl_line_no: int  # 1-based
    indent: str
    method_names: list[str]


@dataclass
class GeneratedMetadata:
    description: str
    tags: list[str]


@dataclass
class GenResult:
    scanned_files: int = 0
    candidates: int = 0
    generated: int = 0
    written: int = 0
    skipped_files: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def collect_targets(root: Path, limit: int) -> list[Target]:
    """Find classes lacking both XML doc and existing frontmatter, up to limit."""
    targets: list[Target] = []
    cs_files = sorted(root.rglob("*.cs"))
    for path in cs_files:
        if len(targets) >= limit:
            break
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        existing_frontmatter = {
            m.group(2) for m in parser_cs._FRONTMATTER_RE.finditer(text)
        }
        existing_xml = {
            m.group(2)
            for m in re.finditer(
                r"((?:[ \t]*///[^\n]*\n)+)\s*(?:(?:public|internal|protected|private|static|abstract|sealed|partial)\s+)*(?:class|struct|interface|record)\s+(\w+)",
                text,
                re.MULTILINE,
            )
        }
        classes = parser_cs.parse_cs_file(path)
        if not classes:
            continue
        for cls in classes:
            if len(targets) >= limit:
                break
            if cls.class_name in existing_frontmatter or cls.class_name in existing_xml:
                continue
            decl = _find_class_decl_line(text, cls.class_name)
            if decl is None:
                continue
            line_no, indent = decl
            targets.append(
                Target(
                    file=path,
                    class_name=cls.class_name,
                    namespace=cls.namespace,
                    kind=cls.kind,
                    decl_line_no=line_no,
                    indent=indent,
                    method_names=[m.name for m in cls.methods[:15]],
                )
            )
    return targets


def _find_class_decl_line(text: str, class_name: str) -> tuple[int, str] | None:
    """Return (1-based line number, leading indent) of the class declaration.

    Uses search() rather than match() so single-line files with multiple constructs
    (e.g. `namespace N { public class F { } }`) are still detected. Indent is taken
    from the start of the matched class declaration substring, not the start of line.
    """
    for line_no, raw in enumerate(text.splitlines(), start=1):
        m = _CLASS_DECL_RE.search(raw)
        if m and m.group("name") == class_name:
            return line_no, m.group("indent")
    return None


def _claude_exe() -> str | None:
    return shutil.which("claude")


def generate_batch(targets: list[Target]) -> dict[tuple[Path, str], GeneratedMetadata]:
    """Call Claude CLI with batched class info. Returns map keyed by (file, class_name)."""
    mock = os.environ.get(_MOCK_ENV)
    if mock == "fail":
        return {}
    if mock == "stub":
        return {
            (t.file, t.class_name): GeneratedMetadata(
                description=f"{t.class_name} (stub)",
                tags=[t.kind, t.class_name.lower()],
            )
            for t in targets
        }

    exe = _claude_exe()
    if exe is None or not _SKILL_PATH.exists():
        return {}

    results: dict[tuple[Path, str], GeneratedMetadata] = {}
    for chunk in _chunks(targets, _BATCH_SIZE):
        payload = _build_prompt(chunk)
        parsed = _call_claude(exe, payload)
        if not parsed:
            continue
        for item in parsed.get("classes", []):
            file_str = item.get("file")
            name = item.get("class_name")
            description = item.get("description") or ""
            tags = item.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]
            if not file_str or not name:
                continue
            file_key = Path(file_str)
            results[(file_key, name)] = GeneratedMetadata(
                description=description, tags=[str(t) for t in tags]
            )
    return results


def _chunks(items: list[Target], size: int) -> Iterable[list[Target]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _build_prompt(chunk: list[Target]) -> str:
    payload = {
        "classes": [
            {
                "file": str(t.file),
                "class_name": t.class_name,
                "namespace": t.namespace,
                "kind": t.kind,
                "methods": t.method_names,
            }
            for t in chunk
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _call_claude(exe: str, payload: str) -> dict | None:
    cmd = [
        exe,
        "-p",
        "--output-format",
        "json",
        "--append-system-prompt-file",
        str(_SKILL_PATH),
    ]
    try:
        result = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_CLAUDE_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    try:
        outer = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return None
    inner = outer.get("result") or outer.get("response", "")
    if inner.startswith("```"):
        lines = inner.splitlines()
        inner = "\n".join(lines[1:-1] if lines and lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(inner)
    except json.JSONDecodeError:
        return None


def render_frontmatter(indent: str, description: str, tags: list[str]) -> list[str]:
    """Build the `// ---` block lines (without trailing newline) using the given indent."""
    safe_desc = description.replace("\n", " ").replace("\r", " ").strip()
    lines = [f"{indent}// ---", f"{indent}// description: {safe_desc}"]
    if tags:
        tag_str = ", ".join(str(t).strip() for t in tags if str(t).strip())
        lines.append(f"{indent}// tags: [{tag_str}]")
    lines.append(f"{indent}// ---")
    return lines


def insert_frontmatter_into_file(
    file: Path, insertions: list[tuple[int, str, str, list[str]]]
) -> None:
    """Insert frontmatter blocks into a single file.

    insertions: list of (decl_line_no_1based, indent, description, tags).
    Multiple insertions in one file are processed bottom-up so earlier line
    numbers stay valid as later lines shift down.
    """
    raw = file.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)

    for line_no, indent, description, tags in sorted(insertions, key=lambda x: x[0], reverse=True):
        block = render_frontmatter(indent, description, tags)
        insert_at = line_no - 1
        lines[insert_at:insert_at] = block

    out = newline.join(lines).encode("utf-8")
    if has_bom:
        out = b"\xef\xbb\xbf" + out
    file.write_bytes(out)


def is_git_clean(root: Path) -> bool:
    """Return True if `git status --porcelain` is empty under root."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and not result.stdout.strip()


def run(
    root: Path,
    *,
    limit: int = 50,
    apply: bool = False,
    allow_dirty: bool = False,
    verbose: bool = False,
) -> GenResult:
    """Top-level orchestration entry point."""
    root = root.resolve()
    result = GenResult()

    if not allow_dirty and not is_git_clean(root):
        raise RuntimeError(
            "git working tree is dirty. Commit/stash first or pass --allow-dirty."
        )

    targets = collect_targets(root, limit)
    result.candidates = len(targets)
    seen_files = {t.file for t in targets}
    result.scanned_files = len(seen_files)

    if not targets:
        return result

    metadata = generate_batch(targets)
    result.generated = len(metadata)

    if not apply:
        if verbose:
            for t in targets:
                key = (t.file, t.class_name)
                meta = metadata.get(key)
                if meta:
                    print(f"[DRY] {t.file}:{t.decl_line_no} {t.class_name} → {meta.description[:60]}", file=sys.stderr)
                else:
                    print(f"[DRY-FAIL] {t.file}:{t.decl_line_no} {t.class_name} (no metadata)", file=sys.stderr)
        return result

    by_file: dict[Path, list[tuple[int, str, str, list[str]]]] = {}
    for t in targets:
        meta = metadata.get((t.file, t.class_name))
        if not meta:
            result.failures.append(f"{t.file}:{t.class_name}")
            continue
        by_file.setdefault(t.file, []).append(
            (t.decl_line_no, t.indent, meta.description, meta.tags)
        )

    for file, insertions in by_file.items():
        try:
            insert_frontmatter_into_file(file, insertions)
            result.written += len(insertions)
        except OSError as exc:
            result.skipped_files.append(f"{file}: {exc}")
    return result
