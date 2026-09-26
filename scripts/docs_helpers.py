"""docs_helpers — v0.7 per-App docs read-only inspection helper.

Subcommands:
    list-apps   /CLAUDE.md Backend Services Overview 표 + docs/<App>/ 폴더 교차검증
    next-id     기존 NNN 최대값 + 1 산출 (frd/task/adr, active 또는 backlog)
    parse-fc    docs/<App>/<App>-FC.md 5 표 파싱
    parse-frd   docs/<App>/FRD/<App>-FRD-<NNN>.md 파싱
    git-user    git config user.name
    check       v0.7 파일 무결성 검사
    check-intent  Intent 문서(<App>-INT-<NNN>.md) 구조 검증 — rule set A·B
    intent-checklist  Intent 문서 검증 기준표(행·코드 facts·인용 표본) 생성 · critic 반환 검사

Standard library only. Windows PowerShell 호환.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


APP_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*$")

FRD_FILENAME_PATTERN = lambda app: re.compile(rf"^{re.escape(app)}-FRD-(\d{{3}})\.md$")
TASK_FILENAME_PATTERN = lambda app: re.compile(rf"^{re.escape(app)}-TASK-(\d{{3}})\.md$")
ADR_FILENAME_PATTERN = lambda app: re.compile(rf"^{re.escape(app)}-ADR-(\d{{3}})\.md$")

FRD_V07_SECTION_TITLES = (
    (1, "기능 요약"),
    (2, "범위"),
    (3, "사용자 역할"),
    (4, "사전 조건"),
    (5, "기본 흐름"),
    (6, "대안 흐름"),
    (7, "예외 흐름"),
    (8, "상세 기능 요구사항"),
    (9, "입출력 개념"),
    (10, "상태 정의"),
    (11, "권한 조건"),
    (12, "데이터 처리 원칙"),
    (13, "비기능 요구사항"),
    (14, "로그 / 알림 / 이력 정책"),
    (15, "UI / 외부 연계 영향"),
    (16, "FC / ADR-CATALOG / ADR 반영 여부"),
    (17, "수용 기준"),
    (18, "테스트 관점"),
    (19, "요구 근거"),
    (20, "미확인 사항"),
)

FRD_EXPECTED_SECTIONS = tuple(s[0] for s in FRD_V07_SECTION_TITLES)
FRD_SECTION_HEAD_PATTERN = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)

META_ROW_PATTERN = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", re.MULTILINE)
DOC_ID_ROW_PATTERN = re.compile(r"^\|\s*문서\s*ID\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
VERSION_ROW_PATTERN = re.compile(r"^\|\s*버전\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)

AC_ID_PATTERN = lambda fid: re.compile(rf"AC-{re.escape(fid)}-(\d{{3}})")
TC_ID_PATTERN = lambda fid: re.compile(rf"TC-{re.escape(fid)}-(\d{{3}})")
Q_ID_PATTERN = lambda fid: re.compile(rf"Q-{re.escape(fid)}-(\d{{3}})")

ACTIVE_RANGE = range(1, 100)   # F001..F099
BACKLOG_RANGE = range(101, 1000)  # F101..F999

BACKEND_TABLE_HEADER_KEYS = ("SYSTEM_CODE", "APP_CODE", "App")

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


# ---------------------------------------------------------------------------
# list-apps
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AppEntry:
    code: str
    docs_dir: str
    src_dir: str

    def to_dict(self) -> dict:
        return {"code": self.code, "docs_dir": self.docs_dir, "src_dir": self.src_dir}


def _parse_backend_services_table(text: str) -> list[AppEntry]:
    """/CLAUDE.md Backend Services Overview 표 파싱.

    헤더 셀에 SYSTEM_CODE / APP_CODE / App 중 하나 포함 시 첫 컬럼 = App code.
    """
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
    candidates: list[AppEntry] = []
    for sec in sections:
        if "Backend Services Overview" not in sec.splitlines()[0:1] and "Backend Services" not in sec.splitlines()[0:1]:
            continue
        lines = sec.splitlines()
        header_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("|") and any(k in line for k in BACKEND_TABLE_HEADER_KEYS):
                header_idx = i
                break
        if header_idx is None:
            continue
        for line in lines[header_idx + 2:]:
            s = line.strip()
            if not s.startswith("|"):
                break
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells:
                continue
            code = cells[0]
            if not APP_CODE_PATTERN.match(code) or code in {"SYSTEM_CODE", "APP_CODE", "App", "{SYSTEM_CODE}", "{APP_CODE}"}:
                continue
            candidates.append(AppEntry(code=code, docs_dir=f"docs/{code}", src_dir=f"Src/{code}"))
        if candidates:
            break
    return candidates


def _scan_docs_folders(repo: Path) -> list[str]:
    docs = repo / "docs"
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


def cmd_list_apps(repo: Path) -> int:
    claude_text = _read_text(repo / "CLAUDE.md")
    parsed: list[AppEntry] = []
    if claude_text:
        parsed = _parse_backend_services_table(claude_text)
    docs_folders = set(_scan_docs_folders(repo))
    if parsed:
        verified = [a for a in parsed if a.code in docs_folders]
        unbootstrapped = [a.code for a in parsed if a.code not in docs_folders]
    else:
        verified = [AppEntry(code=c, docs_dir=f"docs/{c}", src_dir=f"Src/{c}") for c in sorted(docs_folders)]
        unbootstrapped = []
    payload = {
        "apps": [a.to_dict() for a in verified],
        "unbootstrapped": unbootstrapped,
        "source": "claude-md" if parsed else "docs-folder-fallback",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# next-id
# ---------------------------------------------------------------------------


def _scan_nnn(folder: Path, pattern: re.Pattern[str]) -> list[int]:
    if not folder.is_dir():
        return []
    out: list[int] = []
    for f in folder.glob("*.md"):
        m = pattern.match(f.name)
        if m:
            try:
                out.append(int(m.group(1)))
            except ValueError:
                continue
    return sorted(out)


def cmd_next_id(repo: Path, app: str, kind: str, backlog: bool) -> int:
    if kind not in {"frd", "task", "adr"}:
        print(f"FAIL ARGS --kind must be frd|task|adr: {kind}", file=sys.stderr)
        return 2
    if backlog and kind != "frd":
        print("FAIL ARGS --backlog only valid with --kind frd", file=sys.stderr)
        return 2

    docs_dir = repo / "docs" / app
    if not docs_dir.is_dir():
        print(f"FAIL ARGS app docs not found: {docs_dir}", file=sys.stderr)
        return 2

    if kind == "frd":
        folder = docs_dir / "FRD"
        pat = FRD_FILENAME_PATTERN(app)
    elif kind == "task":
        folder = docs_dir / "TASK"
        pat = TASK_FILENAME_PATTERN(app)
    elif kind == "adr":
        folder = docs_dir / "ADR"
        pat = ADR_FILENAME_PATTERN(app)

    used = _scan_nnn(folder, pat)
    if kind == "frd":
        rng = BACKLOG_RANGE if backlog else ACTIVE_RANGE
        in_range = [n for n in used if n in rng]
        if not in_range:
            next_n = rng.start
        else:
            next_n = max(in_range) + 1
            if next_n not in rng:
                print(f"FAIL LIMIT frd {'backlog' if backlog else 'active'} range exhausted (max={max(in_range)})", file=sys.stderr)
                return 2
    else:
        if not used:
            next_n = 1
        else:
            next_n = max(used) + 1
            if next_n > 999:
                print(f"FAIL LIMIT {kind} range exhausted (max={max(used)})", file=sys.stderr)
                return 2

    print(f"{next_n:03d}")
    return 0


# ---------------------------------------------------------------------------
# parse-fc
# ---------------------------------------------------------------------------


def _strip_md_link(value: str) -> str:
    m = re.match(r"^\[([^\]]+)\]\([^)]*\)$", value.strip())
    return m.group(1) if m else value.strip()


def _split_md_row(line: str) -> list[str]:
    s = line.strip()
    if not s.startswith("|"):
        return []
    return [c.strip() for c in s.strip("|").split("|")]


def _is_separator_row(line: str) -> bool:
    s = line.strip()
    if not s.startswith("|"):
        return False
    body = s.strip("|")
    return bool(re.match(r"^[\s\-:|]+$", body))


def _extract_tables_under_heading(text: str, heading_level: int, heading_titles: tuple[str, ...]) -> dict[str, list[list[str]]]:
    """heading_titles 마다 1개의 표 추출. 결과: {title: rows (header+data)}"""
    out: dict[str, list[list[str]]] = {}
    head_re = re.compile(rf"^{'#' * heading_level}\s+(.+?)\s*$", re.MULTILINE)
    matches = list(head_re.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        if title not in heading_titles:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        rows: list[list[str]] = []
        in_table = False
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                if _is_separator_row(line):
                    in_table = True
                    continue
                cells = _split_md_row(line)
                if not cells:
                    continue
                rows.append(cells)
            elif in_table and stripped == "":
                continue
            elif in_table and stripped != "":
                break
        out[title] = rows
    return out


FC_TABLE_TITLES = (
    "기본 식별·설명",
    "문서 연결",
    "검증·근거·확인",
    "기능 요구 추적",
    "타 App 협력 흐름",
)
FC_BACKLOG_HEADINGS = ("확장 후보 기능 (Backlog)",)


def cmd_parse_fc(repo: Path, app: str) -> int:
    fc_path = repo / "docs" / app / f"{app}-FC.md"
    text = _read_text(fc_path)
    if text is None:
        print(f"FAIL FC not found: {fc_path}", file=sys.stderr)
        return 2

    tables = _extract_tables_under_heading(text, 3, FC_TABLE_TITLES)
    backlog_tables = _extract_tables_under_heading(text, 2, FC_BACKLOG_HEADINGS)

    features: dict[str, dict] = {}

    basic = tables.get("기본 식별·설명", [])
    if len(basic) >= 1:
        header = [h for h in basic[0]]
        for row in basic[1:]:
            if not row:
                continue
            fid = row[0]
            if not re.match(r"^F\d{3}$", fid):
                continue
            features.setdefault(fid, {"id": fid})
            for col, val in zip(header, row):
                key = {
                    "기능 ID": "id",
                    "기능명": "name",
                    "기능 설명": "summary",
                    "기능 상태": "status",
                    "구현 상태": "impl_status",
                    "테스트 상태": "test_status",
                    "우선순위": "priority",
                }.get(col, col)
                features[fid][key] = val

    link = tables.get("문서 연결", [])
    if len(link) >= 1:
        header = link[0]
        for row in link[1:]:
            if not row:
                continue
            fid = row[0]
            if not re.match(r"^F\d{3}$", fid):
                continue
            f = features.setdefault(fid, {"id": fid})
            for col, val in zip(header, row):
                if col == "관련 FRD":
                    f["frd_link"] = _strip_md_link(val)

    backlog: list[dict] = []
    if backlog_tables.get("확장 후보 기능 (Backlog)"):
        bl = backlog_tables["확장 후보 기능 (Backlog)"]
        if len(bl) >= 1:
            header = bl[0]
            for row in bl[1:]:
                if not row:
                    continue
                fid = row[0]
                if not re.match(r"^F\d{3}$", fid):
                    continue
                entry: dict = {"id": fid}
                for col, val in zip(header, row):
                    key = {
                        "기능 ID": "id",
                        "기능명": "name",
                        "설명": "summary",
                        "상태": "status",
                        "우선순위": "priority",
                        "근거": "rationale",
                    }.get(col, col)
                    entry[key] = val
                backlog.append(entry)

    payload = {
        "features": list(features.values()),
        "backlog": backlog,
        "tables_found": list(tables.keys()),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# parse-frd
# ---------------------------------------------------------------------------


def cmd_parse_frd(repo: Path, app: str, frd_id: str) -> int:
    if not re.match(r"^F\d{3}$", frd_id):
        print(f"FAIL ARGS --frd-id must match F\\d{{3}}: {frd_id}", file=sys.stderr)
        return 2
    nnn = frd_id[1:]
    frd_path = repo / "docs" / app / "FRD" / f"{app}-FRD-{nnn}.md"
    text = _read_text(frd_path)
    if text is None:
        print(f"FAIL FRD not found: {frd_path}", file=sys.stderr)
        return 2

    meta: dict[str, str] = {}
    for m in META_ROW_PATTERN.finditer(text[:2000]):
        k = m.group(1).strip()
        v = m.group(2).strip()
        if k in {"항목", "---", ""}:
            continue
        meta[k] = v

    version = ""
    vm = VERSION_ROW_PATTERN.search(text)
    if vm:
        version = vm.group(1).strip()

    sections: dict[int, str] = {}
    section_iter = list(FRD_SECTION_HEAD_PATTERN.finditer(text))
    for i, mm in enumerate(section_iter):
        n = int(mm.group(1))
        start = mm.end()
        end = section_iter[i + 1].start() if i + 1 < len(section_iter) else len(text)
        sections[n] = text[start:end].strip()

    def _max(pat: re.Pattern[str]) -> int:
        nums = [int(g) for g in pat.findall(text)]
        return max(nums) if nums else 0

    payload = {
        "frd_id": frd_id,
        "path": str(frd_path),
        "meta": meta,
        "version": version,
        "sections": {str(k): v for k, v in sections.items()},
        "ac_max": _max(AC_ID_PATTERN(frd_id)),
        "tc_max": _max(TC_ID_PATTERN(frd_id)),
        "q_max": _max(Q_ID_PATTERN(frd_id)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# git-user
# ---------------------------------------------------------------------------


def cmd_git_user(repo: Path) -> int:
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("Unknown")
        return 0
    name = (result.stdout or "").strip()
    print(name if name else "Unknown")
    return 0


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


def _check_app(repo: Path, app: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    docs_dir = repo / "docs" / app
    if not docs_dir.is_dir():
        results.append(CheckResult("FAIL", "APP_DIR", "missing", docs_dir))
        return results
    results.append(CheckResult("PASS", "APP_DIR", "exists", docs_dir))

    required_files = [
        f"{app}-PRD.md",
        f"{app}-FC.md",
        f"{app}-ARCHITECTURE.md",
        f"{app}-ADR-CATALOG.md",
    ]
    for rel in required_files:
        p = docs_dir / rel
        if p.is_file():
            results.append(CheckResult("PASS", "APP_FILE", "exists", p))
        else:
            results.append(CheckResult("FAIL", "APP_FILE", "missing", p))

    required_dirs = ["FRD", "ADR", "TASK"]
    for rel in required_dirs:
        d = docs_dir / rel
        if d.is_dir():
            results.append(CheckResult("PASS", "APP_SUBDIR", "exists", d))
        else:
            results.append(CheckResult("FAIL", "APP_SUBDIR", "missing", d))

    frd_dir = docs_dir / "FRD"
    if frd_dir.is_dir():
        pat = FRD_FILENAME_PATTERN(app)
        for f in sorted(frd_dir.glob("*.md")):
            if not pat.match(f.name):
                results.append(CheckResult("FAIL", "FRD_NAME", "invalid filename", f))
                continue
            results.append(CheckResult("PASS", "FRD_NAME", "valid", f))
            text = _read_text(f)
            if text is None:
                results.append(CheckResult("FAIL", "READ_TEXT", "cannot read", f))
                continue
            nums = set(int(n) for n in FRD_SECTION_HEAD_PATTERN.findall(text))
            missing = [n for n in FRD_EXPECTED_SECTIONS if n not in nums]
            if missing:
                for n in missing:
                    results.append(CheckResult("FAIL", "FRD_SECTION", f"missing section {n}", f))
            else:
                results.append(CheckResult("PASS", "FRD_SECTION", "all 20 sections", f))
            doc_id_match = DOC_ID_ROW_PATTERN.search(text)
            expected_id = f.stem
            if doc_id_match is None:
                results.append(CheckResult("FAIL", "FRD_META", "doc id row missing", f))
            elif doc_id_match.group(1).strip() != expected_id:
                results.append(CheckResult(
                    "FAIL", "FRD_META",
                    f"doc id mismatch: {doc_id_match.group(1).strip()} != {expected_id}",
                    f,
                ))
            else:
                results.append(CheckResult("PASS", "FRD_META", "doc id matches", f))

    task_dir = docs_dir / "TASK"
    if task_dir.is_dir():
        pat = TASK_FILENAME_PATTERN(app)
        for f in sorted(task_dir.glob("*.md")):
            if not pat.match(f.name):
                results.append(CheckResult("FAIL", "TASK_NAME", "invalid filename", f))
            else:
                results.append(CheckResult("PASS", "TASK_NAME", "valid", f))

    adr_dir = docs_dir / "ADR"
    if adr_dir.is_dir():
        pat = ADR_FILENAME_PATTERN(app)
        adr_files: list[Path] = []
        for f in sorted(adr_dir.glob("*.md")):
            if not pat.match(f.name):
                results.append(CheckResult("FAIL", "ADR_NAME", "invalid filename", f))
            else:
                results.append(CheckResult("PASS", "ADR_NAME", "valid", f))
                adr_files.append(f)
        catalog_path = docs_dir / f"{app}-ADR-CATALOG.md"
        catalog_text = _read_text(catalog_path) or ""
        for f in adr_files:
            stem = f.stem
            if stem not in catalog_text:
                results.append(CheckResult(
                    "FAIL", "ADR_CATALOG", f"{stem} not referenced in ADR-CATALOG", catalog_path,
                ))
            else:
                results.append(CheckResult("PASS", "ADR_CATALOG", f"{stem} referenced", catalog_path))

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


@dataclass
class IntentItem:
    kind: str                 # "D" | "C" | "OS" | "FR" | "E" | "X" | "A"
    id: str                   # "D1", "C2", "OS3", "FR-4", "E-1", "X-2", "A-5"
    num: int
    text: str                 # id 접두·끝의 refs 그룹을 제외한 본문
    refs: list[str]           # e.g. ["D1", "C2"], ["FR-3", "OS"]; 없으면 []
    line: int                 # 파일 내 1-based 줄번호
    checked: bool | None      # A 항목만: "- [ ]"/"- [x]" → True, "- A-n." → False, 그 외 None


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
INTENT_REF_GROUP_PATTERN = re.compile(r"^(.*)\(([^()]*)\)\s*$")
INTENT_REFS_INNER_PATTERN = re.compile(
    r"^(?:D\d+|C\d+|FR-\d+|OS)(?:,\s*(?:D\d+|C\d+|FR-\d+|OS))*$"
)


def _split_table_cells(line: str) -> list[str]:
    """표 행(`| a | b |`)을 셀로 분할한다. \| 이스케이프는 경계로 취급하지 않는다."""
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
    hits: list[tuple[int, str]] = []
    in_comment = False
    for lineno, line in enumerate(doc.raw_lines, start=1):
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
        for m in re.finditer(r"\{[^{}\n]*\}", _strip_code_spans(live)):
            hits.append((lineno, m.group(0)))
    return hits


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
    out: list[tuple[int, str]] = []
    in_comment = False
    for i, line in enumerate(doc.sections[name].split("\n")):
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
        out.append((doc.section_lines[name] + 1 + i, live))
    return out


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
        path = repo / path
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
    results = _check_intent_file(repo, Path(args.file))
    p = sum(1 for r in results if r.level == "PASS")
    w = sum(1 for r in results if r.level == "WARN")
    f = sum(1 for r in results if r.level == "FAIL")
    if args.json:
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
# Entry
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="v0.7 docs read-only helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_list = sub.add_parser("list-apps")
    sp_list.add_argument("--repo", required=True)

    sp_next = sub.add_parser("next-id")
    sp_next.add_argument("--repo", required=True)
    sp_next.add_argument("--app", required=True)
    sp_next.add_argument("--kind", required=True, choices=("frd", "task", "adr"))
    sp_next.add_argument("--backlog", action="store_true")

    sp_pfc = sub.add_parser("parse-fc")
    sp_pfc.add_argument("--repo", required=True)
    sp_pfc.add_argument("--app", required=True)

    sp_pfrd = sub.add_parser("parse-frd")
    sp_pfrd.add_argument("--repo", required=True)
    sp_pfrd.add_argument("--app", required=True)
    sp_pfrd.add_argument("--frd-id", required=True, dest="frd_id")

    sp_user = sub.add_parser("git-user")
    sp_user.add_argument("--repo", required=True)

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

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else (e.code or 0)

    repo = _resolve_repo(args.repo)

    if args.cmd == "list-apps":
        return cmd_list_apps(repo)
    if args.cmd == "next-id":
        return cmd_next_id(repo, args.app, args.kind, args.backlog)
    if args.cmd == "parse-fc":
        return cmd_parse_fc(repo, args.app)
    if args.cmd == "parse-frd":
        return cmd_parse_frd(repo, args.app, args.frd_id)
    if args.cmd == "git-user":
        return cmd_git_user(repo)
    if args.cmd == "check":
        return cmd_check(repo, args.app)
    if args.cmd == "check-intent":
        return cmd_check_intent(args)
    if args.cmd == "intent-checklist":
        return cmd_intent_checklist(args)
    print(f"FAIL ARGS unknown cmd: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
