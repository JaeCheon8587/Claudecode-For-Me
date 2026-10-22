"""docs_helpers — per-App Intent 문서 · 레포 Task 문서 검사 helper.

Subcommands:
    check       docs/<App>/ 무결성 검사 — App 폴더 존재 + INT-CATALOG 최신 여부 (+ .task/ 가 있으면 task-catalog 최신 여부)
    check-intent  Intent 문서(<App>-INT-<NNN>.md) 구조 검증 — rule set A·B
    intent-checklist  Intent 문서 검증 기준표(행·코드 facts·인용 표본) 생성 · critic 반환 검사
    intent-catalog  docs/<App>/<App>-INT-CATALOG.md 생성·검사 (INTENT/ 에서 파생)
    check-task  Task 문서(.task/TSK-<NNN>.md) 검증 — 형식 · 항목 · 대상 Intent 대조
    task-catalog  .task/task-catalog.md 생성·검사 (.task/ 에서 파생)

파일을 쓰는 것은 `intent-catalog --write` · `task-catalog --write` 뿐이고, 나머지 서브커맨드는 read-only 다.
문서 폴더는 docs·Docs 를 같은 폴더로 본다 (_docs_root) — 이 문서의 docs/ 는 둘 다를 뜻한다.
Task 폴더는 레포 루트의 `.task/` 하나뿐이다 (소문자).

Standard library only. Windows PowerShell 호환.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


APP_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")

INTENT_FILENAME_PATTERN = lambda app: re.compile(rf"^{re.escape(app)}-INT-(\d{{3}})\.md$")

# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (IsADirectoryError, UnicodeDecodeError, PermissionError):
        return None
    return text.lstrip("﻿").replace("\r\n", "\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_repo(arg: str) -> Path:
    p = Path(arg).resolve()
    if not p.is_dir():
        print(f"FAIL ARGS --repo not a directory: {p}", file=sys.stderr)
        sys.exit(2)
    return p


def _match_case(base: Path, rel: str | Path) -> Path:
    """base 아래 rel 을 디스크에 있는 표기로 잇는다 — 대소문자만 다른 이름(docs·Docs)은 같은 것으로 본다.

    대소문자 구분 FS(Linux)는 표기가 다르면 아예 열지 못하고, 대소문자 무시 FS(Windows·macOS)는
    열리기는 해도 받은 표기가 그대로 남아 출력·git 경로가 실제와 어긋난다. 같은 이름이 있으면
    그것을, 없으면 대소문자만 다른 이름을 쓴다. 디스크에 없는 구간부터는 받은 표기 그대로 잇는다.
    """
    cur = base
    for part in Path(rel).parts:
        try:
            names = sorted(p.name for p in cur.iterdir())
        except OSError:
            names = []
        if part not in names:
            part = next((n for n in names if n.lower() == part.lower()), part)
        cur = cur / part
    return cur


def _docs_root(repo: Path) -> Path:
    """repo 의 문서 폴더 — docs·Docs 어느 표기든 같은 폴더로 본다. 없으면 repo/docs."""
    return _match_case(repo, "docs")


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    level: str
    code: str
    message: str
    path: Path | None = None


def _format(r: CheckResult, repo: Path) -> str:
    if r.path is not None:
        try:
            rel = r.path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = str(r.path)
        return f"{r.level} {r.code} {rel} {r.message}"
    return f"{r.level} {r.code} {r.message}"


def _scan_docs_folders(repo: Path) -> list[str]:
    docs = _docs_root(repo)
    if not docs.is_dir():
        return []
    out: list[str] = []
    for p in sorted(docs.iterdir()):
        if not p.is_dir():
            continue
        if p.name.startswith("_") or p.name.startswith("."):
            continue
        if not APP_CODE_PATTERN.match(p.name):
            continue
        out.append(p.name)
    return out


def _check_app(repo: Path, app: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    docs_dir = _docs_root(repo) / app
    if not docs_dir.is_dir():
        results.append(CheckResult("FAIL", "APP_DIR", "missing", docs_dir))
        return results
    results.append(CheckResult("PASS", "APP_DIR", "exists", docs_dir))

    # INTENT 를 실제로 쓰는 repo 에서만 검사한다 — INTENT/ 가 비어 있으면 카탈로그를 요구하지 않는다.
    intent_rows, _ = _collect_intent_rows(repo, app)
    if intent_rows:
        int_catalog_path = docs_dir / f"{app}-INT-CATALOG.md"
        expected_catalog = _render_intent_catalog(app, intent_rows)
        actual_catalog = _read_text(int_catalog_path)
        if actual_catalog is None:
            results.append(CheckResult(
                "FAIL", "INT_CATALOG", "missing — intent-catalog --write 로 생성", int_catalog_path,
            ))
        elif actual_catalog != expected_catalog:
            results.append(CheckResult(
                "FAIL", "INT_CATALOG", "stale — intent-catalog --write 로 재생성", int_catalog_path,
            ))
        else:
            results.append(CheckResult(
                "PASS", "INT_CATALOG", f"{len(intent_rows)} intents 최신", int_catalog_path,
            ))

    return results


def cmd_check(repo: Path, app: str | None) -> int:
    apps: list[str]
    if app:
        apps = [app]
    else:
        apps = _scan_docs_folders(repo)
        if not apps:
            print("FAIL APPS no app found via docs/<App>/ scan")
            return 2

    results: list[CheckResult] = []
    for a in apps:
        results.extend(_check_app(repo, a))
    # Task 는 App 이 아니라 레포 단위다 — --app 을 줘도 검사한다 (Task 가 없으면 결과가 없다).
    results.extend(_check_tasks(repo))

    for r in results:
        print(_format(r, repo))
    p = sum(1 for r in results if r.level == "PASS")
    w = sum(1 for r in results if r.level == "WARN")
    f = sum(1 for r in results if r.level == "FAIL")
    print(f"Summary: {p} PASS, {w} WARN, {f} FAIL")
    return 1 if f > 0 else 0


# ---------------------------------------------------------------------------
# Intent parsing (check-intent)
# ---------------------------------------------------------------------------


def _strip_code_spans(s: str) -> str:
    """인라인 백틱 스팬(`...`, 한 줄)을 제거한다."""
    return re.sub(r"`[^`\n]*`", "", s)


def _live_lines(text: str, first_lineno: int) -> list[tuple[int, str]]:
    """본문을 (파일 줄번호, 줄) 목록으로 돌려준다. HTML 주석 부분은 제거한다 — 여러 줄 주석 포함."""
    out: list[tuple[int, str]] = []
    in_comment = False
    for i, line in enumerate(text.split("\n")):
        live = ""
        rest = line
        while rest:
            if in_comment:
                end = rest.find("-->")
                if end == -1:
                    rest = ""
                else:
                    rest = rest[end + 3:]
                    in_comment = False
            else:
                start = rest.find("<!--")
                if start == -1:
                    live += rest
                    rest = ""
                else:
                    live += rest[:start]
                    rest = rest[start + 4:]
                    in_comment = True
        out.append((first_lineno + i, live))
    return out


def _placeholder_hits(lines: list[str]) -> list[tuple[int, str]]:
    """HTML 주석과 백틱 스팬을 제외한 본문에서 {…} placeholder 를 찾는다."""
    hits: list[tuple[int, str]] = []
    for lineno, live in _live_lines("\n".join(lines), 1):
        for m in re.finditer(r"\{[^{}\n]*\}", _strip_code_spans(live)):
            hits.append((lineno, m.group(0)))
    return hits


@dataclass
class IntentItem:
    kind: str                 # "D" | "C" | "OS" | "FR" | "E" | "X" | "A"
    id: str                   # "D1", "C2", "OS3", "FR-4", "E-1", "X-2", "A-5"
    num: int
    text: str                 # id 접두·끝의 refs 그룹을 제외한 본문
    refs: list[str]           # e.g. ["D1", "C2"], ["FR-3", "OS"]; 없으면 []
    line: int                 # 파일 내 1-based 줄번호
    checked: bool | None      # A 항목만: "- [ ]"/"- [x]" → True, "- A-n." → False, 그 외 None
    body: str = ""            # id 접두 뒤 문장 전체(refs 그룹 포함, 진행 표시 제외) — Task Scope 사본과 대조
    marker: tuple[str, str] | None = None   # 줄 끝 진행 표시 ("TSK-012", "진행 중"|"삭제 예정"); 없으면 None


@dataclass
class IntentDoc:
    title: str                          # 첫 "# " 이후 텍스트
    has_template_warning: bool          # "> " 인용구 안 "**TEMPLATE**" 줄 존재 여부
    meta: dict[str, str]                # 메타 표 항목 -> 값
    meta_order: list[str]               # 항목 키 (파일 순서)
    sections: dict[str, str]            # "### " 헤딩 텍스트 -> 본문
    section_lines: dict[str, int]       # 헤딩 텍스트 -> 헤딩 줄번호
    part1_line: int | None              # "## Part 1" 줄번호
    part2_line: int | None              # "## Part 2" 줄번호
    items: dict[str, list[IntentItem]]  # kind -> 항목(파일 순서); 모든 kind 키 존재
    handoff: dict[str, str]             # Handoff 표 항목 -> 값
    handoff_order: list[str]
    raw_lines: list[str]


INTENT_ITEM_KINDS = ("D", "C", "OS", "FR", "E", "X", "A")

INTENT_ITEM_PATTERNS: dict[str, re.Pattern[str]] = {
    "D": re.compile(r"^- (D)(\d+)\.\s*(.*)$"),
    "C": re.compile(r"^- (C)(\d+)\.\s*(.*)$"),
    "FR": re.compile(r"^- (FR)-(\d+)\.\s*(.*)$"),
    "E": re.compile(r"^- (E)-(\d+)\.\s*(.*)$"),
    "X": re.compile(r"^- (X)-(\d+)\.\s*(.*)$"),
    "A": re.compile(r"^- (?:\[([ xX])\]\s*)?(A)-(\d+)\.\s*(.*)$"),
}

INTENT_SECTION_FOR_KIND = {
    "D": "Decisions",
    "C": "Constraints",
    "FR": "Functional requirements",
    "E": "Edge cases",
    "X": "Error cases",
    "A": "Acceptance",
}

INTENT_OUT_OF_SCOPE_PATTERN = re.compile(r"^- Out of scope:\s*(.*)$", re.MULTILINE)
# Task 가 바꾸는 항목의 줄 끝(refs 그룹 뒤)에 붙는 진행 표시 — refs 를 떼기 전에 먼저 뗀다.
PROGRESS_MARKER_PATTERN = re.compile(r"\s*\[(TSK-\d{3}) (진행 중|삭제 예정)\]\s*$")
INTENT_REF_GROUP_PATTERN = re.compile(r"^(.*)\(([^()]*)\)\s*$")
INTENT_REFS_INNER_PATTERN = re.compile(
    r"^(?:D\d+|C\d+|FR-\d+|OS)(?:,\s*(?:D\d+|C\d+|FR-\d+|OS))*$"
)


def _split_table_cells(line: str) -> list[str]:
    """표 행(`| a | b |`)을 셀로 분할한다. \\| 이스케이프는 경계로 취급하지 않는다."""
    parts = re.split(r"(?<!\\)\|", line.strip())
    if len(parts) < 2:
        return []
    return [c.strip() for c in parts[1:-1]]


def _is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.match(r"^:?-+:?$", c) for c in cells)


def _split_top_level_commas(value: str) -> list[str]:
    """괄호 깊이 0 의 `,` 기준 분할 (반각·전괄호 모두 깊이 카운트)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in value:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _split_intent_refs(body: str) -> tuple[str, list[str]]:
    """본문 끝의 `(D1, C2)` 형 refs 그룹을 떼어낸다. 비참조 괄호는 본문에 유지."""
    m = INTENT_REF_GROUP_PATTERN.match(body)
    if m and INTENT_REFS_INNER_PATTERN.match(m.group(2)):
        refs = [t.strip() for t in m.group(2).split(",")]
        return m.group(1).rstrip(), refs
    return body, []


def _parse_intent(text: str) -> IntentDoc:
    """Intent 문서 텍스트를 파싱한다. 잘못된 입력에서도 예외를 던지지 않는다."""
    lines = text.split("\n")

    title = ""
    for line in lines:
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            title = m.group(1)
            break

    has_template_warning = any(
        line.lstrip().startswith(">") and "**TEMPLATE**" in line for line in lines
    )

    meta: dict[str, str] = {}
    meta_order: list[str] = []
    for i, line in enumerate(lines):
        if _split_table_cells(line) == ["항목", "값"]:
            for row_line in lines[i + 1:]:
                if not row_line.lstrip().startswith("|"):
                    break
                row = _split_table_cells(row_line)
                if len(row) == 2 and not _is_table_separator(row):
                    if row[0] not in meta:
                        meta_order.append(row[0])
                    meta[row[0]] = row[1]
            break

    section_lines: dict[str, int] = {}
    section_bodies: dict[str, list[tuple[int, str]]] = {}
    part1_line: int | None = None
    part2_line: int | None = None
    current: str | None = None
    for idx, line in enumerate(lines, start=1):
        h3 = re.match(r"^###\s+(.+?)\s*$", line)
        h2 = re.match(r"^##\s+(.+?)\s*$", line)
        hr = re.match(r"^-{3,}\s*$", line)
        if h3 or h2 or hr:
            current = None
        if h3:
            name = h3.group(1)
            current = name
            section_lines[name] = idx
            section_bodies.setdefault(name, [])
            continue
        if h2:
            head = h2.group(1)
            if part1_line is None and re.match(r"^Part 1(\s|$)", head):
                part1_line = idx
            elif part2_line is None and re.match(r"^Part 2(\s|$)", head):
                part2_line = idx
            continue
        if current is not None:
            section_bodies[current].append((idx, line))
    sections = {name: "\n".join(l for _, l in body) for name, body in section_bodies.items()}

    items: dict[str, list[IntentItem]] = {kind: [] for kind in INTENT_ITEM_KINDS}
    for kind, pattern in INTENT_ITEM_PATTERNS.items():
        for lineno, line in section_bodies.get(INTENT_SECTION_FOR_KIND[kind], []):
            m = pattern.match(line)
            if not m:
                continue
            if kind == "A":
                num_s, body, bracket = m.group(3), m.group(4), m.group(1)
                checked: bool | None = bracket is not None
            else:
                num_s, body, bracket = m.group(2), m.group(3), None
                checked = None
            marker: tuple[str, str] | None = None
            mm = PROGRESS_MARKER_PATTERN.search(body)
            if mm is not None:
                marker = (mm.group(1), mm.group(2))
                body = body[:mm.start()]
            text_part, refs = _split_intent_refs(body)
            prefix = f"{kind}-" if kind in ("FR", "E", "X", "A") else kind
            items[kind].append(IntentItem(
                kind=kind,
                id=f"{prefix}{num_s}",
                num=int(num_s),
                text=text_part,
                refs=refs,
                line=lineno,
                checked=checked,
                body=body.strip(),
                marker=marker,
            ))

    for lineno, line in section_bodies.get("Outcome", []):
        m = INTENT_OUT_OF_SCOPE_PATTERN.match(line)
        if not m:
            continue
        value = m.group(1).strip()
        if value.lower() == "none":
            continue
        for i, token in enumerate(_split_top_level_commas(value), start=1):
            items["OS"].append(IntentItem("OS", f"OS{i}", i, token, [], lineno, None))

    handoff: dict[str, str] = {}
    handoff_order: list[str] = []
    handoff_body = section_bodies.get("Handoff", [])
    for i, (_, line) in enumerate(handoff_body):
        if _split_table_cells(line) != ["항목", "값"]:
            continue
        for _, row_line in handoff_body[i + 1:]:
            if not row_line.lstrip().startswith("|"):
                break
            row = _split_table_cells(row_line)
            if len(row) == 2 and not _is_table_separator(row):
                if row[0] not in handoff:
                    handoff_order.append(row[0])
                handoff[row[0]] = row[1]
        break

    return IntentDoc(
        title=title,
        has_template_warning=has_template_warning,
        meta=meta,
        meta_order=meta_order,
        sections=sections,
        section_lines=section_lines,
        part1_line=part1_line,
        part2_line=part2_line,
        items=items,
        handoff=handoff,
        handoff_order=handoff_order,
        raw_lines=lines,
    )


# ---------------------------------------------------------------------------
# check-intent (Intent 문서 구조 검증 — rule set A·B)
# ---------------------------------------------------------------------------


INTENT_META_EXPECTED = ["문서 ID", "유형", "상태", "작성", "승인", "관련 Intent", "검증"]
INTENT_HANDOFF_EXPECTED = ["repo · app", "base branch", "브랜치명", "손대지 말 영역", "완료 보고 방식"]
INTENT_PART1_SECTIONS = ("Problem", "Outcome", "Affected", "Constraints", "Decisions", "Open questions")
INTENT_PART2_SECTIONS = (
    "Functional requirements",
    "Edge cases",
    "Error cases",
    "Acceptance",
    "Verification",
    "Risks",
    "Handoff",
)

INTENT_TITLE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*-INT-\d{3} — .+$")
INTENT_TITLE_PREFIX_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9]*-INT-\d{3})(?:\s|$)")
INTENT_AUTHOR_DATE_PATTERN = re.compile(r"^.+ · \d{4}-\d{2}-\d{2}$")
INTENT_GATE_ROW_PATTERN = re.compile(r"^(PASS|FAIL|OVERRIDE|SKIPPED) — .+$")


@dataclass
class _IntentCtx:
    path: Path
    stem: str


def _intent_placeholder_hits(doc: IntentDoc) -> list[tuple[int, str]]:
    """HTML 주석과 백틱 스팬을 제외한 본문에서 {…} placeholder 를 찾는다."""
    return _placeholder_hits(doc.raw_lines)


def _intent_rule_template_warning(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    if doc.has_template_warning:
        return [CheckResult("FAIL", "INT_TEMPLATE_WARNING", "TEMPLATE 경고 블록이 남아 있다", ctx.path)]
    return [CheckResult("PASS", "INT_TEMPLATE_WARNING", "TEMPLATE 경고 블록 없음", ctx.path)]


def _intent_rule_title(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    if INTENT_TITLE_PATTERN.match(doc.title):
        return [CheckResult("PASS", "INT_TITLE", f"제목 형식 일치: {doc.title}", ctx.path)]
    return [CheckResult("FAIL", "INT_TITLE", f"제목이 '<App>-INT-<NNN> — <제목>' 형식이 아님: {doc.title!r}", ctx.path)]


def _intent_rule_id_filename(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    m = INTENT_TITLE_PREFIX_PATTERN.match(doc.title)
    title_prefix = m.group(1) if m else ""
    meta_id = doc.meta.get("문서 ID", "")
    if title_prefix and ctx.stem == meta_id == title_prefix:
        return [CheckResult("PASS", "INT_ID_FILENAME", f"파일명·문서 ID·제목 접두 일치: {ctx.stem}", ctx.path)]
    return [CheckResult(
        "FAIL", "INT_ID_FILENAME",
        f"파일명={ctx.stem}, 문서 ID={meta_id!r}, 제목 접두={title_prefix!r}",
        ctx.path,
    )]


def _intent_rule_meta_rows(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    if doc.meta_order == INTENT_META_EXPECTED:
        return [CheckResult("PASS", "INT_META_ROWS", "메타 7행 순서 일치", ctx.path)]
    if doc.meta_order == INTENT_META_EXPECTED[:6]:
        return [CheckResult("WARN", "INT_META_LEGACY", "pre-3.60 문서 — `검증` 행 없음", ctx.path)]
    missing = [k for k in INTENT_META_EXPECTED if k not in doc.meta_order]
    extra = [k for k in doc.meta_order if k not in INTENT_META_EXPECTED]
    actual = [k for k in doc.meta_order if k in INTENT_META_EXPECTED]
    expected = [k for k in INTENT_META_EXPECTED if k in doc.meta_order]
    problems = []
    if missing:
        problems.append(f"없음: {missing}")
    if extra:
        problems.append(f"추가: {extra}")
    if not missing and not extra and actual != expected:
        problems.append(f"순서 불일치: {actual}")
    detail = ", ".join(problems) if problems else f"순서 불일치: {actual}"
    return [CheckResult("FAIL", "INT_META_ROWS", f"메타 행 불일치 — {detail}", ctx.path)]


def _intent_rule_type_single(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("유형")
    if value in ("기능개발", "리팩토링"):
        return [CheckResult("PASS", "INT_TYPE_SINGLE", f"유형 단일: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_TYPE_SINGLE", f"유형이 '기능개발'/'리팩토링' 중 하나가 아님: {value!r}", ctx.path)]


def _intent_rule_status(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("상태")
    if value in ("draft", "approved", "in-dev", "in-review", "done"):
        return [CheckResult("PASS", "INT_STATUS", f"상태 허용값: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_STATUS", f"상태가 허용값(draft|approved|in-dev|in-review|done)이 아님: {value!r}", ctx.path)]


def _intent_rule_author_format(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("작성", "")
    if INTENT_AUTHOR_DATE_PATTERN.match(value):
        return [CheckResult("PASS", "INT_AUTHOR_FORMAT", f"작성 행 형식 일치: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_AUTHOR_FORMAT", f"작성 행이 '<작성자> · <YYYY-MM-DD>' 형식이 아님: {value!r}", ctx.path)]


def _intent_rule_approval_format(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("승인", "")
    if value == "pending" or INTENT_AUTHOR_DATE_PATTERN.match(value):
        return [CheckResult("PASS", "INT_APPROVAL_FORMAT", f"승인 행 형식 일치: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_APPROVAL_FORMAT", f"승인 행이 'pending' 또는 '<승인자> · <YYYY-MM-DD>' 형식이 아님: {value!r}", ctx.path)]


def _intent_rule_part1_headings(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    missing = [name for name in INTENT_PART1_SECTIONS if name not in doc.sections]
    if doc.part1_line is not None and not missing:
        return [CheckResult("PASS", "INT_PART1_HEADINGS", "Part 1 필수 섹션 6개 존재", ctx.path)]
    problems = []
    if doc.part1_line is None:
        problems.append("'## Part 1' 헤딩 없음")
    if missing:
        problems.append(f"없는 섹션: {missing}")
    return [CheckResult("FAIL", "INT_PART1_HEADINGS", ", ".join(problems), ctx.path)]


def _intent_rule_part2_headings(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    missing = [name for name in INTENT_PART2_SECTIONS if name not in doc.sections]
    if doc.part2_line is not None and not missing:
        return [CheckResult("PASS", "INT_PART2_HEADINGS", "Part 2 필수 섹션 7개 존재", ctx.path)]
    problems = []
    if doc.part2_line is None:
        problems.append("'## Part 2' 헤딩 없음")
    if missing:
        problems.append(f"없는 섹션: {missing}")
    return [CheckResult("FAIL", "INT_PART2_HEADINGS", ", ".join(problems), ctx.path)]


def _intent_rule_out_of_scope(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    m = INTENT_OUT_OF_SCOPE_PATTERN.search(doc.sections.get("Outcome", ""))
    if m and m.group(1).strip():
        return [CheckResult("PASS", "INT_OUT_OF_SCOPE", "Out of scope 행 존재", ctx.path)]
    return [CheckResult("FAIL", "INT_OUT_OF_SCOPE", "Outcome 에 값이 있는 '- Out of scope:' 행이 없음", ctx.path)]


def _intent_rule_open_questions(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    body = re.sub(r"<!--.*?-->", "", doc.sections.get("Open questions", ""), flags=re.DOTALL).strip()
    if body:
        return [CheckResult("PASS", "INT_OPEN_QUESTIONS", "Open questions 본문 있음", ctx.path)]
    return [CheckResult("FAIL", "INT_OPEN_QUESTIONS", "Open questions 본문이 비어 있음 (없으면 none)", ctx.path)]


def _intent_rule_handoff_rows(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    if doc.handoff_order == INTENT_HANDOFF_EXPECTED:
        return [CheckResult("PASS", "INT_HANDOFF_ROWS", "Handoff 5행 순서 일치", ctx.path)]
    return [CheckResult(
        "FAIL", "INT_HANDOFF_ROWS",
        f"Handoff 행 불일치 — 기대 {INTENT_HANDOFF_EXPECTED}, 실제 {doc.handoff_order}",
        ctx.path,
    )]


def _intent_rule_branch_placeholder(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.handoff.get("브랜치명", "")
    if "{App}" in value or "{NNN}" in value:
        return [CheckResult("FAIL", "INT_BRANCH_PLACEHOLDER", f"브랜치명에 placeholder 가 남아 있다: {value}", ctx.path)]
    return [CheckResult("PASS", "INT_BRANCH_PLACEHOLDER", f"브랜치명 placeholder 없음: {value}", ctx.path)]


def _intent_rule_placeholder(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    hits = _intent_placeholder_hits(doc)
    if not hits:
        return [CheckResult("PASS", "INT_PLACEHOLDER", "주석·백틱 밖 placeholder 없음", ctx.path)]
    shown = ", ".join(f"{lineno}:{snippet}" for lineno, snippet in hits[:3])
    return [CheckResult("FAIL", "INT_PLACEHOLDER", f"주석·백틱 밖 placeholder 남음: {shown}", ctx.path)]


def _intent_rule_gate_row(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    if "검증" not in doc.meta:
        return []
    value = doc.meta["검증"]
    if value == "pending" or INTENT_GATE_ROW_PATTERN.match(value):
        return [CheckResult("PASS", "INT_GATE_ROW_FORMAT", f"검증 행 형식 일치: {value}", ctx.path)]
    return [CheckResult(
        "FAIL", "INT_GATE_ROW_FORMAT",
        f"검증 행이 'pending' 또는 '<총평> — ...' 형식이 아님: {value!r}",
        ctx.path,
    )]


# ---------------------------------------------------------------------------
# check-intent — rule set B (항목 ID · 참조 · 게이트)
# ---------------------------------------------------------------------------


INTENT_DECISION_LINE_PATTERN = re.compile(r"^- D\d+\. .+ — 근거: .+ — 기각 대안: .+$")
INTENT_CONSTRAINT_PREFIX_PATTERN = re.compile(r"^- C\d+\. ")
INTENT_ID_ORDER_KINDS = ("D", "C", "FR", "E", "X", "A")
INTENT_VERIFY_COMMAND_PREFIXES = (
    "python ", "python3 ", "dotnet ", "npm ", "pnpm ", "yarn ", "pytest",
    "curl ", "git ", "make ", "go ", "cargo ",
)


def _intent_live_lines(doc: IntentDoc, name: str) -> list[tuple[int, str]]:
    """섹션 본문을 (파일 줄번호, 줄) 목록으로 돌려준다. HTML 주석 부분은 제거한다."""
    if name not in doc.section_lines or name not in doc.sections:
        return []
    return _live_lines(doc.sections[name], doc.section_lines[name] + 1)


def _intent_body_is_none(doc: IntentDoc, name: str) -> bool:
    """섹션 본문(주석 제거)이 정확히 `none` 인지."""
    return "\n".join(text for _, text in _intent_live_lines(doc, name)).strip() == "none"


def _intent_rule_decision_format(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """Decisions 행은 `- Dn. <결정> — 근거: <근거> — 기각 대안: <대안>` 형식 (`none` 허용)."""
    offenders = [
        lineno
        for lineno, text in _intent_live_lines(doc, "Decisions")
        if re.match(r"^- ", text) and not INTENT_DECISION_LINE_PATTERN.match(text)
    ]
    if offenders:
        return [CheckResult("FAIL", "INT_DECISION_FORMAT", f"Decisions 행 형식 불일치 — 줄 {offenders}", ctx.path)]
    return [CheckResult("PASS", "INT_DECISION_FORMAT", "Decisions 행 형식 일치", ctx.path)]


def _intent_rule_constraint_id(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """Constraints 행은 `- Cn. ` 로 시작해야 한다 (`none` 허용)."""
    offenders = [
        lineno
        for lineno, text in _intent_live_lines(doc, "Constraints")
        if re.match(r"^- ", text) and not INTENT_CONSTRAINT_PREFIX_PATTERN.match(text)
    ]
    if offenders:
        return [CheckResult("FAIL", "INT_CONSTRAINT_ID", f"Constraints 행에 C 번호 없음 — 줄 {offenders}", ctx.path)]
    return [CheckResult("PASS", "INT_CONSTRAINT_ID", "Constraints 행 C 번호 형식 일치", ctx.path)]


def _intent_rule_id_order(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """항목 번호는 종류별 오름차순(빈 번호 허용, 중복·하강 금지). FR·A 는 1개 이상, D·C·E·X 는 본문이 `none` 일 때만 비울 수 있다."""
    results: list[CheckResult] = []
    for kind in INTENT_ID_ORDER_KINDS:
        items = doc.items[kind]
        problems: list[str] = []
        if not items:
            if kind in ("FR", "A"):
                problems.append("항목이 1개도 없음")
            elif not _intent_body_is_none(doc, INTENT_SECTION_FOR_KIND[kind]):
                problems.append("항목이 없는데 본문이 none 이 아님")
        else:
            bad = [it.id for i, it in enumerate(items) if i and it.num <= items[i - 1].num]
            if bad:
                problems.append(f"중복·하강: {bad}")
        if problems:
            results.append(CheckResult("FAIL", "INT_ID_ORDER", f"{kind} — {', '.join(problems)}", ctx.path))
        elif items:
            nums = [it.num for it in items]
            results.append(CheckResult("PASS", "INT_ID_ORDER", f"{kind} 번호 오름차순: {nums}", ctx.path))
        else:
            results.append(CheckResult("PASS", "INT_ID_ORDER", f"{kind} 항목 없음 — none", ctx.path))
    return results


def _intent_rule_acceptance_type(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """유형이 기능개발이면 A 는 체크박스 형태, 리팩토링이면 평문 목록이어야 한다."""
    value = doc.meta.get("유형")
    if value not in ("기능개발", "리팩토링"):
        return []
    expected = value == "기능개발"
    offenders = [it.id for it in doc.items["A"] if it.checked is not expected]
    if offenders:
        return [CheckResult("FAIL", "INT_ACCEPTANCE_TYPE", f"유형 {value} — 형식 불일치 항목: {offenders}", ctx.path)]
    return [CheckResult("PASS", "INT_ACCEPTANCE_TYPE", f"유형 {value} — A 항목 형식 일치", ctx.path)]


def _intent_rule_ref_dangling(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """모든 참조 토큰(Dn/Cn/FR-n/OS)은 실제 항목으로 해결되어야 한다."""
    ids = {it.id for items in doc.items.values() for it in items}
    has_os = bool(doc.items["OS"])
    dangling: list[str] = []
    for kind in INTENT_ITEM_KINDS:
        for it in doc.items[kind]:
            for ref in it.refs:
                if (ref == "OS" and not has_os) or (ref != "OS" and ref not in ids):
                    dangling.append(f"{it.id} → {ref}")
    if dangling:
        return [CheckResult("FAIL", "INT_REF_DANGLING", f"존재하지 않는 참조: {', '.join(dangling)}", ctx.path)]
    return [CheckResult("PASS", "INT_REF_DANGLING", "모든 참조가 실제 항목을 가리킴", ctx.path)]


def _intent_rule_ref_kind(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """FR 은 Dn/Cn 만 인용 가능. E/X/A 는 Dn/Cn/FR-n/OS 인용 가능. D/C/OS 는 참조 불가. 위반은 WARN."""
    violations: list[str] = []
    for it in doc.items["FR"]:
        for ref in it.refs:
            if ref == "OS" or ref.startswith("FR-"):
                violations.append(f"{it.id} → {ref}")
    for kind in ("D", "C", "OS"):
        for it in doc.items[kind]:
            if it.refs:
                violations.append(f"{it.id} → {', '.join(it.refs)}")
    if violations:
        return [CheckResult("WARN", "INT_REF_KIND", f"참조 종류 위반: {', '.join(violations)}", ctx.path)]
    return [CheckResult("PASS", "INT_REF_KIND", "참조 종류 적합", ctx.path)]


def _intent_rule_verify_command(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """Verification 은 확인 '방법' 섹션 — 실행 명령 코드 스팬이면 WARN."""
    spans: list[str] = []
    for _, text in _intent_live_lines(doc, "Verification"):
        for m in re.finditer(r"`[^`\n]*`", text):
            span = m.group(0)[1:-1]
            if span.startswith(INTENT_VERIFY_COMMAND_PREFIXES):
                spans.append(span)
    if spans:
        return [CheckResult("WARN", "INT_VERIFY_COMMAND", f"Verification 에 실행 명령 존재: {spans}", ctx.path)]
    return [CheckResult("PASS", "INT_VERIFY_COMMAND", "Verification 에 실행 명령 없음", ctx.path)]


def _intent_rule_approved_gate(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """`상태: approved` 는 Open questions 가 `none` 이고, Handoff 에 `pending` 이 없고, `유형` 이 한 값이고, `검증` 이 `PASS`·`OVERRIDE`·`SKIPPED` 중 하나로 시작할 때만 가능하다. 메타 `검증` 행 없는 레거시(pre-3.60) 문서는 건너뛴다."""
    if doc.meta.get("상태") != "approved" or "검증" not in doc.meta:
        return []
    failed: list[str] = []
    if not _intent_body_is_none(doc, "Open questions"):
        failed.append("Open questions != none")
    if any(value == "pending" for value in doc.handoff.values()):
        failed.append("Handoff pending")
    if doc.meta.get("유형") not in ("기능개발", "리팩토링"):
        failed.append("유형 not single")
    if not doc.meta["검증"].startswith(("PASS", "OVERRIDE", "SKIPPED")):
        failed.append("검증 not PASS/OVERRIDE/SKIPPED")
    if failed:
        return [CheckResult("FAIL", "INT_APPROVED_GATE", ", ".join(failed), ctx.path)]
    return [CheckResult("PASS", "INT_APPROVED_GATE", "approved 게이트 조건 충족", ctx.path)]


INTENT_RULES = (
    _intent_rule_template_warning,
    _intent_rule_title,
    _intent_rule_id_filename,
    _intent_rule_meta_rows,
    _intent_rule_type_single,
    _intent_rule_status,
    _intent_rule_author_format,
    _intent_rule_approval_format,
    _intent_rule_part1_headings,
    _intent_rule_part2_headings,
    _intent_rule_out_of_scope,
    _intent_rule_open_questions,
    _intent_rule_handoff_rows,
    _intent_rule_branch_placeholder,
    _intent_rule_placeholder,
    _intent_rule_gate_row,
    _intent_rule_decision_format,
    _intent_rule_constraint_id,
    _intent_rule_id_order,
    _intent_rule_acceptance_type,
    _intent_rule_ref_dangling,
    _intent_rule_ref_kind,
    _intent_rule_verify_command,
    _intent_rule_approved_gate,
)


def _check_intent_file(repo: Path, path: Path) -> list[CheckResult]:
    if not path.is_absolute():
        path = _match_case(repo, path)   # docs·Docs 표기 무관
    path = path.resolve()

    results: list[CheckResult] = []

    text = _read_text(path)
    if text is None:
        results.append(CheckResult("FAIL", "READ_TEXT", "cannot read", path))
        return results
    results.append(CheckResult("PASS", "READ_TEXT", "readable", path))

    doc = _parse_intent(text)
    ctx = _IntentCtx(path=path, stem=path.stem)
    for rule in INTENT_RULES:
        results.extend(rule(doc, ctx))
    return results


def _relpath_for(path: Path | None, repo: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def cmd_check_intent(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args.repo)
    return _report_results(repo, _check_intent_file(repo, Path(args.file)), args.json)


def _report_results(repo: Path, results: list[CheckResult], as_json: bool) -> int:
    """check-intent · check-task 공용 출력 — 사람용 줄 또는 JSON. FAIL 이 있으면 1."""
    p = sum(1 for r in results if r.level == "PASS")
    w = sum(1 for r in results if r.level == "WARN")
    f = sum(1 for r in results if r.level == "FAIL")
    if as_json:
        payload = {
            "summary": {"pass": p, "warn": w, "fail": f},
            "results": [
                {
                    "level": r.level,
                    "code": r.code,
                    "path": _relpath_for(r.path, repo),
                    "message": r.message,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(_format(r, repo))
        print(f"Summary: {p} PASS, {w} WARN, {f} FAIL")
    return 1 if f > 0 else 0


# ---------------------------------------------------------------------------
# intent-checklist (검증 기준표 생성 · critic 반환 검사)
# ---------------------------------------------------------------------------


@dataclass
class ChecklistCriterion:
    key: str                  # "a" | "b" | "c"
    text: str
    severity: str             # "MAJOR" | "MINOR"


@dataclass
class ChecklistRow:
    id: str                   # 항목 ID (D1, C2, OS3, FR-4, E-1, X-2, A-5) 또는 G-1..G-5
    kind: str                 # D C OS FR E X A G
    target: str               # 항목 본문 80자 절삭 (G 행은 "")
    facts: str                # 코드가 뽑은 참조 사실 (G 행은 "")
    criteria: list[ChecklistCriterion]
    na_allowed: bool
    quote_required: bool
    line: int | None          # 항목 파일 줄번호 (G 행은 None)


EXPECTED_KINDS: tuple[str, ...] = ("요구", "완료조건", "결정", "제약", "제외", "프로세스", "배경")

EXPECTED_LINE_PATTERN = re.compile(
    r"^- (EXP-\d+)\. (.+) — 출처: (Q\d+/A\d+) — 종류: (요구|완료조건|결정|제약|제외|프로세스|배경)$"
)


@dataclass
class ExpectedItem:
    id: str
    num: int
    text: str
    source: str
    kind: str
    line: int


def _parse_expected(text: str) -> tuple[list[ExpectedItem], list[str]]:
    """expected.md 오라클을 파싱한다 — (항목, 오류) 반환, 오류 있으면 호출처가 exit 2 한다."""
    items: list[ExpectedItem] = []
    errors: list[str] = []
    seen: set[str] = set()
    prev_num = 0
    for lineno, line in enumerate(text.split("\n"), start=1):
        if not line.strip() or line.startswith("#") or not line.startswith("- "):
            continue
        m = EXPECTED_LINE_PATTERN.match(line)
        if m is None:
            errors.append(f"{lineno}: 형식 불일치 — {line[:60]}")
            continue
        item_id, item_text, source, kind = m.group(1), m.group(2), m.group(3), m.group(4)
        num = int(item_id[4:])
        if item_id in seen:
            errors.append(f"{lineno}: EXP ID 중복 — {item_id}")
        if num <= prev_num:
            errors.append(f"{lineno}: EXP ID 오름차순 아님 — {item_id}")
        seen.add(item_id)
        prev_num = num
        items.append(
            ExpectedItem(id=item_id, num=num, text=item_text, source=source, kind=kind, line=lineno)
        )
    if not items:
        errors.append("expected.md 에 EXP 항목이 없다")
    return items, errors


CHECKLIST_KIND_ORDER = ("OS", "C", "D", "FR", "E", "X", "A")

CHECKLIST_CRITERIA: dict[str, tuple[tuple[str, str, str], ...]] = {
    "D": (("a", "결정·제약이 요구하는 동작이 Part 2 로 내려왔나 — 참조 없으면 Handoff·Risks 에서 인용", "MAJOR"),),
    "C": (("a", "결정·제약이 요구하는 동작이 Part 2 로 내려왔나 — 참조 없으면 Handoff·Risks 에서 인용", "MAJOR"),),
    "OS": (("a", "Part 2 어느 항목도 이 범위의 구현을 지시하지 않는다 (제외 확인 A 는 허용)", "MAJOR"),),
    "FR": (
        ("a", "참조 근거가 FR 을 뒷받침 (참조 없으면 Outcome 문단에 근거)", "MAJOR"),
        ("b", "테스트 가능한 문장", "MINOR"),
        ("c", "완료를 판정하는 A 가 있다", "MAJOR"),
    ),
    "E": (
        ("a", "→ 뒤 기대 동작 명시", "MAJOR"),
        ("b", "참조 항목의 정상 경로와 양립", "MAJOR"),
        ("c", "참조 항목이 이 상황의 주체", "MINOR"),
    ),
    "X": (
        ("a", "→ 뒤 기대 동작 명시", "MAJOR"),
        ("b", "참조 항목의 정상 경로와 양립", "MAJOR"),
        ("c", "참조 항목이 이 상황의 주체", "MINOR"),
    ),
    "A": (
        ("a", "판정 가능한 문장", "MAJOR"),
        ("b", "Verification 섹션에 확인 수단 존재", "MAJOR"),
        ("c", "참조 근거가 A 를 뒷받침", "MAJOR"),
    ),
}

CHECKLIST_NA_ALLOWED: dict[str, bool] = {
    "D": True, "C": True, "OS": False, "FR": False, "E": False, "X": False, "A": False,
}

EXPECTED_CRITERIA_DESCENT: tuple[tuple[str, str, str], ...] = (
    ("a", "Intent(Part 1 또는 Part 2)에 담겨 있다 — 위치 항목 ID 인용", "MAJOR"),
    ("b", "Part 2 항목(FR/E/X/A)으로 실행 가능하게 내려왔다 — ID 인용", "MAJOR"),
)
EXPECTED_CRITERIA_POSITION: tuple[tuple[str, str, str], ...] = (
    (
        "a",
        "Intent 에 담겨 있다 — 제약은 Constraints/FR/Risks, 제외는 Out of scope, 프로세스는 Handoff/Decisions 중 위치 항목 ID 인용",
        "MAJOR",
    ),
)
EXPECTED_CRITERIA_BACKGROUND: tuple[tuple[str, str, str], ...] = (
    ("a", "Intent 어딘가에 담겨 있다 — 위치 항목 ID 인용", "MINOR"),
)

EXPECTED_KIND_CRITERIA: dict[str, tuple[tuple[str, str, str], ...]] = {
    "요구": EXPECTED_CRITERIA_DESCENT,
    "완료조건": EXPECTED_CRITERIA_DESCENT,
    "결정": EXPECTED_CRITERIA_DESCENT,
    "제약": EXPECTED_CRITERIA_POSITION,
    "제외": EXPECTED_CRITERIA_POSITION,
    "프로세스": EXPECTED_CRITERIA_POSITION,
    "배경": EXPECTED_CRITERIA_BACKGROUND,
}

CHECKLIST_G_ROWS: tuple[tuple[str, str, str], ...] = (
    ("G-1", "Part 1 내부 모순 없음", "MAJOR"),
    ("G-2", "Part 1 ↔ Part 2 수치·식별자·상태코드·범위 일치", "MAJOR"),
    ("G-3", "Part 1 + Part 2(Handoff 표 제외)에 생성·수정 대상 클래스명·메서드명·파일 경로·라이브러리 API 지정 없음. 계층·패턴 용어, 손대지 말 경로, 스택명은 허용", "MINOR"),
    ("G-4", "Outcome 문단의 결과가 FR 집합으로 달성 가능", "MAJOR"),
    ("G-5", "Problem 이 Outcome 으로 해소됨", "MINOR"),
)

CHECKLIST_SECTION_NAMES = (
    "Problem", "Outcome", "Affected", "Constraints", "Decisions", "Open questions",
    "Functional requirements", "Edge cases", "Error cases", "Acceptance",
    "Verification", "Risks", "Handoff",
)
CHECKLIST_ITEM_ID_PATTERN = re.compile(r"\b(?:D|C|OS)\d+\b|\b(?:FR|E|X|A)-\d+\b")
CRITIC_RETURN_NA_PATTERN = re.compile(r"^N/A:\s*(.+?)\s*(?:—|--)\s*(.+)$")
CRITIC_RETURN_QUOTE_PATTERN = re.compile(r'^QUOTE:\s*(.+?)\s*(?:—|--)\s*[""](.+)[""]\s*$')
CRITIC_RETURN_EMPTY_TOKENS: frozenset[str] = frozenset({"none", "없음", "-", "n/a", "na"})


def _build_checklist(
    doc: IntentDoc,
    intent_id: str,
    round_no: int,
    expected: list[ExpectedItem] | None = None,
) -> list[ChecklistRow]:
    """Intent 항목에서 검증 기준표 행을 생성한다. 인용 표본은 (intent_id, round) 시드로 결정된다."""
    referencing = sorted(
        (it for kind in ("FR", "E", "X", "A") for it in doc.items[kind]),
        key=lambda it: it.line,
    )

    rows: list[ChecklistRow] = []
    if expected:
        for item in expected:
            rows.append(ChecklistRow(
                id=item.id,
                kind="EXP",
                target=item.text[:80],
                facts=f"출처: {item.source} · 종류: {item.kind}",
                criteria=[
                    ChecklistCriterion(k, t, s) for k, t, s in EXPECTED_KIND_CRITERIA[item.kind]
                ],
                na_allowed=False,
                quote_required=False,
                line=item.line,
            ))
    for kind in CHECKLIST_KIND_ORDER:
        for it in doc.items[kind]:
            if kind in ("D", "C"):
                ids = [r.id for r in referencing if it.id in r.refs]
                facts = f"참조: {', '.join(ids)}" if ids else "참조: 없음"
            elif kind == "OS":
                ids = [a.id for a in doc.items["A"] if "OS" in a.refs]
                facts = f"참조 A: {', '.join(ids)}" if ids else "참조 A: 없음"
            elif kind == "FR":
                base = ", ".join(it.refs) if it.refs else "없음"
                ids = [r.id for r in referencing if r.kind in ("E", "X", "A") and it.id in r.refs]
                facts = f"근거: {base} · 참조하는 E/X/A: {', '.join(ids) if ids else '없음'}"
            else:  # E, X, A
                facts = f"근거: {', '.join(it.refs)}" if it.refs else "근거: 없음"
            rows.append(ChecklistRow(
                id=it.id,
                kind=kind,
                target=it.text[:80],
                facts=facts,
                criteria=[ChecklistCriterion(k, t, s) for k, t, s in CHECKLIST_CRITERIA[kind]],
                na_allowed=CHECKLIST_NA_ALLOWED[kind],
                quote_required=False,
                line=it.line,
            ))
    for gid, gtext, gsev in CHECKLIST_G_ROWS:
        rows.append(ChecklistRow(
            id=gid,
            kind="G",
            target="",
            facts="",
            criteria=[ChecklistCriterion("a", gtext, gsev)],
            na_allowed=False,
            quote_required=False,
            line=None,
        ))

    candidates = [r.id for r in rows if r.kind not in ("G", "EXP")]
    rng = random.Random(f"{intent_id}:{round_no}")
    sampled = set(rng.sample(candidates, min(5, len(candidates))))
    for row in rows:
        if row.id in sampled:
            row.quote_required = True
    return rows


def _checklist_traceability(doc: IntentDoc) -> dict[str, int]:
    referenced = {ref for kind in ("FR", "E", "X", "A") for it in doc.items[kind] for ref in it.refs}
    return {
        "fr": len(doc.items["FR"]),
        "fr_with_ref": sum(1 for it in doc.items["FR"] if it.refs),
        "a": len(doc.items["A"]),
        "a_with_ref": sum(1 for it in doc.items["A"] if it.refs),
        "ex": len(doc.items["E"]) + len(doc.items["X"]),
        "ex_with_ref": sum(1 for kind in ("E", "X") for it in doc.items[kind] if it.refs),
        "d_unreferenced": sum(1 for it in doc.items["D"] if it.id not in referenced),
        "c_unreferenced": sum(1 for it in doc.items["C"] if it.id not in referenced),
    }


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _format_checklist_markdown(rows: list[ChecklistRow], intent_id: str, round_no: int) -> str:
    out = [f"# Checklist — {intent_id} — round {round_no}", ""]
    out.append("| ID | 대상 | facts | 판정 기준 | 심각도 | N/A | 인용 |")
    out.append("|---|---|---|---|---|---|---|")
    for row in rows:
        target = f'"{_md_cell(row.target)}"' if row.target else ""
        criteria = " ".join(f"({c.key}) {_md_cell(c.text)}" for c in row.criteria)
        severity = " · ".join(f"({c.key}) {c.severity}" for c in row.criteria)
        na = "허용" if row.na_allowed else "불가"
        quote = "[인용]" if row.quote_required else ""
        out.append(f"| {row.id} | {target} | {_md_cell(row.facts)} | {criteria} | {severity} | {na} | {quote} |")
    quote_ids = [r.id for r in rows if r.quote_required]
    out.append(f"rows: {len(rows)} · quote: {', '.join(quote_ids)}")
    return "\n".join(out)


def _parse_critic_return(text: str) -> tuple[list[str], list[str], list[tuple[str, str]], list[tuple[str, str]]]:
    """critic 반환 텍스트 → (PASS 행 ID, FAIL 키, N/A (키, 사유), QUOTE (행ID, 인용))."""
    pass_ids: list[str] = []
    fail_keys: list[str] = []
    na_entries: list[tuple[str, str]] = []
    quotes: list[tuple[str, str]] = []

    def _is_empty_marker(token: str) -> bool:
        return token.strip().lower() in CRITIC_RETURN_EMPTY_TOKENS

    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("PASS:"):
            pass_ids.extend(
                t for t in (x.strip() for x in s[len("PASS:"):].split(","))
                if t and not _is_empty_marker(t)
            )
        elif s.startswith("FAIL:"):
            fail_keys.extend(
                re.sub(r"\s+", "", x) for x in s[len("FAIL:"):].split(",")
                if x.strip() and not _is_empty_marker(x)
            )
        else:
            if s.startswith("N/A:") and _is_empty_marker(s[len("N/A:"):]):
                continue
            m = CRITIC_RETURN_NA_PATTERN.match(s)
            if m:
                na_entries.append((re.sub(r"\s+", "", m.group(1)), m.group(2).strip()))
                continue
            if s.startswith("QUOTE:") and _is_empty_marker(s[len("QUOTE:"):]):
                continue
            m = CRITIC_RETURN_QUOTE_PATTERN.match(s)
            if m:
                quotes.append((m.group(1).strip(), m.group(2)))
    return pass_ids, fail_keys, na_entries, quotes


def _check_critic_return(doc: IntentDoc, rows: list[ChecklistRow], text: str) -> list[str]:
    """critic 반환을 기준표와 대조해 finding 목록(빈 목록 = OK)을 돌려준다."""
    row_by_id = {r.id: r for r in rows}
    pass_ids, fail_keys, na_entries, quotes = _parse_critic_return(text)

    def row_part(key: str) -> str:
        return key.partition(":")[0]

    pass_set = set(pass_ids)
    fail_rows = {row_part(k) for k in fail_keys}
    na_rows = {row_part(k) for k, _ in na_entries}
    covered = pass_set | fail_rows | na_rows

    findings: list[str] = []

    missing = [r.id for r in rows if r.id not in covered]
    if missing:
        findings.append(f"MISSING: {', '.join(missing)}")

    extra: list[str] = []
    mentioned = (
        list(pass_ids)
        + [row_part(k) for k in fail_keys]
        + [row_part(k) for k, _ in na_entries]
        + [q for q, _ in quotes]
    )
    for rid in mentioned:
        if rid and rid not in row_by_id and rid not in extra:
            extra.append(rid)
    if extra:
        findings.append(f"EXTRA: {', '.join(extra)}")

    overlap = [r.id for r in rows if r.id in pass_set and (r.id in fail_rows or r.id in na_rows)]
    if overlap:
        findings.append(f"OVERLAP: {', '.join(overlap)}")

    bad_keys: list[str] = []
    for key in fail_keys + [ek for ek, _ in na_entries]:
        row = row_by_id.get(row_part(key))
        if row is not None and key.partition(":")[2] not in {c.key for c in row.criteria}:
            bad_keys.append(key)
    if bad_keys:
        findings.append(f"BAD-KEY: {', '.join(bad_keys)}")

    na_not_allowed: list[str] = []
    na_no_location: list[str] = []
    for key, reason in na_entries:
        row = row_by_id.get(row_part(key))
        if row is not None and not row.na_allowed:
            na_not_allowed.append(key)
        has_location = (
            any(name in reason for name in CHECKLIST_SECTION_NAMES)
            or bool(CHECKLIST_ITEM_ID_PATTERN.search(reason))
        )
        if not has_location:
            na_no_location.append(key)
    if na_not_allowed:
        findings.append(f"NA-NOT-ALLOWED: {', '.join(na_not_allowed)}")
    if na_no_location:
        findings.append(f"NA-NO-LOCATION: {', '.join(na_no_location)}")

    quoted = {q for q, _ in quotes}
    quote_missing = [r.id for r in rows if r.quote_required and r.id not in quoted]
    if quote_missing:
        findings.append(f"QUOTE-MISSING: {', '.join(quote_missing)}")

    norm_intent = re.sub(r"\s+", " ", "\n".join(doc.raw_lines)).strip()
    quote_not_found: list[str] = []
    checked_quotes: set[str] = set()
    for qid, qtext in quotes:
        if qid in checked_quotes:
            continue
        checked_quotes.add(qid)
        if re.sub(r"\s+", " ", qtext).strip() not in norm_intent:
            quote_not_found.append(qid)
    if quote_not_found:
        findings.append(f"QUOTE-NOT-FOUND: {', '.join(quote_not_found)}")
    return findings


def cmd_intent_checklist(args: argparse.Namespace) -> int:
    if args.round < 1:
        print(f"FAIL ARGS --round must be >= 1: {args.round}", file=sys.stderr)
        return 2
    repo = _resolve_repo(args.repo)
    path = Path(args.file)
    if not path.is_absolute():
        path = _match_case(repo, path)   # docs·Docs 표기 무관
    path = path.resolve()
    text = _read_text(path)
    if text is None:
        print(f"FAIL READ_TEXT cannot read: {path}", file=sys.stderr)
        return 2
    doc = _parse_intent(text)
    if not doc.title or doc.part2_line is None:
        print("FAIL PARSE 제목 또는 '## Part 2' 헤딩 없음", file=sys.stderr)
        return 2
    m = INTENT_TITLE_PREFIX_PATTERN.match(doc.title)
    intent_id = (m.group(1) if m else "") or doc.meta.get("문서 ID", "") or path.stem
    expected: list[ExpectedItem] | None = None
    if args.oracle is not None:
        oracle_path = Path(args.oracle)
        if not oracle_path.is_absolute():
            oracle_path = repo / oracle_path
        oracle_path = oracle_path.resolve()
        oracle_text = _read_text(oracle_path)
        if oracle_text is None:
            print(f"FAIL READ_TEXT cannot read: {oracle_path}", file=sys.stderr)
            return 2
        expected, oracle_errors = _parse_expected(oracle_text)
        if oracle_errors:
            for err in oracle_errors:
                print(f"ORACLE: {err}")
            return 2
    rows = _build_checklist(doc, intent_id, args.round, expected)

    if args.check_return is not None:
        ret_path = Path(args.check_return)
        if not ret_path.is_absolute():
            ret_path = repo / ret_path
        ret_path = ret_path.resolve()
        ret_text = _read_text(ret_path)
        if ret_text is None:
            print(f"FAIL READ_TEXT cannot read: {ret_path}", file=sys.stderr)
            return 1
        findings = _check_critic_return(doc, rows, ret_text)
        if not findings:
            print("OK")
            print(f"RETURN-SHA256: {_sha256_file(ret_path)}  {ret_path.name}")
            return 0
        for line in findings:
            print(line)
        return 1

    if args.json:
        payload = {
            "intent": intent_id,
            "round": args.round,
            "rows": [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "target": r.target,
                    "facts": r.facts,
                    "criteria": [
                        {"key": c.key, "text": c.text, "severity": c.severity} for c in r.criteria
                    ],
                    "na_allowed": r.na_allowed,
                    "quote_required": r.quote_required,
                    "line": r.line,
                }
                for r in rows
            ],
            "quote_rows": [r.id for r in rows if r.quote_required],
            "traceability": _checklist_traceability(doc),
        }
        if expected is not None:
            kinds: dict[str, int] = {}
            for item in expected:
                kinds[item.kind] = kinds.get(item.kind, 0) + 1
            payload["oracle"] = {"expected": len(expected), "kinds": kinds}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_checklist_markdown(rows, intent_id, args.round))
    return 0


# ---------------------------------------------------------------------------
# intent-catalog (docs/<App>/<App>-INT-CATALOG.md 생성 · 검사)
# ---------------------------------------------------------------------------


INTENT_CATALOG_SUMMARY_MAX = 50


@dataclass
class CatalogRow:
    """카탈로그 한 행. 값은 전부 Intent 문서에서 파생한다 — 카탈로그 고유 정보는 없다."""

    intent_id: str
    stem: str
    title: str
    kind: str      # 메타 `유형`
    status: str    # 메타 `상태`
    gate: str      # 메타 `검증` 축약
    summary: str   # Outcome 첫 줄
    fr: int
    a: int

    def to_dict(self) -> dict:
        return {
            "id": self.intent_id,
            "file": f"INTENT/{self.stem}.md",
            "title": self.title,
            "type": self.kind,
            "status": self.status,
            "gate": self.gate,
            "summary": self.summary,
            "fr": self.fr,
            "a": self.a,
        }


def _intent_gate_short(value: str) -> str:
    """메타 `검증` 값을 카탈로그 한 칸 폭으로 줄인다. `PASS — code PASS · llm PASS · 2/3` → `PASS 2/3`."""
    v = value.strip()
    if not v:
        return "?"
    m = re.match(r"^(PASS|FAIL|OVERRIDE|SKIPPED)\b", v)
    if m is None:
        return v if len(v) <= 20 else v[:19].rstrip() + "…"
    verdict = m.group(1)
    r = re.search(r"(\d+)/(\d+)", v)
    if r is not None:
        return f"{verdict} {r.group(1)}/{r.group(2)}"
    tail = re.sub(r"^[\s—·]+", "", v[len(verdict):]).strip()
    if tail and len(tail) <= 20:
        return f"{verdict} — {tail}"
    return verdict


def _intent_short_title(doc: IntentDoc, intent_id: str) -> str:
    """H1 에서 `<ID> — ` 접두를 뗀 제목."""
    t = doc.title.strip()
    if not t:
        return "?"
    if intent_id and t.startswith(intent_id):
        t = t[len(intent_id):].lstrip(" —-").strip()
    return t or "?"


def _intent_summary(doc: IntentDoc) -> str:
    """Outcome 본문의 첫 실질 줄(주석·Out of scope 제외)을 잘라 쓴다."""
    for _, line in _intent_live_lines(doc, "Outcome"):
        text = re.sub(r"^[-*]\s+", "", line.strip()).strip()
        if not text or line.strip().startswith("- Out of scope:"):
            continue
        if len(text) > INTENT_CATALOG_SUMMARY_MAX:
            text = text[:INTENT_CATALOG_SUMMARY_MAX - 1].rstrip() + "…"
        return text
    return "?"


def _collect_intent_rows(repo: Path, app: str) -> tuple[list[CatalogRow], list[str]]:
    """docs/<App>/INTENT/<App>-INT-<NNN>.md 를 파싱해 카탈로그 행으로 만든다."""
    intent_dir = _docs_root(repo) / app / "INTENT"
    rows: list[CatalogRow] = []
    skipped: list[str] = []
    if not intent_dir.is_dir():
        return rows, skipped
    pat = INTENT_FILENAME_PATTERN(app)
    for f in sorted(intent_dir.glob("*.md")):
        if not pat.match(f.name):
            skipped.append(f.name)
            continue
        text = _read_text(f)
        if text is None:
            skipped.append(f.name)
            continue
        doc = _parse_intent(text)
        intent_id = (doc.meta.get("문서 ID") or "").strip() or f.stem
        rows.append(CatalogRow(
            intent_id=intent_id,
            stem=f.stem,
            title=_intent_short_title(doc, intent_id),
            kind=(doc.meta.get("유형") or "").strip() or "?",
            status=(doc.meta.get("상태") or "").strip() or "?",
            gate=_intent_gate_short(doc.meta.get("검증") or ""),
            summary=_intent_summary(doc),
            fr=len(doc.items["FR"]),
            a=len(doc.items["A"]),
        ))
    return rows, skipped


def _render_intent_catalog(app: str, rows: list[CatalogRow]) -> str:
    """카탈로그 마크다운 전문. 타임스탬프를 넣지 않는다 — stale 비교가 항상 불일치가 되기 때문."""
    out = [
        f"# {app}-INT-CATALOG — {app} Intent Catalog",
        "",
        f"> **생성물** — `docs_helpers.py intent-catalog --repo . --app {app} --write` 가 "
        "`INTENT/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — 값을 바꾸려면 해당 Intent 문서를 "
        f"고치고 재생성한다. `check --app {app}` 이 불일치를 FAIL 로 잡는다.",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 문서 ID | {app}-INT-CATALOG |",
        "| 생성 | docs_helpers.py intent-catalog |",
        "| 대상 | [INTENT 폴더](INTENT/) |",
        "",
        "| Intent | 제목 | 유형 | 상태 | 검증 | 요약 | 규모 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| [{_md_cell(r.intent_id)}](INTENT/{r.stem}.md) | {_md_cell(r.title)} | "
            f"{_md_cell(r.kind)} | {_md_cell(r.status)} | {_md_cell(r.gate)} | "
            f"{_md_cell(r.summary)} | FR {r.fr} · A {r.a} |"
        )
    out += ["", f"intents: {len(rows)}", ""]
    return "\n".join(out)


def _catalog_row_index(text: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(r"^\|\s*\[([^\]]+)\]\(INTENT/", line)
        if m is not None:
            idx[m.group(1)] = line.strip()
    return idx


def _catalog_diff(actual: str, expected: str, index=_catalog_row_index, tail: str = "intents") -> list[str]:
    """카탈로그 두 본문의 행 단위 차이. index 는 행 키 → 행 사전을 만든다 (intent · task 카탈로그 공용)."""
    a = index(actual)
    e = index(expected)
    out = [f"MISSING {k}" for k in sorted(set(e) - set(a))]
    out += [f"EXTRA {k}" for k in sorted(set(a) - set(e))]
    out += [f"CHANGED {k}" for k in sorted(set(a) & set(e)) if a[k] != e[k]]
    if not out:
        out.append(f"CHANGED (헤더 또는 {tail} 줄)")
    return out


def cmd_intent_catalog(repo: Path, args: argparse.Namespace) -> int:
    """`--json` 은 **출력 포맷 플래그**다 — 동작과 exit code 는 `--check`/`--write` 가 정하고,
    `--json` 은 사람이 읽는 출력 대신 같은 결과를 JSON 으로 낼 뿐이다.
    (cmd_intent_checklist 가 `--check-return` 을 `--json` 보다 먼저 처리하고, cmd_check_intent 가
    `--json` 출력에서도 실패 exit code 를 유지하는 것과 같은 관례.)"""
    app = args.app
    if args.write and args.check:
        print("FAIL ARGS --write 와 --check 는 함께 쓸 수 없다", file=sys.stderr)
        return 2
    docs_dir = _docs_root(repo) / app
    if not docs_dir.is_dir():
        print(f"FAIL ARGS --app not a directory: {docs_dir}", file=sys.stderr)
        return 2
    rows, skipped = _collect_intent_rows(repo, app)
    catalog_path = docs_dir / f"{app}-INT-CATALOG.md"
    rel = _relpath_for(catalog_path, repo)
    # 모든 모드가 공유하는 파생 내용. 마크다운 전문은 실제로 필요한 분기에서만 렌더한다.
    payload = {
        "app": app,
        "catalog": rel,
        "count": len(rows),
        "intents": [r.to_dict() for r in rows],
        "skipped": skipped,
    }

    if args.check:
        text = _render_intent_catalog(app, rows)
        actual = _read_text(catalog_path)
        exists = actual is not None
        if not exists:
            stale, diff = True, []
        elif actual != text:
            stale, diff = True, _catalog_diff(actual, text)
        else:
            stale, diff = False, []
        if args.json:
            payload["check"] = {"exists": exists, "stale": stale, "diff": diff}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif not exists:
            print(f"STALE missing: {rel}")
        elif stale:
            for line in diff:
                print(line)
            print(f"STALE {rel}")
        else:
            print("OK")
            print(f"intents: {len(rows)}")
        return 1 if stale else 0

    if args.write:
        text = _render_intent_catalog(app, rows)
        catalog_path.write_text(text, encoding="utf-8", newline="\n")
        if args.json:
            payload["write"] = {"written": True, "path": rel}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"WROTE {rel} · intents: {len(rows)}")
        return 0

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(_render_intent_catalog(app, rows), end="")
    return 0


# ---------------------------------------------------------------------------
# Task — 레포 루트 .task/TSK-<NNN>.md (파싱 · check-task · task-catalog)
#
# Task 는 작업 계약서다. Intent(기능 문서)의 어느 항목을 어떻게 바꾸는지(Scope 사본),
# 무엇이 되면 완료인지(Acceptance)를 정한다. App 하나에 묶이지 않는다.
# ---------------------------------------------------------------------------


TASK_DIR = ".task"
TASK_CATALOG_NAME = "task-catalog.md"
TASK_FILENAME_PATTERN = re.compile(r"^TSK-(\d{3})\.md$")
TASK_TITLE_PATTERN = re.compile(r"^TSK-\d{3} — .+$")
TASK_TITLE_PREFIX_PATTERN = re.compile(r"^(TSK-\d{3})(?:\s|$)")
TASK_META_EXPECTED = ["문서 ID", "유형", "상태", "대상 Intent", "작성", "승인", "검증"]
TASK_SECTIONS = ("Goal", "Scope", "Acceptance", "Verification", "Risks", "Handoff")
TASK_TYPES = ("기능개발", "버그수정", "리팩토링")
TASK_STATUSES = ("draft", "approved", "in-dev", "in-review", "done", "dropped")
TASK_CLOSED_STATUSES = ("done", "dropped")
# 진행 표시가 Intent 에 붙어 있어야 하는 상태 — in-review 전이(마감)에서 지운다.
TASK_MARKED_STATUSES = ("draft", "approved", "in-dev")
# 유형별로 Scope 에 쓸 수 있는 변경.
TASK_SCOPE_KINDS_BY_TYPE = {
    "기능개발": ("신규", "변경", "삭제"),
    "버그수정": ("위반", "신규"),
    "리팩토링": ("보존",),
}
# Intent 를 바꾸는 변경과 그 항목에 붙는 진행 표시. 위반 · 보존은 Intent 를 바꾸지 않아 표시가 없다.
TASK_MARKER_FOR_KIND = {"신규": "진행 중", "변경": "진행 중", "삭제": "삭제 예정"}

INTENT_ID_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9]*)-INT-\d{3}$")
TASK_SCOPE_LINE_PATTERN = re.compile(
    r"^- (신규|변경|삭제|위반|보존) · ([A-Za-z][A-Za-z0-9]*-INT-\d{3}) ((?:FR|E|X)-\d+)\. (.+)$"
)
TASK_SCOPE_PREV_PATTERN = re.compile(r"^\s+- 이전: (.+)$")
TASK_RISK_PATTERN = re.compile(r"^- R-(\d+)\.\s*(.*)$")
TASK_REF_ITEM_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*-INT-\d{3} (?:FR|E|X)-\d+$")
TASK_REF_RISK_PATTERN = re.compile(r"^R-\d+$")

# 이름 규칙 — 내부 코드 이름은 쓰지 않고, 밖에서 보이는 이름만 바로 앞에 종류를 붙여 백틱으로 쓴다.
# Handoff(`손대지 말 영역` 의 폴더 경로)와 메타 표는 검사하지 않는다.
TASK_NAME_SECTIONS = ("Goal", "Scope", "Acceptance", "Verification", "Risks")
TASK_NAME_KINDS = ("API", "요청 필드", "응답 필드", "설정 키", "오류 코드", "상태 코드")
# "상태 코드 `400` · `503`" 처럼 같은 종류를 잇는 말.
TASK_NAME_LIST_JOINERS = ("·", ",", "/", "또는", "와", "과", "및")
# re.ASCII — 유니코드 \w 는 한글을 단어 문자로 봐서 "정책(" 같은 한글 괄호를 호출로 잡는다.
TASK_NAME_CALL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\((\))?", re.ASCII
)
TASK_NAME_FILE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_\-./])[A-Za-z0-9_\-./]*[A-Za-z0-9_\-]"
    r"\.(?:cs|csproj|sln|py|ts|tsx|js|jsx|java|kt|go|rs|cpp|hpp|vb|fs)\b",
    re.ASCII,
)
TASK_NAME_IDENT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+"   # PascalCase 2단어 이상
    r"|[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+"                        # camelCase
    r"|[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)(?![A-Za-z0-9_])",     # snake_case · SCREAMING_SNAKE
    re.ASCII,
)


@dataclass
class TaskScopeItem:
    kind: str            # 신규 | 변경 | 삭제 | 위반 | 보존
    intent_id: str       # "LOADER-INT-003"
    item_id: str         # "FR-2"
    text: str            # Intent 문장 사본 (refs 그룹 포함, 진행 표시 제외)
    prev: str | None     # 변경 항목의 `이전` 문장
    line: int

    @property
    def key(self) -> str:
        return f"{self.intent_id} {self.item_id}"


@dataclass
class TaskAcceptance:
    id: str              # "A-3"
    num: int
    text: str            # 끝의 근거 괄호를 뗀 본문
    refs: list[str]      # 근거 토큰 — 끝 괄호가 없으면 []
    has_refs: bool
    checked: bool        # "- [ ] A-n." → True, "- A-n." → False
    line: int


@dataclass
class TaskDoc:
    title: str                           # 첫 "# " 이후 텍스트
    has_template_warning: bool
    meta: dict[str, str]
    meta_order: list[str]
    targets: list[str]                   # 대상 Intent 중 ID 형식인 것(중복 제거) — none 이면 []
    sections: dict[str, str]             # "## " 헤딩 텍스트 -> 본문
    section_lines: dict[str, int]
    scope: list[TaskScopeItem]
    scope_bad_lines: list[int]           # Scope 에서 항목 · 이전 · Out of scope 어디에도 맞지 않는 줄
    scope_none: bool                     # Scope 본문(Out of scope 줄 제외)이 정확히 none
    out_of_scope: str | None             # `- Out of scope:` 값 — 줄이 없으면 None
    acceptance: list[TaskAcceptance]
    risks: list[tuple[str, int, int]]    # (R-n, 번호, 줄번호)
    handoff: dict[str, str]
    handoff_order: list[str]
    raw_lines: list[str]


def _kv_table(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """처음 나오는 `| 항목 | 값 |` 표를 (값 사전, 키 순서) 로 읽는다."""
    table: dict[str, str] = {}
    order: list[str] = []
    for i, line in enumerate(lines):
        if _split_table_cells(line) != ["항목", "값"]:
            continue
        for row_line in lines[i + 1:]:
            if not row_line.lstrip().startswith("|"):
                break
            row = _split_table_cells(row_line)
            if len(row) == 2 and not _is_table_separator(row):
                if row[0] not in table:
                    order.append(row[0])
                table[row[0]] = row[1]
        break
    return table, order


def _task_section_live(sections: dict[str, str], section_lines: dict[str, int], name: str) -> list[tuple[int, str]]:
    if name not in sections or name not in section_lines:
        return []
    return _live_lines(sections[name], section_lines[name] + 1)


def _task_live_lines(doc: TaskDoc, name: str) -> list[tuple[int, str]]:
    """섹션 본문을 (파일 줄번호, 줄) 목록으로 돌려준다. HTML 주석 부분은 제거한다."""
    return _task_section_live(doc.sections, doc.section_lines, name)


def _parse_task(text: str) -> TaskDoc:
    """Task 문서 텍스트를 파싱한다. 잘못된 입력에서도 예외를 던지지 않는다."""
    lines = text.split("\n")

    title = ""
    for line in lines:
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            title = m.group(1)
            break

    has_template_warning = any(
        line.lstrip().startswith(">") and "**TEMPLATE**" in line for line in lines
    )
    meta, meta_order = _kv_table(lines)

    targets: list[str] = []
    raw_targets = (meta.get("대상 Intent") or "").strip()
    if raw_targets and raw_targets != "none":
        for token in (t.strip() for t in raw_targets.split("·")):
            if INTENT_ID_PATTERN.match(token) and token not in targets:
                targets.append(token)

    section_lines: dict[str, int] = {}
    section_bodies: dict[str, list[str]] = {}
    current: str | None = None
    for idx, line in enumerate(lines, start=1):
        h2 = re.match(r"^##\s+(.+?)\s*$", line)
        if h2 or re.match(r"^#\s", line):
            current = None
        if h2:
            current = h2.group(1)
            section_lines.setdefault(current, idx)
            section_bodies.setdefault(current, [])
            continue
        if current is not None:
            section_bodies[current].append(line)
    sections = {name: "\n".join(body) for name, body in section_bodies.items()}

    scope: list[TaskScopeItem] = []
    scope_bad_lines: list[int] = []
    none_lines: list[int] = []
    body_texts: list[str] = []          # Out of scope 를 뺀 본문 — none 판정용
    out_of_scope: str | None = None
    last_item: TaskScopeItem | None = None   # 바로 앞 줄이 `이전` 없는 항목일 때만
    for lineno, live in _task_section_live(sections, section_lines, "Scope"):
        line = live.rstrip()
        if not line.strip():
            last_item = None
            continue
        m = TASK_SCOPE_LINE_PATTERN.match(line)
        if m:
            last_item = TaskScopeItem(
                kind=m.group(1), intent_id=m.group(2), item_id=m.group(3),
                text=m.group(4).strip(), prev=None, line=lineno,
            )
            scope.append(last_item)
            body_texts.append(line)
            continue
        pm = TASK_SCOPE_PREV_PATTERN.match(line)
        if pm and last_item is not None:
            last_item.prev = pm.group(1).strip()
            last_item = None
            continue
        last_item = None
        om = INTENT_OUT_OF_SCOPE_PATTERN.match(line)
        if om:
            out_of_scope = om.group(1).strip()
            continue
        body_texts.append(line)
        if line.strip() == "none":
            none_lines.append(lineno)
        else:
            scope_bad_lines.append(lineno)
    if scope:
        scope_bad_lines = sorted(scope_bad_lines + none_lines)
    scope_none = "\n".join(body_texts).strip() == "none"

    acceptance: list[TaskAcceptance] = []
    for lineno, live in _task_section_live(sections, section_lines, "Acceptance"):
        m = INTENT_ITEM_PATTERNS["A"].match(live.rstrip())
        if not m:
            continue
        body = m.group(4).strip()
        g = INTENT_REF_GROUP_PATTERN.match(body)
        if g:
            text_part, refs, has_refs = g.group(1).rstrip(), [t.strip() for t in g.group(2).split(",")], True
        else:
            text_part, refs, has_refs = body, [], False
        acceptance.append(TaskAcceptance(
            id=f"A-{m.group(3)}", num=int(m.group(3)), text=text_part, refs=refs,
            has_refs=has_refs, checked=m.group(1) is not None, line=lineno,
        ))

    risks: list[tuple[str, int, int]] = []
    for lineno, live in _task_section_live(sections, section_lines, "Risks"):
        m = TASK_RISK_PATTERN.match(live.rstrip())
        if m:
            risks.append((f"R-{m.group(1)}", int(m.group(1)), lineno))

    handoff, handoff_order = _kv_table(sections.get("Handoff", "").split("\n"))

    return TaskDoc(
        title=title,
        has_template_warning=has_template_warning,
        meta=meta,
        meta_order=meta_order,
        targets=targets,
        sections=sections,
        section_lines=section_lines,
        scope=scope,
        scope_bad_lines=scope_bad_lines,
        scope_none=scope_none,
        out_of_scope=out_of_scope,
        acceptance=acceptance,
        risks=risks,
        handoff=handoff,
        handoff_order=handoff_order,
        raw_lines=lines,
    )


def _intent_path(repo: Path, intent_id: str) -> Path | None:
    """Intent ID → docs/<App>/INTENT/<ID>.md 의 디스크 표기 경로 (docs·Docs 무관). ID 형식이 아니면 None."""
    m = INTENT_ID_PATTERN.match(intent_id)
    if m is None:
        return None
    return _match_case(repo, Path("docs") / m.group(1) / "INTENT" / f"{intent_id}.md")


def _intent_item_by_id(doc: IntentDoc, item_id: str) -> IntentItem | None:
    for it in doc.items.get(item_id.split("-", 1)[0], []):
        if it.id == item_id:
            return it
    return None


# ---------------------------------------------------------------------------
# check-task — rule set A(형식) · B(항목) · C(대상 Intent 대조)
# ---------------------------------------------------------------------------


@dataclass
class _TaskCtx:
    repo: Path
    path: Path
    stem: str
    intents: dict[str, IntentDoc | None]       # 대상 Intent ID -> 파싱 결과 (파일이 없으면 None)
    intent_paths: dict[str, Path | None]


def _task_status(doc: TaskDoc) -> str:
    return (doc.meta.get("상태") or "").strip()


def _task_id(doc: TaskDoc, ctx: _TaskCtx) -> str:
    return (doc.meta.get("문서 ID") or "").strip() or ctx.stem


def _task_body_is_none(doc: TaskDoc, name: str) -> bool:
    """섹션 본문(주석 제거)이 정확히 `none` 인지."""
    return "\n".join(text for _, text in _task_live_lines(doc, name)).strip() == "none"


def _task_rule_template_warning(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if doc.has_template_warning:
        return [CheckResult("FAIL", "TSK_TEMPLATE_WARNING", "TEMPLATE 경고 블록이 남아 있다", ctx.path)]
    return [CheckResult("PASS", "TSK_TEMPLATE_WARNING", "TEMPLATE 경고 블록 없음", ctx.path)]


def _task_rule_title(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if TASK_TITLE_PATTERN.match(doc.title):
        return [CheckResult("PASS", "TSK_TITLE", f"제목 형식 일치: {doc.title}", ctx.path)]
    return [CheckResult("FAIL", "TSK_TITLE", f"제목이 'TSK-<NNN> — <제목>' 형식이 아님: {doc.title!r}", ctx.path)]


def _task_rule_id_filename(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    m = TASK_TITLE_PREFIX_PATTERN.match(doc.title)
    title_prefix = m.group(1) if m else ""
    meta_id = doc.meta.get("문서 ID", "")
    if title_prefix and ctx.stem == meta_id == title_prefix:
        return [CheckResult("PASS", "TSK_ID_FILENAME", f"파일명·문서 ID·제목 접두 일치: {ctx.stem}", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_ID_FILENAME",
        f"파일명={ctx.stem}, 문서 ID={meta_id!r}, 제목 접두={title_prefix!r}",
        ctx.path,
    )]


def _task_rule_location(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """Task 는 레포 루트 `.task/` 바로 아래에만 둔다 — 폴더 이름은 소문자 그대로."""
    parent = ctx.path.parent
    if parent.name == TASK_DIR and parent == (ctx.repo / TASK_DIR).resolve():
        return [CheckResult("PASS", "TSK_LOCATION", f"위치 일치: {TASK_DIR}/", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_LOCATION",
        f"Task 는 레포 루트 {TASK_DIR}/TSK-<NNN>.md 에 둔다: {_relpath_for(ctx.path, ctx.repo)}",
        ctx.path,
    )]


def _task_rule_meta_rows(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if doc.meta_order == TASK_META_EXPECTED:
        return [CheckResult("PASS", "TSK_META_ROWS", "메타 7행 순서 일치", ctx.path)]
    missing = [k for k in TASK_META_EXPECTED if k not in doc.meta_order]
    extra = [k for k in doc.meta_order if k not in TASK_META_EXPECTED]
    actual = [k for k in doc.meta_order if k in TASK_META_EXPECTED]
    problems = []
    if missing:
        problems.append(f"없음: {missing}")
    if extra:
        problems.append(f"추가: {extra}")
    if not problems:
        problems.append(f"순서 불일치: {actual}")
    return [CheckResult("FAIL", "TSK_META_ROWS", f"메타 행 불일치 — {', '.join(problems)}", ctx.path)]


def _task_rule_type_single(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.meta.get("유형")
    if value in TASK_TYPES:
        return [CheckResult("PASS", "TSK_TYPE_SINGLE", f"유형 단일: {value}", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_TYPE_SINGLE", f"유형이 '기능개발'/'버그수정'/'리팩토링' 중 하나가 아님: {value!r}", ctx.path,
    )]


def _task_rule_status(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.meta.get("상태")
    if value in TASK_STATUSES:
        return [CheckResult("PASS", "TSK_STATUS", f"상태 허용값: {value}", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_STATUS", f"상태가 허용값({'|'.join(TASK_STATUSES)})이 아님: {value!r}", ctx.path,
    )]


def _task_rule_author_format(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.meta.get("작성", "")
    if INTENT_AUTHOR_DATE_PATTERN.match(value):
        return [CheckResult("PASS", "TSK_AUTHOR_FORMAT", f"작성 행 형식 일치: {value}", ctx.path)]
    return [CheckResult("FAIL", "TSK_AUTHOR_FORMAT", f"작성 행이 '<작성자> · <YYYY-MM-DD>' 형식이 아님: {value!r}", ctx.path)]


def _task_rule_approval_format(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.meta.get("승인", "")
    if value == "pending" or INTENT_AUTHOR_DATE_PATTERN.match(value):
        return [CheckResult("PASS", "TSK_APPROVAL_FORMAT", f"승인 행 형식 일치: {value}", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_APPROVAL_FORMAT", f"승인 행이 'pending' 또는 '<승인자> · <YYYY-MM-DD>' 형식이 아님: {value!r}", ctx.path,
    )]


def _task_rule_gate_row(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.meta.get("검증", "")
    if value == "pending" or INTENT_GATE_ROW_PATTERN.match(value):
        return [CheckResult("PASS", "TSK_GATE_ROW_FORMAT", f"검증 행 형식 일치: {value}", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_GATE_ROW_FORMAT", f"검증 행이 'pending' 또는 '<총평> — ...' 형식이 아님: {value!r}", ctx.path,
    )]


def _task_rule_targets(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """대상 Intent 는 `<App>-INT-<NNN>` 을 ` · ` 로 나열한다 — App 이 달라도 된다. none 은 Intent 가 없는 영역의 리팩토링만."""
    value = (doc.meta.get("대상 Intent") or "").strip()
    problems: list[str] = []
    if not value:
        problems.append("값이 비어 있음")
    elif value == "none":
        if doc.meta.get("유형") != "리팩토링":
            problems.append("none 은 Intent 가 없는 영역의 리팩토링만 쓸 수 있다")
    else:
        tokens = [t.strip() for t in value.split("·")]
        bad = [t for t in tokens if not INTENT_ID_PATTERN.match(t)]
        if bad:
            problems.append(f"'<App>-INT-<NNN>' 를 ' · ' 로 나열한 형식이 아님: {bad}")
        dup = sorted({t for t in tokens if tokens.count(t) > 1})
        if dup:
            problems.append(f"중복: {dup}")
    if problems:
        return [CheckResult("FAIL", "TSK_TARGETS", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_TARGETS", f"대상 Intent: {value}", ctx.path)]


def _task_rule_sections(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    missing = [name for name in TASK_SECTIONS if name not in doc.sections]
    if not missing:
        return [CheckResult("PASS", "TSK_SECTIONS", "필수 섹션 6개 존재", ctx.path)]
    return [CheckResult("FAIL", "TSK_SECTIONS", f"없는 섹션: {missing}", ctx.path)]


def _task_rule_placeholder(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    hits = _placeholder_hits(doc.raw_lines)
    if not hits:
        return [CheckResult("PASS", "TSK_PLACEHOLDER", "주석·백틱 밖 placeholder 없음", ctx.path)]
    shown = ", ".join(f"{lineno}:{snippet}" for lineno, snippet in hits[:3])
    return [CheckResult("FAIL", "TSK_PLACEHOLDER", f"주석·백틱 밖 placeholder 남음: {shown}", ctx.path)]


def _task_rule_handoff_rows(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if doc.handoff_order == INTENT_HANDOFF_EXPECTED:
        return [CheckResult("PASS", "TSK_HANDOFF_ROWS", "Handoff 5행 순서 일치", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_HANDOFF_ROWS",
        f"Handoff 행 불일치 — 기대 {INTENT_HANDOFF_EXPECTED}, 실제 {doc.handoff_order}",
        ctx.path,
    )]


def _task_rule_branch_placeholder(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    value = doc.handoff.get("브랜치명", "")
    if "{NNN}" in value:
        return [CheckResult("FAIL", "TSK_BRANCH_PLACEHOLDER", f"브랜치명에 placeholder 가 남아 있다: {value}", ctx.path)]
    return [CheckResult("PASS", "TSK_BRANCH_PLACEHOLDER", f"브랜치명 placeholder 없음: {value}", ctx.path)]


def _task_rule_scope_format(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """Scope 는 `- <변경> · <App>-INT-<NNN> <항목 ID>. <Intent 문장>` 줄과 `이전` · `Out of scope` 줄로만 이뤄진다."""
    problems: list[str] = []
    if doc.scope_bad_lines:
        problems.append(
            f"형식 밖 줄 {doc.scope_bad_lines} — '- <변경> · <App>-INT-<NNN> <항목 ID>. <Intent 문장>'"
        )
    if doc.targets and not doc.scope:
        problems.append("대상 Intent 가 있는데 Scope 항목이 없음")
    if (doc.meta.get("대상 Intent") or "").strip() == "none" and not doc.scope_none:
        problems.append("대상 Intent 가 none 인데 Scope 본문이 none 이 아님")
    if problems:
        return [CheckResult("FAIL", "TSK_SCOPE_FORMAT", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_FORMAT", f"Scope 항목 {len(doc.scope)}개 형식 일치", ctx.path)]


def _task_rule_scope_kind(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    kind = doc.meta.get("유형", "")
    allowed = TASK_SCOPE_KINDS_BY_TYPE.get(kind)
    if allowed is None:
        return []   # 유형 자체가 틀렸다 — TSK_TYPE_SINGLE 몫
    bad = [f"{it.kind} · {it.key}" for it in doc.scope if it.kind not in allowed]
    if bad:
        return [CheckResult(
            "FAIL", "TSK_SCOPE_KIND", f"유형 {kind} 에 쓸 수 없는 변경: {bad} (허용: {' · '.join(allowed)})", ctx.path,
        )]
    return [CheckResult("PASS", "TSK_SCOPE_KIND", f"유형 {kind} — 변경 종류 일치", ctx.path)]


def _task_rule_scope_target(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    bad = [it.key for it in doc.scope if it.intent_id not in doc.targets]
    if bad:
        return [CheckResult("FAIL", "TSK_SCOPE_TARGET", f"대상 Intent 에 없는 Intent 의 항목: {bad}", ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_TARGET", "Scope 항목이 모두 대상 Intent 에 속함", ctx.path)]


def _task_rule_scope_prev(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """변경 항목만 바로 아래에 `  - 이전: <바뀌기 전 문장>` 을 갖는다 — dropped 때 Intent 를 되돌리는 근거다."""
    missing = [it.key for it in doc.scope if it.kind == "변경" and not it.prev]
    extra = [it.key for it in doc.scope if it.kind != "변경" and it.prev]
    problems = []
    if missing:
        problems.append(f"변경 항목에 '이전' 줄 없음: {missing}")
    if extra:
        problems.append(f"변경이 아닌 항목에 '이전' 줄: {extra}")
    if problems:
        return [CheckResult("FAIL", "TSK_SCOPE_PREV", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_PREV", "'이전' 줄 일치", ctx.path)]


def _task_rule_scope_dup(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    keys = [it.key for it in doc.scope]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        return [CheckResult("FAIL", "TSK_SCOPE_DUP", f"같은 항목이 두 번 나옴: {dup}", ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_DUP", "Scope 항목 중복 없음", ctx.path)]


def _task_rule_out_of_scope(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if doc.out_of_scope:
        return [CheckResult("PASS", "TSK_OUT_OF_SCOPE", "Out of scope 행 존재", ctx.path)]
    return [CheckResult("FAIL", "TSK_OUT_OF_SCOPE", "Scope 에 값이 있는 '- Out of scope:' 행이 없음", ctx.path)]


def _task_rule_id_order(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """A · R 은 1부터 오름차순(빈 번호 허용, 중복·하강 금지). A 는 1개 이상, R 은 Risks 본문이 none 일 때만 비울 수 있다."""
    results: list[CheckResult] = []
    a = doc.acceptance
    if not a:
        results.append(CheckResult("FAIL", "TSK_ID_ORDER", "A — 항목이 1개도 없음", ctx.path))
    else:
        bad = [it.id for i, it in enumerate(a) if i and it.num <= a[i - 1].num]
        if bad:
            results.append(CheckResult("FAIL", "TSK_ID_ORDER", f"A — 중복·하강: {bad}", ctx.path))
        else:
            results.append(CheckResult("PASS", "TSK_ID_ORDER", f"A 번호 오름차순: {[it.num for it in a]}", ctx.path))
    r = doc.risks
    if not r:
        if _task_body_is_none(doc, "Risks"):
            results.append(CheckResult("PASS", "TSK_ID_ORDER", "R 항목 없음 — none", ctx.path))
        else:
            results.append(CheckResult("FAIL", "TSK_ID_ORDER", "R — 항목이 없는데 본문이 none 이 아님", ctx.path))
    else:
        bad = [rid for i, (rid, num, _) in enumerate(r) if i and num <= r[i - 1][1]]
        if bad:
            results.append(CheckResult("FAIL", "TSK_ID_ORDER", f"R — 중복·하강: {bad}", ctx.path))
        else:
            results.append(CheckResult("PASS", "TSK_ID_ORDER", f"R 번호 오름차순: {[num for _, num, _ in r]}", ctx.path))
    return results


def _task_rule_acceptance_type(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """기능개발 · 버그수정이면 A 는 체크박스, 리팩토링이면 평문 목록이다."""
    value = doc.meta.get("유형")
    if value not in TASK_TYPES:
        return []
    expected = value != "리팩토링"
    offenders = [it.id for it in doc.acceptance if it.checked is not expected]
    if offenders:
        return [CheckResult("FAIL", "TSK_ACCEPTANCE_TYPE", f"유형 {value} — 형식 불일치 항목: {offenders}", ctx.path)]
    return [CheckResult("PASS", "TSK_ACCEPTANCE_TYPE", f"유형 {value} — A 항목 형식 일치", ctx.path)]


def _task_rule_ref_format(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """A 끝 괄호의 근거는 `<App>-INT-<NNN> <항목 ID>` · `R-n` · `OS` · `Goal` 뿐이다 — App 접두 없는 `FR-4` 는 여러 App 에 걸친 Task 에서 모호하다."""
    bad: list[str] = []
    for it in doc.acceptance:
        if not it.has_refs:
            bad.append(f"{it.id} — 근거 괄호 없음")
            continue
        for ref in it.refs:
            if not (TASK_REF_ITEM_PATTERN.match(ref) or TASK_REF_RISK_PATTERN.match(ref) or ref in ("OS", "Goal")):
                bad.append(f"{it.id} → {ref!r}")
    if bad:
        return [CheckResult(
            "FAIL", "TSK_REF_FORMAT",
            f"근거 형식 밖: {bad} — '<App>-INT-<NNN> <항목 ID>' · 'R-n' · 'OS' · 'Goal'",
            ctx.path,
        )]
    return [CheckResult("PASS", "TSK_REF_FORMAT", "A 근거 형식 일치", ctx.path)]


def _task_rule_ref_dangling(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    scope_keys = {it.key for it in doc.scope}
    risk_ids = {rid for rid, _, _ in doc.risks}
    has_os = bool(doc.out_of_scope) and (doc.out_of_scope or "").lower() != "none"
    dangling: list[str] = []
    for it in doc.acceptance:
        for ref in it.refs:
            if TASK_REF_ITEM_PATTERN.match(ref):
                if ref not in scope_keys:
                    dangling.append(f"{it.id} → {ref} (Scope 에 없음)")
            elif TASK_REF_RISK_PATTERN.match(ref):
                if ref not in risk_ids:
                    dangling.append(f"{it.id} → {ref} (Risks 에 없음)")
            elif ref == "OS":
                if not has_os:
                    dangling.append(f"{it.id} → OS (Out of scope 값 없음)")
            elif ref == "Goal" and doc.targets:
                dangling.append(f"{it.id} → Goal (대상 Intent 가 있으면 그 항목을 근거로 쓴다)")
    if dangling:
        return [CheckResult("FAIL", "TSK_REF_DANGLING", f"가리키는 곳이 없는 근거: {', '.join(dangling)}", ctx.path)]
    return [CheckResult("PASS", "TSK_REF_DANGLING", "모든 근거가 실제 항목을 가리킴", ctx.path)]


def _task_rule_scope_coverage(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """모든 Scope 항목은 A 하나 이상의 근거로 쓰인다 — E · X 항목도 예외가 없다."""
    cited = {ref for it in doc.acceptance for ref in it.refs}
    uncovered = [it.key for it in doc.scope if it.key not in cited]
    if uncovered:
        return [CheckResult("FAIL", "TSK_SCOPE_COVERAGE", f"A 의 근거로 쓰이지 않은 Scope 항목: {uncovered}", ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_COVERAGE", "모든 Scope 항목이 A 의 근거로 쓰임", ctx.path)]


def _task_rule_verify_command(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """Verification 은 확인 '방법' 섹션 — 실행 명령 코드 스팬이면 WARN."""
    spans: list[str] = []
    for _, text in _task_live_lines(doc, "Verification"):
        for m in re.finditer(r"`[^`\n]*`", text):
            span = m.group(0)[1:-1]
            if span.startswith(INTENT_VERIFY_COMMAND_PREFIXES):
                spans.append(span)
    if spans:
        return [CheckResult("WARN", "TSK_VERIFY_COMMAND", f"Verification 에 실행 명령 존재: {spans}", ctx.path)]
    return [CheckResult("PASS", "TSK_VERIFY_COMMAND", "Verification 에 실행 명령 없음", ctx.path)]


def _task_name_lines(doc: TaskDoc) -> list[tuple[str, int, str]]:
    """이름 규칙을 적용할 줄 — (섹션, 줄번호, 주석을 뺀 줄)."""
    out: list[tuple[str, int, str]] = []
    for name in TASK_NAME_SECTIONS:
        for lineno, text in _task_live_lines(doc, name):
            if text.strip():
                out.append((name, lineno, text))
    return out


def _ends_with_name_kind(before: str) -> bool:
    t = before.rstrip()
    for kind in TASK_NAME_KINDS:
        if t.endswith(kind):
            head = t[: -len(kind)]
            if not head or not (head[-1].isascii() and head[-1].isalnum()):   # "XAPI" 는 종류어가 아니다
                return True
    return False


def _task_rule_name_kind(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """백틱은 밖에서 보이는 이름에만 쓰고 바로 앞에 종류를 쓴다 — 응답 필드 `retryCount`."""
    offenders: list[str] = []
    for section, lineno, text in _task_name_lines(doc):
        prev_end, prev_ok = 0, False
        for m in re.finditer(r"`([^`\n]*)`", text):
            span = m.group(1)
            between = text[prev_end:m.start()]
            if section == "Verification" and span.startswith(INTENT_VERIFY_COMMAND_PREFIXES):
                ok = True   # 실행 명령은 TSK_VERIFY_COMMAND 가 따로 알린다
            elif _ends_with_name_kind(between):
                ok = True
            else:
                ok = prev_ok and between.strip() in TASK_NAME_LIST_JOINERS
            if not ok:
                offenders.append(f"{lineno}:`{span}`")
            prev_end, prev_ok = m.end(), ok
    if offenders:
        return [CheckResult(
            "FAIL", "TSK_NAME_KIND",
            f"백틱 이름 앞에 종류({' · '.join(TASK_NAME_KINDS)})가 없음: {offenders[:5]}",
            ctx.path,
        )]
    return [CheckResult("PASS", "TSK_NAME_KIND", "백틱 이름마다 종류가 붙음", ctx.path)]


def _task_rule_name_call(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """`식별자(` 형태의 호출 구문은 내부 코드 이름이다. 한글 · 전부 대문자(`API(결제)`)는 잡지 않는다."""
    offenders: list[str] = []
    for _, lineno, text in _task_name_lines(doc):
        for m in TASK_NAME_CALL_PATTERN.finditer(_strip_code_spans(text)):
            name, empty = m.group(1), m.group(2)
            if not re.search(r"[a-z]", name):
                continue
            if empty or "." in name or "_" in name or re.search(r"[a-z0-9][A-Z]", name):
                offenders.append(f"{lineno}:{name}(")
    if offenders:
        return [CheckResult("FAIL", "TSK_NAME_CALL", f"코드 호출 구문: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "TSK_NAME_CALL", "코드 호출 구문 없음", ctx.path)]


def _task_rule_name_file(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    offenders: list[str] = []
    for _, lineno, text in _task_name_lines(doc):
        for m in TASK_NAME_FILE_PATTERN.finditer(_strip_code_spans(text)):
            offenders.append(f"{lineno}:{m.group(0)}")
    if offenders:
        return [CheckResult("FAIL", "TSK_NAME_FILE", f"소스 파일 이름: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "TSK_NAME_FILE", "소스 파일 이름 없음", ctx.path)]


def _task_rule_name_ident(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    hits: list[str] = []
    for _, lineno, text in _task_name_lines(doc):
        for m in TASK_NAME_IDENT_PATTERN.finditer(_strip_code_spans(text)):
            hits.append(f"{lineno}:{m.group(0)}")
    if hits:
        return [CheckResult(
            "WARN", "TSK_NAME_IDENT",
            f"코드 이름처럼 보이는 영문 토큰: {hits[:5]} — 밖에서 보이는 이름이면 종류를 붙여 백틱으로 쓴다",
            ctx.path,
        )]
    return [CheckResult("PASS", "TSK_NAME_IDENT", "코드 이름처럼 보이는 영문 토큰 없음", ctx.path)]


def _task_rule_intent_exists(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if not doc.targets:
        return []   # none 또는 형식 오류 — TSK_TARGETS 몫
    missing = [i for i in doc.targets if ctx.intents.get(i) is None]
    if missing:
        shown = [f"{i} ({_relpath_for(ctx.intent_paths.get(i), ctx.repo)})" for i in missing]
        return [CheckResult("FAIL", "TSK_INTENT_EXISTS", f"대상 Intent 파일이 없음: {shown}", ctx.path)]
    return [CheckResult("PASS", "TSK_INTENT_EXISTS", f"대상 Intent {len(doc.targets)}개 존재", ctx.path)]


def _task_rule_scope_match(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """Task 는 새 동작을 만들지 않는다 — Scope 문장은 Intent 항목과 글자까지 같다(진행 표시 제외).

    삭제 항목은 마감(in-review) 뒤에는 Intent 에서 사라져 있어야 한다. done · dropped 는 뒤의 Task 가
    같은 항목을 다시 바꿀 수 있어 대조하지 않는다.
    """
    status = _task_status(doc)
    if status in TASK_CLOSED_STATUSES:
        return [CheckResult("PASS", "TSK_SCOPE_MATCH", f"상태 {status} — Intent 대조 건너뜀", ctx.path)]
    problems: list[str] = []
    for it in doc.scope:
        intent = ctx.intents.get(it.intent_id)
        if intent is None:
            continue   # TSK_SCOPE_TARGET · TSK_INTENT_EXISTS 몫
        src = _intent_item_by_id(intent, it.item_id)
        if it.kind == "삭제" and status == "in-review":
            if src is not None:
                problems.append(f"{it.key} 마감했는데 Intent 에 남아 있음")
            continue
        if src is None:
            problems.append(f"{it.key} Intent 에 없음")
        elif src.body != it.text:
            problems.append(f"{it.key} 문장이 Intent 와 다름")
    if problems:
        return [CheckResult("FAIL", "TSK_SCOPE_MATCH", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_MATCH", "Scope 문장이 Intent 와 일치", ctx.path)]


def _task_rule_marker(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """진행 표시는 Scope 의 신규 · 변경 · 삭제와 1:1 이다. 마감(in-review) 뒤에는 이 Task 의 표시가 남지 않는다."""
    status = _task_status(doc)
    task_id = _task_id(doc, ctx)
    expect = status in TASK_MARKED_STATUSES
    by_key = {it.key: it for it in doc.scope}
    problems: list[str] = []
    for intent_id in doc.targets:
        intent = ctx.intents.get(intent_id)
        if intent is None:
            continue
        for kind in ("FR", "E", "X"):
            for item in intent.items[kind]:
                key = f"{intent_id} {item.id}"
                mine = item.marker is not None and item.marker[0] == task_id
                if not expect:
                    if mine:
                        problems.append(f"{key} [{task_id} {item.marker[1]}] 가 남아 있음")
                    continue
                sc = by_key.get(key)
                want = TASK_MARKER_FOR_KIND.get(sc.kind) if sc is not None else None
                if want is not None:
                    if item.marker != (task_id, want):
                        actual = f"[{item.marker[0]} {item.marker[1]}]" if item.marker else "없음"
                        problems.append(f"{key} 기대 [{task_id} {want}], 실제 {actual}")
                elif mine:
                    where = "Scope 밖" if sc is None else sc.kind
                    problems.append(f"{key} {where} 항목에 [{task_id} {item.marker[1]}] 가 붙음")
    if problems:
        return [CheckResult("FAIL", "TSK_MARKER", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_MARKER", f"진행 표시 일치 (상태 {status or '?'})", ctx.path)]


def _task_rule_conflict(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """한 항목은 한 Task 만 바꾼다 — 끝나지 않은 다른 Task 와 Scope 항목이 겹치고, 어느 한쪽이 그 항목을 바꾸면(신규 · 변경 · 삭제) FAIL."""
    status = _task_status(doc)
    if status in TASK_CLOSED_STATUSES:
        return [CheckResult("PASS", "TSK_CONFLICT", f"상태 {status} — 충돌 검사 건너뜀", ctx.path)]
    mine = {it.key: it.kind for it in doc.scope}
    conflicts: list[str] = []
    task_dir = ctx.repo / TASK_DIR
    if mine and task_dir.is_dir():
        for f in sorted(task_dir.glob("*.md")):
            if not TASK_FILENAME_PATTERN.match(f.name) or f.resolve() == ctx.path:
                continue
            text = _read_text(f)
            if text is None:
                continue
            other = _parse_task(text)
            if _task_status(other) in TASK_CLOSED_STATUSES:
                continue
            for it in other.scope:
                kind = mine.get(it.key)
                if kind is not None and (kind in TASK_MARKER_FOR_KIND or it.kind in TASK_MARKER_FOR_KIND):
                    conflicts.append(f"{f.stem}: {it.key}")
    if conflicts:
        return [CheckResult(
            "FAIL", "TSK_CONFLICT", f"끝나지 않은 다른 Task 와 Scope 항목이 겹침: {conflicts}", ctx.path,
        )]
    return [CheckResult("PASS", "TSK_CONFLICT", "다른 Task 와 겹치는 Scope 항목 없음", ctx.path)]


def _task_rule_approved_gate(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """`상태: approved` 는 Handoff 에 pending 이 없고, 유형이 한 값이고, 검증이 PASS · OVERRIDE · SKIPPED 로 시작하고, 대상 Intent 의 Open questions 가 모두 none 일 때만 가능하다."""
    if _task_status(doc) != "approved":
        return []
    failed: list[str] = []
    if any(value == "pending" for value in doc.handoff.values()):
        failed.append("Handoff pending")
    if doc.meta.get("유형") not in TASK_TYPES:
        failed.append("유형 not single")
    if not (doc.meta.get("검증") or "").startswith(("PASS", "OVERRIDE", "SKIPPED")):
        failed.append("검증 not PASS/OVERRIDE/SKIPPED")
    open_q = [
        i for i in doc.targets
        if ctx.intents.get(i) is not None and not _intent_body_is_none(ctx.intents[i], "Open questions")
    ]
    if open_q:
        failed.append(f"대상 Intent Open questions != none: {open_q}")
    if failed:
        return [CheckResult("FAIL", "TSK_APPROVED_GATE", ", ".join(failed), ctx.path)]
    return [CheckResult("PASS", "TSK_APPROVED_GATE", "approved 게이트 조건 충족", ctx.path)]


TASK_RULES = (
    # A. 형식
    _task_rule_template_warning,
    _task_rule_title,
    _task_rule_id_filename,
    _task_rule_location,
    _task_rule_meta_rows,
    _task_rule_type_single,
    _task_rule_status,
    _task_rule_author_format,
    _task_rule_approval_format,
    _task_rule_gate_row,
    _task_rule_targets,
    _task_rule_sections,
    _task_rule_placeholder,
    _task_rule_handoff_rows,
    _task_rule_branch_placeholder,
    # B. 항목
    _task_rule_scope_format,
    _task_rule_scope_kind,
    _task_rule_scope_target,
    _task_rule_scope_prev,
    _task_rule_scope_dup,
    _task_rule_out_of_scope,
    _task_rule_id_order,
    _task_rule_acceptance_type,
    _task_rule_ref_format,
    _task_rule_ref_dangling,
    _task_rule_scope_coverage,
    _task_rule_verify_command,
    _task_rule_name_kind,
    _task_rule_name_call,
    _task_rule_name_file,
    _task_rule_name_ident,
    # C. 대상 Intent 대조
    _task_rule_intent_exists,
    _task_rule_scope_match,
    _task_rule_marker,
    _task_rule_conflict,
    _task_rule_approved_gate,
)


def _check_task_file(repo: Path, path: Path) -> list[CheckResult]:
    if not path.is_absolute():
        path = _match_case(repo, path)
    path = path.resolve()

    results: list[CheckResult] = []

    text = _read_text(path)
    if text is None:
        results.append(CheckResult("FAIL", "READ_TEXT", "cannot read", path))
        return results
    results.append(CheckResult("PASS", "READ_TEXT", "readable", path))

    doc = _parse_task(text)
    intents: dict[str, IntentDoc | None] = {}
    intent_paths: dict[str, Path | None] = {}
    for intent_id in doc.targets:
        p = _intent_path(repo, intent_id)
        intent_paths[intent_id] = p
        intent_text = _read_text(p) if p is not None else None
        intents[intent_id] = _parse_intent(intent_text) if intent_text is not None else None
    ctx = _TaskCtx(repo=repo.resolve(), path=path, stem=path.stem, intents=intents, intent_paths=intent_paths)
    for rule in TASK_RULES:
        results.extend(rule(doc, ctx))
    return results


def cmd_check_task(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args.repo)
    return _report_results(repo, _check_task_file(repo, Path(args.file)), args.json)


# ---------------------------------------------------------------------------
# task-catalog — 파생 인덱스 .task/task-catalog.md
# ---------------------------------------------------------------------------


@dataclass
class TaskCatalogRow:
    """task-catalog 한 행. 값은 전부 Task 문서의 H1 · 메타 표에서 파생한다."""

    task_id: str
    stem: str
    title: str
    kind: str                              # 메타 `유형`
    status: str                            # 메타 `상태`
    targets: str                           # 메타 `대상 Intent` 원문
    links: list[tuple[str, str | None]]    # (Intent ID, 카탈로그 기준 링크 — 파일이 없으면 None)

    def to_dict(self) -> dict:
        return {
            "id": self.task_id,
            "file": f"{self.stem}.md",
            "title": self.title,
            "type": self.kind,
            "status": self.status,
            "intents": [{"id": i, "link": link} for i, link in self.links],
        }


def _task_short_title(doc: TaskDoc, task_id: str) -> str:
    """H1 에서 `<ID> — ` 접두를 뗀 제목."""
    t = doc.title.strip()
    if not t:
        return "?"
    if task_id and t.startswith(task_id):
        t = t[len(task_id):].lstrip(" —-").strip()
    return t or "?"


def _collect_task_rows(repo: Path) -> tuple[list[TaskCatalogRow], list[str]]:
    """.task/TSK-<NNN>.md 를 파싱해 카탈로그 행으로 만든다. 카탈로그 자신은 건너뛴다."""
    task_dir = repo / TASK_DIR
    rows: list[TaskCatalogRow] = []
    skipped: list[str] = []
    if not task_dir.is_dir():
        return rows, skipped
    for f in sorted(task_dir.glob("*.md")):
        if f.name == TASK_CATALOG_NAME:
            continue
        if not TASK_FILENAME_PATTERN.match(f.name):
            skipped.append(f.name)
            continue
        text = _read_text(f)
        if text is None:
            skipped.append(f.name)
            continue
        doc = _parse_task(text)
        task_id = (doc.meta.get("문서 ID") or "").strip() or f.stem
        targets = (doc.meta.get("대상 Intent") or "").strip()
        links: list[tuple[str, str | None]] = []
        if targets and targets != "none":
            for token in (t.strip() for t in targets.split("·")):
                if not token:
                    continue
                p = _intent_path(repo, token)
                # 실제 디스크 표기(docs·Docs)로 링크한다 — GitHub · Linux 는 대소문자를 구분한다.
                link = "../" + p.relative_to(repo).as_posix() if p is not None and p.is_file() else None
                links.append((token, link))
        rows.append(TaskCatalogRow(
            task_id=task_id,
            stem=f.stem,
            title=_task_short_title(doc, task_id),
            kind=(doc.meta.get("유형") or "").strip() or "?",
            status=(doc.meta.get("상태") or "").strip() or "?",
            targets=targets,
            links=links,
        ))
    return rows, skipped


def _task_targets_cell(row: TaskCatalogRow) -> str:
    if row.targets == "none":
        return "none"
    if not row.links:
        return "?"
    return " · ".join(
        f"[{_md_cell(i)}]({link})" if link is not None else f"?{_md_cell(i)}" for i, link in row.links
    )


def _render_task_catalog(rows: list[TaskCatalogRow]) -> str:
    """카탈로그 마크다운 전문. 타임스탬프를 넣지 않는다 — stale 비교가 항상 불일치가 되기 때문."""
    out = [
        "# TASK-CATALOG — Task Catalog",
        "",
        "> **생성물** — `docs_helpers.py task-catalog --repo . --write` 가 `.task/` 를 훑어 다시 쓴다. "
        "**직접 고치지 않는다** — 값을 바꾸려면 해당 Task 문서를 고치고 재생성한다. "
        "`check` 가 불일치를 FAIL 로 잡는다.",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        "| 문서 ID | TASK-CATALOG |",
        "| 생성 | docs_helpers.py task-catalog |",
        "| 대상 | [.task 폴더](./) |",
        "",
        "| Task | 설명 | 유형 | 상태 | 대상 Intent |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| [{_md_cell(r.task_id)}]({r.stem}.md) | {_md_cell(r.title)} | "
            f"{_md_cell(r.kind)} | {_md_cell(r.status)} | {_task_targets_cell(r)} |"
        )
    out += ["", f"tasks: {len(rows)}", ""]
    return "\n".join(out)


def _task_catalog_row_index(text: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(r"^\|\s*\[([^\]]+)\]\(TSK-\d{3}\.md\)", line)
        if m is not None:
            idx[m.group(1)] = line.strip()
    return idx


def _check_tasks(repo: Path) -> list[CheckResult]:
    """레포 단위 — .task/ 에 Task 가 있을 때만 task-catalog 최신 여부를 본다. Task 가 없으면 아무 결과도 내지 않는다."""
    rows, _ = _collect_task_rows(repo)
    if not rows:
        return []
    path = repo / TASK_DIR / TASK_CATALOG_NAME
    actual = _read_text(path)
    if actual is None:
        return [CheckResult("FAIL", "TSK_CATALOG", "missing — task-catalog --write 로 생성", path)]
    if actual != _render_task_catalog(rows):
        return [CheckResult("FAIL", "TSK_CATALOG", "stale — task-catalog --write 로 재생성", path)]
    return [CheckResult("PASS", "TSK_CATALOG", f"{len(rows)} tasks 최신", path)]


def cmd_task_catalog(repo: Path, args: argparse.Namespace) -> int:
    """intent-catalog 와 같은 모드 · exit code 다. `--json` 은 출력 포맷 플래그일 뿐이다."""
    if args.write and args.check:
        print("FAIL ARGS --write 와 --check 는 함께 쓸 수 없다", file=sys.stderr)
        return 2
    task_dir = repo / TASK_DIR
    if not task_dir.is_dir():
        print(f"FAIL ARGS no {TASK_DIR}/ folder: {task_dir}", file=sys.stderr)
        return 2
    rows, skipped = _collect_task_rows(repo)
    catalog_path = task_dir / TASK_CATALOG_NAME
    rel = _relpath_for(catalog_path, repo)
    payload = {
        "catalog": rel,
        "count": len(rows),
        "tasks": [r.to_dict() for r in rows],
        "skipped": skipped,
    }

    if args.check:
        text = _render_task_catalog(rows)
        actual = _read_text(catalog_path)
        exists = actual is not None
        if not exists:
            stale, diff = True, []
        elif actual != text:
            stale, diff = True, _catalog_diff(actual, text, index=_task_catalog_row_index, tail="tasks")
        else:
            stale, diff = False, []
        if args.json:
            payload["check"] = {"exists": exists, "stale": stale, "diff": diff}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif not exists:
            print(f"STALE missing: {rel}")
        elif stale:
            for line in diff:
                print(line)
            print(f"STALE {rel}")
        else:
            print("OK")
            print(f"tasks: {len(rows)}")
        return 1 if stale else 0

    if args.write:
        text = _render_task_catalog(rows)
        catalog_path.write_text(text, encoding="utf-8", newline="\n")
        if args.json:
            payload["write"] = {"written": True, "path": rel}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"WROTE {rel} · tasks: {len(rows)}")
        return 0

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(_render_task_catalog(rows), end="")
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(
        description="Intent · Task 문서 검사 helper (intent-catalog · task-catalog 의 --write 외 read-only)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_check = sub.add_parser("check")
    sp_check.add_argument("--repo", required=True)
    sp_check.add_argument("--app", default=None)

    sp_check_intent = sub.add_parser("check-intent")
    sp_check_intent.add_argument("--repo", required=True)
    sp_check_intent.add_argument("--file", required=True)
    sp_check_intent.add_argument("--json", action="store_true")

    sp_checklist = sub.add_parser("intent-checklist")
    sp_checklist.add_argument("--repo", required=True)
    sp_checklist.add_argument("--file", required=True)
    sp_checklist.add_argument("--round", required=True, type=int)
    sp_checklist.add_argument("--json", action="store_true")
    sp_checklist.add_argument("--check-return", dest="check_return", default=None)
    sp_checklist.add_argument("--oracle", dest="oracle", default=None, metavar="PATH", help="인터뷰 오라클 파일(expected.md). 각 줄은 '- EXP-1. <문장> — 출처: Q3/A3 — 종류: 요구' 형식이며 종류는 요구·완료조건·결정·제약·제외·프로세스·배경 중 하나. 주면 EXP 행이 체크리스트 맨 앞에 생성된다.")

    sp_catalog = sub.add_parser("intent-catalog")
    sp_catalog.add_argument("--repo", required=True)
    sp_catalog.add_argument("--app", required=True)
    sp_catalog.add_argument("--write", action="store_true", help="docs/<App>/<App>-INT-CATALOG.md 에 기록한다. 없으면 stdout 으로만 낸다.")
    sp_catalog.add_argument("--check", action="store_true", help="기존 카탈로그가 재생성 결과와 같은지 검사한다. 다르면 exit 1 + 차이 줄.")
    sp_catalog.add_argument("--json", action="store_true", help="출력 포맷만 JSON 으로 바꾼다. --check/--write 의 동작과 exit code 는 그대로다.")

    sp_check_task = sub.add_parser("check-task")
    sp_check_task.add_argument("--repo", required=True)
    sp_check_task.add_argument("--file", required=True, help="Task 문서 경로 (.task/TSK-<NNN>.md, --repo 기준 상대경로 가능)")
    sp_check_task.add_argument("--json", action="store_true")

    sp_task_catalog = sub.add_parser("task-catalog")
    sp_task_catalog.add_argument("--repo", required=True)
    sp_task_catalog.add_argument("--write", action="store_true", help=".task/task-catalog.md 에 기록한다. 없으면 stdout 으로만 낸다.")
    sp_task_catalog.add_argument("--check", action="store_true", help="기존 카탈로그가 재생성 결과와 같은지 검사한다. 다르면 exit 1 + 차이 줄.")
    sp_task_catalog.add_argument("--json", action="store_true", help="출력 포맷만 JSON 으로 바꾼다. --check/--write 의 동작과 exit code 는 그대로다.")

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else (e.code or 0)

    repo = _resolve_repo(args.repo)

    if args.cmd == "check":
        return cmd_check(repo, args.app)
    if args.cmd == "check-intent":
        return cmd_check_intent(args)
    if args.cmd == "intent-checklist":
        return cmd_intent_checklist(args)
    if args.cmd == "intent-catalog":
        return cmd_intent_catalog(repo, args)
    if args.cmd == "check-task":
        return cmd_check_task(args)
    if args.cmd == "task-catalog":
        return cmd_task_catalog(repo, args)
    print(f"FAIL ARGS unknown cmd: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
