#!/usr/bin/env python3
"""worktree_setup — 워크트리 셋업 helper (/worktree-init · /worktree-delete).

오케스트레이션은 하지 않는다. 셋업·정리와 Task 상태 전이만 담당하고, 실제 개발은
사용자가 워크트리 안에서 시작한 Claude Code 세션이 한다.

워크트리는 이름 하나로 만든다 — Task 를 읽지 않는다. 한 워크트리에서 Task 여러 개를
개발할 수 있고, 어떤 Task 를 개발할지는 개발 세션에 주는 프롬프트(/task-split 이 만든다)가 정한다.

설계 문서(문서 폴더 docs·Docs 와 .task/)는 커밋하지 않는다(팀 정책). 정본은 메인 작업트리에
있고, init 이 워크트리에 사본을 복사한다. Task 상태 전이는 전부 메인 정본에 쓴다(커밋 없음).

Subcommands
-----------
- ``init``    : info/exclude 등록 → 워크트리(.worktree/<slug>, 브랜치 work/<slug>) 생성 → 서브모듈 링크 →
                가드레일 · 문서 사본 복사 → JSON 매니페스트 출력.
- ``branches``: base 후보 브랜치 나열 (로컬 + origin/*, JSON). 읽기 전용.
- ``list``    : /worktree-init 워크트리 나열 (JSON).
- ``finish``  : (워크트리 안에서) 마감 — 메인 정본 Task approved → in-review, Task 카탈로그 재생성,
                메인 매니페스트에 Task ID 기록.
- ``delete``  : 안전 게이트(미커밋 변경 · 머지 여부) → 머지됐으면 마감한 Task done + 진행 표시 정리 →
                서브모듈 링크 해제(메인 타깃 보존) → worktree remove → branch -D.

표준 라이브러리만 사용한다 (Python 3.10+).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat as _stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docs_helpers as _dh  # noqa: E402  (same scripts/ directory)

EXIT_OK = 0
EXIT_ERR = 1
EXIT_BLOCKED = 2  # 게이트 미통과 (머지 안 됨 · 미커밋 변경 · Task 상태)

# 가드레일 복사 대상: .claude 전체가 아니라 .claude/rules + settings.json 만.
# settings.json 은 base 커밋에 없을 수 있는데(로컬 미커밋), 없으면 워크트리 세션이
# 권한 allowlist·훅 없이 부팅해 첫 bash 호출부터 프롬프트가 뜬다.
# settings.local.json 은 기계 로컬이라 제외한다.
GUARDRAIL_FILES = ["CLAUDE.md", ".claude/settings.json"]
# 문서 폴더는 레포마다 docs·Docs 로 표기가 갈린다 — 한 폴더로 보고 디스크 표기로 복사·보고한다.
# 문서 폴더와 .task/ 는 커밋하지 않으므로 base 커밋에 없다 — 정본(메인 작업트리)을 복사해 넣는다.
GUARDRAIL_DIRS = [".claude/rules", "docs", _dh.TASK_DIR]

# init 이 남기는 매니페스트. 워크트리 사본은 개발 세션 인수인계용,
# 메인 repo 사본은 finish · delete · list 가 읽고 쓴다. 둘 다 .process/ 아래라 커밋되지 않는다.
MANIFEST_DIR = ".process/worktree"
HANDOFF_NAME = "handoff.json"

# 메인 repo 의 dirty 판정에서 빼는 폴더 — 이 helper 가 관리하거나 커밋하지 않는 것들이다.
UNTRACKED_PREFIXES = (".worktree/", ".process/", "docs/", f"{_dh.TASK_DIR}/")


# ============================================================================
# 공통 git/링크 유틸 (v3.0 이전 스크립트에서 포팅)
# ============================================================================
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


def _is_dir_link(p: Path) -> bool:
    """junction(Windows reparse) 또는 symlink면 True."""
    try:
        if p.is_symlink():
            return True
        if os.name == "nt":
            attrs = p.lstat().st_file_attributes  # type: ignore[attr-defined]
            return bool(attrs & _stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False
    return False


def _make_dir_link(src: Path, dst: Path) -> None:
    """dst → src 디렉토리 링크. Windows=junction(mklink /J, 관리자 불필요), Unix=symlink."""
    if os.name == "nt":
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            raise OSError(r.stderr.strip() or r.stdout.strip() or "mklink /J 실패")
    else:
        os.symlink(src, dst, target_is_directory=True)


def _abs_git_path(start: Path, which: str) -> Optional[Path]:
    """`git rev-parse <which>` 를 절대경로로. git < 2.31 은 --path-format 이 없다."""
    r = _git(start, "rev-parse", "--path-format=absolute", which)
    if r.returncode != 0 or not r.stdout.strip():
        r = _git(start, "rev-parse", which)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    p = Path(r.stdout.strip())
    return p if p.is_absolute() else (start / p).resolve()


def _repo_root(start: Path) -> Optional[Path]:
    """메인 repo 루트. linked worktree 안에서 호출해도 메인을 가리킨다.

    `--show-toplevel` 만 쓰면 워크트리 안에서 그 워크트리 자신을 돌려줘
    `.worktree/<slug>` 계산이 전부 어긋난다 — list 가 항상 빈 배열이 되고
    finish 가 메인 정본을 못 찾는다.

    다만 `--git-common-dir` 의 부모를 무조건 쓰면 **서브모듈**에서 깨진다
    (common-dir 이 `<super>/.git/modules/<name>` 이라 부모가 루트가 아니다).
    그래서 linked worktree 일 때만 올라간다 — 그때만 git-dir 과 common-dir 이 다르다.
    """
    git_dir = _abs_git_path(start, "--git-dir")
    common_dir = _abs_git_path(start, "--git-common-dir")
    if git_dir is not None and common_dir is not None and git_dir != common_dir:
        return common_dir.parent  # linked worktree → 메인 repo

    r = _git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return Path(r.stdout.strip())


def _slugify(name: str) -> str:
    """워크트리 폴더 이름 — 영문 · 숫자 · `. _ -` 만 남긴다. 남는 게 없으면 빈 문자열."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")


def _resolve_commit(root: Path, ref: str) -> Optional[str]:
    """ref 가 가리키는 커밋 sha (없으면 None). 로컬·원격·태그·sha 모두 허용."""
    r = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return r.stdout.strip() or None


def _is_remote_ref(root: Path, ref: str) -> bool:
    """원격 추적 ref 인가. 문자열 휴리스틱(슬래시 포함 여부) 금지 — feat/foo 같은 로컬을 오인한다."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}").returncode == 0


def _current_branch(root: Path) -> str:
    r = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else ""


# 고쳐 쓰는 문서(Task · Intent)는 docs_helpers 와 같은 방식으로 읽고 쓴다 — 줄바꿈 그대로, 엄격 UTF-8
# (UTF-8 이 아니면 UnicodeDecodeError — 되쓰면 유일한 사본이 깨진다), 임시 파일에 쓴 뒤 바꿔 끼운다.
_read_raw = _dh._read_raw
_write_all = _dh._write_all


def _set_table_row(text: str, key: str, value: str, old_value: Optional[str] = None) -> str:
    """`| key | … |` 첫 행의 값을 바꾼다(줄 끝 \\r 보존). old_value 를 주면 그 값일 때만 바꾼다."""
    cell = re.escape(old_value) if old_value is not None else r"[^\r\n]*?"
    return re.sub(
        rf"(?m)^\|[ \t]*{re.escape(key)}[ \t]*\|[ \t]*{cell}[ \t]*\|[ \t]*(\r?)$",
        # lambda: value 안의 백슬래시가 치환 escape 로 해석되는 것을 막는다.
        lambda m: f"| {key} | {value} |{m.group(1)}",
        text,
        count=1,
    )


def _submodule_entries(root: Path, worktree: Path) -> list[tuple[str, str]]:
    """워크트리 .gitmodules 에서 (submodule name, path) 목록."""
    gm = worktree / ".gitmodules"
    r = _git(root, "config", "-f", str(gm), "--get-regexp", r"submodule\..*\.path")
    out: list[tuple[str, str]] = []
    for line in r.stdout.splitlines():
        key, _, path = line.partition(" ")
        name = key[len("submodule."):-len(".path")] if key.startswith("submodule.") else ""
        if name and path.strip():
            out.append((name, path.strip()))
    return out


def _is_guardrail_copy(root: Path, wt: Path, path: str) -> bool:
    """init 이 메인에서 복사해 넣은 가드레일(CLAUDE.md · .claude/ 아래)을 그대로 둔 사본인가.

    내용이 메인과 같을 때만 사본으로 본다 — 개발 세션이 새로 만든 .claude/ 파일이나 고친 사본은
    지우면 사라지는 변경이다.
    """
    low = path.lower()
    if not (low == "claude.md" or low.startswith(".claude/")):
        return False
    src, dst = root / path, wt / path
    try:
        return src.is_file() and dst.is_file() and src.read_bytes() == dst.read_bytes()
    except OSError:
        return False


def _changed_paths(cwd: Path, *, copied_from: Optional[Path] = None) -> list[str]:
    """`git status` 에 잡히는 경로 — 커밋 안 된 변경. exclude 된 문서 · 작업 폴더는 git 이 이미 뺀다.

    UNTRACKED_PREFIXES 아래 경로도 뺀다 — exclude 등록 전이거나 문서가 이미 커밋돼 있어도
    워크트리에 들어가는 건 git 사본이 아니라 정본의 복사본이라 문서 변경은 판정과 무관하다.
    copied_from(메인 repo)을 주면 워크트리로 보고, init 이 복사해 넣은 가드레일 사본(_is_guardrail_copy)도 뺀다.
    """
    extra = ["--untracked-files=all"] if copied_from is not None else []   # 접힌 `?? .claude/` 안을 하나씩 본다
    r = _git(cwd, "status", "--porcelain=v1", "-z", *extra)
    tokens = r.stdout.split("\0")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1   # rename · copy 는 원래 경로가 다음 토큰에 온다
        low = path.lower()
        if any(low.startswith(p) or low == p.rstrip("/") for p in UNTRACKED_PREFIXES):
            continue
        if copied_from is not None and xy == "??" and _is_guardrail_copy(copied_from, cwd, path):
            continue
        out.append(path)
    return out


# ============================================================================
# 매니페스트
# ============================================================================
def _main_manifest_path(root: Path, slug: str) -> Path:
    return root / MANIFEST_DIR / f"{slug}.json"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_manifests(root: Path, wt: Path, slug: str, manifest: dict) -> list[str]:
    """매니페스트를 워크트리·메인 두 곳에 쓴다. 쓴 경로 목록을 돌려준다.

    한 번 정확히 알아낸 값(브랜치·base·워크트리 경로)을 버리지 않기 위한 것이다.
    이게 없으면 delete·list 가 나중에 slug 로부터 브랜치를 추측하게 된다.
    """
    written: list[str] = []
    for target in (wt / MANIFEST_DIR / HANDOFF_NAME, _main_manifest_path(root, slug)):
        try:
            _write_json(target, manifest)
            written.append(str(target))
        except OSError as e:
            print(f"NOTE: 매니페스트를 쓰지 못했다: {target} ({e})", file=sys.stderr)
    return written


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _read_main_manifest(root: Path, slug: str) -> Optional[dict]:
    return _read_json(_main_manifest_path(root, slug))


def _manifest_for_worktree(root: Path, wt: Path) -> tuple[Optional[Path], Optional[dict]]:
    """wt 를 만든 메인 매니페스트 — 경로가 같은 것을 찾고, 없으면 워크트리 사본의 slug 로 찾는다."""
    for mf in sorted((root / MANIFEST_DIR).glob("*.json")):
        data = _read_json(mf)
        if data and data.get("worktree"):
            try:
                if Path(data["worktree"]).resolve() == wt.resolve():
                    return mf, data
            except OSError:
                continue
    handoff = _read_json(wt / MANIFEST_DIR / HANDOFF_NAME)
    slug = str((handoff or {}).get("slug") or "")
    if slug:
        mf = _main_manifest_path(root, slug)
        data = _read_json(mf)
        if data is not None:
            return mf, data
    return None, None


# ============================================================================
# init
# ============================================================================
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


def _ensure_worktree(
    root: Path, slug: str, branch: str, *, force: bool, base: Optional[str] = None,
) -> tuple[Path, str, bool, bool]:
    """(worktree, branch, created, base_applied).

    base 는 브랜치를 **새로 만들 때만** 분기점으로 쓰인다. 브랜치가 이미 있으면
    물리적으로 적용할 수 없으므로 무시하고 base_applied=False 로 알린다.
    """
    wt = root / ".worktree" / slug

    registered = _registered_worktree_path(root, branch)
    if registered is not None:
        if registered.resolve() != wt.resolve():
            _err(f"ERROR: branch '{branch}'가 다른 워크트리에 attach됨: {registered}\n"
                 "  Hint: 다른 이름이나 --branch 로 새 브랜치를 쓰거나, 그 워크트리를 정리한 뒤 재실행 — "
                 ".worktree/ 아래면 `worktree_setup.py delete <slug>`, 그 밖이면 `git worktree remove <경로>`.")
        if not registered.exists():
            _err(f"ERROR: 워크트리 등록됐으나 디렉토리 없음(stale): {registered}\n"
                 "  Hint: `git worktree prune` 후 재실행.")
        return wt, branch, False, False

    if wt.exists():
        _err(f"ERROR: 디렉토리 존재하나 워크트리 미등록: {wt}\n"
             "  Hint: 수동 삭제하거나 `git worktree prune` 후 재시도.")

    if not force:
        dirty = _changed_paths(root)
        if dirty:
            _err("ERROR: 메인 repo 작업트리가 dirty — 워크트리에는 커밋된 코드만 들어간다. "
                 "commit/stash 후 재시도 (또는 --force).\n"
                 + "\n".join(f"  {l}" for l in dirty[:10]))

    wt.parent.mkdir(parents=True, exist_ok=True)
    exists = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    base_applied = False
    if exists:
        if base:
            print(f"NOTE: 브랜치 '{branch}' 가 이미 있어 base '{base}' 는 적용되지 않는다 (resume).",
                  file=sys.stderr)
        r = _git(root, "worktree", "add", str(wt), branch)
    else:
        # 원격 ref 에서 분기하면 git 이 upstream 을 잡는다. 이 helper 는 push 하지 않으므로 끊는다.
        extra = ["--no-track"] if base and _is_remote_ref(root, base) else []
        r = _git(root, "worktree", "add", *extra, "-b", branch, str(wt), *([base] if base else []))
        base_applied = True
    if r.returncode != 0:
        _err(f"ERROR: 워크트리 생성 실패 ({wt}).\n  {r.stderr.strip()}")
    return wt, branch, True, base_applied


def _link_submodules(root: Path, wt: Path, log: list[str]) -> None:
    if not (wt / ".gitmodules").exists():
        return
    for name, rel in _submodule_entries(root, wt):
        src = root / rel
        dst = wt / rel
        if not src.is_dir() or not any(src.iterdir()):
            log.append(f"submodule skip (메인 미populate): {rel}")
            continue
        try:
            if _is_dir_link(dst):
                log.append(f"submodule 링크 재사용: {rel}")
            else:
                if dst.exists():
                    os.rmdir(dst)
                dst.parent.mkdir(parents=True, exist_ok=True)
                _make_dir_link(src, dst)
                log.append(f"submodule 링크: {rel} → 메인")
            _run(["git", "config", f"submodule.{name}.ignore", "all"], cwd=wt)
        except OSError as e:
            log.append(f"submodule 링크 실패(무시): {rel} — {e}")


def _copy_guardrails(root: Path, wt: Path) -> tuple[list[str], list[str]]:
    """가드레일과 문서 사본을 메인 작업트리에서 워크트리로 복사한다 — 워크트리에 없는 파일만.

    문서 폴더 · .task/ 는 링크하지 않고 복사한다. 링크가 남은 채 `git worktree remove --force` 를
    하면 링크 대상(메인 정본)의 내용까지 지워진다. 있는 파일을 덮지 않으므로 재실행하면 새 파일만 더해진다.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for rel in GUARDRAIL_FILES:
        src = root / rel
        if src.is_file():
            dst = wt / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel)
        else:
            skipped.append(rel)
    for rel in GUARDRAIL_DIRS:
        src = _dh._match_case(root, rel)
        rel = src.relative_to(root).as_posix()
        if src.is_dir():
            n_copied = 0
            for f in src.rglob("*"):
                if not f.is_file():
                    continue
                dst = wt / f.relative_to(root)
                if dst.exists():
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                n_copied += 1
            if n_copied:
                copied.append(rel + "/")
        else:
            skipped.append(rel + "/")
    return copied, skipped


def _branch_rows(root: Path) -> list[dict]:
    """base 후보 — 로컬 브랜치 + origin/* 추적 브랜치, 최근 커밋 순."""
    fmt = ("%(refname)%09%(refname:short)%09%(objectname:short)"
           "%09%(committerdate:short)%09%(contents:subject)")
    rows: list[dict] = []
    local_sha: dict[str, str] = {}
    for scope, kind in (("refs/heads", "local"), ("refs/remotes/origin", "remote")):
        r = _git(root, "for-each-ref", "--sort=-committerdate", f"--format={fmt}", scope)
        for line in r.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 4)   # subject 안의 탭은 subject 에 남긴다
            if len(parts) < 4:
                continue
            full, ref, sha, date = parts[0], parts[1], parts[2], parts[3]
            subject = parts[4] if len(parts) > 4 else ""
            if kind == "local":
                local_sha[ref] = sha
            else:
                # origin/HEAD 는 short name 이 'origin' 이라 short 이름으론 못 거른다.
                if full == "refs/remotes/origin/HEAD":
                    continue
                # 로컬과 같은 커밋이면 중복 — 다르면(로컬이 뒤처짐) 남긴다.
                if local_sha.get(ref[len("origin/"):]) == sha:
                    continue
            rows.append({"ref": ref, "kind": kind, "sha": sha, "date": date, "subject": subject})
    return rows


def _target_branch(name: str, branch: Optional[str]) -> str:
    return (branch or "").strip() or f"work/{_slugify(name)}"


def cmd_branches(args: argparse.Namespace) -> int:
    """읽기 전용 — 세션이 base 선택지를 사용자에게 제시하기 위한 목록. 추천은 현재 HEAD 브랜치."""
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.", EXIT_BLOCKED)

    current = _current_branch(root)
    target_branch = _target_branch(args.name, args.branch) if (args.name or args.branch) else ""

    rows = _branch_rows(root)
    for row in rows:
        row["is_current"] = row["kind"] == "local" and row["ref"] == current
    rows.sort(key=lambda row: not row["is_current"])   # stable — 현재 브랜치만 맨 앞으로

    target_exists = bool(target_branch) and _git(
        root, "rev-parse", "--verify", "--quiet", f"refs/heads/{target_branch}"
    ).returncode == 0

    print(json.dumps({
        "current": current,
        "target_branch": target_branch,
        "target_branch_exists": target_exists,
        "candidates": rows,
    }, ensure_ascii=False))
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다. `git init` 후 재시도.", EXIT_BLOCKED)

    slug = _slugify(args.name)
    if not slug:
        _err(f"ERROR: 이름 '{args.name}' 에서 폴더 이름을 만들 수 없다 — 영문 · 숫자 · `. _ -` 로 쓴다 "
             "(예: login-api).")
    branch = _target_branch(args.name, args.branch)
    if _git(root, "check-ref-format", "--branch", branch).returncode != 0:
        _err(f"ERROR: 브랜치 이름 '{branch}' 를 쓸 수 없다 — --branch 로 다른 이름을 준다.")

    base = (args.base or "").strip() or None
    if base:
        base_commit = _resolve_commit(root, base)
        if base_commit is None:
            _err(f"ERROR: base '{base}' 를 찾을 수 없다 — "
                 "`worktree_setup.py branches` 로 목록을 확인하고 다시 고른다.")
    else:
        base_commit = _resolve_commit(root, "HEAD")
        if base_commit is None:
            _err("§F 커밋이 하나도 없다 — 프로젝트 골격(소스·테스트·솔루션)을 먼저 커밋한다. "
                 "워크트리는 마지막 커밋을 복사한다(문서 폴더 · .task/ 는 커밋하지 않는다).", EXIT_BLOCKED)

    # dirty 판정 전에 올린다 — 문서 폴더 · .task/ 가 untracked 로 잡히지 않게.
    exclude = _dh.ensure_local_exclude(root)

    wt, branch, created, base_applied = _ensure_worktree(
        root, slug, branch, force=args.force, base=base,
    )

    log: list[str] = []
    _link_submodules(root, wt, log)
    copied, skipped = _copy_guardrails(root, wt)

    # 브랜치가 이미 있었을 때(resume)만 앞 매니페스트를 이어받는다. 새 브랜치를 만들었으면 같은 이름의
    # 옛 매니페스트는 지난 워크트리의 찌꺼기다 — 그 tasks 를 이어받으면 머지 안 된 Task 가 done 이 된다.
    previous = _read_main_manifest(root, slug) or {}
    if base_applied or previous.get("branch") != branch:
        previous = {}
    manifest = {
        "root": str(root),
        "worktree": str(wt),
        "branch": branch,
        # 머지 확인(delete)의 기준 — 고른 ref, 안 골랐으면 그때의 현재 브랜치.
        "base": base or _current_branch(root),
        "base_commit": base_commit,         # 분기 시점 sha — 개발 커밋 유무 · 마감 diff 기준
        "base_applied": base_applied,       # False = 브랜치가 이미 있어 분기점을 못 바꿨다
        "slug": slug,
        "created": created,
        # finish 가 마감한 Task ID — delete 가 머지를 확인하면 done 으로 바꾼다. resume 에서도 잃지 않는다.
        "tasks": list(previous.get("tasks") or []),
        "copied": copied,
        "skipped": skipped,
        "submodule_log": log,
        "exclude": exclude["exclude"],
        "exclude_added": exclude["added"],
        "tracked_docs": exclude["tracked"][:10],
    }
    if previous.get("base"):
        manifest["base"] = previous["base"]                  # resume — 처음 분기한 기준을 유지한다
        manifest["base_commit"] = previous.get("base_commit") or base_commit
    manifest["manifests"] = _write_manifests(root, wt, slug, manifest)

    if not args.quiet:
        print(f"[worktree] worktree: {wt}")
        print(f"[worktree] branch:   {branch}")
        mark = "" if base_applied else " (무시됨 — 브랜치 기존재)"
        print(f"[worktree] base:     {manifest['base'] or '(detached)'} ({(manifest['base_commit'] or '')[:7]}){mark}")
        if copied:
            print(f"[worktree] 복사:     {', '.join(copied)}")
        if skipped:
            print(f"[worktree] skip:     {', '.join(skipped)}")
        if exclude["added"]:
            print(f"[worktree] exclude:  {exclude['exclude']} += {' '.join(exclude['added'])}")
        for name in manifest["tracked_docs"]:
            print(f"[worktree] WARN 커밋된 문서: {name} — exclude 로 숨지 않고, 워크트리에는 커밋된 사본이 들어간다")
        for m in manifest["manifests"]:
            print(f"[worktree] manifest: {m}")
        for l in log:
            print(f"[worktree] {l}")
    print(json.dumps(manifest, ensure_ascii=False))
    return EXIT_OK


# ============================================================================
# finish — 마감 (워크트리 안에서)
# ============================================================================
def _refresh_int_catalog(repo: Path, intent_rel: str) -> Optional[str]:
    """<App>-INT-CATALOG.md 를 INTENT/ 에서 다시 생성한다.

    카탈로그는 파생 인덱스라 Intent 를 고친 직후 갱신한다. 실패해도 막지 않는다 —
    docs_helpers.py check --app <App> 이 stale 로 잡는다.
    """
    parts = Path(intent_rel).parts
    # 문서 폴더는 docs·Docs 둘 다 받는다 — 카탈로그는 Intent 와 같은 표기의 폴더에 둔다.
    if len(parts) < 4 or parts[0].lower() != "docs" or parts[2] != "INTENT":
        return None
    app = parts[1]
    rel = f"{parts[0]}/{app}/{app}-INT-CATALOG.md"
    try:   # 게이트가 아니다 — 문서 문제로 죽지 않는다 (쓰기 실패 포함)
        rows, _ = _dh._collect_intent_rows(repo, app)
        (repo / rel).write_text(_dh._render_intent_catalog(app, rows), encoding="utf-8", newline="\n")
    except Exception as e:
        print(f"WARN: {rel} 갱신 실패 ({type(e).__name__}: {e}). "
              f"docs_helpers.py check --app {app} 로 확인할 것.", file=sys.stderr)
        return None
    return rel


def _refresh_task_catalog(repo: Path) -> Optional[str]:
    """.task/task-catalog.md 를 .task/ 에서 다시 생성한다.

    _refresh_int_catalog 와 같은 원칙 — 상태 전이 직후 갱신하고, 실패해도 막지 않는다
    (docs_helpers.py check 가 TSK_CATALOG stale 로 잡는다).
    """
    rel = f"{_dh.TASK_DIR}/{_dh.TASK_CATALOG_NAME}"
    try:   # 게이트가 아니다 — 문서 문제로 죽지 않는다 (쓰기 실패 포함)
        rows, _ = _dh._collect_task_rows(repo)
        (repo / rel).write_text(_dh._render_task_catalog(rows), encoding="utf-8", newline="\n")
    except Exception as e:
        print(f"WARN: {rel} 갱신 실패 ({type(e).__name__}: {e}). docs_helpers.py check 로 확인할 것.",
              file=sys.stderr)
        return None
    return rel


def _read_task(path: Path):
    # 파싱만 한다(읽기 전용) — 고쳐 쓸 때는 _read_raw 로 원본 줄바꿈 그대로, 엄격 UTF-8 로 다시 읽는다.
    return _dh._parse_task(path.read_text(encoding="utf-8", errors="replace"))


def _task_status(path: Path) -> str:
    return _read_task(path).meta.get("상태", "").strip()


def cmd_finish(args: argparse.Namespace) -> int:
    """마감 — 메인 정본 Task approved → in-review + Task 카탈로그 재생성 + 메인 매니페스트에 Task ID 기록.

    개발을 마친 세션이 워크트리 안에서 Task 마다(또는 여러 개를 한 번에) 부른다. 문서는
    커밋하지 않으므로 커밋을 만들지 않는다. 진행 표시는 머지를 확인한 delete 가 지운다.
    """
    cwd = Path.cwd()
    git_dir = _abs_git_path(cwd, "--git-dir")
    common_dir = _abs_git_path(cwd, "--git-common-dir")
    if git_dir is None or common_dir is None:
        _err("ERROR: git repository가 아닙니다.", EXIT_BLOCKED)
    if git_dir == common_dir:
        _err("§F finish 는 /worktree-init 이 만든 워크트리 안에서 실행한다 — 여기는 메인 repo(또는 서브모듈)다.",
             EXIT_BLOCKED)
    root = common_dir.parent
    wt = Path(_git(cwd, "rev-parse", "--show-toplevel").stdout.strip())

    mpath, manifest = _manifest_for_worktree(root, wt)
    if mpath is None or manifest is None:
        _err(f"§F 이 워크트리의 매니페스트가 없다 ({root / MANIFEST_DIR}) — /worktree-init 이 만든 워크트리인지 확인한다.",
             EXIT_BLOCKED)

    task_ids = list(dict.fromkeys(args.task_ids))   # 순서를 지키며 중복 제거
    bad = [t for t in task_ids if not _dh.TASK_ID_PATTERN.fullmatch(t)]
    if bad:
        _err(f"§F Task ID 형식이 아니다: {bad} — TSK-<NNN> 으로 준다.", EXIT_BLOCKED)

    listed = list(manifest.get("tasks") or [])
    todo: list[str] = []
    already: list[str] = []
    problems: list[str] = []
    for task_id in task_ids:
        path = root / _dh.TASK_DIR / f"{task_id}.md"
        if not path.is_file():
            problems.append(f"{task_id}: 메인 정본에 없다 ({_dh.TASK_DIR}/{task_id}.md)")
            continue
        status = _task_status(path)
        if status == "approved":
            todo.append(task_id)
        elif status == "in-review" and task_id in listed:
            already.append(task_id)
        elif status == "in-review":
            # 이 워크트리가 마감한 Task 가 아니다 — 기록하면 이 워크트리의 머지로 done 이 된다.
            problems.append(f"{task_id}: 이미 in-review — 다른 워크트리에서 마감한 Task 다 (이 워크트리 매니페스트에 없다)")
        else:
            problems.append(f"{task_id}: 상태가 '{status or '(없음)'}' — approved 일 때만 마감한다")
    if problems:
        _err("§F 마감할 수 없는 Task:\n" + "\n".join(f"  - {p}" for p in problems), EXIT_BLOCKED)

    if todo:
        dirty = _changed_paths(wt, copied_from=root)
        if dirty:
            _err("§F 커밋 안 된 변경이 있다 — 개발 커밋을 마친 뒤 finish 한다:\n"
                 + "\n".join(f"  {n}" for n in dirty[:10]), EXIT_BLOCKED)
        base_commit = str(manifest.get("base_commit") or "")
        if base_commit and _resolve_commit(wt, base_commit):
            count = _git(wt, "rev-list", "--count", f"{base_commit}..HEAD").stdout.strip()
            if count == "0":
                _err(f"§F base({base_commit[:7]}) 이후 개발 커밋이 없다 — 개발을 커밋한 뒤 finish 한다.",
                     EXIT_BLOCKED)

    # 전부 계산한 뒤 쓴다 — 하나라도 못 바꾸면 아무것도 쓰지 않는다. 반쯤 쓰고 멈추면 in-review 인데
    # 매니페스트에 없는 Task 가 남아, 다시 실행해도 "다른 워크트리의 Task" 로 막힌다.
    rewrites: list[tuple[Path, str]] = []
    for task_id in todo:
        path = root / _dh.TASK_DIR / f"{task_id}.md"
        try:
            text = _read_raw(path)
        except UnicodeDecodeError:
            _err(f"§F {_dh.TASK_DIR}/{task_id}.md 를 UTF-8 로 읽을 수 없다 — 되쓰면 내용이 깨진다. UTF-8 로 저장한 뒤 "
                 "다시 실행한다. 아무 Task 도 바꾸지 않았다.", EXIT_BLOCKED)
        new_text = _set_table_row(text, "상태", "in-review", old_value="approved")
        if new_text == text:
            _err(f"ERROR: Task 상태 행을 바꾸지 못했다 ({_dh.TASK_DIR}/{task_id}.md) — 메타 표의 `| 상태 | approved |` 를 "
                 "확인한다. 아무 Task 도 바꾸지 않았다.")
        rewrites.append((path, new_text))
    # 매니페스트를 먼저 쓴다 — Task 를 쓰다 멈춰도 다시 실행하면 이 워크트리의 Task 로 알아본다.
    manifest["tasks"] = listed + [t for t in task_ids if t not in listed]
    _write_json(mpath, manifest)
    try:
        _write_all(rewrites)
    except OSError as e:
        _err(f"§F Task 상태를 쓰다가 멈췄다 ({type(e).__name__}: {e}) — 일부 Task 만 in-review 일 수 있다. "
             "파일을 잡고 있는 프로그램을 닫고 같은 명령을 다시 실행하면 이어서 끝낸다.", EXIT_BLOCKED)
    catalog = _refresh_task_catalog(root) if todo else None

    result = {
        "tasks": [{"id": t, "status": "in-review", "already": t in already} for t in task_ids],
        "manifest": str(mpath),
        "catalog": catalog,
    }
    if not args.quiet:
        for t in todo:
            print(f"[worktree] task:     {t} approved → in-review")
        for t in already:
            print(f"[worktree] task:     {t} 이미 in-review")
        print(f"[worktree] manifest: {mpath}")
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


# ============================================================================
# delete — 안전 게이트 · done 전이 · 정리 (메인 repo 에서)
# ============================================================================
def _unlink_submodule_links(worktree: Path) -> None:
    """워크트리 서브모듈 junction/symlink 만 제거(메인 타깃 보존)."""
    gm = worktree / ".gitmodules"
    if not gm.exists():
        return
    r = _run(["git", "config", "-f", str(gm), "--get-regexp", r"submodule\..*\.path"], cwd=worktree)
    for line in r.stdout.splitlines():
        _, _, path = line.partition(" ")
        path = path.strip()
        if not path:
            continue
        p = worktree / path
        try:
            is_link = p.is_symlink() or (
                os.name == "nt" and bool(p.lstat().st_file_attributes & 0x400)  # REPARSE_POINT
            )
        except (OSError, AttributeError):
            is_link = False
        if is_link:
            try:
                os.rmdir(p) if os.name == "nt" else p.unlink()
            except OSError:
                pass


def _worktree_branch(root: Path, wt: Path) -> Optional[str]:
    """git worktree list --porcelain 에서 wt 경로에 attach된 브랜치명(없으면 None)."""
    r = _git(root, "worktree", "list", "--porcelain")
    current: Optional[Path] = None
    for line in r.stdout.splitlines():
        if not line.strip():
            current = None
        elif line.startswith("worktree "):
            current = Path(line[len("worktree "):])
        elif line.startswith("branch ") and current is not None:
            if current.resolve() == wt.resolve():
                ref = line[len("branch "):].strip()
                return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
            current = None
    return None


def _merged_into(root: Path, branch: str, base: str) -> Optional[str]:
    """branch 끝 커밋이 들어 있는 base 쪽 ref (없으면 None).

    base 가 원격 추적 ref(origin/develop)면 같은 이름의 로컬 브랜치(develop)도 본다 —
    로컬에서 머지하고 아직 푸시하지 않은 경우다.
    """
    candidates = [base] if base else []
    if base and _is_remote_ref(root, base) and "/" in base:
        candidates.append(base.split("/", 1)[1])
    for ref in candidates:
        if _resolve_commit(root, ref) is None:
            continue
        if _git(root, "merge-base", "--is-ancestor", f"refs/heads/{branch}", ref).returncode == 0:
            return ref
    return None


def _close_tasks(root: Path, task_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """마감한 Task 를 done 으로 바꾸고 대상 Intent 의 진행 표시 · 삭제 예정 줄을 지운다 (메인 정본).

    (보고 줄, 건너뛴 Task, 막힌 Task) 를 돌려준다. 상태 행 · 진행 표시 정리 중 하나라도 할 수 없으면(상태 행이
    깨짐 · UTF-8 이 아님 · 표시 줄에 HTML 주석이 섞임) 아무것도 쓰지 않고 막힌 사유만 돌려준다 — 호출측은
    워크트리 · 매니페스트를 지우기 전에 멈춰야 한다(지우면 Task ID 기록이 사라져 다시 할 수 없다). Task 와
    Intent 를 모두 계산한 뒤 한 번에 쓴다. 이미 done 인 Task 도 표시 정리를 다시 한다 — 앞선 delete 가 중간에
    멈췄을 때 다시 실행하면 이어서 끝낸다. 카탈로그는 이번에 바꾼 것이 없어도 다시 쓴다 — 앞선 실행이 문서를
    쓴 뒤 멈췄으면 카탈로그만 옛 상태로 남아 있다.
    """
    lines: list[str] = []
    skipped: list[str] = []
    blocked: list[str] = []
    plan: list[tuple[str, Path, object, Optional[str]]] = []   # (Task ID, 경로, 파싱 결과, done 으로 바꾼 본문 | None)
    for task_id in task_ids:
        path = root / _dh.TASK_DIR / f"{task_id}.md"
        if not path.is_file():
            skipped.append(f"{task_id} (메인 정본에 없음)")
            continue
        task = _read_task(path)
        status = task.meta.get("상태", "").strip()
        if status not in ("in-review", "done"):
            skipped.append(f"{task_id} ({status or '상태 없음'} — 마감하지 않았다)")
            continue
        new_text = None
        if status == "in-review":
            try:
                text = _read_raw(path)
            except UnicodeDecodeError:
                blocked.append(f"{task_id} ({_dh.TASK_DIR}/{task_id}.md 를 UTF-8 로 읽을 수 없다 — UTF-8 로 저장한다)")
                continue
            new_text = _set_table_row(text, "상태", "done", old_value="in-review")
            if new_text == text:
                blocked.append(f"{task_id} (상태 행을 done 으로 바꾸지 못했다 — 메타 표의 `| 상태 | in-review |` 를 확인한다)")
                continue
        plan.append((task_id, path, task, new_text))
    if blocked:
        return [], skipped, blocked

    # 여러 Task 가 같은 Intent 를 가리킬 수 있다 — 같은 본문에 이어서 정리한다.
    original: dict[Path, str] = {}
    current: dict[Path, str] = {}
    for task_id, path, task, _ in plan:
        notes: list[str] = []
        for intent_id in task.targets:
            p = _dh._intent_path(root, intent_id)
            if p is None or not p.is_file():
                notes.append(f"{intent_id}: 파일 없음")
                continue
            if p not in current:
                try:
                    original[p] = current[p] = _read_raw(p)
                except UnicodeDecodeError:
                    blocked.append(f"{task_id} → {intent_id} (UTF-8 로 읽을 수 없다 — UTF-8 로 저장한다)")
                    continue
            new_text, cleared, deleted, problems = _dh.clear_task_marks(current[p], task_id)
            if problems:
                blocked += [f"{task_id} → {intent_id} {pr}" for pr in problems]
                continue
            current[p] = new_text
            notes.append(f"{intent_id}: 표시 {len(cleared)} · 삭제 줄 {len(deleted)}")
        lines.append(f"{task_id} done ({'; '.join(notes) or '대상 Intent 없음'})")
    if blocked:
        return [], skipped, blocked

    task_writes = [(path, new_text) for _, path, _, new_text in plan if new_text is not None]
    intent_writes = [(p, text) for p, text in current.items() if text != original[p]]
    _write_all(task_writes + intent_writes)
    if plan:
        _refresh_task_catalog(root)
    # Intent 줄이 지워지면 규모(FR 수)가 바뀐다 — 대상 Intent 의 App 카탈로그도 App 마다 한 번 다시 쓴다
    for p in {p.parent: p for p in current}.values():
        _refresh_int_catalog(root, p.relative_to(root).as_posix())
    return lines, skipped, []


def _close_or_stop(root: Path, task_ids: list[str]) -> tuple[list[str], list[str]]:
    """_close_tasks 를 부르고, 막힌 Task 가 있거나 문서를 쓰다 멈추면 워크트리 · 브랜치를 지우지 않은 채 exit 2."""
    try:
        closed, skipped, blocked = _close_tasks(root, task_ids)
    except OSError as e:
        _err(f"§F 문서를 쓰다가 멈춰 삭제를 멈춘다 ({type(e).__name__}: {e}) — 워크트리 · 브랜치는 그대로다. "
             "Task · Intent 는 일부만 바뀌었을 수 있다 — 파일을 잡고 있는 프로그램을 닫고 같은 명령을 다시 실행하면 "
             "이어서 끝낸다.", EXIT_BLOCKED)
    if blocked:
        _err("§F Task 를 done 으로 바꾸지 못해 삭제를 멈춘다 — 문서 · 워크트리 · 브랜치 모두 그대로다:\n"
             + "\n".join(f"  - {b}" for b in blocked)
             + "\n  Hint: 위 사유를 고친 뒤 같은 명령을 다시 실행한다.", EXIT_BLOCKED)
    return closed, skipped


def cmd_list(args: argparse.Namespace) -> int:
    """/worktree-init 워크트리 나열 — 매니페스트 우선, 없으면 .worktree/ 스캔 폴백."""
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    out: dict[str, dict] = {}

    # ① 매니페스트 — init 이 기록한 사실. 브랜치 이름 규칙에 의존하지 않는다.
    for mf in sorted((root / MANIFEST_DIR).glob("*.json")):
        data = _read_json(mf)
        if data is None:
            continue
        slug, branch, wtp = data.get("slug"), data.get("branch"), data.get("worktree")
        if not (slug and branch and wtp) or not Path(wtp).is_dir():
            continue
        out[slug] = {"slug": slug, "branch": branch, "worktree": wtp, "base": data.get("base", ""),
                     "tasks": list(data.get("tasks") or []), "source": "manifest"}

    # ② 스캔 폴백 — 매니페스트를 잃은 워크트리. .worktree/ 바로 아래는 이 helper 가 만든 것이다.
    wt_base = (root / ".worktree").resolve()
    r = _git(root, "worktree", "list", "--porcelain")
    cur: Optional[Path] = None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            cur = Path(line[len("worktree "):])
        elif line.startswith("branch ") and cur is not None:
            ref = line[len("branch "):].strip()  # refs/heads/<branch>
            br = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
            try:
                under = cur.resolve().parent == wt_base
            except OSError:
                under = False
            if under and cur.name not in out:
                out[cur.name] = {"slug": cur.name, "branch": br, "worktree": str(cur), "base": "",
                                 "tasks": [], "source": "scan"}
            cur = None

    print(json.dumps([out[k] for k in sorted(out)], ensure_ascii=False))
    return EXIT_OK


def cmd_delete(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    slug = _slugify(args.slug)
    manifest = _read_main_manifest(root, slug) if slug else None

    # 브랜치 이름은 --branch 로 바뀔 수 있으므로 slug 에서 유도하지 않는다.
    # ① 매니페스트(init 이 기록한 사실) → ② 워크트리 역인덱싱 → ③ 명시 실패.
    wt = Path(manifest["worktree"]) if manifest and manifest.get("worktree") \
        else root / ".worktree" / slug
    branch = (manifest or {}).get("branch") or (_worktree_branch(root, wt) if slug else None)
    if not branch:
        _err(f"삭제 대상 브랜치를 특정할 수 없다: slug={slug or args.slug}, worktree={wt}\n"
             f"  Hint: `python worktree_setup.py list` 로 slug 를 확인하거나, "
             f"브랜치명을 알면 `git worktree remove` + `git branch -D` 로 직접 정리한다.")
    registered = _registered_worktree_path(root, branch)

    if registered is not None and not registered.exists():
        _git(root, "worktree", "prune")
        registered = _registered_worktree_path(root, branch)

    branch_exists = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    if not branch_exists and registered is None and not wt.exists():
        # 워크트리 · 브랜치를 손으로 지웠으면 매니페스트만 남는다. 남겨 두면 같은 이름의 다음 init 이
        # 헷갈리니 지우되, 마감한 Task 가 기록돼 있으면 그 ID 의 유일한 기록이다 — 머지 여부를 물은 뒤 지운다.
        mpath = _main_manifest_path(root, slug)
        if not (slug and mpath.is_file()):
            _err(f"삭제 대상 없음: branch={branch}, worktree={wt}")
        stale_tasks = list((manifest or {}).get("tasks") or [])
        if stale_tasks and not (args.merged or args.force):
            _err("§F 삭제를 멈춘다:\n"
                 f"  - 워크트리 · 브랜치가 이미 없어 머지를 확인할 수 없다 — 매니페스트에 마감한 Task 가 있다: {', '.join(stale_tasks)}\n"
                 "  Hint: 머지했으면 --merged (Task 를 done 으로 바꾸고 진행 표시를 지운다), "
                 "버렸으면 --force (매니페스트만 지운다 — Task 문서는 그대로 둔다).", EXIT_BLOCKED)
        closed, not_closed = _close_or_stop(root, stale_tasks) if args.merged and stale_tasks else ([], [])
        mpath.unlink()
        print("worktree_setup: delete 완료")
        if args.merged:
            print("- merged:           --merged (사용자 확인)")
        for line in closed:
            print(f"- task:             {line}")
        for line in not_closed:
            print(f"- task skip:        {line}")
        if stale_tasks and not args.merged:
            print(f"- task 그대로:      {', '.join(stale_tasks)} (머지를 확인하지 못했다 — 다시 개발하거나 dropped 로 바꾼다)")
        print(f"- removed manifest: {mpath} (워크트리 · 브랜치는 이미 없다)")
        return EXIT_OK

    cwd_real = Path.cwd().resolve()
    target = registered if registered is not None else (wt if wt.exists() else None)
    if target is not None:
        wt_real = target.resolve()
        if cwd_real == wt_real or wt_real in cwd_real.parents:
            _err("현재 cwd가 제거 대상 워크트리 내부입니다. 메인 repo로 이동 후 재실행:\n"
                 f"  cd {root}")

    tasks = list((manifest or {}).get("tasks") or [])
    # 매니페스트를 잃었으면 메인의 현재 브랜치를 base 로 본다 — 머지는 보통 거기로 한다.
    base = str((manifest or {}).get("base") or "") or _current_branch(root)

    # 머지 확인 — 조상 검사로 찾거나, 사용자가 --merged 로 확인해 준다(squash · rebase 머지).
    merged_ref = _merged_into(root, branch, base) if branch_exists else None
    merged = bool(args.merged or merged_ref)

    # 안전 게이트 — 지우면 되돌릴 수 없는 것(커밋 안 된 변경 · 머지 안 된 커밋)을 먼저 본다.
    if not args.force:
        problems: list[str] = []
        if target is not None:
            dirty = _changed_paths(target, copied_from=root)
            if dirty:
                problems.append("워크트리에 커밋 안 된 변경이 있다 — 지우면 사라진다:\n"
                                + "\n".join(f"      {n}" for n in dirty[:10]))
        if branch_exists and not merged:
            problems.append(f"브랜치 '{branch}' 가 base '{base or '(기록 없음)'}' 에 머지되지 않았다")
        if problems:
            _err("§F 삭제를 멈춘다:\n" + "\n".join(f"  - {p}" for p in problems)
                 + "\n  Hint: 머지했는데(squash · rebase 머지 포함) 조상 검사에 안 잡히면 --merged, "
                   "커밋 안 된 변경 · 머지 안 된 커밋을 버리려면 --force (머지를 확인하지 못하면 Task 문서는 그대로 둔다).",
                 EXIT_BLOCKED)

    # done 전이 — 머지가 확인됐을 때만. 머지되지 않은 채 --force 로 버리면 문서를 건드리지 않는다.
    closed: list[str] = []
    not_closed: list[str] = []
    if merged and tasks:
        closed, not_closed = _close_or_stop(root, tasks)

    removed_worktree = False
    if target is not None:
        # 서브모듈 링크만 해제 — worktree remove 가 junction 따라 메인 삭제하는 사고 방지.
        # 메인 repo 서브모듈 원본은 절대 건드리지 않는다 (deinit 등 미수행).
        _unlink_submodule_links(target)
        # 링크를 끊으면 서브모듈 경로가 지워진 것으로 잡힌다 — 게이트를 통과한 뒤라 --force 로 지운다.
        st = _run(["git", "status", "--porcelain"], cwd=target)
        wt_dirty = bool([l for l in st.stdout.splitlines() if l.strip()])
        cmd = ["worktree", "remove"]
        if args.force or wt_dirty:
            cmd.append("--force")
        cmd.append(str(target))
        r = _git(root, *cmd)
        if r.returncode != 0:
            _err(f"git worktree remove 실패: {r.stderr.strip()}\n  (--force 로 dirty 워크트리 강제 제거 가능)")
        removed_worktree = True
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)

    removed_branch = False
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        r = _git(root, "branch", "-D", branch)
        if r.returncode != 0:
            _err(f"git branch -D 실패: {r.stderr.strip()}")
        removed_branch = True

    # 메인 매니페스트는 "살아 있는 워크트리" 대장이므로 정리와 함께 지운다.
    removed_manifest = False
    mpath = _main_manifest_path(root, slug)
    if slug and mpath.is_file():
        try:
            mpath.unlink()
            removed_manifest = True
        except OSError as e:
            print(f"NOTE: 매니페스트를 지우지 못했다: {mpath} ({e})", file=sys.stderr)

    print("worktree_setup: delete 완료")
    if merged_ref:
        print(f"- merged into:      {merged_ref}")
    elif args.merged:
        print("- merged:           --merged (사용자 확인)")
    for line in closed:
        print(f"- task:             {line}")
    for line in not_closed:
        print(f"- task skip:        {line}")
    if tasks and not merged:
        print(f"- task 그대로:      {', '.join(tasks)} (머지를 확인하지 못했다 — 다시 개발하거나 dropped 로 바꾼다)")
    if removed_worktree:
        print(f"- removed worktree: {wt}")
    if removed_branch:
        print(f"- deleted branch:   {branch}")
    if removed_manifest:
        print(f"- removed manifest: {mpath}")
    return EXIT_OK


# ============================================================================
# CLI
# ============================================================================
def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="worktree_setup", description="워크트리 셋업 helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="exclude 등록 + 워크트리 + 링크 + 가드레일 · 문서 사본 복사")
    pi.add_argument("name", help="워크트리 이름 (.worktree/<이름>, 브랜치 기본 work/<이름>)")
    pi.add_argument("--branch", default=None, help="브랜치 이름 (기본: work/<이름>)")
    pi.add_argument("--base", default=None,
                    help="워크트리 분기점 ref (기본: 현재 HEAD). 예: main, develop, origin/develop")
    pi.add_argument("--force", action="store_true", help="메인 repo dirty 검사 우회")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    pb = sub.add_parser("branches", help="base 후보 브랜치 나열 (로컬 + origin/*, JSON)")
    pb.add_argument("--name", default=None, help="워크트리 이름 (대상 브랜치 work/<이름> 존재 여부 계산용)")
    pb.add_argument("--branch", default=None, help="브랜치 이름 (--name 대신 직접)")
    pb.set_defaults(func=cmd_branches)

    pl = sub.add_parser("list", help="/worktree-init 워크트리 나열 (JSON)")
    pl.set_defaults(func=cmd_list)

    pf = sub.add_parser("finish", help="(워크트리 안에서) 마감 — 메인 정본 Task approved → in-review + 카탈로그 + 매니페스트 기록")
    pf.add_argument("task_ids", nargs="+", metavar="TSK-NNN", help="마감할 Task ID (여러 개 가능)")
    pf.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pf.set_defaults(func=cmd_finish)

    pd = sub.add_parser("delete", help="머지 확인 → 마감한 Task done + 진행 표시 정리 → 워크트리 + 브랜치 정리")
    pd.add_argument("slug", help="워크트리 이름 (.worktree/<slug>)")
    pd.add_argument("--merged", action="store_true",
                    help="머지됐다고 사용자가 확인 (squash · rebase 머지처럼 조상 검사로 안 잡힐 때)")
    pd.add_argument("--force", action="store_true",
                    help="커밋 안 된 변경 · 머지 안 된 커밋을 버리고 지운다 (Task 문서는 그대로)")
    pd.set_defaults(func=cmd_delete)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
