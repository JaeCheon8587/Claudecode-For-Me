#!/usr/bin/env python3
"""ddr_loop — doc-driven 수렴 루프 셋업 helper.

forge-scope 워크트리(feat-<slug>)에 ddr-loop 빌드/프로그레스 문서를 스캐폴딩한다.
오케스트레이션·리뷰·수정은 하지 않는다 — 그건 호출 세션이 doc_driven_review.py 를
반복 호출하며 워크트리 안에서 인라인으로 수행한다.

Subcommands
-----------
- init : 워크트리·docs 검증 → .process/<docName>/{ddr-loop-build.md, ddr-loop-progress.md}
         스캐폴딩(자기 파일만 덮어쓰기 — forge-scope 산출물 보존) → JSON 매니페스트.

표준 라이브러리만 사용한다 (Python 3.10+).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

EXIT_OK = 0
EXIT_ERR = 1
EXIT_BLOCKED = 2  # git repo 아님 / 워크트리 없음 / docs 없음

DDR_TEMPLATES = ["ddr-loop-build.md", "ddr-loop-progress.md"]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd=root)


def _err(msg: str, code: int = EXIT_ERR) -> "NoReturn":  # type: ignore[name-defined]
    print(msg, file=sys.stderr)
    sys.exit(code)


def _repo_root(start: Path) -> Optional[Path]:
    r = _git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip())


def _slugify(stem: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return s or "task"


def _split_md_row(line: str) -> list[str]:
    if not line.strip().startswith("|"):
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells)


def _section(text: str, heading_re: str) -> Optional[str]:
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(heading_re, ln):
            start = i
            break
    if start is None:
        return None
    body: list[str] = []
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        body.append(ln)
    return "\n".join(body)


def _markdown_links(text: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2).strip()) for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text)]


def _markdown_table(section_text: str) -> list[dict[str, str]]:
    header: Optional[list[str]] = None
    rows: list[dict[str, str]] = []
    for line in section_text.splitlines():
        cells = _split_md_row(line)
        if not cells:
            if header and rows:
                break
            continue
        if _is_separator_row(cells):
            continue
        if header is None:
            header = cells
            continue
        padded = cells + [""] * max(0, len(header) - len(cells))
        rows.append(dict(zip(header, padded)))
    return rows


def _resolve_path(root: Path, base_doc: Optional[Path], value: str) -> Path:
    value = value.split("#", 1)[0].strip()
    p = Path(value)
    if p.is_absolute():
        return p.resolve()
    if base_doc is not None and value.startswith(".."):
        return (base_doc.parent / p).resolve()
    return (root / p).resolve()


def _path_from_build_line(build_text: str, label: str) -> Optional[str]:
    pattern = rf"^\s*-\s*{re.escape(label)}:\s*`([^`]+)`"
    for line in build_text.splitlines():
        m = re.match(pattern, line)
        if m:
            value = m.group(1).strip()
            if value and not value.startswith("("):
                return value
    return None


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            out.append(p.resolve())
    return out


def _auto_docs_from_forge_scope(root: Path, wt: Path, doc_name: str) -> tuple[list[Path], dict, list[str]]:
    """forge-scope-build.md의 Work Packet에서 DDR 비교 문서를 자동 구성."""
    build_md = wt / ".process" / doc_name / "forge-scope-build.md"
    meta: dict = {
        "docs_source": "auto-work-packet",
        "forge_build_md": str(build_md),
        "work_packet": None,
        "task_doc": None,
        "required_ssot": [],
    }
    problems: list[str] = []

    if not build_md.is_file():
        problems.append(f"forge-scope-build.md 없음: {build_md} — `--docs <doc...>`를 명시하세요.")
        return [], meta, problems

    build_text = build_md.read_text(encoding="utf-8", errors="replace")
    wp_value = _path_from_build_line(build_text, "Work Packet")
    if not wp_value:
        problems.append("forge-scope-build.md에 Work Packet 경로가 없음 — `--docs <doc...>`를 명시하세요.")
        return [], meta, problems

    work_packet = _resolve_path(root, None, wp_value)
    meta["work_packet"] = str(work_packet)
    if not work_packet.is_file():
        problems.append(f"Work Packet 파일 없음: {work_packet}")
        return [], meta, problems

    wp_text = work_packet.read_text(encoding="utf-8", errors="replace")
    docs = [work_packet]

    task_value = _path_from_build_line(build_text, "TASK 문서")
    task_doc: Optional[Path] = _resolve_path(root, None, task_value) if task_value else None
    if task_doc is None:
        links = _markdown_links(_section(wp_text, r"^##\s*2\.\s*TASK\b") or "")
        if links:
            task_doc = _resolve_path(root, work_packet, links[0][1])
    if task_doc is None or not task_doc.is_file():
        problems.append(f"연결 TASK 파일 없음: {task_doc or '(경로 없음)'}")
    else:
        meta["task_doc"] = str(task_doc)
        docs.append(task_doc)

    matrix = _section(wp_text, r"^##\s*4\.\s*Required SSOT Execution Matrix\b")
    if matrix is None:
        problems.append("Required SSOT Execution Matrix 섹션 없음.")
    else:
        rows = _markdown_table(matrix)
        for idx, row in enumerate([r for r in rows if r.get("Priority", "").strip() == "Required"], start=1):
            links = _markdown_links(row.get("Document", ""))
            if not links:
                problems.append(f"Required SSOT row {idx}: Document 링크 없음.")
                continue
            ssot = _resolve_path(root, work_packet, links[0][1])
            if not ssot.is_file():
                problems.append(f"Required SSOT row {idx}: 파일 없음: {ssot}")
                continue
            meta["required_ssot"].append(str(ssot))
            docs.append(ssot)

    if not meta["required_ssot"]:
        problems.append("Required SSOT 문서가 자동 발견되지 않음 — `--docs <doc...>`를 명시하세요.")

    return _unique_paths(docs), meta, problems


def _registered_worktree_path(root: Path, branch: str) -> Optional[Path]:
    r = _git(root, "worktree", "list", "--porcelain")
    if r.returncode != 0:
        return None
    current: Optional[Path] = None
    target_ref = f"refs/heads/{branch}"
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree "):])
        elif line.startswith("branch ") and current is not None:
            if line[len("branch "):].strip() == target_ref:
                return current
    return None


def _ensure_gitignore(wt: Path, entries: list[str]) -> None:
    gi = wt / ".gitignore"
    have = gi.read_text(encoding="utf-8", errors="replace") if gi.exists() else ""
    lines = {l.strip() for l in have.splitlines()}
    add = [e for e in entries if e not in lines]
    if add:
        prefix = "" if have.endswith("\n") or not have else "\n"
        with gi.open("a", encoding="utf-8") as f:
            f.write(prefix + "\n".join(add) + "\n")


def cmd_init(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다. forge 메인 repo 루트에서 실행하세요.", EXIT_BLOCKED)

    slug = _slugify(args.slug)
    branch = f"feat-{slug}"

    registered = _registered_worktree_path(root, branch)
    if registered is None or not registered.exists():
        _err(
            f"ERROR: forge 워크트리 없음: branch={branch}, dir={root / '.worktree' / slug}\n"
            "  Hint: 먼저 `/forge-scope <WORK_PACKET>`로 워크트리를 만들거나 slug를 확인하세요.\n"
            "  목록: `python worktree_setup.py list`",
            EXIT_BLOCKED,
        )
    wt = registered

    doc_name = args.name or slug

    docs_meta: dict = {
        "docs_source": "explicit",
        "forge_build_md": None,
        "work_packet": None,
        "task_doc": None,
        "required_ssot": [],
    }

    # docs 존재 검사. --docs 생략 시 forge-scope Work Packet에서 자동 구성한다.
    docs_paths: list[Path] = []
    missing: list[str] = []
    if args.docs:
        for d in args.docs:
            p = Path(d)
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            (docs_paths if p.is_file() else missing).append(p)
        if missing:
            _err("ERROR: 비교 문서 없음:\n" + "\n".join(f"  - {m}" for m in missing), EXIT_BLOCKED)
    else:
        docs_paths, docs_meta, auto_problems = _auto_docs_from_forge_scope(root, wt, doc_name)
        if auto_problems:
            _err("ERROR: 비교 문서 자동 구성 실패:\n" + "\n".join(f"  - {p}" for p in auto_problems), EXIT_BLOCKED)

    docs_abs = [str(p.resolve()) for p in _unique_paths(docs_paths)]

    def _rel(p: str) -> str:
        try:
            return Path(p).relative_to(root).as_posix()
        except ValueError:
            return Path(p).as_posix()
    doc_disp = ", ".join(_rel(d) for d in docs_abs)
    work_packet_disp = _rel(docs_meta["work_packet"]) if docs_meta.get("work_packet") else "(explicit docs - none)"
    task_doc_disp = _rel(docs_meta["task_doc"]) if docs_meta.get("task_doc") else "(explicit docs - none)"
    required_ssot_disp = ", ".join(_rel(d) for d in docs_meta.get("required_ssot", [])) or "(explicit docs - none)"

    # .process/<docName>/ 는 rmtree 하지 않는다 — forge-scope 산출물 보존. 자기 파일만 덮어쓴다.
    proc = wt / ".process" / doc_name
    proc.mkdir(parents=True, exist_ok=True)

    tmpl_dir = Path(__file__).resolve().parent / "ddr_templates"
    subs = {
        "{docName}": doc_name,
        "{docPath}": doc_disp,
        "{slug}": slug,
        "{branch}": branch,
        "{docsSource}": docs_meta["docs_source"],
        "{workPacketPath}": work_packet_disp,
        "{taskDocPath}": task_doc_disp,
        "{requiredSsotDocs}": required_ssot_disp,
    }
    written: dict[str, Path] = {}
    for name in DDR_TEMPLATES:
        out = proc / name
        src = tmpl_dir / name
        if src.is_file():
            content = src.read_text(encoding="utf-8", errors="replace")
            for k, v in subs.items():
                content = content.replace(k, v)
        else:
            content = f"# {name} — {doc_name}\n(템플릿 없음: {name})\n"
        out.write_text(content, encoding="utf-8")  # 덮어쓰기 = 재호출 시 루프 상태 리셋
        written[name] = out

    _ensure_gitignore(wt, [".review/", ".claude/doc-driven-review-logs/"])

    manifest = {
        "root": str(root),
        "worktree": str(wt),
        "branch": branch,
        "docName": doc_name,
        "docs": docs_abs,
        **docs_meta,
        "base": args.base,
        "build_md": str(written["ddr-loop-build.md"]),
        "progress_md": str(written["ddr-loop-progress.md"]),
    }
    if not args.quiet:
        print(f"[ddr] worktree: {wt}")
        print(f"[ddr] branch:   {branch}")
        print(f"[ddr] docs:     {doc_disp}")
        print(f"[ddr] .process: {proc}")
    print(json.dumps(manifest, ensure_ascii=False))
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="ddr_loop", description="doc-driven 수렴 루프 셋업 helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="워크트리·docs 검증 + ddr 빌드/프로그레스 스캐폴딩")
    pi.add_argument("--slug", required=True, help="forge 워크트리 slug (.worktree/<slug>, feat-<slug>)")
    pi.add_argument("--docs", nargs="+", default=None, help="비교 문서 경로 1개 이상 (생략 시 forge-scope Work Packet에서 자동 구성)")
    pi.add_argument("--name", default=None, help="docName 명시 (기본: slug — forge-scope .process 폴더 공유)")
    pi.add_argument("--base", default=None, help="branch scope 기준 ref (manifest 기록 → 세션이 review에 전달)")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
