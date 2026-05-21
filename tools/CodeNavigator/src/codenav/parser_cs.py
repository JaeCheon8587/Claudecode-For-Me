"""Regex-based C# class/namespace/method extractor (MVP)."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_NS_RE = re.compile(r"^\s*namespace\s+([\w.]+)", re.MULTILINE)
_CLASS_RE = re.compile(
    r"""
    (?:^|\n)\s*
    (?:(?:public|internal|protected|private|static|abstract|sealed|partial)\s+)*
    (?:class|struct|interface|record)\s+
    (\w+)                       # class name
    (?:\s*<[^>]+>)?             # optional generic params
    (?:\s*:\s*[^\n{]+)?         # optional base / interfaces
    \s*\{
    """,
    re.VERBOSE | re.MULTILINE,
)
_METHOD_RE = re.compile(
    r"""
    (?:^|\n)[ \t]*
    (?:(?:public|private|protected|internal|static|virtual|override|abstract|async|sealed)\s+)+
    (?:[\w<>\[\],\s\.?]+?)\s+  # return type
    (\w+)\s*                    # method name
    \(                          # opening paren
    """,
    re.VERBOSE | re.MULTILINE,
)
_COMMENT_STRIP = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_STRIP = re.compile(r"/\*.*?\*/", re.DOTALL)
_XML_SUMMARY_RE = re.compile(
    r"///\s*<summary>(.*?)</summary>", re.DOTALL | re.IGNORECASE
)
_FRONTMATTER_RE = re.compile(
    r"""
    ^[ \t]*//[ \t]*---[ \t]*\n       # opening marker
    ((?:[ \t]*//[^\n]*\n)+?)         # body lines
    [ \t]*//[ \t]*---[ \t]*\n        # closing marker
    (?:[ \t]*\n){0,2}                # up to 2 blank lines
    [ \t]*                           # class line indent
    (?:(?:public|internal|protected|private|static|abstract|sealed|partial)[ \t]+)*
    (?:class|struct|interface|record)[ \t]+
    (\w+)                            # class name
    """,
    re.VERBOSE | re.MULTILINE,
)
_FM_KV_RE = re.compile(r"^\s*(\w+)\s*:\s*(.+?)\s*$")
_FM_TAGS_RE = re.compile(r"^\[(.*)\]$")


@dataclass
class MethodInfo:
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    class_name: str
    namespace: str
    file: str
    folder: str
    kind: str = "class"
    xml_summary: str = ""
    methods: list[MethodInfo] = field(default_factory=list)
    frontmatter_tags: list[str] | None = None


def _parse_frontmatter_block(body: str) -> dict:
    """Parse `// key: value` lines from a frontmatter block body. Unknown keys skipped."""
    out: dict = {}
    for raw_line in body.splitlines():
        line = re.sub(r"^\s*//\s?", "", raw_line)
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        m = _FM_KV_RE.match(line)
        if not m:
            continue
        key = m.group(1)
        value = m.group(2).strip()
        if key == "description":
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            out["description"] = value
        elif key == "tags":
            tm = _FM_TAGS_RE.match(value)
            if not tm:
                continue
            inner = tm.group(1).strip()
            if not inner:
                out["tags"] = []
            else:
                out["tags"] = [t.strip() for t in inner.split(",") if t.strip()]
    return out


def _extract_xml_summary(block: str) -> str:
    m = _XML_SUMMARY_RE.search(block)
    if not m:
        return ""
    raw = m.group(1)
    lines = [re.sub(r"^\s*///\s?", "", ln) for ln in raw.splitlines()]
    return re.sub(r"\s+", " ", " ".join(lines).strip())


def _extract_class_body(text: str, body_start: int) -> str:
    """Return the text of the first balanced {...} block starting at body_start."""
    depth = 1
    i = body_start
    n = len(text)
    while i < n and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return text[body_start:i]


def _pascal_to_words(name: str) -> list[str]:
    parts = re.sub(r"([A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z])|[A-Z]+$|\d+)", r" \1", name)
    return [p.lower() for p in parts.split() if p]


def file_hash(path: Path) -> str:
    sha = hashlib.sha1(path.read_bytes())
    return f"sha1:{sha.hexdigest()}"


def parse_cs_file(path: Path, solution: str = "", project: str = "") -> list[ClassInfo]:
    """Parse a C# file and return ClassInfo list (one per class/struct/interface/record)."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    namespace = ""
    ns_match = _NS_RE.search(text)
    if ns_match:
        namespace = ns_match.group(1).strip()

    # Extract XML summaries before stripping comments
    xml_summaries: dict[str, str] = {}
    for m in re.finditer(
        r"((?:[ \t]*///[^\n]*\n)+)\s*(?:(?:public|internal|protected|private|static|abstract|sealed|partial)\s+)*(?:class|struct|interface|record)\s+(\w+)",
        text,
        re.MULTILINE,
    ):
        xml_summaries[m.group(2)] = _extract_xml_summary(m.group(1))

    # Extract `// ---` YAML-ish frontmatter blocks directly above class declarations
    frontmatter_by_class: dict[str, dict] = {}
    for fm in _FRONTMATTER_RE.finditer(text):
        parsed = _parse_frontmatter_block(fm.group(1))
        if parsed:
            frontmatter_by_class[fm.group(2)] = parsed

    clean = _BLOCK_COMMENT_STRIP.sub(" ", text)
    clean = _COMMENT_STRIP.sub("", clean)

    folder = str(path.parent)
    file_str = str(path)

    classes: list[ClassInfo] = []
    for m in _CLASS_RE.finditer(clean):
        class_name = m.group(1)

        snippet = m.group(0)
        kind_m = re.search(r"\b(interface|struct|record|class)\b", snippet)
        kind = kind_m.group(1) if kind_m else "class"

        body_start = m.end()
        body_snippet = _extract_class_body(clean, body_start)

        methods: list[MethodInfo] = []
        seen_methods: set[str] = set()
        for mm in _METHOD_RE.finditer(body_snippet):
            mname = mm.group(1)
            if mname == class_name:
                continue
            if mname not in seen_methods:
                seen_methods.add(mname)
                methods.append(MethodInfo(name=mname))

        xml_summary = xml_summaries.get(class_name, "")
        fm_meta = frontmatter_by_class.get(class_name, {})
        description = xml_summary or fm_meta.get("description", "")
        fm_tags = fm_meta.get("tags") if "tags" in fm_meta else None

        classes.append(
            ClassInfo(
                class_name=class_name,
                namespace=namespace,
                file=file_str,
                folder=folder,
                kind=kind,
                xml_summary=description,
                methods=methods,
                frontmatter_tags=fm_tags,
            )
        )

    return classes


def classes_to_index_entries(
    classes: list[ClassInfo],
    path: Path,
    solution: str = "",
    project: str = "",
    description_overrides: dict[str, dict] | None = None,
) -> list[dict]:
    """Convert parsed ClassInfo list to index-entry dicts ready for store.upsert_class()."""
    src_hash = file_hash(path)
    overrides = description_overrides or {}
    entries = []
    for c in classes:
        override = overrides.get(c.class_name, {})
        pascal_tags = _pascal_to_words(c.class_name)
        default_tags = c.frontmatter_tags if c.frontmatter_tags is not None else pascal_tags
        methods_out = []
        for m in c.methods:
            mo = overrides.get(f"{c.class_name}.{m.name}", {})
            methods_out.append(
                {
                    "name": m.name,
                    "description": mo.get("description", m.description),
                    "tags": mo.get("tags", m.tags or _pascal_to_words(m.name)),
                }
            )
        entries.append(
            {
                "solution": solution,
                "project": project,
                "namespace": c.namespace,
                "folder": c.folder,
                "file": c.file,
                "class_name": c.class_name,
                "kind": c.kind,
                "description": override.get("description", c.xml_summary),
                "tags": override.get("tags", default_tags),
                "methods": methods_out,
                "source_hash": src_hash,
            }
        )
    return entries
