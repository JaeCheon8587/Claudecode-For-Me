"""docs_helpers — Intent 문서(intent/<app>/) · 레포 Task 문서(.task/) 검사 helper.

Subcommands:
    check       intent/<app>/ 무결성 검사 — App 폴더 존재 + App 카탈로그 · 상위 카탈로그 최신 여부 (+ .task/ 가 있으면 task-catalog 최신 여부)
    check-intent  Intent 문서(<app>-int-<NNN>.md) 구조 검증 — rule set A·B
    intent-checklist  Intent 문서 검증 기준표(행·코드 facts·인용 표본) 생성 · critic 반환 검사
    intent-catalog  intent/<app>/intent-catalog.md 와 상위 카탈로그 intent/intent-app-catalog.md 생성·검사
    check-task  Task 문서(.task/tsk-<NNN>.md) 검증 — 형식 · 항목 · 대상 Intent 대조
    task-catalog  .task/task-catalog.md 생성·검사 (.task/ 에서 파생)
    ensure-exclude  문서 폴더 · intent/ · .task/ · 작업 폴더를 이 clone 의 .git/info/exclude 에 올린다 (커밋하지 않는 설계 문서)
    intent-base  Intent 를 고치기 전 기준선 사본 .process/intent-base/<ID>.md 저장 · 소비 (requirement-spec · task-split)
    intent-diff  기준선과 지금 Intent 를 비교해 바뀐 항목(신규 · 변경 · 삭제)과 Task Scope 줄을 낸다
    mark-intent  Task Scope 대로 대상 Intent 에 진행 표시를 붙인다 (--remove 면 걷어 낸다)
    split-check  /task-split 이 만든 Task 묶음이 바뀐 항목을 정확히 한 번씩 나눴는지 검사

파일을 쓰는 것은 `intent-catalog --write` · `task-catalog --write` · `ensure-exclude` · `intent-base` · `mark-intent` 뿐이고,
나머지 서브커맨드는 read-only 다.
Intent 폴더는 레포 루트 `intent/`, Task 폴더는 `.task/` 다 — 폴더 · 파일명 · 문서 ID 모두 소문자다
(항목 번호 FR-1 · A-1 등만 대문자). 옛 표기(docs/<App>/INTENT/, TSK-001.md)는 읽지 않는다.

Standard library only. Windows PowerShell 호환.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# App 이름 · Intent ID 의 App 부분 — 소문자 하나로 정한다. Intent 관련 패턴은 모두 이것에서 만든다.
APP_RE = r"[a-z][a-z0-9]*"
APP_CODE_PATTERN = re.compile(rf"^{APP_RE}$")

INTENT_FILENAME_PATTERN = lambda app: re.compile(rf"^{re.escape(app)}-int-(\d{{3}})\.md$")

# 루트 Intent 폴더 · 카탈로그 이름. App 카탈로그는 intent/<app>/ 안, 상위 카탈로그는 intent/ 바로 아래.
INTENT_DIR = "intent"
INTENT_CATALOG_NAME = "intent-catalog.md"
INTENT_APP_CATALOG_NAME = "intent-app-catalog.md"
# Intent · 카탈로그 폴더에 둔 템플릿 사본은 문서가 아니다.
TEMPLATE_SUFFIX = "-template.md"

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


def _exact_file(path: Path) -> bool:
    """대소문자까지 같은 이름의 파일이 있는가 — 대소문자 무시 FS(Windows · macOS)의 is_file() 은
    `Loader-INT-003.md` 가 있으면 `loader-int-003.md` 도 있다고 답한다. 옛 표기 파일을 없는 것으로 본다."""
    try:
        return path.is_file() and path.name in os.listdir(path.parent)
    except OSError:
        return False


def _intent_root(repo: Path) -> Path:
    return repo / INTENT_DIR


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


def _scan_intent_apps(repo: Path) -> list[str]:
    root = _intent_root(repo)
    if not root.is_dir():
        return []
    out: list[str] = []
    for p in sorted(root.iterdir()):
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
    app_dir = _intent_root(repo) / app
    if not app_dir.is_dir():
        results.append(CheckResult("FAIL", "APP_DIR", "missing", app_dir))
        return results
    results.append(CheckResult("PASS", "APP_DIR", "exists", app_dir))

    # Intent 를 실제로 쓰는 App 에서만 검사한다 — 폴더가 비어 있으면 카탈로그를 요구하지 않는다.
    intent_rows, _ = _collect_intent_rows(repo, app)
    if intent_rows:
        int_catalog_path = app_dir / INTENT_CATALOG_NAME
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
        apps = [app.lower()]
    else:
        apps = _scan_intent_apps(repo)
        if not apps:
            print("FAIL APPS no app found via intent/<app>/ scan")
            return 2

    results: list[CheckResult] = []
    for a in apps:
        results.extend(_check_app(repo, a))
    # 상위 카탈로그는 레포 단위다 — --app 을 줘도 검사한다 (Intent 가 없으면 결과가 없다).
    results.extend(_check_app_catalog(repo))
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
    kind: str                 # "D" | "C" | "OS" | "FR" | "E" | "X"
    id: str                   # "D1", "C2", "OS3", "FR-4", "E-1", "X-2"
    num: int
    text: str                 # id 접두·끝의 refs 그룹을 제외한 본문
    refs: list[str]           # e.g. ["D1", "C2"], ["FR-3", "OS"]; 없으면 []
    line: int                 # 파일 내 1-based 줄번호
    body: str = ""            # id 접두 뒤 문장 전체(refs 그룹 포함, 진행 표시 제외) — Task Scope 사본과 대조
    marker: tuple[str, str] | None = None   # 줄 끝 진행 표시 ("tsk-012", "진행 중"|"삭제 예정"); 없으면 None


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
    raw_lines: list[str]


INTENT_ITEM_KINDS = ("D", "C", "OS", "FR", "E", "X")

INTENT_ITEM_PATTERNS: dict[str, re.Pattern[str]] = {
    "D": re.compile(r"^- (D)(\d+)\.\s*(.*)$"),
    "C": re.compile(r"^- (C)(\d+)\.\s*(.*)$"),
    "FR": re.compile(r"^- (FR)-(\d+)\.\s*(.*)$"),
    "E": re.compile(r"^- (E)-(\d+)\.\s*(.*)$"),
    "X": re.compile(r"^- (X)-(\d+)\.\s*(.*)$"),
}

INTENT_SECTION_FOR_KIND = {
    "D": "Decisions",
    "C": "Constraints",
    "FR": "Functional requirements",
    "E": "Edge cases",
    "X": "Error cases",
}

INTENT_OUT_OF_SCOPE_PATTERN = re.compile(r"^- Out of scope:\s*(.*)$", re.MULTILINE)
# Task 가 바꾸는 항목의 줄 끝(refs 그룹 뒤)에 붙는 진행 표시 — refs 를 떼기 전에 먼저 뗀다.
PROGRESS_MARKER_PATTERN = re.compile(r"\s*\[(tsk-\d{3}) (진행 중|삭제 예정)\]\s*$")
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


INTENT_SECTION_BOUNDARY_PATTERN = re.compile(r"^(?:#{2,3}\s|-{3,}\s*$)")


def _intent_section_boundary(live_line: str) -> bool:
    """Intent 섹션이 끝나는 줄 — `##` · `###` 헤딩이나 `---` 구분선. 주석을 뺀 줄로 판단한다.

    파싱(_parse_intent) · 진행 표시(apply_task_marks) · 표시 정리(clear_task_marks)가 같은 경계를 써야
    변경 목록과 표시가 같은 항목을 본다 — `####` 소제목은 섹션을 끝내지 않는다.
    """
    return INTENT_SECTION_BOUNDARY_PATTERN.match(live_line.rstrip("\r")) is not None


def _parse_intent(text: str) -> IntentDoc:
    """Intent 문서 텍스트를 파싱한다. 잘못된 입력에서도 예외를 던지지 않는다.

    섹션 경계와 항목은 HTML 주석을 뺀 줄에서 찾는다 — 주석 안의 `### …` · `- FR-1. …` 은 섹션도 항목도 아니다.
    """
    lines = text.split("\n")
    live_lines = [live for _, live in _live_lines(text, 1)]

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
    section_bodies: dict[str, list[tuple[int, str]]] = {}   # 원문 줄 — sections 본문(주석 포함)
    section_live: dict[str, list[tuple[int, str]]] = {}     # 주석을 뺀 줄 — 항목 · 표
    part1_line: int | None = None
    part2_line: int | None = None
    current: str | None = None
    for idx, (line, live) in enumerate(zip(lines, live_lines), start=1):
        h3 = re.match(r"^###\s+(.+?)\s*$", live)
        h2 = re.match(r"^##\s+(.+?)\s*$", live)
        if _intent_section_boundary(live):
            current = None
        if h3:
            name = h3.group(1)
            current = name
            section_lines[name] = idx
            section_bodies.setdefault(name, [])
            section_live.setdefault(name, [])
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
            section_live[current].append((idx, live))
    sections = {name: "\n".join(l for _, l in body) for name, body in section_bodies.items()}

    items: dict[str, list[IntentItem]] = {kind: [] for kind in INTENT_ITEM_KINDS}
    for kind, pattern in INTENT_ITEM_PATTERNS.items():
        for lineno, line in section_live.get(INTENT_SECTION_FOR_KIND[kind], []):
            m = pattern.match(line.rstrip())
            if not m:
                continue
            num_s, body = m.group(2), m.group(3)
            marker: tuple[str, str] | None = None
            mm = PROGRESS_MARKER_PATTERN.search(body)
            if mm is not None:
                marker = (mm.group(1), mm.group(2))
                body = body[:mm.start()]
            text_part, refs = _split_intent_refs(body)
            prefix = f"{kind}-" if kind in ("FR", "E", "X") else kind
            items[kind].append(IntentItem(
                kind=kind,
                id=f"{prefix}{num_s}",
                num=int(num_s),
                text=text_part,
                refs=refs,
                line=lineno,
                body=body.strip(),
                marker=marker,
            ))

    for lineno, line in section_live.get("Outcome", []):
        m = INTENT_OUT_OF_SCOPE_PATTERN.match(line.rstrip())
        if not m:
            continue
        value = m.group(1).strip()
        if value.lower() == "none":
            continue
        for i, token in enumerate(_split_top_level_commas(value), start=1):
            items["OS"].append(IntentItem("OS", f"OS{i}", i, token, [], lineno))

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
        raw_lines=lines,
    )


# ---------------------------------------------------------------------------
# check-intent (Intent v2.0 문서 구조 검증 — rule set A·B)
# ---------------------------------------------------------------------------


INTENT_META_EXPECTED = ["문서 ID", "기능 ID", "상태", "작성", "관련 Intent"]
# v1(3.74 이하) Intent 에만 있던 메타 행 · Part 2 섹션 — 작업 지시(유형 · 승인 · 검증 · 완료 조건 · 확인 · 위험 · 착수)는 Task 로 갔다.
INTENT_LEGACY_META = ("유형", "승인", "검증")
INTENT_LEGACY_SECTIONS = ("Acceptance", "Verification", "Risks", "Handoff")
INTENT_STATUSES = ("active", "retired")
INTENT_PART1_SECTIONS = ("Problem", "Outcome", "Affected", "Constraints", "Decisions", "Open questions")
INTENT_PART2_SECTIONS = ("Functional requirements", "Edge cases", "Error cases")

INTENT_TITLE_PATTERN = re.compile(rf"^{APP_RE}-int-\d{{3}} — .+$")
INTENT_TITLE_PREFIX_PATTERN = re.compile(rf"^({APP_RE}-int-\d{{3}})(?:\s|$)")
INTENT_AUTHOR_DATE_PATTERN = re.compile(r"^.+ · \d{4}-\d{2}-\d{2}$")
INTENT_GATE_ROW_PATTERN = re.compile(r"^(PASS|FAIL|OVERRIDE|SKIPPED) — .+$")   # Task `검증` 행
INTENT_FEATURE_ID_PATTERN = re.compile(r"^F\d{3}$")
INTENT_LEGACY_HINT = " — v1(3.74 이하) 형식이다. requirement-spec 수정 모드가 v2 로 옮긴다"


@dataclass
class _IntentCtx:
    path: Path
    stem: str
    repo: Path


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
    return [CheckResult("FAIL", "INT_TITLE", f"제목이 '<app>-int-<NNN> — <기능 이름>' 형식이 아님: {doc.title!r}", ctx.path)]


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
        return [CheckResult("PASS", "INT_META_ROWS", f"메타 {len(INTENT_META_EXPECTED)}행 순서 일치", ctx.path)]
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
    hint = INTENT_LEGACY_HINT if any(k in doc.meta for k in INTENT_LEGACY_META) else ""
    return [CheckResult("FAIL", "INT_META_ROWS", f"메타 행 불일치 — {detail}{hint}", ctx.path)]


def _intent_rule_feature_id(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """기능 ID 는 App PRD §7 기능 목록의 행 — 기능 1개 = Intent 1개."""
    if "기능 ID" not in doc.meta:
        return []   # 행 자체가 없다 — INT_META_ROWS 몫
    value = doc.meta["기능 ID"].strip()
    if INTENT_FEATURE_ID_PATTERN.match(value):
        return [CheckResult("PASS", "INT_FEATURE_ID", f"기능 ID: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_FEATURE_ID", f"기능 ID 가 'F<NNN>' 형식이 아님: {value!r}", ctx.path)]


def _intent_rule_status(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("상태")
    if value in INTENT_STATUSES:
        return [CheckResult("PASS", "INT_STATUS", f"상태 허용값: {value}", ctx.path)]
    hint = INTENT_LEGACY_HINT if any(k in doc.meta for k in INTENT_LEGACY_META) else ""
    return [CheckResult(
        "FAIL", "INT_STATUS", f"상태가 허용값({'|'.join(INTENT_STATUSES)})이 아님: {value!r}{hint}", ctx.path,
    )]


def _intent_rule_author_format(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    value = doc.meta.get("작성", "")
    if INTENT_AUTHOR_DATE_PATTERN.match(value):
        return [CheckResult("PASS", "INT_AUTHOR_FORMAT", f"작성 행 형식 일치: {value}", ctx.path)]
    return [CheckResult("FAIL", "INT_AUTHOR_FORMAT", f"작성 행이 '<작성자> · <YYYY-MM-DD>' 형식이 아님: {value!r}", ctx.path)]


def _intent_rule_related(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """관련 Intent 는 none 이거나 Intent ID 를 ` · ` 로 나열한다 — 계약을 주고받는 다른 App 의 Intent 도 여기에 둔다."""
    if "관련 Intent" not in doc.meta:
        return []   # INT_META_ROWS 몫
    value = doc.meta["관련 Intent"].strip()
    if value == "none":
        return [CheckResult("PASS", "INT_RELATED", "관련 Intent 없음", ctx.path)]
    tokens = [t.strip() for t in value.split("·")]
    me = (doc.meta.get("문서 ID") or "").strip() or ctx.stem
    problems: list[str] = []
    bad = [t for t in tokens if not INTENT_ID_PATTERN.match(t)]
    if bad:
        problems.append(f"'<app>-int-<NNN>' 을 ' · ' 로 나열한 형식이 아님: {bad}")
    if me in tokens:
        problems.append("자기 자신을 넣음")
    if problems:
        return [CheckResult("FAIL", "INT_RELATED", ", ".join(problems), ctx.path)]
    missing = [t for t in tokens if (p := _intent_path(ctx.repo, t)) is None or not _exact_file(p)]
    if missing:
        return [CheckResult("WARN", "INT_RELATED", f"관련 Intent 파일이 없다: {missing}", ctx.path)]
    return [CheckResult("PASS", "INT_RELATED", f"관련 Intent: {value}", ctx.path)]


def _intent_rule_part1_headings(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    missing = [name for name in INTENT_PART1_SECTIONS if name not in doc.sections]
    if doc.part1_line is not None and not missing:
        return [CheckResult("PASS", "INT_PART1_HEADINGS", f"Part 1 필수 섹션 {len(INTENT_PART1_SECTIONS)}개 존재", ctx.path)]
    problems = []
    if doc.part1_line is None:
        problems.append("'## Part 1' 헤딩 없음")
    if missing:
        problems.append(f"없는 섹션: {missing}")
    return [CheckResult("FAIL", "INT_PART1_HEADINGS", ", ".join(problems), ctx.path)]


def _intent_rule_part2_headings(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    missing = [name for name in INTENT_PART2_SECTIONS if name not in doc.sections]
    if doc.part2_line is not None and not missing:
        return [CheckResult("PASS", "INT_PART2_HEADINGS", f"Part 2 필수 섹션 {len(INTENT_PART2_SECTIONS)}개 존재", ctx.path)]
    problems = []
    if doc.part2_line is None:
        problems.append("'## Part 2' 헤딩 없음")
    if missing:
        problems.append(f"없는 섹션: {missing}")
    return [CheckResult("FAIL", "INT_PART2_HEADINGS", ", ".join(problems), ctx.path)]


def _intent_rule_legacy_sections(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """완료 조건 · 확인 방법 · 위험 · 착수 정보는 Task 몫이다 — Intent 에 그 섹션이 남아 있으면 v1 문서다."""
    found = [name for name in INTENT_LEGACY_SECTIONS if name in doc.sections]
    if found:
        return [CheckResult("FAIL", "INT_LEGACY_SECTIONS", f"작업 지시 섹션이 남아 있다: {found}{INTENT_LEGACY_HINT}", ctx.path)]
    return [CheckResult("PASS", "INT_LEGACY_SECTIONS", "작업 지시 섹션 없음", ctx.path)]


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


def _intent_rule_placeholder(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    hits = _intent_placeholder_hits(doc)
    if not hits:
        return [CheckResult("PASS", "INT_PLACEHOLDER", "주석·백틱 밖 placeholder 없음", ctx.path)]
    shown = ", ".join(f"{lineno}:{snippet}" for lineno, snippet in hits[:3])
    return [CheckResult("FAIL", "INT_PLACEHOLDER", f"주석·백틱 밖 placeholder 남음: {shown}", ctx.path)]


# ---------------------------------------------------------------------------
# check-intent — rule set B (항목 ID · 참조 · 진행 표시 · 이름)
# ---------------------------------------------------------------------------


INTENT_DECISION_LINE_PATTERN = re.compile(r"^- D\d+\. .+ — 근거: .+ — 기각 대안: .+$")
INTENT_CONSTRAINT_PREFIX_PATTERN = re.compile(r"^- C\d+\. ")
INTENT_ID_ORDER_KINDS = ("D", "C", "FR", "E", "X")
INTENT_VERIFY_COMMAND_PREFIXES = (   # Task Verification 의 실행 명령
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
        if re.match(r"^- ", text) and not INTENT_DECISION_LINE_PATTERN.match(text.rstrip())
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
    """항목 번호는 종류별 오름차순(빈 번호 허용, 중복·하강 금지). FR 은 1개 이상, D·C·E·X 는 본문이 `none` 일 때만 비울 수 있다.

    `retired` Intent 는 FR 도 `none` 일 수 있다 — 기능을 없애는 Task 가 끝나면(done) 삭제 예정 줄이 다 지워진다.
    """
    results: list[CheckResult] = []
    retired = (doc.meta.get("상태") or "").strip() == "retired"
    for kind in INTENT_ID_ORDER_KINDS:
        items = doc.items[kind]
        problems: list[str] = []
        if not items:
            if kind == "FR" and not (retired and _intent_body_is_none(doc, INTENT_SECTION_FOR_KIND[kind])):
                problems.append("항목이 1개도 없음" + (" (retired 면 none 으로 둔다)" if retired else ""))
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
    """FR 은 Dn/Cn 만 인용 가능. E/X 는 Dn/Cn/FR-n/OS 인용 가능. D/C/OS 는 참조 불가. 위반은 WARN."""
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


def _intent_rule_marker(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    """진행 표시는 /task-split 이 붙이고 Task 가 끝나면 지운다 — 끝난 Task 의 표시가 남아 있으면 FAIL, Task 가 없으면 WARN."""
    marks = [(it.id, it.marker) for kind in INTENT_CHANGE_KINDS for it in doc.items[kind] if it.marker is not None]
    if not marks:
        return [CheckResult("PASS", "INT_MARKER", "진행 표시 없음", ctx.path)]
    status = {stem: _task_status(t) for stem, t in _load_tasks(ctx.repo).items()}
    closed = [f"{iid} [{t} {k}] ({status[t]})" for iid, (t, k) in marks if status.get(t) in TASK_CLOSED_STATUSES]
    if closed:
        return [CheckResult(
            "FAIL", "INT_MARKER",
            f"끝난 Task 의 진행 표시가 남아 있다: {closed} — done 은 표시를 지우고, dropped 는 Task Scope 로 되돌린다",
            ctx.path,
        )]
    missing = [f"{iid} [{t} {k}]" for iid, (t, k) in marks if t not in status]
    if missing:
        return [CheckResult("WARN", "INT_MARKER", f"진행 표시의 Task 가 .task/ 에 없다: {missing}", ctx.path)]
    owners = sorted({t for _, (t, _) in marks})
    return [CheckResult("PASS", "INT_MARKER", f"진행 표시 {len(marks)}개 — {' · '.join(owners)}", ctx.path)]


def _intent_name_lines(doc: IntentDoc) -> list[tuple[str, int, str]]:
    """이름 규칙을 적용할 줄 — Part 2(FR · E · X)의 (섹션, 줄번호, 주석을 뺀 줄). Task Scope 가 이 문장을 그대로 옮긴다."""
    out: list[tuple[str, int, str]] = []
    for name in INTENT_PART2_SECTIONS:
        for lineno, text in _intent_live_lines(doc, name):
            if text.strip():
                out.append((name, lineno, text))
    return out


def _intent_rule_name_kind(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    offenders = _name_kind_offenders(_intent_name_lines(doc))
    if offenders:
        return [CheckResult(
            "FAIL", "INT_NAME_KIND",
            f"백틱 이름 앞에 종류({' · '.join(TASK_NAME_KINDS)})가 없음: {offenders[:5]}",
            ctx.path,
        )]
    return [CheckResult("PASS", "INT_NAME_KIND", "백틱 이름마다 종류가 붙음", ctx.path)]


def _intent_rule_name_call(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    offenders = _name_call_offenders(_intent_name_lines(doc))
    if offenders:
        return [CheckResult("FAIL", "INT_NAME_CALL", f"코드 호출 구문: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "INT_NAME_CALL", "코드 호출 구문 없음", ctx.path)]


def _intent_rule_name_file(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    offenders = _name_file_offenders(_intent_name_lines(doc))
    if offenders:
        return [CheckResult("FAIL", "INT_NAME_FILE", f"소스 파일 이름: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "INT_NAME_FILE", "소스 파일 이름 없음", ctx.path)]


def _intent_rule_name_ident(doc: IntentDoc, ctx: _IntentCtx) -> list[CheckResult]:
    hits = _name_ident_hits(_intent_name_lines(doc))
    if hits:
        return [CheckResult(
            "WARN", "INT_NAME_IDENT",
            f"코드 이름처럼 보이는 영문 토큰: {hits[:5]} — 밖에서 보이는 이름이면 종류를 붙여 백틱으로 쓴다",
            ctx.path,
        )]
    return [CheckResult("PASS", "INT_NAME_IDENT", "코드 이름처럼 보이는 영문 토큰 없음", ctx.path)]


INTENT_RULES = (
    _intent_rule_template_warning,
    _intent_rule_title,
    _intent_rule_id_filename,
    _intent_rule_meta_rows,
    _intent_rule_feature_id,
    _intent_rule_status,
    _intent_rule_author_format,
    _intent_rule_related,
    _intent_rule_part1_headings,
    _intent_rule_part2_headings,
    _intent_rule_legacy_sections,
    _intent_rule_out_of_scope,
    _intent_rule_open_questions,
    _intent_rule_placeholder,
    _intent_rule_decision_format,
    _intent_rule_constraint_id,
    _intent_rule_id_order,
    _intent_rule_ref_dangling,
    _intent_rule_ref_kind,
    _intent_rule_marker,
    _intent_rule_name_kind,
    _intent_rule_name_call,
    _intent_rule_name_file,
    _intent_rule_name_ident,
)


def _check_intent_file(repo: Path, path: Path) -> list[CheckResult]:
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()

    results: list[CheckResult] = []

    text = _read_text(path)
    if text is None:
        results.append(CheckResult("FAIL", "READ_TEXT", "cannot read", path))
        return results
    results.append(CheckResult("PASS", "READ_TEXT", "readable", path))

    doc = _parse_intent(text)
    ctx = _IntentCtx(path=path, stem=path.stem, repo=repo)
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
    id: str                   # 항목 ID (D1, C2, OS3, FR-4, E-1, X-2), EXP-n 또는 G-1..G-5
    kind: str                 # D C OS FR E X G EXP
    target: str               # 항목 본문 80자 절삭 (G 행은 "")
    facts: str                # 코드가 뽑은 참조 사실 (G 행은 "")
    criteria: list[ChecklistCriterion]
    na_allowed: bool
    quote_required: bool
    line: int | None          # 항목 파일 줄번호 (G 행은 None)


EXPECTED_KINDS: tuple[str, ...] = ("요구", "완료조건", "결정", "제약", "제외", "프로세스", "배경")

# 대상 — 한 인터뷰가 Intent 여러 개(계약을 주고받는 App 마다)를 쓸 때 그 항목이 담길 Intent. 없으면 모든 Intent.
EXPECTED_LINE_PATTERN = re.compile(
    r"^- (EXP-\d+)\. (.+) — 출처: (Q\d+/A\d+) — 종류: (요구|완료조건|결정|제약|제외|프로세스|배경)"
    rf"(?: — 대상: ({APP_RE}-int-\d{{3}}(?: · {APP_RE}-int-\d{{3}})*))?$"
)


@dataclass
class ExpectedItem:
    id: str
    num: int
    text: str
    source: str
    kind: str
    line: int
    targets: list[str]        # 대상 Intent ID — 비어 있으면 모든 Intent


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
        targets = m.group(5).split(" · ") if m.group(5) else []
        num = int(item_id[4:])
        if item_id in seen:
            errors.append(f"{lineno}: EXP ID 중복 — {item_id}")
        if num <= prev_num:
            errors.append(f"{lineno}: EXP ID 오름차순 아님 — {item_id}")
        seen.add(item_id)
        prev_num = num
        items.append(
            ExpectedItem(id=item_id, num=num, text=item_text, source=source, kind=kind, line=lineno, targets=targets)
        )
    if not items:
        errors.append("expected.md 에 EXP 항목이 없다")
    return items, errors


CHECKLIST_KIND_ORDER = ("OS", "C", "D", "FR", "E", "X")

CHECKLIST_CRITERIA: dict[str, tuple[tuple[str, str, str], ...]] = {
    "D": (("a", "결정이 요구하는 동작이 Part 2(FR · E · X)로 내려왔나 — 동작을 요구하지 않는 결정이면 N/A(이유와 위치)", "MAJOR"),),
    "C": (("a", "제약이 요구하는 동작이 Part 2(FR · E · X)로 내려왔나 — 동작으로 옮길 수 없는 제약이면 N/A(이유와 위치)", "MAJOR"),),
    "OS": (("a", "Part 2 어느 항목도 이 범위의 동작을 정하지 않는다", "MAJOR"),),
    "FR": (
        ("a", "참조 근거가 FR 을 뒷받침 (참조 없으면 Outcome 문단에 근거)", "MAJOR"),
        ("b", "테스트 가능한 문장 — Task 의 완료 조건이 이 문장에서 나온다", "MAJOR"),
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
}

CHECKLIST_NA_ALLOWED: dict[str, bool] = {
    "D": True, "C": True, "OS": False, "FR": False, "E": False, "X": False,
}

EXPECTED_CRITERIA_DESCENT: tuple[tuple[str, str, str], ...] = (
    ("a", "Intent(Part 1 또는 Part 2)에 담겨 있다 — 위치 항목 ID 인용", "MAJOR"),
    ("b", "Part 2 항목(FR/E/X)으로 테스트할 수 있게 내려왔다 — ID 인용", "MAJOR"),
)
EXPECTED_CRITERIA_POSITION: tuple[tuple[str, str, str], ...] = (
    ("a", "Intent 에 담겨 있다 — 제약은 Constraints/FR, 제외는 Out of scope 중 위치 항목 ID 인용", "MAJOR"),
)
EXPECTED_CRITERIA_PROCESS: tuple[tuple[str, str, str], ...] = (
    ("a", "진행 방식(완료 보고 · 브랜치 · 커밋 · 배포 절차)은 Task 몫이다 — Intent 에 동작처럼 섞여 들어가지 않았다", "MINOR"),
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
    "프로세스": EXPECTED_CRITERIA_PROCESS,
    "배경": EXPECTED_CRITERIA_BACKGROUND,
}

CHECKLIST_G_ROWS: tuple[tuple[str, str, str], ...] = (
    ("G-1", "Part 1 내부 모순 없음", "MAJOR"),
    ("G-2", "Part 1 ↔ Part 2 수치·식별자·상태코드·범위 일치", "MAJOR"),
    ("G-3", "내부 코드 이름(클래스 · 인터페이스 · 메서드 · 함수 · 속성 · 필드 · 변수 · 네임스페이스 · 파일 · 라이브러리 API)이 없다 — "
            "밖에서 보이는 이름(API 경로 · 요청/응답 필드 · 설정 키 · 오류/상태 코드 · 화면 문구)만 종류어 + 백틱으로 쓴다. "
            "판별: 코드를 열지 않고 볼 수 있는 이름인가", "MAJOR"),
    ("G-4", "Outcome 문단의 결과가 FR 집합으로 달성 가능", "MAJOR"),
    ("G-5", "Problem 이 Outcome 으로 해소됨", "MINOR"),
)

CHECKLIST_SECTION_NAMES = (
    "Problem", "Outcome", "Affected", "Constraints", "Decisions", "Open questions",
    "Functional requirements", "Edge cases", "Error cases",
)
CHECKLIST_ITEM_ID_PATTERN = re.compile(r"\b(?:D|C|OS)\d+\b|\b(?:FR|E|X)-\d+\b")
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
        (it for kind in ("FR", "E", "X") for it in doc.items[kind]),
        key=lambda it: it.line,
    )

    rows: list[ChecklistRow] = []
    if expected:
        for item in expected:
            rows.append(ChecklistRow(
                id=item.id,
                kind="EXP",
                target=item.text[:80],
                facts=f"출처: {item.source} · 종류: {item.kind}"
                + (f" · 대상: {' · '.join(item.targets)}" if item.targets else ""),
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
                ids = [r.id for r in referencing if "OS" in r.refs]
                facts = f"참조: {', '.join(ids)}" if ids else "참조: 없음"
            elif kind == "FR":
                base = ", ".join(it.refs) if it.refs else "없음"
                ids = [r.id for r in referencing if r.kind in ("E", "X") and it.id in r.refs]
                facts = f"근거: {base} · 참조하는 E/X: {', '.join(ids) if ids else '없음'}"
            else:  # E, X
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
    referenced = {ref for kind in ("FR", "E", "X") for it in doc.items[kind] for ref in it.refs}
    return {
        "fr": len(doc.items["FR"]),
        "fr_with_ref": sum(1 for it in doc.items["FR"] if it.refs),
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
        path = repo / path
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
        expected = [item for item in expected if not item.targets or intent_id in item.targets]
        if not expected:
            print(f"ORACLE: {intent_id} 를 대상으로 한 EXP 항목이 없다 — 대상 표기를 확인한다")
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
# intent-catalog (intent/<app>/intent-catalog.md · intent/intent-app-catalog.md 생성 · 검사)
# ---------------------------------------------------------------------------


INTENT_CATALOG_SUMMARY_MAX = 50


@dataclass
class CatalogRow:
    """카탈로그 한 행. 값은 전부 Intent 문서에서 파생한다 — 카탈로그 고유 정보는 없다."""

    intent_id: str
    stem: str
    title: str
    feature: str        # 메타 `기능 ID`
    status: str         # 메타 `상태`
    tasks: list[str]    # 진행 표시를 단 Task (번호 순)
    summary: str        # Outcome 첫 줄
    fr: int
    e: int
    x: int

    def to_dict(self) -> dict:
        return {
            "id": self.intent_id,
            "file": f"{self.stem}.md",
            "title": self.title,
            "feature": self.feature,
            "status": self.status,
            "tasks": self.tasks,
            "summary": self.summary,
            "fr": self.fr,
            "e": self.e,
            "x": self.x,
        }


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


def _intent_marker_tasks(doc: IntentDoc) -> list[str]:
    """진행 표시를 단 Task ID — 이 기능을 지금 바꾸는 중인 Task."""
    return sorted({it.marker[0] for kind in ("FR", "E", "X") for it in doc.items[kind] if it.marker is not None})


def _collect_intent_rows(repo: Path, app: str) -> tuple[list[CatalogRow], list[str]]:
    """intent/<app>/<app>-int-<NNN>.md 를 파싱해 카탈로그 행으로 만든다. 카탈로그 자신과 템플릿 사본은 건너뛴다."""
    intent_dir = _intent_root(repo) / app
    rows: list[CatalogRow] = []
    skipped: list[str] = []
    if not intent_dir.is_dir():
        return rows, skipped
    pat = INTENT_FILENAME_PATTERN(app)
    for f in sorted(intent_dir.glob("*.md")):
        if f.name == INTENT_CATALOG_NAME or f.name.endswith(TEMPLATE_SUFFIX):
            continue
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
            feature=(doc.meta.get("기능 ID") or "").strip() or "?",
            status=(doc.meta.get("상태") or "").strip() or "?",
            tasks=_intent_marker_tasks(doc),
            summary=_intent_summary(doc),
            fr=len(doc.items["FR"]),
            e=len(doc.items["E"]),
            x=len(doc.items["X"]),
        ))
    return rows, skipped


def _render_intent_catalog(app: str, rows: list[CatalogRow]) -> str:
    """카탈로그 마크다운 전문. 타임스탬프를 넣지 않는다 — stale 비교가 항상 불일치가 되기 때문.

    `진행 중 Task` 는 Task 문서로 잇는다 — 카탈로그(intent/<app>/)에서 레포 루트의 .task/ 까지 두 단계 위다.
    """
    out = [
        f"# {app}-intent-catalog — {app} Intent Catalog",
        "",
        f"> **생성물** — `docs_helpers.py intent-catalog --repo . --app {app} --write` 가 "
        f"`intent/{app}/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — 값을 바꾸려면 해당 Intent 문서를 "
        f"고치고 재생성한다. `check --app {app}` 이 불일치를 FAIL 로 잡는다.",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 문서 ID | {app}-intent-catalog |",
        "| 생성 | docs_helpers.py intent-catalog |",
        f"| 대상 | [{app} 폴더](./) |",
        "",
        "| Intent | 제목 | 기능 ID | 상태 | 진행 중 Task | 요약 | 규모 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        tasks = " · ".join(f"[{t}](../../{TASK_DIR}/{t}.md)" for t in r.tasks) or "none"
        out.append(
            f"| [{_md_cell(r.intent_id)}]({r.stem}.md) | {_md_cell(r.title)} | "
            f"{_md_cell(r.feature)} | {_md_cell(r.status)} | {tasks} | "
            f"{_md_cell(r.summary)} | FR {r.fr} · E {r.e} · X {r.x} |"
        )
    out += ["", f"intents: {len(rows)}", ""]
    return "\n".join(out)


def _catalog_row_index(text: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(rf"^\|\s*\[([^\]]+)\]\({APP_RE}-int-\d{{3}}\.md\)", line)
        if m is not None:
            idx[m.group(1)] = line.strip()
    return idx


@dataclass
class AppCatalogRow:
    """상위 카탈로그 한 행 — App 하나. App 카탈로그와 같은 Intent 행에서 센다."""

    app: str
    count: int
    active: int
    retired: int

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "catalog": f"{self.app}/{INTENT_CATALOG_NAME}",
            "count": self.count,
            "active": self.active,
            "retired": self.retired,
        }


def _collect_app_rows(repo: Path) -> list[AppCatalogRow]:
    """intent/ 아래 App 마다 Intent 수를 센다. Intent 가 하나도 없는 App 폴더는 넣지 않는다."""
    out: list[AppCatalogRow] = []
    for app in _scan_intent_apps(repo):
        rows, _ = _collect_intent_rows(repo, app)
        if not rows:
            continue
        out.append(AppCatalogRow(
            app=app,
            count=len(rows),
            active=sum(1 for r in rows if r.status == "active"),
            retired=sum(1 for r in rows if r.status == "retired"),
        ))
    return out


def _render_app_catalog(rows: list[AppCatalogRow]) -> str:
    """상위 카탈로그 전문 — CLAUDE.md 가 링크하는 Intent 진입점. 타임스탬프를 넣지 않는다."""
    out = [
        "# intent-app-catalog — Intent App Catalog",
        "",
        "> **생성물** — `docs_helpers.py intent-catalog --repo . --app <app> --write` 가 App 카탈로그와 함께 "
        "`intent/` 를 훑어 다시 쓴다. **직접 고치지 않는다** — Intent 문서를 고치고 재생성한다. "
        "`check` 가 불일치를 FAIL 로 잡는다.",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        "| 문서 ID | intent-app-catalog |",
        "| 생성 | docs_helpers.py intent-catalog |",
        f"| 대상 | [{INTENT_DIR} 폴더](./) |",
        "",
        "| App | 카탈로그 | Intents | active | retired |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r.app} | [{r.app}-intent-catalog]({r.app}/{INTENT_CATALOG_NAME}) | "
            f"{r.count} | {r.active} | {r.retired} |"
        )
    out += ["", f"apps: {len(rows)}", ""]
    return "\n".join(out)


def _app_catalog_row_index(text: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(rf"^\|\s*({APP_RE})\s*\|\s*\[", line)
        if m is not None:
            idx[m.group(1)] = line.strip()
    return idx


def _app_catalog_path(repo: Path) -> Path:
    return _intent_root(repo) / INTENT_APP_CATALOG_NAME


def _check_app_catalog(repo: Path) -> list[CheckResult]:
    """check 의 INT_APP_CATALOG — Intent 가 하나도 없으면 아무 줄도 내지 않는다."""
    rows = _collect_app_rows(repo)
    if not rows:
        return []
    path = _app_catalog_path(repo)
    actual = _read_text(path)
    if actual is None:
        return [CheckResult("FAIL", "INT_APP_CATALOG", "missing — intent-catalog --write 로 생성", path)]
    if actual != _render_app_catalog(rows):
        return [CheckResult("FAIL", "INT_APP_CATALOG", "stale — intent-catalog --write 로 재생성", path)]
    return [CheckResult("PASS", "INT_APP_CATALOG", f"{len(rows)} apps 최신", path)]


def _write_app_catalog(repo: Path) -> tuple[str, int]:
    """상위 카탈로그를 다시 쓴다 — (레포 상대 경로, App 수). Intent 가 없으면 파일을 지우지는 않고 빈 표를 쓴다."""
    rows = _collect_app_rows(repo)
    path = _app_catalog_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_app_catalog(rows), encoding="utf-8", newline="\n")
    return _relpath_for(path, repo), len(rows)


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
    app = args.app.lower()   # App 이름은 소문자다 — `--app LOADER` 도 받아 준다
    if args.write and args.check:
        print("FAIL ARGS --write 와 --check 는 함께 쓸 수 없다", file=sys.stderr)
        return 2
    if not APP_CODE_PATTERN.match(app):
        print(f"FAIL ARGS --app 은 소문자 App 이름이다 ({APP_RE}): {args.app!r}", file=sys.stderr)
        return 2
    app_dir = _intent_root(repo) / app
    if not app_dir.is_dir():
        print(f"FAIL ARGS --app not a directory: {app_dir}", file=sys.stderr)
        return 2
    rows, skipped = _collect_intent_rows(repo, app)
    catalog_path = app_dir / INTENT_CATALOG_NAME
    rel = _relpath_for(catalog_path, repo)
    app_rows = _collect_app_rows(repo)
    app_path = _app_catalog_path(repo)
    app_rel = _relpath_for(app_path, repo)
    # 모든 모드가 공유하는 파생 내용. 마크다운 전문은 실제로 필요한 분기에서만 렌더한다.
    payload = {
        "app": app,
        "catalog": rel,
        "count": len(rows),
        "intents": [r.to_dict() for r in rows],
        "skipped": skipped,
        "app_catalog": {"catalog": app_rel, "count": len(app_rows), "apps": [r.to_dict() for r in app_rows]},
    }

    if args.check:
        # App 카탈로그와 상위 카탈로그를 같이 본다 — 둘 중 하나라도 낡았으면 exit 1.
        checks = []
        for path, label, text, index, tail in (
            (catalog_path, rel, _render_intent_catalog(app, rows), _catalog_row_index, "intents"),
            (app_path, app_rel, _render_app_catalog(app_rows), _app_catalog_row_index, "apps"),
        ):
            actual = _read_text(path)
            exists = actual is not None
            if not exists:
                stale, diff = True, []
            elif actual != text:
                stale, diff = True, _catalog_diff(actual, text, index=index, tail=tail)
            else:
                stale, diff = False, []
            checks.append((label, exists, stale, diff))
        stale_any = any(c[2] for c in checks)
        if args.json:
            (_, exists, stale, diff), (_, a_exists, a_stale, a_diff) = checks
            payload["check"] = {"exists": exists, "stale": stale, "diff": diff,
                                "app_catalog": {"exists": a_exists, "stale": a_stale, "diff": a_diff}}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif not stale_any:
            print("OK")
            print(f"intents: {len(rows)}")
            print(f"apps: {len(app_rows)}")
        else:
            for label, exists, stale, diff in checks:
                if not exists:
                    print(f"STALE missing: {label}")
                elif stale:
                    for line in diff:
                        print(line)
                    print(f"STALE {label}")
        return 1 if stale_any else 0

    if args.write:
        catalog_path.write_text(_render_intent_catalog(app, rows), encoding="utf-8", newline="\n")
        app_rel, n_apps = _write_app_catalog(repo)
        if args.json:
            payload["write"] = {"written": True, "path": rel, "app_catalog": app_rel}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"WROTE {rel} · intents: {len(rows)}")
            print(f"WROTE {app_rel} · apps: {n_apps}")
        return 0

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(_render_intent_catalog(app, rows), end="")
    return 0


# ---------------------------------------------------------------------------
# Task — 레포 루트 .task/tsk-<NNN>.md (파싱 · check-task · task-catalog)
#
# Task 는 작업 계약서다. Intent(기능 문서)의 어느 항목을 어떻게 바꾸는지(Scope 사본),
# 무엇이 되면 완료인지(Acceptance)를 정한다. App 하나에 묶이지 않는다.
# ---------------------------------------------------------------------------


TASK_DIR = ".task"
TASK_CATALOG_NAME = "task-catalog.md"
TASK_FILENAME_PATTERN = re.compile(r"^tsk-(\d{3})\.md$")
TASK_ID_PATTERN = re.compile(r"^tsk-\d{3}$")
TASK_TITLE_PATTERN = re.compile(r"^tsk-\d{3} — .+$")
TASK_TITLE_PREFIX_PATTERN = re.compile(r"^(tsk-\d{3})(?:\s|$)")
TASK_META_EXPECTED = ["문서 ID", "유형", "상태", "대상 Intent", "선행 Task", "작성", "승인", "검증"]
# 브랜치 · 분기점은 Task 가 아니라 워크트리(/worktree-init <이름>)가 정한다 — 한 워크트리에서 Task 여러 개를 개발한다.
TASK_HANDOFF_EXPECTED = ["repo · app", "손대지 말 영역", "완료 보고 방식"]
TASK_SECTIONS = ("Goal", "Scope", "Acceptance", "Verification", "Risks", "Handoff")
TASK_TYPES = ("기능개발", "버그수정", "리팩토링")
TASK_STATUSES = ("draft", "approved", "in-review", "done", "dropped")
TASK_CLOSED_STATUSES = ("done", "dropped")
# 진행 표시가 Intent 에 붙어 있어야 하는 상태 — 머지를 확인한 done 전이(/worktree-delete)에서 지운다.
TASK_MARKED_STATUSES = ("draft", "approved", "in-review")
# 유형별로 Scope 에 쓸 수 있는 변경.
TASK_SCOPE_KINDS_BY_TYPE = {
    "기능개발": ("신규", "변경", "삭제"),
    "버그수정": ("위반", "신규"),
    "리팩토링": ("보존",),
}
# Intent 를 바꾸는 변경과 그 항목에 붙는 진행 표시. 위반 · 보존은 Intent 를 바꾸지 않아 표시가 없다.
TASK_MARKER_FOR_KIND = {"신규": "진행 중", "변경": "진행 중", "삭제": "삭제 예정"}
# 기능개발 · 버그수정 `- [ ] A-n.` 체크리스트, 리팩토링 `- A-n.` 목록.
TASK_ACCEPTANCE_PATTERN = re.compile(r"^- (?:\[([ xX])\]\s*)?(A)-(\d+)\.\s*(.*)$")
# /task-split 의 크기 기본 상한 — 넘으면 split-check 가 WARN.
SPLIT_MAX_SCOPE = 7
SPLIT_MAX_FR = 3

INTENT_ID_PATTERN = re.compile(rf"^({APP_RE})-int-\d{{3}}$")
TASK_SCOPE_LINE_PATTERN = re.compile(
    rf"^- (신규|변경|삭제|위반|보존) · ({APP_RE}-int-\d{{3}}) ((?:FR|E|X)-\d+)\. (.+)$"
)
TASK_SCOPE_PREV_PATTERN = re.compile(r"^\s+- 이전: (.+)$")
TASK_RISK_PATTERN = re.compile(r"^- R-(\d+)\.\s*(.*)$")
TASK_REF_ITEM_PATTERN = re.compile(rf"^{APP_RE}-int-\d{{3}} (?:FR|E|X)-\d+$")
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
    intent_id: str       # "loader-int-003"
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
    depends: list[str]                   # 선행 Task 중 ID 형식인 것(중복 제거) — none 이면 []
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

    depends: list[str] = []
    raw_depends = (meta.get("선행 Task") or "").strip()
    if raw_depends and raw_depends != "none":
        for token in (t.strip() for t in raw_depends.split("·")):
            if TASK_ID_PATTERN.match(token) and token not in depends:
                depends.append(token)

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
        m = TASK_ACCEPTANCE_PATTERN.match(live.rstrip())
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
        depends=depends,
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
    """Intent ID → intent/<app>/<ID>.md. ID 형식이 아니면 None. 존재 판정은 _exact_file 로 한다."""
    m = INTENT_ID_PATTERN.match(intent_id)
    if m is None:
        return None
    return repo / INTENT_DIR / m.group(1) / f"{intent_id}.md"


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
    others: dict[str, TaskDoc] | None = None   # .task/ 의 다른 Task(파일 이름 stem -> 파싱 결과) — _other_tasks 가 채운다


def _load_tasks(repo: Path) -> dict[str, TaskDoc]:
    """.task/tsk-<NNN>.md 전부를 파싱한다 (stem -> TaskDoc). 읽지 못한 파일은 건너뛴다."""
    out: dict[str, TaskDoc] = {}
    task_dir = repo / TASK_DIR
    if not task_dir.is_dir():
        return out
    for f in sorted(task_dir.glob("*.md")):
        if not TASK_FILENAME_PATTERN.match(f.name):
            continue
        text = _read_text(f)
        if text is not None:
            out[f.stem] = _parse_task(text)
    return out


def _other_tasks(ctx: "_TaskCtx") -> dict[str, TaskDoc]:
    if ctx.others is None:
        ctx.others = {stem: doc for stem, doc in _load_tasks(ctx.repo).items() if stem != ctx.stem}
    return ctx.others


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
    return [CheckResult("FAIL", "TSK_TITLE", f"제목이 'tsk-<NNN> — <제목>' 형식이 아님: {doc.title!r}", ctx.path)]


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
        f"Task 는 레포 루트 {TASK_DIR}/tsk-<NNN>.md 에 둔다: {_relpath_for(ctx.path, ctx.repo)}",
        ctx.path,
    )]


def _task_rule_meta_rows(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    if doc.meta_order == TASK_META_EXPECTED:
        return [CheckResult("PASS", "TSK_META_ROWS", f"메타 {len(TASK_META_EXPECTED)}행 순서 일치", ctx.path)]
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
    """대상 Intent 는 `<app>-int-<NNN>` 을 ` · ` 로 나열한다 — App 이 달라도 된다. none 은 Intent 가 없는 영역의 리팩토링만."""
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
            problems.append(f"'<app>-int-<NNN>' 를 ' · ' 로 나열한 형식이 아님: {bad}")
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
    if doc.handoff_order == TASK_HANDOFF_EXPECTED:
        return [CheckResult("PASS", "TSK_HANDOFF_ROWS", f"Handoff {len(TASK_HANDOFF_EXPECTED)}행 순서 일치", ctx.path)]
    return [CheckResult(
        "FAIL", "TSK_HANDOFF_ROWS",
        f"Handoff 행 불일치 — 기대 {TASK_HANDOFF_EXPECTED}, 실제 {doc.handoff_order}",
        ctx.path,
    )]


def _task_rule_depends(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """선행 Task 는 none 이거나, 실제로 있는 다른 Task ID 를 ` · ` 로 나열한다 — 자기 자신 · 중복 · 순환 금지.

    취소(dropped)된 Task 를 선행으로 두면 WARN — 기다릴 것이 없어졌다.
    """
    if "선행 Task" not in doc.meta:
        return []   # 행 자체가 없다 — TSK_META_ROWS 몫
    value = doc.meta["선행 Task"].strip()
    if value == "none":
        return [CheckResult("PASS", "TSK_DEPENDS", "선행 Task 없음", ctx.path)]
    tokens = [t.strip() for t in value.split("·")] if value else []
    me = _task_id(doc, ctx)
    problems: list[str] = []
    if not tokens:
        problems.append("값이 비어 있음 — 없으면 none")
    bad = [t for t in tokens if not TASK_ID_PATTERN.match(t)]
    if bad:
        problems.append(f"'tsk-<NNN>' 을 ' · ' 로 나열한 형식이 아님: {bad}")
    if me in tokens:
        problems.append("자기 자신을 선행으로 둠")
    dup = sorted({t for t in tokens if tokens.count(t) > 1})
    if dup:
        problems.append(f"중복: {dup}")
    others = _other_tasks(ctx)
    missing = [t for t in doc.depends if t != me and t not in others]
    if missing:
        problems.append(f"없는 Task: {missing}")
    # 순환 — 선행을 따라가다 이 Task 로 돌아오면 어느 쪽도 먼저 할 수 없다.
    path: list[str] = []
    seen: set[str] = set()

    def walk(task_id: str) -> bool:
        if task_id == me:
            return True
        if task_id in seen or task_id not in others:
            return False
        seen.add(task_id)
        path.append(task_id)
        if any(walk(nxt) for nxt in others[task_id].depends):
            return True
        path.pop()
        return False

    cycle = next((d for d in doc.depends if d != me and walk(d)), None)
    if cycle is not None:
        problems.append(f"순환: {' → '.join([me, *path, me])}")
    if problems:
        return [CheckResult("FAIL", "TSK_DEPENDS", ", ".join(problems), ctx.path)]
    dropped = [t for t in doc.depends if _task_status(others[t]) == "dropped"]
    if dropped:
        return [CheckResult("WARN", "TSK_DEPENDS", f"취소된 Task 를 선행으로 둠: {dropped}", ctx.path)]
    return [CheckResult("PASS", "TSK_DEPENDS", f"선행 Task: {value}", ctx.path)]


def _task_closure(task_id: str, tasks: dict[str, TaskDoc], depends: list[str]) -> set[str]:
    """선행을 거쳐 닿는 Task 전부 (자기 자신 제외)."""
    out: set[str] = set()
    stack = list(depends)
    while stack:
        cur = stack.pop()
        if cur in out or cur == task_id:
            continue
        out.add(cur)
        if cur in tasks:
            stack.extend(tasks[cur].depends)
    return out


def _task_rule_depends_order(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """E · X 가 기대는 FR 을 끝나지 않은 다른 Task 가 신규 · 변경으로 바꾸면, 그 Task 가 선행(거쳐서도)이어야 한다.

    기댈 동작보다 앞서 개발하지 않는다 — /task-split 의 "E · X 를 그 FR 보다 앞 Task 에 두지 않는다".
    """
    status = _task_status(doc)
    if status in TASK_CLOSED_STATUSES:
        return [CheckResult("PASS", "TSK_DEPENDS_ORDER", f"상태 {status} — 선행 순서 검사 건너뜀", ctx.path)]
    others = _other_tasks(ctx)
    changed_by: dict[str, str] = {}   # "<Intent ID> FR-n" -> 그 FR 을 신규 · 변경으로 바꾸는 다른 끝나지 않은 Task
    for stem, other in others.items():
        if _task_status(other) in TASK_CLOSED_STATUSES:
            continue
        for it in other.scope:
            if it.item_id.startswith("FR-") and it.kind in ("신규", "변경"):
                changed_by.setdefault(it.key, (other.meta.get("문서 ID") or "").strip() or stem)
    me = _task_id(doc, ctx)
    closure = _task_closure(me, others, doc.depends)
    problems: list[str] = []
    for it in doc.scope:
        if it.item_id.startswith("FR-") or it.kind not in ("신규", "변경"):
            continue
        for ref in _split_intent_refs(it.text)[1]:
            owner = changed_by.get(f"{it.intent_id} {ref}")
            if owner is not None and owner not in closure:
                problems.append(f"{it.key} 가 기대는 {ref} 를 {owner} 가 바꾸는데 선행이 아님")
    if problems:
        return [CheckResult("FAIL", "TSK_DEPENDS_ORDER", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_DEPENDS_ORDER", "기대는 FR 을 바꾸는 Task 가 모두 선행", ctx.path)]


def _task_rule_scope_format(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """Scope 는 `- <변경> · <app>-int-<NNN> <항목 ID>. <Intent 문장>` 줄과 `이전` · `Out of scope` 줄로만 이뤄진다."""
    problems: list[str] = []
    if doc.scope_bad_lines:
        problems.append(
            f"형식 밖 줄 {doc.scope_bad_lines} — '- <변경> · <app>-int-<NNN> <항목 ID>. <Intent 문장>'"
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
    """A 끝 괄호의 근거는 `<app>-int-<NNN> <항목 ID>` · `R-n` · `OS` · `Goal` 뿐이다 — App 접두 없는 `FR-4` 는 여러 App 에 걸친 Task 에서 모호하다."""
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
            f"근거 형식 밖: {bad} — '<app>-int-<NNN> <항목 ID>' · 'R-n' · 'OS' · 'Goal'",
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


# 이름 규칙(DOCUMENT_GUIDE §1.4)은 Intent 와 Task 가 같다 — 줄 목록 (섹션, 줄번호, 주석을 뺀 줄)을 받아 걸린 곳을 돌려준다.
def _name_kind_offenders(lines: list[tuple[str, int, str]]) -> list[str]:
    """백틱은 밖에서 보이는 이름에만 쓰고 바로 앞에 종류를 쓴다 — 응답 필드 `retryCount`."""
    offenders: list[str] = []
    for section, lineno, text in lines:
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
    return offenders


def _name_call_offenders(lines: list[tuple[str, int, str]]) -> list[str]:
    """`식별자(` 형태의 호출 구문은 내부 코드 이름이다. 한글 · 전부 대문자(`API(결제)`)는 잡지 않는다."""
    offenders: list[str] = []
    for _, lineno, text in lines:
        for m in TASK_NAME_CALL_PATTERN.finditer(_strip_code_spans(text)):
            name, empty = m.group(1), m.group(2)
            if not re.search(r"[a-z]", name):
                continue
            if empty or "." in name or "_" in name or re.search(r"[a-z0-9][A-Z]", name):
                offenders.append(f"{lineno}:{name}(")
    return offenders


def _name_file_offenders(lines: list[tuple[str, int, str]]) -> list[str]:
    return [
        f"{lineno}:{m.group(0)}"
        for _, lineno, text in lines
        for m in TASK_NAME_FILE_PATTERN.finditer(_strip_code_spans(text))
    ]


def _name_ident_hits(lines: list[tuple[str, int, str]]) -> list[str]:
    return [
        f"{lineno}:{m.group(0)}"
        for _, lineno, text in lines
        for m in TASK_NAME_IDENT_PATTERN.finditer(_strip_code_spans(text))
    ]


def _task_rule_name_kind(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    offenders = _name_kind_offenders(_task_name_lines(doc))
    if offenders:
        return [CheckResult(
            "FAIL", "TSK_NAME_KIND",
            f"백틱 이름 앞에 종류({' · '.join(TASK_NAME_KINDS)})가 없음: {offenders[:5]}",
            ctx.path,
        )]
    return [CheckResult("PASS", "TSK_NAME_KIND", "백틱 이름마다 종류가 붙음", ctx.path)]


def _task_rule_name_call(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    offenders = _name_call_offenders(_task_name_lines(doc))
    if offenders:
        return [CheckResult("FAIL", "TSK_NAME_CALL", f"코드 호출 구문: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "TSK_NAME_CALL", "코드 호출 구문 없음", ctx.path)]


def _task_rule_name_file(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    offenders = _name_file_offenders(_task_name_lines(doc))
    if offenders:
        return [CheckResult("FAIL", "TSK_NAME_FILE", f"소스 파일 이름: {offenders[:5]}", ctx.path)]
    return [CheckResult("PASS", "TSK_NAME_FILE", "소스 파일 이름 없음", ctx.path)]


def _task_rule_name_ident(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    hits = _name_ident_hits(_task_name_lines(doc))
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

    삭제 항목도 done 전까지는 `삭제 예정` 표시를 달고 Intent 에 남아 있다. done · dropped 는 뒤의 Task 가
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
        if src is None:
            problems.append(f"{it.key} Intent 에 없음")
        elif src.body != it.text:
            problems.append(f"{it.key} 문장이 Intent 와 다름")
    if problems:
        return [CheckResult("FAIL", "TSK_SCOPE_MATCH", ", ".join(problems), ctx.path)]
    return [CheckResult("PASS", "TSK_SCOPE_MATCH", "Scope 문장이 Intent 와 일치", ctx.path)]


def _task_rule_marker(doc: TaskDoc, ctx: _TaskCtx) -> list[CheckResult]:
    """진행 표시는 Scope 의 신규 · 변경 · 삭제와 1:1 이다. done · dropped 뒤에는 이 Task 의 표시가 남지 않는다."""
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
    if mine:
        for stem, other in _other_tasks(ctx).items():
            if _task_status(other) in TASK_CLOSED_STATUSES:
                continue
            for it in other.scope:
                kind = mine.get(it.key)
                if kind is not None and (kind in TASK_MARKER_FOR_KIND or it.kind in TASK_MARKER_FOR_KIND):
                    conflicts.append(f"{stem}: {it.key}")
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
    _task_rule_depends,
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
    _task_rule_depends_order,
    _task_rule_approved_gate,
)


def _check_task_file(repo: Path, path: Path) -> list[CheckResult]:
    if not path.is_absolute():
        path = repo / path
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
        intent_text = _read_text(p) if p is not None and _exact_file(p) else None
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
    depends: str                           # 메타 `선행 Task` 원문
    depend_links: list[tuple[str, str | None]]   # (Task ID, 카탈로그 기준 링크 — 파일이 없으면 None)

    def to_dict(self) -> dict:
        return {
            "id": self.task_id,
            "file": f"{self.stem}.md",
            "title": self.title,
            "type": self.kind,
            "status": self.status,
            "depends": [{"id": i, "link": link} for i, link in self.depend_links],
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
    """.task/tsk-<NNN>.md 를 파싱해 카탈로그 행으로 만든다. 카탈로그 자신은 건너뛴다."""
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
                link = f"../{INTENT_DIR}/{p.parent.name}/{p.name}" if p is not None and _exact_file(p) else None
                links.append((token, link))
        depends = (doc.meta.get("선행 Task") or "").strip()
        depend_links: list[tuple[str, str | None]] = []
        if depends and depends != "none":
            for token in (t.strip() for t in depends.split("·")):
                if token:
                    exists = TASK_ID_PATTERN.match(token) and _exact_file(task_dir / f"{token}.md")
                    depend_links.append((token, f"{token}.md" if exists else None))
        rows.append(TaskCatalogRow(
            task_id=task_id,
            stem=f.stem,
            title=_task_short_title(doc, task_id),
            kind=(doc.meta.get("유형") or "").strip() or "?",
            status=(doc.meta.get("상태") or "").strip() or "?",
            targets=targets,
            links=links,
            depends=depends,
            depend_links=depend_links,
        ))
    return rows, skipped


def _task_links_cell(raw: str, links: list[tuple[str, str | None]]) -> str:
    if raw == "none":
        return "none"
    if not links:
        return "?"
    return " · ".join(
        f"[{_md_cell(i)}]({link})" if link is not None else f"?{_md_cell(i)}" for i, link in links
    )


def _render_task_catalog(rows: list[TaskCatalogRow]) -> str:
    """카탈로그 마크다운 전문. 타임스탬프를 넣지 않는다 — stale 비교가 항상 불일치가 되기 때문."""
    out = [
        "# task-catalog — Task Catalog",
        "",
        "> **생성물** — `docs_helpers.py task-catalog --repo . --write` 가 `.task/` 를 훑어 다시 쓴다. "
        "**직접 고치지 않는다** — 값을 바꾸려면 해당 Task 문서를 고치고 재생성한다. "
        "`check` 가 불일치를 FAIL 로 잡는다.",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        "| 문서 ID | task-catalog |",
        "| 생성 | docs_helpers.py task-catalog |",
        "| 대상 | [.task 폴더](./) |",
        "",
        "| Task | 설명 | 유형 | 상태 | 선행 | 대상 Intent |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| [{_md_cell(r.task_id)}]({r.stem}.md) | {_md_cell(r.title)} | "
            f"{_md_cell(r.kind)} | {_md_cell(r.status)} | {_task_links_cell(r.depends, r.depend_links)} | "
            f"{_task_links_cell(r.targets, r.links)} |"
        )
    out += ["", f"tasks: {len(rows)}", ""]
    return "\n".join(out)


def _task_catalog_row_index(text: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for line in text.split("\n"):
        m = re.match(r"^\|\s*\[([^\]]+)\]\(tsk-\d{3}\.md\)", line)
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
# Intent 변경 — 기준선(intent-base) · 변경 목록(intent-diff) · 진행 표시(mark-intent) · 자르기 검사(split-check)
#
# 문서는 커밋하지 않으므로 git 이력이 "고치기 전" 을 알려 주지 못한다. requirement-spec 수정 모드가
# 고치기 전 사본을 .process/intent-base/<ID>.md 에 남기고, /task-split 이 그 사본과 지금 Intent 를
# 비교해 바뀐 항목을 Task 로 나눈 뒤 사본을 지운다. 초안이 아닌 Task 가 가리킨 적 없는 Intent 는 새로 쓴
# 것이라 항목 전부가 신규다.
# ---------------------------------------------------------------------------


INTENT_BASE_DIR = ".process/intent-base"
INTENT_CHANGE_KINDS = ("FR", "E", "X")
INTENT_ITEM_LINE = re.compile(r"^- ((?:FR|E|X)-\d+)\.")


def _intent_base_path(repo: Path, intent_id: str) -> Path:
    return repo / INTENT_BASE_DIR / f"{intent_id}.md"


def _read_raw(path: Path) -> str:
    """줄바꿈을 바꾸지 않고 읽는다 (CRLF 면 \\r\\n 그대로). 고쳐 쓸 문서는 이렇게 읽는다.

    UTF-8 이 아니면 UnicodeDecodeError 를 그대로 낸다 — 바꿔 읽고 되쓰면 그 바이트가 U+FFFD 로 굳는다.
    문서는 git 에 없어(커밋하지 않는다) 깨진 파일이 유일한 사본이 되므로, 고쳐 쓰는 쪽은 아무것도 쓰지 않고 멈춘다.
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        return f.read()


def _write_all(pairs: list[tuple[Path, str]]) -> None:
    """여러 파일을 고쳐 쓴다 — 임시 파일을 전부 쓴 뒤에야 원본과 바꿔 끼운다(os.replace).

    임시 파일을 쓰다 실패하면 원본은 하나도 바뀌지 않는다. 바로 열어 쓰면(open "w") 쓰기 전에 파일이 비워져,
    도중에 멈추면 유일한 사본이 반쯤 빈다. 바꿔 끼우다 실패하면(Windows 에서 다른 프로세스가 파일을 잡고 있을 때)
    앞서 바꾼 파일만 새 본문이고 나머지는 원본 그대로다. 어느 쪽이든 남은 임시 파일을 지우고 예외를 올린다 —
    호출측의 고침은 되풀이해도 같은 결과라, 같은 명령을 다시 실행하면 이어서 끝난다.
    """
    temps: list[tuple[Path, Path]] = []
    try:
        for path, text in pairs:
            tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temps.append((tmp, path))
            with tmp.open("w", encoding="utf-8", newline="") as f:
                f.write(text)
        for tmp, path in temps:
            os.replace(tmp, path)
    except BaseException:
        for tmp, _ in temps:   # 바꿔 끼운 임시 파일은 이미 없다
            tmp.unlink(missing_ok=True)
        raise


def _comment_open_after(lines: list[str]) -> list[bool]:
    """줄마다 그 줄 끝에서 HTML 주석이 열려 있는지 — 그 줄 뒤에 넣은 줄은 주석 안에 들어가 보이지 않는다.

    _live_lines 와 같은 규칙으로 `<!--` · `-->` 를 따라간다.
    """
    out: list[bool] = []
    in_comment = False
    for line in lines:
        rest = line
        while rest:
            if in_comment:
                end = rest.find("-->")
                if end == -1:
                    break
                rest, in_comment = rest[end + 3:], False
            else:
                start = rest.find("<!--")
                if start == -1:
                    break
                rest, in_comment = rest[start + 4:], True
        out.append(in_comment)
    return out


def _intent_referenced_by_tasks(tasks: dict[str, TaskDoc], intent_id: str) -> bool:
    """초안이 아닌 Task 의 대상 Intent 에 들어 있는가 — 아니면 아직 한 번도 자르지 않은 Intent 다.

    초안(draft)은 지금 자르는 중인 Task 다 — /task-split 이 초안을 쓴 뒤 split-check 로 다시 비교할 때
    그 초안 때문에 새 Intent 가 '바뀐 것 없음' 으로 보이면 안 된다.
    """
    return any(intent_id in doc.targets and _task_status(doc) != "draft" for doc in tasks.values())


def _intent_next_ids(cur: IntentDoc, base: IntentDoc | None, tasks: dict[str, TaskDoc], intent_id: str) -> dict[str, int]:
    """새 항목에 쓸 번호 — 지운 번호도 다시 쓰지 않도록 지금 Intent · 기준선 · 이 Intent 를 가리키는 Task Scope 에
    나온 번호 중 가장 큰 것 다음."""
    out: dict[str, int] = {}
    for kind in ("D", "C", *INTENT_CHANGE_KINDS):
        nums = [it.num for it in cur.items[kind]]
        if base is not None:
            nums += [it.num for it in base.items[kind]]
        nums += [
            int(it.item_id.split("-", 1)[1])
            for doc in tasks.values() for it in doc.scope
            if it.intent_id == intent_id and it.item_id.split("-", 1)[0] == kind
        ]
        out[kind] = max(nums, default=0) + 1
    return out


def intent_changes(repo: Path, intent_id: str) -> dict:
    """기준선과 지금 Intent 를 FR · E · X 항목 ID 로 맞대어 바뀐 항목을 뽑는다.

    - mode: base(기준선과 비교) · new(초안이 아닌 Task 가 가리킨 적 없음 — 전부 신규) · none(바뀐 것 없음)
    - `삭제 예정` 표시가 붙은 항목도 삭제다 — mark-intent 가 기준선 문장으로 제자리에 다시 넣은 줄이다.
      기준선에 같은 표시가 이미 있으면 다른 Task 가 지우는 중인 항목이라 이번 변경이 아니다.
    - 다른 Task 의 표시가 붙은 채 기준선에 들어간 항목은 그 Task 가 끝나며 생긴 차이를 변경으로 세지 않는다 —
      done 이 지운 `삭제 예정` 줄, dropped 가 되돌린 신규 · 변경.
    - locked_by: 그 항목에 진행 표시를 단 끝나지 않은 Task. 이번에 만드는 Task 가 아니면 한 항목을 두 Task 가 바꾼다.
    - next_ids: 새 항목에 쓸 번호(D · C · FR · E · X).
    """
    path = _intent_path(repo, intent_id)
    text = _read_text(path) if path is not None and _exact_file(path) else None
    if text is None:
        return {"intent": intent_id, "path": None, "error": "Intent 파일이 없다"}
    cur = _parse_intent(text)
    tasks = _load_tasks(repo)
    status = {stem: _task_status(doc) for stem, doc in tasks.items()}
    base_path = _intent_base_path(repo, intent_id)
    base_text = _read_text(base_path)
    if base_text is not None:
        mode, base = "base", _parse_intent(base_text)
    elif not _intent_referenced_by_tasks(tasks, intent_id):
        mode, base = "new", None
    else:
        mode, base = "none", None

    def open_lock(it: IntentItem | None) -> str | None:
        if it is None or it.marker is None or status.get(it.marker[0]) in TASK_CLOSED_STATUSES:
            return None
        return it.marker[0]

    changes: list[dict] = []
    if mode != "none":
        for kind in INTENT_CHANGE_KINDS:
            b_items = {it.id: it for it in base.items[kind]} if base is not None else {}
            c_items = {it.id: it for it in cur.items[kind]}
            for item_id in sorted(set(b_items) | set(c_items), key=lambda i: int(i.split("-", 1)[1])):
                b, c = b_items.get(item_id), c_items.get(item_id)
                b_mark = b.marker if b is not None else None
                c_mark = c.marker if c is not None else None
                b_owner = status.get(b_mark[0]) if b_mark is not None else None   # 기준선에 표시를 단 Task 의 지금 상태
                if c is None:
                    if b_mark is not None and (
                        (b_mark[1] == "삭제 예정" and b_owner == "done")        # done 이 지운 줄
                        or (b_mark[1] == "진행 중" and b_owner == "dropped")    # dropped 가 되돌린 신규
                    ):
                        continue
                    change, body, prev = "삭제", b.body, None
                elif c_mark is not None and c_mark[1] == "삭제 예정" and c_mark != b_mark:
                    change, body, prev = "삭제", (b or c).body, None
                elif b is None:
                    change, body, prev = "신규", c.body, None
                elif b.body != c.body:
                    if b_mark is not None and b_owner == "dropped" and c_mark is None:
                        continue   # dropped 가 `이전` 문장으로 되돌렸다
                    change, body, prev = "변경", c.body, b.body
                else:
                    continue
                changes.append({
                    "kind": change,
                    "id": item_id,
                    "text": body,
                    "prev": prev,
                    "scope_line": f"- {change} · {intent_id} {item_id}. {body}",
                    "prev_line": f"  - 이전: {prev}" if prev is not None else None,
                    "locked_by": open_lock(c) or open_lock(b),
                })
    return {
        "intent": intent_id,
        "path": _relpath_for(path, repo),
        "base": _relpath_for(base_path, repo) if mode == "base" else None,
        "mode": mode,
        "open_questions": _intent_body_is_none(cur, "Open questions"),
        "changes": changes,
        "next_ids": _intent_next_ids(cur, base, tasks, intent_id),
    }


def _bad_intent_arg(intent_id: str, code: str) -> bool:
    """--intent 는 Intent ID 만 받는다 — 경로 조각이 섞이면 기준선 경로가 .process/intent-base/ 밖을 가리킨다."""
    if INTENT_ID_PATTERN.match(intent_id):
        return False
    print(f"FAIL {code} Intent ID 가 '<app>-int-<NNN>' 이 아니다: {intent_id!r}", file=sys.stderr)
    return True


def cmd_intent_base(repo: Path, args: argparse.Namespace) -> int:
    if _bad_intent_arg(args.intent, "INTENT_BASE"):
        return 2
    base = _intent_base_path(repo, args.intent)
    rel = _relpath_for(base, repo)
    if args.drop:
        if base.is_file():
            base.unlink()
            print(f"DROPPED {rel}")
        else:
            print(f"NONE {rel}")
        return 0
    path = _intent_path(repo, args.intent)
    if path is None or not _exact_file(path):
        print(f"FAIL INTENT_BASE Intent 파일이 없다: {args.intent}", file=sys.stderr)
        return 2
    if base.is_file():
        # 아직 자르지 않은 앞선 고침이 있다 — 더 오래된 기준선을 지켜야 두 번의 고침이 다 변경 목록에 나온다.
        print(f"KEPT {rel} — 아직 자르지 않은 기준선을 그대로 둔다")
        return 0
    if not args.implemented and not _intent_referenced_by_tasks(_load_tasks(repo), args.intent):
        # 한 번도 자르지 않은 Intent 는 항목 전부가 아직 코드에 없다 — 기준선을 남기면 고친 차이만 잘린다.
        print(f"NEW {rel} — 아직 자르지 않은 Intent 라 기준선을 남기지 않는다(자를 때 항목 전부가 신규다). "
              "옛 방식으로 이미 구현한 Intent 면 --implemented")
        return 0
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_bytes(path.read_bytes())
    print(f"SAVED {rel}")
    return 0


def cmd_intent_diff(repo: Path, args: argparse.Namespace) -> int:
    if _bad_intent_arg(args.intent, "INTENT_DIFF"):
        return 2
    result = intent_changes(repo, args.intent)
    if "error" in result:
        print(f"FAIL INTENT_DIFF {result['error']}: {args.intent}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"{result['intent']} · mode {result['mode']}" + (f" · base {result['base']}" if result["base"] else ""))
    for ch in result["changes"]:
        lock = f"  (표시: {ch['locked_by']})" if ch["locked_by"] else ""
        print(ch["scope_line"] + lock)
        if ch["prev_line"]:
            print(ch["prev_line"])
    if not result["open_questions"]:
        print("WARN OPEN_QUESTIONS Open questions 가 none 이 아니다 — Task 를 승인할 수 없다")
    print(f"changes: {len(result['changes'])}")
    return 0


def clear_task_marks(
    text: str, task_id: str, keep: frozenset[str] = frozenset(),
) -> tuple[str, list[str], list[str], list[str]]:
    """이 Task 의 진행 표시를 지우고, 이 Task 의 `삭제 예정` 항목 줄을 지운다 — keep 에 든 항목 ID 는 그대로 둔다.

    (새 텍스트, 표시를 지운 항목 ID, 줄을 지운 항목 ID, 문제) 를 돌려준다. 다른 Task 의 표시는 건드리지 않는다.
    줄을 지워 섹션에 남는 본문이 없으면 그 자리에 `none` 을 남긴다 — Intent 는 빈 섹션 대신 none 을 쓴다.
    진행 표시가 있는 줄에 HTML 주석이 섞여 있으면 그 줄은 고치지 않고 문제로 돌려준다 — 줄째 지우거나 표시를
    떼면 주석 여닫이가 깨져 뒤 본문이 숨거나 드러난다. 문제가 있으면 호출측은 아무것도 쓰지 않는다.
    줄바꿈은 원본 그대로다(CRLF 면 줄 끝 \\r 이 남는다). done 전이(/worktree-delete), 자르기 취소
    (mark-intent --remove), Scope 에서 빠진 항목의 표시 정리(mark-intent)가 쓴다.
    """
    mark_at_end = re.compile(rf"\s*\[{re.escape(task_id)} (진행 중|삭제 예정)\]\s*$")
    lines = text.split("\n")
    live = [t for _, t in _live_lines(text, 1)]   # 주석을 뺀 본문 — 같은 "\n" 기준이라 줄 수가 같다
    out: list[str] = []
    cleared: list[str] = []
    deleted: list[str] = []
    problems: list[str] = []
    first_del: int | None = None   # 이 섹션에서 처음 지운 줄이 out 에 들어갈 자리
    del_eol = ""
    has_live = False

    def close_section() -> None:
        if first_del is not None and not has_live:
            out.insert(first_del, "none" + del_eol)

    for raw, live_line in zip(lines, live):
        body = raw.rstrip("\r")
        eol = raw[len(body):]
        live_body = live_line.rstrip("\r").rstrip()
        if _intent_section_boundary(live_body):   # 주석 안의 # 은 헤딩이 아니다
            close_section()
            first_del, del_eol, has_live = None, "", False
            out.append(raw)
            continue
        item = INTENT_ITEM_LINE.match(live_body)
        m = mark_at_end.search(live_body) if item and item.group(1) not in keep else None
        if m is not None and live_line.rstrip("\r") != body:
            problems.append(f"{item.group(1)} — 진행 표시가 있는 줄에 HTML 주석이 섞여 있다. 주석을 다른 줄로 옮긴 뒤 다시 실행한다")
            out.append(raw)
            has_live = True
            continue
        if m is not None and m.group(1) == "삭제 예정":
            deleted.append(item.group(1))
            if first_del is None:
                first_del, del_eol = len(out), eol
            continue
        if m is not None:
            out.append(mark_at_end.sub("", body) + eol)
            cleared.append(item.group(1))
            has_live = True
            continue
        out.append(raw)
        if live_body.strip():
            has_live = True
    close_section()
    if out and lines and not lines[-1].endswith("\r") and out[-1].endswith("\r"):
        out[-1] = out[-1][:-1]   # 줄바꿈 없이 끝난 마지막 줄을 지웠다 — 남은 끝 줄의 \r 은 지운 줄 앞 구분자였다
    return "\n".join(out), cleared, deleted, problems


def _section_span(live: list[str], name: str) -> tuple[int, int] | None:
    """`### <name>` 헤딩 줄 번호와 섹션 끝(다음 `##` · `###` 헤딩 · 구분선, 0-based exclusive)."""
    start = next((i for i, line in enumerate(live) if re.match(rf"^###\s+{re.escape(name)}\s*$", line.rstrip("\r"))), None)
    if start is None:
        return None
    end = len(live)
    for i in range(start + 1, len(live)):
        if _intent_section_boundary(live[i]):
            end = i
            break
    return start, end


def _insert_intent_line(lines: list[str], pos: int, body: str, crlf: bool) -> None:
    """줄 목록(텍스트를 \\n 으로 나눈 것)의 pos 에 한 줄을 넣는다 — 줄 끝(CRLF 면 \\r)과 파일 끝 줄바꿈 유무를 지킨다."""
    if pos >= len(lines):   # 줄바꿈 없이 끝난 마지막 줄 뒤 — 그 줄에 줄 끝을 주고 새 줄이 마지막이 된다
        if crlf and lines and not lines[-1].endswith("\r"):
            lines[-1] += "\r"
        lines.append(body)
        return
    lines.insert(pos, body + ("\r" if crlf else ""))


def apply_task_marks(text: str, task_id: str, items: list[TaskScopeItem]) -> tuple[str, list[str], list[str], list[str]]:
    """Scope 의 신규 · 변경 · 삭제 항목에 이 Task 의 진행 표시를 붙인다 — (새 텍스트, 표시, 다시 넣은 항목, 문제).

    Intent 에 없는 삭제 항목은 Scope 문장(기준선 문장)으로 ID 순서 자리에 다시 넣고 `삭제 예정` 을 단다 —
    고칠 때 지웠어도 코드에는 아직 그 동작이 있다. 다른 Task 의 표시가 붙은 항목 · Intent 에 없는
    신규 · 변경 항목 · 같은 ID 가 둘인 항목 · HTML 주석이 섞인 줄 · 주석 안이 되는 삽입 자리는 문제로
    돌려준다(그때는 아무것도 쓰지 않아야 한다). 이미 같은 표시면 건너뛴다.
    """
    crlf = "\r\n" in text
    lines = text.split("\n")
    marked: list[str] = []
    inserted: list[str] = []
    problems: list[str] = []
    for it in items:
        want = TASK_MARKER_FOR_KIND.get(it.kind)
        if want is None:
            continue   # 위반 · 보존 — 표시가 없다
        live = [t for _, t in _live_lines("\n".join(lines), 1)]
        kind = it.item_id.split("-", 1)[0]
        section = _section_span(live, INTENT_SECTION_FOR_KIND[kind])
        rows: list[int] = []
        if section is not None:
            rows = [i for i in range(section[0] + 1, section[1])
                    if (m := INTENT_ITEM_LINE.match(live[i].rstrip("\r"))) and m.group(1) == it.item_id]
        if len(rows) > 1:
            problems.append(f"{it.key} 가 섹션에 {len(rows)}번 있다 — 항목 ID 는 하나만 쓴다")
            continue
        if rows:
            idx = rows[0]
            body = lines[idx].rstrip("\r")
            if live[idx].rstrip("\r") != body:
                problems.append(f"{it.key} 줄에 HTML 주석이 섞여 있다 — 주석을 다른 줄로 옮긴 뒤 다시 실행한다")
                continue
            line_eol = lines[idx][len(body):]
            mm = PROGRESS_MARKER_PATTERN.search(body)
            if mm is not None:
                if mm.group(1) != task_id:
                    problems.append(f"{it.key} 에 다른 Task 의 표시 [{mm.group(1)} {mm.group(2)}] 가 있다")
                    continue
                if mm.group(2) == want:
                    continue
                body = body[:mm.start()]
            lines[idx] = f"{body.rstrip()} [{task_id} {want}]{line_eol}"
            marked.append(it.item_id)
            continue
        if it.kind != "삭제":
            problems.append(f"{it.key} 가 Intent 에 없다 — {it.kind} 항목은 Intent 에 있어야 한다")
            continue
        if section is None:
            problems.append(f"{it.key} 를 넣을 섹션 '### {INTENT_SECTION_FOR_KIND[kind]}' 이 없다")
            continue
        new_body = f"- {it.item_id}. {it.text} [{task_id} 삭제 예정]"
        num = int(it.item_id.split("-", 1)[1])
        item_rows = [(i, int(m.group(1).split("-", 1)[1])) for i in range(section[0] + 1, section[1])
                     if (m := INTENT_ITEM_LINE.match(live[i].rstrip("\r")))]
        none_row = next((i for i in range(section[0] + 1, section[1]) if live[i].rstrip("\r").strip() == "none"), None)
        after = next((i for i, n in item_rows if n > num), None)
        if after is None and not item_rows and none_row is not None:
            raw_none = lines[none_row]
            if raw_none.rstrip("\r").strip() != "none":
                problems.append(f"{it.key} 를 넣을 섹션의 `none` 줄에 HTML 주석이 섞여 있다 — 주석을 다른 줄로 옮긴 뒤 다시 실행한다")
                continue
            lines[none_row] = new_body + raw_none[len(raw_none.rstrip("\r")):]
            inserted.append(it.item_id)
            marked.append(it.item_id)
            continue
        if after is not None:
            pos = after
        elif item_rows:
            pos = item_rows[-1][0] + 1
            while pos < section[1] and lines[pos][:1] in (" ", "\t") and live[pos].strip():
                pos += 1   # 마지막 항목에 딸린 들여 쓴 줄을 가르지 않는다
        else:
            pos = section[0] + 1
        if pos > 0 and _comment_open_after(lines)[pos - 1]:
            problems.append(f"{it.key} 를 다시 넣을 자리가 HTML 주석 안이다 — 주석을 닫은 뒤 다시 실행한다")
            continue
        _insert_intent_line(lines, pos, new_body, crlf)
        inserted.append(it.item_id)
        marked.append(it.item_id)
    return "\n".join(lines), marked, inserted, problems


def cmd_mark_intent(repo: Path, args: argparse.Namespace) -> int:
    """이 Task 의 진행 표시를 Scope 와 같게 맞춘다 — Scope 항목에 붙이고, Scope 에서 빠진 항목의 표시는 걷어 낸다.

    --remove 면 이 Task 의 표시를 전부 걷어 낸다(다시 넣은 삭제 항목 줄도 지운다). 하나라도 막히면 아무 Intent 도 고치지 않는다.
    """
    task_path = Path(args.task)
    if not task_path.is_absolute():
        task_path = repo / task_path
    text = _read_text(task_path) if _exact_file(task_path) else None
    if text is None:
        print(f"FAIL MARK Task 를 읽지 못했다: {args.task}", file=sys.stderr)
        return 2
    doc = _parse_task(text)
    task_id = (doc.meta.get("문서 ID") or "").strip() or task_path.stem
    if not TASK_ID_PATTERN.match(task_id):
        print(f"FAIL MARK 문서 ID 가 'tsk-<NNN>' 이 아니다: {task_id!r}", file=sys.stderr)
        return 2
    plans: list[tuple[str, Path, str, str, list[str], list[str], list[str]]] = []
    problems: list[str] = []
    missing: list[str] = []
    for intent_id in doc.targets:
        path = _intent_path(repo, intent_id)
        if path is None or not _exact_file(path):
            if args.remove:
                missing.append(intent_id)   # 걷어 낼 표시가 없다 — 취소 정리를 막지 않는다
            else:
                problems.append(f"{intent_id}: Intent 파일이 없다")
            continue
        try:
            raw = _read_raw(path)
        except UnicodeDecodeError:
            problems.append(f"{intent_id}: UTF-8 로 읽을 수 없다 — 되쓰면 내용이 깨진다. UTF-8 로 저장한 뒤 다시 실행한다")
            continue
        if args.remove:
            new, done_ids, extra_ids, issues = clear_task_marks(raw, task_id)
            problems += [f"{intent_id} {p}" for p in issues]
            unmarked: list[str] = []
        else:
            items = [it for it in doc.scope if it.intent_id == intent_id]
            wanted = frozenset(it.item_id for it in items if it.kind in TASK_MARKER_FOR_KIND)
            kept, stale_cleared, stale_deleted, issues = clear_task_marks(raw, task_id, keep=wanted)
            problems += [f"{intent_id} {p}" for p in issues]
            new, done_ids, extra_ids, issues = apply_task_marks(kept, task_id, items)
            unmarked = stale_cleared + stale_deleted
            problems += issues
        plans.append((intent_id, path, raw, new, done_ids, extra_ids, unmarked))
    if problems:
        # 하나라도 막히면 아무 Intent 도 고치지 않는다 — 반쯤 붙은 표시는 check-task 를 헷갈리게 한다.
        for p in problems:
            print(f"FAIL MARK {p}")
        return 1
    try:
        _write_all([(path, new) for _, path, raw, new, *_ in plans if new != raw])
    except OSError as e:
        print(f"FAIL MARK Intent 를 쓰다가 멈췄다 ({type(e).__name__}: {e}) — 일부 Intent 만 바뀌었을 수 있다. "
              "파일을 잡고 있는 프로그램을 닫고 같은 명령을 다시 실행하면 이어서 맞춘다", file=sys.stderr)
        return 2
    report = []
    for intent_id, path, raw, new, done_ids, extra_ids, unmarked in plans:
        rel = _relpath_for(path, repo)
        if args.remove:
            report.append({"intent": intent_id, "path": rel, "cleared": done_ids, "deleted": extra_ids})
        else:
            report.append({"intent": intent_id, "path": rel, "marked": done_ids, "inserted": extra_ids, "unmarked": unmarked})
    if args.json:
        print(json.dumps(
            {"task": task_id, "remove": bool(args.remove), "intents": report, "missing": missing}, ensure_ascii=False,
        ))
        return 0
    for r in report:
        if args.remove:
            print(f"CLEARED {r['path']} · 표시 {len(r['cleared'])} · 삭제 줄 {len(r['deleted'])}")
        else:
            gone = f" · 걷어 낸 표시 {len(r['unmarked'])}" if r["unmarked"] else ""
            print(f"MARKED {r['path']} · 표시 {len(r['marked'])} · 다시 넣은 삭제 항목 {len(r['inserted'])}{gone}")
    for intent_id in missing:
        print(f"SKIP {intent_id} — Intent 파일이 없다")
    return 0


def _split_check(repo: Path, task_paths: list[Path]) -> list[CheckResult]:
    """이번에 만든 Task 묶음이 대상 Intent 의 바뀐 항목을 정확히 한 번씩 나눴는지 본다."""
    results: list[CheckResult] = []
    tasks: list[tuple[str, Path, TaskDoc]] = []
    for path in task_paths:
        text = _read_text(path)
        if text is None:
            results.append(CheckResult("FAIL", "READ_TEXT", "cannot read", path))
            continue
        doc = _parse_task(text)
        tasks.append(((doc.meta.get("문서 ID") or "").strip() or path.stem, path, doc))
    mine = {task_id for task_id, _, _ in tasks}
    claimed: dict[str, list[tuple[str, Path, TaskScopeItem]]] = {}
    intents: list[str] = []
    for task_id, path, doc in tasks:
        for it in doc.scope:
            if it.kind in TASK_MARKER_FOR_KIND:
                claimed.setdefault(it.key, []).append((task_id, path, it))
        intents += [i for i in doc.targets if i not in intents]
        fr = sum(1 for it in doc.scope if it.item_id.startswith("FR-"))
        if len(doc.scope) > SPLIT_MAX_SCOPE or fr > SPLIT_MAX_FR:
            results.append(CheckResult(
                "WARN", "SPLIT_SIZE",
                f"{task_id}: Scope {len(doc.scope)} · FR {fr} — 기본 상한 Scope {SPLIT_MAX_SCOPE} · FR {SPLIT_MAX_FR}. "
                "더 나눌 수 있는지 보고, 못 나누면 이유를 자르기 표에 적는다",
                path,
            ))
    changed: set[str] = set()
    for intent_id in intents:
        diff = intent_changes(repo, intent_id)
        if "error" in diff:
            results.append(CheckResult("FAIL", "SPLIT_INTENT", f"{intent_id}: {diff['error']}", None))
            continue
        for ch in diff["changes"]:
            key = f"{intent_id} {ch['id']}"
            changed.add(key)
            owners = claimed.get(key, [])
            if ch["locked_by"] and ch["locked_by"] not in mine:
                results.append(CheckResult("FAIL", "SPLIT_LOCKED", f"{key}: {ch['locked_by']} 가 이미 바꾸는 중", None))
            if not owners:
                results.append(CheckResult("FAIL", "SPLIT_UNASSIGNED", f"{key} ({ch['kind']}) 가 어느 Task 에도 없다", None))
                continue
            if len(owners) > 1:
                results.append(CheckResult(
                    "FAIL", "SPLIT_DUP", f"{key} 가 여러 Task 에 있다: {' · '.join(o[0] for o in owners)}", None,
                ))
                continue
            task_id, path, it = owners[0]
            if it.kind != ch["kind"]:
                results.append(CheckResult("FAIL", "SPLIT_KIND", f"{key}: 변경 목록은 {ch['kind']}, {task_id} 는 {it.kind}", path))
            elif it.text != ch["text"]:
                results.append(CheckResult("FAIL", "SPLIT_TEXT", f"{key}: {task_id} Scope 문장이 변경 목록과 다르다", path))
            elif ch["kind"] == "변경" and it.prev != ch["prev"]:
                results.append(CheckResult("FAIL", "SPLIT_PREV", f"{key}: {task_id} 의 '이전' 이 기준선 문장과 다르다", path))
    for key, owners in claimed.items():
        if key not in changed:
            for task_id, path, it in owners:
                results.append(CheckResult(
                    "FAIL", "SPLIT_EXTRA", f"{key}: {task_id} Scope 의 {it.kind} 항목이지만 바뀐 항목이 아니다", path,
                ))
    if not any(r.level == "FAIL" for r in results):
        results.append(CheckResult(
            "PASS", "SPLIT_COVERAGE",
            f"바뀐 항목 {len(changed)}개를 Task {len(tasks)}개가 한 번씩 나눴다", None,
        ))
    return results


def cmd_split_check(repo: Path, args: argparse.Namespace) -> int:
    paths = [Path(p) if Path(p).is_absolute() else repo / p for p in args.task]
    return _report_results(repo, _split_check(repo, paths), args.json)


# ---------------------------------------------------------------------------
# ensure-exclude — 설계 문서는 커밋하지 않는다
#
# 문서 폴더(docs·Docs) · intent/ · .task/ 는 팀 밖으로 나가지 않는 설계 문서다 — 커밋 · 푸시하지 않는다.
# 공유 .gitignore 를 고치면 그 고침이 커밋 대상이 되므로 이 clone 에만 있는 info/exclude 에 올린다.
# info/exclude 는 공통 git 디렉터리에 있어 linked worktree(.worktree/<이름>)도 같은 규칙을 쓴다.
# 레포 루트로 고정한다(/docs/ · /intent/) — 하위 폴더의 같은 이름까지 숨기지 않는다. 문서 폴더는
# Linux 가 대소문자를 구분하므로 두 표기를 다 적는다(intent/ · .task/ 는 소문자 하나).
# ---------------------------------------------------------------------------


LOCAL_EXCLUDE_ENTRIES = (".worktree/", ".process/", "/docs/", "/Docs/", f"/{INTENT_DIR}/", f"/{TASK_DIR}/")
LOCAL_EXCLUDE_HEADER = "# claudecode-for-me: local-only design docs and work dirs (never committed)"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return None


def _git_common_dir(repo: Path) -> Path | None:
    """공통 git 디렉터리 절대경로 — linked worktree 안에서도 메인의 .git. git < 2.31 은 --path-format 이 없다."""
    for args in (("rev-parse", "--path-format=absolute", "--git-common-dir"), ("rev-parse", "--git-common-dir")):
        r = _git(repo, *args)
        if r is None:
            return None
        out = r.stdout.strip()
        if r.returncode == 0 and out:
            p = Path(out)
            return p if p.is_absolute() else (repo / p).resolve()
    return None


def _tracked_docs(repo: Path) -> list[str]:
    """문서 폴더 · intent/ · .task/ 아래 이미 커밋된 파일 — exclude 는 tracked 파일을 숨기지 못한다."""
    r = _git(repo, "ls-files", "-z", "--", ":(top,icase)docs", f":(top){INTENT_DIR}", f":(top){TASK_DIR}")
    if r is None or r.returncode != 0:
        return []
    return [n for n in r.stdout.split("\0") if n]


def ensure_local_exclude(repo: Path) -> dict:
    """info/exclude 에 LOCAL_EXCLUDE_ENTRIES 를 넣는다 — 이미 있는 줄은 건너뛴다.

    {"exclude": 경로 | None(git repo 아님), "added": 새로 넣은 줄, "tracked": 이미 커밋된 문서}.
    """
    common = _git_common_dir(repo)
    if common is None:
        return {"exclude": None, "added": [], "tracked": []}
    path = common / "info" / "exclude"
    have = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    lines = {line.strip() for line in have.splitlines()}
    added = [e for e in LOCAL_EXCLUDE_ENTRIES if e not in lines]
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "" if not have or have.endswith("\n") else "\n"
        header = "" if LOCAL_EXCLUDE_HEADER in lines else LOCAL_EXCLUDE_HEADER + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(prefix + header + "\n".join(added) + "\n")
    return {"exclude": str(path), "added": added, "tracked": _tracked_docs(repo)}


def cmd_ensure_exclude(repo: Path, args: argparse.Namespace) -> int:
    result = ensure_local_exclude(repo)
    if result["exclude"] is None:
        print("FAIL EXCLUDE git repository 가 아니다 — `git init` 뒤에 다시 실행한다", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if result["added"]:
        print(f"ADDED {result['exclude']} · {' '.join(result['added'])}")
    else:
        print(f"OK {result['exclude']}")
    for name in result["tracked"][:10]:
        print(f"WARN TRACKED {name} — 이미 커밋된 문서라 exclude 로 숨지 않는다. 추적을 끊을지(git rm --cached) 사용자가 정한다")
    if len(result["tracked"]) > 10:
        print(f"WARN TRACKED … 외 {len(result['tracked']) - 10}개")
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
        description="Intent · Task 문서 검사 helper (intent-catalog · task-catalog 의 --write 와 ensure-exclude 외 read-only)."
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
    sp_catalog.add_argument("--write", action="store_true", help="intent/<app>/intent-catalog.md 와 intent/intent-app-catalog.md 에 기록한다. 없으면 stdout 으로만 낸다(App 카탈로그).")
    sp_catalog.add_argument("--check", action="store_true", help="기존 카탈로그가 재생성 결과와 같은지 검사한다. 다르면 exit 1 + 차이 줄.")
    sp_catalog.add_argument("--json", action="store_true", help="출력 포맷만 JSON 으로 바꾼다. --check/--write 의 동작과 exit code 는 그대로다.")

    sp_check_task = sub.add_parser("check-task")
    sp_check_task.add_argument("--repo", required=True)
    sp_check_task.add_argument("--file", required=True, help="Task 문서 경로 (.task/tsk-<NNN>.md, --repo 기준 상대경로 가능)")
    sp_check_task.add_argument("--json", action="store_true")

    sp_task_catalog = sub.add_parser("task-catalog")
    sp_task_catalog.add_argument("--repo", required=True)
    sp_task_catalog.add_argument("--write", action="store_true", help=".task/task-catalog.md 에 기록한다. 없으면 stdout 으로만 낸다.")
    sp_task_catalog.add_argument("--check", action="store_true", help="기존 카탈로그가 재생성 결과와 같은지 검사한다. 다르면 exit 1 + 차이 줄.")
    sp_task_catalog.add_argument("--json", action="store_true", help="출력 포맷만 JSON 으로 바꾼다. --check/--write 의 동작과 exit code 는 그대로다.")

    sp_exclude = sub.add_parser("ensure-exclude")
    sp_exclude.add_argument("--repo", required=True)
    sp_exclude.add_argument("--json", action="store_true")

    sp_base = sub.add_parser("intent-base")
    sp_base.add_argument("--repo", required=True)
    sp_base.add_argument("--intent", required=True, help="Intent ID (<app>-int-<NNN>)")
    mode = sp_base.add_mutually_exclusive_group(required=True)
    mode.add_argument("--save", action="store_true",
                      help="고치기 전 사본을 남긴다(SAVED) — 이미 있으면 더 오래된 쪽을 지키고(KEPT), "
                           "아직 자르지 않은 Intent 면 남기지 않는다(NEW)")
    mode.add_argument("--drop", action="store_true", help="기준선을 지운다 (/task-split 승인 뒤)")
    sp_base.add_argument("--implemented", action="store_true",
                         help="--save 와 함께 — 한 번도 자르지 않았지만 옛 방식으로 이미 구현한 Intent 의 기준선을 남긴다")

    sp_diff = sub.add_parser("intent-diff")
    sp_diff.add_argument("--repo", required=True)
    sp_diff.add_argument("--intent", required=True, help="Intent ID (<app>-int-<NNN>)")
    sp_diff.add_argument("--json", action="store_true")

    sp_mark = sub.add_parser("mark-intent")
    sp_mark.add_argument("--repo", required=True)
    sp_mark.add_argument("--task", required=True, help="Task 문서 경로 (.task/tsk-<NNN>.md)")
    sp_mark.add_argument("--remove", action="store_true", help="이 Task 의 진행 표시를 걷어 낸다 (삭제 예정 줄은 지운다)")
    sp_mark.add_argument("--json", action="store_true")

    sp_split = sub.add_parser("split-check")
    sp_split.add_argument("--repo", required=True)
    sp_split.add_argument("--task", required=True, action="append", help="이번에 만든 Task 문서 경로 (여러 번)")
    sp_split.add_argument("--json", action="store_true")

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else (e.code or 0)

    repo = _resolve_repo(args.repo)
    # 문서 ID · App 이름은 소문자다 — 사람이 대문자로 줘도 받아 준다(문서 안 표기는 검사가 엄격히 본다).
    for name in ("app", "intent"):
        if isinstance(getattr(args, name, None), str):
            setattr(args, name, getattr(args, name).lower())

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
    if args.cmd == "ensure-exclude":
        return cmd_ensure_exclude(repo, args)
    if args.cmd == "intent-base":
        return cmd_intent_base(repo, args)
    if args.cmd == "intent-diff":
        return cmd_intent_diff(repo, args)
    if args.cmd == "mark-intent":
        return cmd_mark_intent(repo, args)
    if args.cmd == "split-check":
        return cmd_split_check(repo, args)
    print(f"FAIL ARGS unknown cmd: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
