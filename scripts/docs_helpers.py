"""docs_helpers — v0.7 per-App docs read-only inspection helper.

Subcommands:
    list-apps   /CLAUDE.md Backend Services Overview 표 + docs/<App>/ 폴더 교차검증
    next-id     기존 NNN 최대값 + 1 산출 (frd/task/adr, active 또는 backlog)
    parse-fc    docs/<App>/<App>-FC.md 5 표 파싱
    parse-frd   docs/<App>/FRD/<App>-FRD-<NNN>.md 파싱
    git-user    git config user.name
    check       v0.7 파일 무결성 검사

Standard library only. Windows PowerShell 호환.
"""

from __future__ import annotations

import argparse
import json
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
    else:
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
    print(f"FAIL ARGS unknown cmd: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
