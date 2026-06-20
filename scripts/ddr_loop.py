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
            "  Hint: 먼저 `/forge-scope <TASK-doc>`로 워크트리를 만들거나 slug를 확인하세요.\n"
            "  목록: `python worktree_setup.py list`",
            EXIT_BLOCKED,
        )
    wt = registered

    # docs 존재 검사
    docs_abs: list[str] = []
    missing: list[str] = []
    for d in args.docs:
        p = Path(d)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        (docs_abs if p.is_file() else missing).append(str(p))
    if missing:
        _err("ERROR: 비교 문서 없음:\n" + "\n".join(f"  - {m}" for m in missing), EXIT_BLOCKED)

    doc_name = args.name or slug

    def _rel(p: str) -> str:
        try:
            return Path(p).relative_to(root).as_posix()
        except ValueError:
            return Path(p).as_posix()
    doc_disp = ", ".join(_rel(d) for d in docs_abs)

    # .process/<docName>/ 는 rmtree 하지 않는다 — forge-scope 산출물 보존. 자기 파일만 덮어쓴다.
    proc = wt / ".process" / doc_name
    proc.mkdir(parents=True, exist_ok=True)

    tmpl_dir = Path(__file__).resolve().parent / "ddr_templates"
    subs = {"{docName}": doc_name, "{docPath}": doc_disp, "{slug}": slug, "{branch}": branch}
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
    pi.add_argument("--docs", nargs="+", required=True, help="비교 문서 경로 1개 이상")
    pi.add_argument("--name", default=None, help="docName 명시 (기본: slug — forge-scope .process 폴더 공유)")
    pi.add_argument("--base", default=None, help="branch scope 기준 ref (manifest 기록 → 세션이 review에 전달)")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
