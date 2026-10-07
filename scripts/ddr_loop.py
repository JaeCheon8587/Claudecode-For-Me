#!/usr/bin/env python3
"""ddr_loop — doc-driven 수렴 루프 셋업 helper.

forge-init 이 만든 워크트리에 ddr-loop 빌드/프로그레스 문서를 스캐폴딩한다. 브랜치·비교 문서(Intent)·
base 는 forge-init 매니페스트(.process/forge/<slug>.json)에서 읽는다.
오케스트레이션·리뷰·수정은 하지 않는다 — 그건 호출 세션이 doc_driven_review.py 를
반복 호출하며 워크트리 안에서 인라인으로 수행한다.

Subcommands
-----------
- init : 워크트리·docs 검증 → .process/<docName>/{ddr-loop-build.md, ddr-loop-progress.md}
         스캐폴딩(자기 파일만 덮어쓰기 — 다른 산출물 보존) → JSON 매니페스트.

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


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            out.append(p.resolve())
    return out


def _load_forge_manifest(path: Path) -> Optional[dict]:
    """forge-init 이 메인 repo 에 남긴 매니페스트(.process/forge/<slug>.json). 없거나 깨지면 None."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _intent_from_manifest(manifest: dict) -> Optional[Path]:
    """비교 문서 = 워크트리 안 Intent 사본(in-dev). 없으면 메인 repo 원본으로 폴백."""
    for key in ("intent_worktree", "intent"):
        value = manifest.get(key)
        if value and Path(value).is_file():
            return Path(value).resolve()
    return None


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

    # 브랜치·비교 문서·base 는 forge-init 매니페스트에서 읽는다. 브랜치 이름은 Intent Handoff 로
    # 정해지므로(기본 intent/<문서 ID>) slug 에서 유도하지 않는다.
    mf_path = root / ".process" / "forge" / f"{slug}.json"
    forge = _load_forge_manifest(mf_path)
    if forge is None or not forge.get("branch"):
        _err(
            f"ERROR: forge-init 매니페스트 없음 또는 손상: {mf_path}\n"
            "  Hint: 먼저 `/forge-init <Intent 경로>`로 워크트리를 만들거나 slug를 확인하세요.\n"
            "  목록: `python worktree_setup.py list`",
            EXIT_BLOCKED,
        )
    branch = forge["branch"]

    registered = _registered_worktree_path(root, branch)
    if registered is None or not registered.exists():
        _err(
            f"ERROR: forge 워크트리 없음: branch={branch}\n"
            "  Hint: 워크트리가 지워졌다면 `/forge-init <Intent 경로>`로 다시 만들거나 slug를 확인하세요.\n"
            "  목록: `python worktree_setup.py list`",
            EXIT_BLOCKED,
        )
    wt = registered

    doc_name = args.name or slug
    base = args.base or forge.get("base_commit") or None

    # docs 존재 검사. --docs 생략 시 매니페스트의 Intent 를 비교 문서로 쓴다.
    docs_source = "explicit"
    intent: Optional[Path] = None
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
        intent = _intent_from_manifest(forge)
        if intent is None:
            _err(
                "ERROR: 비교 문서 자동 구성 실패:\n"
                f"  - 매니페스트에 Intent 경로가 없거나 파일이 없음: {mf_path}\n"
                "  - `--docs <doc...>`를 명시하세요.",
                EXIT_BLOCKED,
            )
        docs_source = "auto-intent"
        docs_paths = [intent]

    docs_abs = [str(p.resolve()) for p in _unique_paths(docs_paths)]

    def _rel(p: str) -> str:
        try:
            return Path(p).relative_to(root).as_posix()
        except ValueError:
            return Path(p).as_posix()
    doc_disp = ", ".join(_rel(d) for d in docs_abs)
    intent_disp = _rel(str(intent)) if intent else "(explicit docs - none)"

    # .process/<docName>/ 는 rmtree 하지 않는다 — 다른 산출물 보존. 자기 파일만 덮어쓴다.
    proc = wt / ".process" / doc_name
    proc.mkdir(parents=True, exist_ok=True)

    tmpl_dir = Path(__file__).resolve().parent / "ddr_templates"
    subs = {
        "{docName}": doc_name,
        "{docPath}": doc_disp,
        "{slug}": slug,
        "{branch}": branch,
        "{docsSource}": docs_source,
        "{intentPath}": intent_disp,
        "{base}": base or "(미지정 — doc_driven_review 기본값)",
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
        "docs_source": docs_source,
        "intent": str(intent) if intent else None,
        "base": base,
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
    pi.add_argument("--slug", required=True, help="forge 워크트리 slug (forge-init 매니페스트 .process/forge/<slug>.json 의 키)")
    pi.add_argument("--docs", nargs="+", default=None, help="비교 문서 경로 1개 이상 (생략 시 forge-init 매니페스트의 Intent)")
    pi.add_argument("--name", default=None, help="docName 명시 (기본: slug)")
    pi.add_argument("--base", default=None, help="branch scope 기준 ref (생략 시 매니페스트 base_commit. manifest 기록 → 세션이 review에 전달)")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
