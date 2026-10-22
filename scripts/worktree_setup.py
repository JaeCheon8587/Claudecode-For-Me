#!/usr/bin/env python3
"""worktree_setup — forge 워크트리 셋업 helper (/forge-init · /forge-cancel).

오케스트레이션은 하지 않는다. 셋업·검증·정리·마감 전이만 담당하고, 실제 개발은
사용자가 워크트리 안에서 시작한 Claude Code 세션이 한다.

입력은 승인된 Task(``.task/TSK-<NNN>.md``)다. Intent 는 기능 문서라 개발 입력이 아니다 —
Task 가 바꾸는 Intent 항목(Scope)과 완료 조건(Acceptance)을 정한다.

Subcommands
-----------
- ``init``   : 검증 게이트(Task + 대상 Intent) → 워크트리(.worktree/<slug>) 생성 → 서브모듈 링크 →
               가드레일 복사 → Task 상태 전이(approved → in-dev) → JSON 매니페스트 출력.
- ``branches``: base 후보 브랜치 나열 (로컬 + origin/*, JSON). 읽기 전용.
- ``list``   : forge 워크트리 나열 (JSON).
- ``cancel`` : 서브모듈 링크 해제(메인 타깃 보존) → worktree remove → branch -D.
- ``finish`` : (워크트리 안에서) 마감 전이 — 대상 Intent 의 진행 표시 정리 → Task 상태
               in-dev → in-review → 카탈로그 재생성 → 커밋.

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
EXIT_BLOCKED = 2  # 검증 게이트 미통과 (미결 항목 / 미완성 문서)

# 가드레일 복사 대상: .claude 전체가 아니라 .claude/rules + settings.json 만.
# settings.json 은 base 커밋에 없을 수 있는데(로컬 미커밋), 없으면 워크트리 세션이
# 권한 allowlist·훅 없이 부팅해 첫 bash 호출부터 프롬프트가 뜬다.
# settings.local.json 은 기계 로컬이라 제외한다.
GUARDRAIL_FILES = ["CLAUDE.md", ".claude/settings.json"]
# 문서 폴더는 레포마다 docs·Docs 로 표기가 갈린다 — 한 폴더로 보고 디스크 표기로 복사·보고한다.
GUARDRAIL_DIRS = [".claude/rules", "docs"]

# init 이 남기는 매니페스트. 워크트리 사본은 개발 세션 인수인계용,
# 메인 repo 사본은 cancel·list 조회용이다. 둘 다 .process/ 아래라 gitignore.
MANIFEST_DIR = ".process/forge"
HANDOFF_NAME = "handoff.json"


# ============================================================================
# 공통 git/링크 유틸 (v3.0 이전 forge 스크립트에서 포팅)
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
    cancel 이 브랜치를 추측하게 된다.

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


def _slugify(stem: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return s or "task"


def _task_branch(root: Path, task_id: str, handoff_value: str) -> str:
    v = handoff_value.strip()
    if v and _git(root, "check-ref-format", "--branch", v).returncode == 0:
        return v
    return f"task/{task_id}"


def _resolve_commit(root: Path, ref: str) -> Optional[str]:
    """ref 가 가리키는 커밋 sha (없으면 None). 로컬·원격·태그·sha 모두 허용."""
    r = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return r.stdout.strip() or None


def _is_remote_ref(root: Path, ref: str) -> bool:
    """원격 추적 ref 인가. 문자열 휴리스틱(슬래시 포함 여부) 금지 — feat/foo 같은 로컬을 오인한다."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}").returncode == 0


def _norm(text: str) -> str:
    """CRLF·양끝 공백 차이를 흡수한 비교용 정규화."""
    return text.replace("\r\n", "\n").strip()


def _read_raw(path: Path) -> str:
    """줄바꿈을 바꾸지 않고 읽는다 (CRLF 면 \\r\\n 그대로)."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def _write_raw(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def _rewrite(path: Path, fn) -> bool:
    """파일을 줄바꿈 그대로 읽어 fn(text) 로 바꿔 쓴다. 바뀌었으면 True.

    read_text/write_text 는 Windows 에서 LF 파일을 CRLF 로 바꿔 써서 문서 전체가 diff 가 된다 —
    newline="" 로 읽고 써서 줄바꿈을 건드리지 않는다. fn 은 줄 끝의 \\r 을 보존해야 한다.
    """
    text = _read_raw(path)
    new_text = fn(text)
    if new_text == text:
        return False
    _write_raw(path, new_text)
    return True


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


# ============================================================================
# 검증 게이트
# ============================================================================
TASK_START_STATUSES: tuple[str, ...] = ("approved", "in-dev")


def _doc_path(root: Path, raw: str) -> Path:
    """--doc 인자 → 디스크 표기의 절대경로. docs/Docs 처럼 대소문자만 다른 표기는 같은 파일로 본다."""
    doc = Path(raw)
    if not doc.is_absolute():
        doc = Path.cwd() / doc
    doc = doc.resolve()
    try:
        return _dh._match_case(root.resolve(), doc.relative_to(root.resolve()))
    except ValueError:
        return doc   # repo 밖 — init 은 _gate_start 가 막는다


def _tree_rel(root: Path, ref: str, rel: str) -> Optional[str]:
    """ref 트리에 실제로 있는 표기로 rel 을 돌려준다 — 대소문자만 다르면 같은 파일로 본다.

    git 은 경로를 대소문자 구분으로 비교한다(`show <ref>:<path>` · pathspec · add). 레포마다
    docs/Docs 표기가 다르고, Windows·macOS 에서 탐색기로 폴더 이름만 바꾸면 디스크 표기와
    커밋된 표기가 어긋난다(core.ignorecase 라 git status 는 깨끗하다). 디스크 표기를 그대로
    쓰면 커밋된 Intent 를 없다고 막고, tracked 파일 add 가 조용히 아무것도 하지 않는다.
    `ls-tree` 는 :(icase) pathspec 을 받지 않아 전체 목록에서 고른다.
    """
    r = _git(root, "ls-tree", "-r", "-z", "--name-only", ref)
    if r.returncode != 0:
        return None
    names = r.stdout.split("\0")
    if rel in names:
        return rel
    low = rel.lower()
    return next((n for n in names if n and n.lower() == low), None)


def _detect_input_kind(doc: Path, raw: str) -> str:
    # Task 는 레포 루트 `.task/` 에만 있다(소문자). 0.x 문서 폴더의 대문자 작업 폴더와 겹치지 않는다.
    if doc.parent.name == _dh.TASK_DIR and _dh.TASK_FILENAME_PATTERN.match(doc.name):
        return "TASK"
    if any(p.upper() == "INTENT" for p in doc.parts):
        return "INTENT"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*-INT-\d{3}", doc.stem):
        return "INTENT"
    return "LEGACY"


def _gate_task(root: Path, doc: Path) -> list[str]:
    """Task 승인·형식 게이트 — check-task 가 대상 Intent 대조(Scope 사본 · 진행 표시 · 충돌)까지 한다.
    문제 목록(빈 목록 = 통과)."""
    problems: list[str] = []

    raw = doc.read_text(encoding="utf-8", errors="replace")
    status = _dh._parse_task(raw).meta.get("상태", "").strip()
    if status not in TASK_START_STATUSES:
        problems.append(f"Task 상태가 '{status or '(없음)'}' — approved 여야 개발을 시작한다.")

    for r in _dh._check_task_file(root, doc):
        if r.level == "FAIL":
            problems.append(f"{r.code}: {r.message}")

    return problems


def _gate_start(root: Path, doc: Path, start_ref: str = "HEAD", label: str = "Task") -> list[str]:
    """워크트리 시작 조건 — 분기점(start_ref) 존재 + 그 사본이 디스크 문서(Task · 대상 Intent)와 같음.

    워크트리에 들어가는 건 디스크 파일이 아니라 start_ref 의 사본이다. 사본이 다르면
    승인 상태 · 진행 표시가 워크트리에 반영되지 않고 `_mark_in_dev` 가 조용히 실패해 resume 으로 오판된다.
    """
    if _resolve_commit(root, start_ref) is None:
        if start_ref == "HEAD":
            return ["커밋이 하나도 없다 — Task · Intent 와 프로젝트 골격(소스·테스트·솔루션)을 먼저 커밋한다. 워크트리는 마지막 커밋을 복사한다."]
        return [f"base '{start_ref}' 가 커밋을 가리키지 않는다."]
    try:
        rel = doc.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return [f"{label} 가 이 repo 밖에 있다: {doc}"]
    where = "마지막 커밋" if start_ref == "HEAD" else f"base '{start_ref}'"
    tree_rel = _tree_rel(root, start_ref, rel)
    show = _git(root, "show", f"{start_ref}:{tree_rel}") if tree_rel else None
    if show is None or show.returncode != 0:
        return [f"{label} 가 {where}에 없다: {rel} — 먼저 그 브랜치에 커밋하거나 다른 base 를 고른다."]
    if _norm(show.stdout) != _norm(doc.read_text(encoding="utf-8", errors="replace")):
        return [f"{label} 가 {where}의 사본과 다르다: {rel} — 워크트리에는 그 사본이 들어가므로 "
                "승인 상태 · 진행 표시가 반영되지 않는다. 먼저 커밋하거나 다른 base 를 고른다."]
    return []


def _gate_start_all(root: Path, doc: Path, intent_docs: list[Path], start_ref: str) -> list[str]:
    """Task 와 대상 Intent 마다 _gate_start. 분기점이 없으면 문서마다 같은 말을 되풀이하지 않는다."""
    problems = _gate_start(root, doc, start_ref, "Task")
    if _resolve_commit(root, start_ref) is None:
        return problems
    for p in intent_docs:
        if p.is_file():   # 없는 Intent 는 TSK_INTENT_EXISTS 가 이미 알린다
            problems += _gate_start(root, p, start_ref, "Intent")
    return problems


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
                 "  Hint: 그 워크트리를 정리한 뒤 재실행 — .worktree/ 아래면 "
                 "`worktree_setup.py cancel <slug>`, 그 밖이면 `git worktree remove <경로>`. "
                 "브랜치는 Task Handoff 로 정해지므로 --name 으로는 피할 수 없다.")
        if not registered.exists():
            _err(f"ERROR: 워크트리 등록됐으나 디렉토리 없음(stale): {registered}\n"
                 "  Hint: `git worktree prune` 후 재실행.")
        return wt, branch, False, False

    if wt.exists():
        _err(f"ERROR: 디렉토리 존재하나 워크트리 미등록: {wt}\n"
             "  Hint: 수동 삭제하거나 `git worktree prune` 후 재시도.")

    if not force:
        st = _git(root, "status", "--porcelain")
        # forge가 관리하는 워크트리/상태 디렉토리는 dirty 오탐에서 제외
        dirty = [
            l for l in st.stdout.splitlines()
            if l.strip() and not re.search(r"\.worktree/|\.process/", l)
        ]
        if dirty:
            _err("ERROR: 메인 repo 작업트리가 dirty — commit/stash 후 재시도 (또는 --force).\n"
                 + "\n".join(f"  {l}" for l in dirty[:10]))

    wt.parent.mkdir(parents=True, exist_ok=True)
    exists = _git(root, "rev-parse", "--verify", "--quiet", branch).returncode == 0
    base_applied = False
    if exists:
        if base:
            print(f"NOTE: 브랜치 '{branch}' 가 이미 있어 base '{base}' 는 적용되지 않는다 (resume).",
                  file=sys.stderr)
        r = _git(root, "worktree", "add", str(wt), branch)
    elif base:
        # 원격 ref 에서 분기하면 git 이 upstream 을 잡는다. forge 는 push 하지 않으므로 끊는다.
        extra = ["--no-track"] if _is_remote_ref(root, base) else []
        r = _git(root, "worktree", "add", *extra, "-b", branch, str(wt), base)
        base_applied = True
    else:
        r = _git(root, "worktree", "add", "-b", branch, str(wt))
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


def _refresh_int_catalog(wt: Path, intent_rel: str) -> Optional[str]:
    """워크트리의 <App>-INT-CATALOG.md 를 INTENT/ 에서 다시 생성한다.

    카탈로그는 파생 인덱스라 상태 전이 직후 반드시 갱신해야 한다. 실패해도 init 을
    막지 않는다 — docs_helpers.py check --app <App> 이 stale 로 잡는다.
    """
    parts = Path(intent_rel).parts
    # 문서 폴더는 docs·Docs 둘 다 받는다 — 카탈로그는 Intent 와 같은 표기의 폴더에 둔다.
    if len(parts) < 4 or parts[0].lower() != "docs" or parts[2] != "INTENT":
        return None
    app = parts[1]
    rel = f"{parts[0]}/{app}/{app}-INT-CATALOG.md"
    try:   # 게이트가 아니다 — 문서 문제로 죽지 않는다 (쓰기 실패 포함)
        rows, _ = _dh._collect_intent_rows(wt, app)
        text = _dh._render_intent_catalog(app, rows)
        (wt / rel).write_text(text, encoding="utf-8", newline="\n")
    except Exception as e:
        # None 을 돌려주면 호출측이 카탈로그를 git add 하지 않고 넘어간다 —
        # 커밋이 조용히 1파일로 줄어들지 않도록 경고 1줄을 남긴다 (init 은 막지 않는다).
        print(f"WARN: {rel} 갱신 실패 — 상태 전이 커밋에 동봉되지 않는다 "
              f"({type(e).__name__}: {e}). docs_helpers.py check --app {app} 로 확인할 것.",
              file=sys.stderr)
        return None
    return rel


def _refresh_task_catalog(wt: Path) -> Optional[str]:
    """워크트리의 .task/task-catalog.md 를 .task/ 에서 다시 생성한다.

    _refresh_int_catalog 와 같은 원칙 — 상태 전이 직후 갱신하고, 실패해도 막지 않는다
    (docs_helpers.py check 가 TSK_CATALOG stale 로 잡는다).
    """
    rel = f"{_dh.TASK_DIR}/{_dh.TASK_CATALOG_NAME}"
    try:   # 게이트가 아니다 — 문서 문제로 죽지 않는다 (쓰기 실패 포함)
        rows, _ = _dh._collect_task_rows(wt)
        (wt / rel).write_text(_dh._render_task_catalog(rows), encoding="utf-8", newline="\n")
    except Exception as e:
        print(f"WARN: {rel} 갱신 실패 — 상태 전이 커밋에 동봉되지 않는다 "
              f"({type(e).__name__}: {e}). docs_helpers.py check 로 확인할 것.",
              file=sys.stderr)
        return None
    return rel


def _mark_in_dev(wt: Path, task_rel: str, task_id: str, base: Optional[str] = None) -> bool:
    """워크트리 Task 를 approved → in-dev 로 바꿔 task-catalog 와 함께 커밋한다.

    Intent 는 바뀌지 않는다 — 진행 표시는 승인 커밋에 이미 들어 있다. 그래서 INT 카탈로그도 동봉하지 않는다.
    """
    def transition(text: str) -> str:
        new_text = _set_table_row(text, "상태", "in-dev", old_value="approved")
        if new_text != text and base:
            # Handoff `base branch` 를 실제 분기점으로 치환해 상태 전이와 같은 커밋에 동봉한다.
            # TSK_HANDOFF_ROWS 가 5행 존재를 강제하므로 게이트를 통과한 Task 에는 항상 이 행이 있다.
            new_text = _set_table_row(new_text, "base branch", base)
        return new_text

    if not _rewrite(wt / task_rel, transition):
        return False
    _git(wt, "add", task_rel)
    cat_rel = _refresh_task_catalog(wt)
    if cat_rel:
        _git(wt, "add", cat_rel)
    r = _git(wt, "commit", "-m", f"chore({task_id}): 상태 in-dev")
    if r.returncode != 0:
        _err(f"ERROR: 상태 in-dev 커밋 실패 ({task_rel}).\n  {r.stderr.strip()}")
    return True


def _ensure_gitignore(wt: Path) -> None:
    gi = wt / ".gitignore"
    have = gi.read_text(encoding="utf-8", errors="replace") if gi.exists() else ""
    lines = {l.strip() for l in have.splitlines()}
    add = [e for e in (".worktree/", ".process/") if e not in lines]
    if add:
        prefix = "" if have.endswith("\n") or not have else "\n"
        with gi.open("a", encoding="utf-8") as f:
            f.write(prefix + "\n".join(add) + "\n")


def _main_manifest_path(root: Path, slug: str) -> Path:
    return root / MANIFEST_DIR / f"{slug}.json"


def _write_manifests(root: Path, wt: Path, slug: str, manifest: dict) -> list[str]:
    """매니페스트를 워크트리·메인 두 곳에 쓴다. 쓴 경로 목록을 돌려준다.

    한 번 정확히 알아낸 값(브랜치·base_commit·워크트리 경로)을 버리지 않기 위한 것이다.
    이게 없으면 cancel·list 가 나중에 slug 로부터 브랜치를 추측하게 된다.
    """
    written: list[str] = []
    for target in (wt / MANIFEST_DIR / HANDOFF_NAME, _main_manifest_path(root, slug)):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(str(target))
        except OSError as e:
            print(f"NOTE: 매니페스트를 쓰지 못했다: {target} ({e})", file=sys.stderr)
    return written


def _read_main_manifest(root: Path, slug: str) -> Optional[dict]:
    p = _main_manifest_path(root, slug)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def cmd_branches(args: argparse.Namespace) -> int:
    """읽기 전용 — 세션이 base 선택지를 사용자에게 제시하기 위한 목록."""
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.", EXIT_BLOCKED)

    r = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    current = r.stdout.strip() if r.returncode == 0 else ""

    recommended = ""
    recommended_source = "head"
    target_branch = ""
    if args.doc:
        doc = _doc_path(root, args.doc)
        try:   # 게이트가 아니다 — 문서 문제로 죽지 않는다
            task = _dh._parse_task(doc.read_text(encoding="utf-8", errors="replace"))
            task_id = task.meta.get("문서 ID", "").strip() or doc.stem
            target_branch = _task_branch(root, task_id, task.handoff.get("브랜치명", ""))
            handoff_base = task.handoff.get("base branch", "").strip()
            if handoff_base:
                recommended = handoff_base
                recommended_source = "handoff"
        except Exception:
            pass
    if not recommended:
        recommended = current
        recommended_source = "head"

    rows = _branch_rows(root)
    for row in rows:
        row["is_current"] = row["kind"] == "local" and row["ref"] == current
        row["is_recommended"] = row["ref"] == recommended
    rows.sort(key=lambda row: not row["is_recommended"])   # stable — 추천만 맨 앞으로

    target_exists = bool(target_branch) and _git(
        root, "rev-parse", "--verify", "--quiet", f"refs/heads/{target_branch}"
    ).returncode == 0

    print(json.dumps({
        "recommended": recommended,
        "recommended_source": recommended_source,
        "recommended_exists": bool(recommended) and _resolve_commit(root, recommended) is not None,
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

    doc = _doc_path(root, args.doc)

    if not doc.exists():
        _err(f"§F 문서 없음: {doc}", EXIT_BLOCKED)

    raw = doc.read_text(encoding="utf-8", errors="replace")
    input_kind = _detect_input_kind(doc, raw)
    if input_kind == "INTENT":
        _err(
            "§F Intent 는 기능 문서라 개발 입력이 아니다 — 바뀐 항목을 Task(.task/TSK-NNN.md)로 옮겨 "
            "승인한 뒤 그 Task 경로를 넣는다.",
            EXIT_BLOCKED,
        )
    if input_kind != "TASK":
        _err(
            "§F Work Packet·TASK 입력은 v3.58 에서 폐지됐다 — "
            "승인한 Task(.task/TSK-NNN.md) 경로를 넣는다.",
            EXIT_BLOCKED,
        )

    base = (args.base or "").strip() or None
    base_commit = None
    if base:
        if "|" in base or "\r" in base or "\n" in base:
            _err(f"ERROR: base '{base}' 에 쓸 수 없는 문자(| 또는 개행)가 있다 — Handoff 표를 깨뜨린다.")
        base_commit = _resolve_commit(root, base)
        if base_commit is None:
            _err(f"ERROR: base '{base}' 를 찾을 수 없다 — "
                 "`worktree_setup.py branches` 로 목록을 확인하고 다시 고른다.")

    task = _dh._parse_task(raw)
    # targets 는 ID 형식인 것만 담으므로 경로가 항상 나온다 (파일이 없을 수는 있다 — 게이트가 막는다).
    intent_pairs = [(i, _dh._intent_path(root, i)) for i in task.targets]
    intent_docs = [p for _, p in intent_pairs if p is not None]
    problems = _gate_task(root, doc) + _gate_start_all(root, doc, intent_docs, base or "HEAD")
    if problems:
        _err("§F Task 게이트 미통과:\n" + "\n".join(f"  - {p}" for p in problems), EXIT_BLOCKED)

    task_id = task.meta.get("문서 ID", "").strip() or doc.stem
    slug = _slugify(args.name or task_id)
    branch = _task_branch(root, task_id, task.handoff.get("브랜치명", ""))

    wt, branch, created, base_applied = _ensure_worktree(
        root, slug, branch, force=args.force, base=base,
    )

    log: list[str] = []
    _link_submodules(root, wt, log)
    copied, skipped = _copy_guardrails(root, wt)

    # _gate_start 와 같은 방식 — 게이트가 repo 내부임을 이미 보장했다. 워크트리는 커밋된
    # 표기로 체크아웃되므로 디스크 표기(docs/Docs)가 아니라 그 표기를 쓴다 (_tree_rel).
    def wt_rel(p: Path) -> str:
        rel = p.resolve().relative_to(root.resolve()).as_posix()
        return _tree_rel(wt, "HEAD", rel) or rel

    task_rel = wt_rel(doc)
    _ensure_gitignore(wt)

    status_committed = False
    if created:
        status_committed = _mark_in_dev(wt, task_rel, task_id, base)

    wt_task = _dh._parse_task((wt / task_rel).read_text(encoding="utf-8", errors="replace"))
    status = wt_task.meta.get("상태", "")

    manifest = {
        "root": str(root),
        "worktree": str(wt),
        "branch": branch,
        "base": base or "",                 # 사용자가 고른 분기점 ref
        "base_commit": base_commit or "",   # 그 시점 sha — 마감 diff 는 이걸 쓰는 게 안전
        "base_applied": base_applied,       # False = 브랜치가 이미 있어 분기점을 못 바꿨다
        "slug": slug,
        "task": str(doc),
        "task_worktree": str(wt / task_rel),
        "task_id": task_id,
        # 대상 Intent — 개발 세션은 이 워크트리 경로로 읽는다. 문장은 Scope 사본과 같다.
        "intents": [
            {"id": i, "path": str(p), "worktree_path": str(wt / wt_rel(p))}
            for i, p in intent_pairs if p is not None
        ],
        "status": status,
        "created": created,
        "status_committed": status_committed,
        "scope": [{"kind": it.kind, "key": it.key, "text": it.text} for it in wt_task.scope],
        "acceptance": [{"id": a.id, "text": a.text, "refs": a.refs} for a in wt_task.acceptance],
        "handoff": {k: wt_task.handoff.get(k, "") for k in _dh.INTENT_HANDOFF_EXPECTED},
        "copied": copied,
        "skipped": skipped,
        "submodule_log": log,
    }

    # 메인 .gitignore 는 건드리지 않는다 — 고치면 ` M .gitignore` 가 남아 다음 init 이
    # dirty 로 막힌다. `?? .process/` 는 _ensure_worktree 의 dirty 검사에서 이미 제외되고,
    # requirement-spec Phase 0 이 소비자 repo .gitignore 에 .process/ 를 넣어둔다.
    manifest["manifests"] = _write_manifests(root, wt, slug, manifest)

    if not args.quiet:
        print(f"[forge] worktree: {wt}")
        print(f"[forge] branch:   {branch}")
        if base:
            mark = "" if base_applied else " (무시됨 — 브랜치 기존재)"
            print(f"[forge] base:     {base} ({(base_commit or '')[:7]}){mark}")
        print(f"[forge] status:   {status}")
        if copied:
            print(f"[forge] 복사:     {', '.join(copied)}")
        if skipped:
            print(f"[forge] skip:     {', '.join(skipped)}")
        for m in manifest["manifests"]:
            print(f"[forge] manifest: {m}")
        for l in log:
            print(f"[forge] {l}")
    print(json.dumps(manifest, ensure_ascii=False))
    return EXIT_OK


# ============================================================================
# cancel
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


def cmd_list(args: argparse.Namespace) -> int:
    """forge 워크트리 나열 — 매니페스트 우선, 없으면 .worktree/ 스캔 폴백."""
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    out: dict[str, dict] = {}

    # ① 매니페스트 — init 이 기록한 사실. 브랜치 이름 규칙에 의존하지 않는다.
    for mf in sorted((root / MANIFEST_DIR).glob("*.json")):
        try:
            data = json.loads(mf.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        slug, branch, wtp = data.get("slug"), data.get("branch"), data.get("worktree")
        if not (slug and branch and wtp) or not Path(wtp).is_dir():
            continue
        out[slug] = {"slug": slug, "branch": branch, "worktree": wtp, "source": "manifest"}

    # ② 스캔 폴백 — 매니페스트 이전에 만들어진 워크트리.
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
            if under and cur.name not in out and br.startswith(("feat-", "intent/", "task/")):
                out[cur.name] = {"slug": cur.name, "branch": br,
                                 "worktree": str(cur), "source": "scan"}
            cur = None

    print(json.dumps([out[k] for k in sorted(out)], ensure_ascii=False))
    return EXIT_OK


def cmd_cancel(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    slug = _slugify(args.slug)
    manifest = _read_main_manifest(root, slug)

    # 브랜치 이름은 Handoff 로 정해지므로 slug 에서 유도할 수 없다.
    # ① 매니페스트(init 이 기록한 사실) → ② 워크트리 역인덱싱 → ③ 명시 실패.
    # 예전의 `feat-<slug>` 추측은 기본 브랜치(intent/<ID>, 지금은 task/<ID>)와 어긋나 조용히 실패했다.
    wt = Path(manifest["worktree"]) if manifest and manifest.get("worktree") \
        else root / ".worktree" / slug
    branch = (manifest or {}).get("branch") or _worktree_branch(root, wt)
    if not branch:
        _err(f"취소 대상 브랜치를 특정할 수 없다: slug={slug}, worktree={wt}\n"
             f"  Hint: `python worktree_setup.py list` 로 slug 를 확인하거나, "
             f"브랜치명을 알면 `git worktree remove` + `git branch -D` 로 직접 정리한다.")
    registered = _registered_worktree_path(root, branch)

    if registered is not None and not registered.exists():
        _git(root, "worktree", "prune")
        registered = _registered_worktree_path(root, branch)

    branch_exists = _git(root, "rev-parse", "--verify", "--quiet", branch).returncode == 0
    if not branch_exists and registered is None and not wt.exists():
        _err(f"취소 대상 없음: branch={branch}, worktree={wt}")

    cwd_real = Path.cwd().resolve()
    target = registered if registered is not None else (wt if wt.exists() else None)
    if target is not None:
        wt_real = target.resolve()
        if cwd_real == wt_real or wt_real in cwd_real.parents:
            _err("현재 cwd가 제거 대상 워크트리 내부입니다. 메인 repo로 이동 후 재실행:\n"
                 f"  cd {root}")

    removed_worktree = False
    if target is not None:
        # 서브모듈 링크만 해제 — worktree remove 가 junction 따라 메인 삭제하는 사고 방지.
        # 메인 repo 서브모듈 원본은 절대 건드리지 않는다 (deinit 등 미수행).
        _unlink_submodule_links(target)
        # 워크트리는 .process/.gitignore 등 uncommitted 상태를 거의 항상 가짐 →
        # dirty면 자동 --force (forge_cancel.py 원본 동작).
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
    if _git(root, "rev-parse", "--verify", "--quiet", branch).returncode == 0:
        r = _git(root, "branch", "-D", branch)
        if r.returncode != 0:
            _err(f"git branch -D 실패: {r.stderr.strip()}")
        removed_branch = True

    # 메인 매니페스트는 "살아 있는 워크트리" 대장이므로 정리와 함께 지운다.
    removed_manifest = False
    mpath = _main_manifest_path(root, slug)
    if mpath.is_file():
        try:
            mpath.unlink()
            removed_manifest = True
        except OSError as e:
            print(f"NOTE: 매니페스트를 지우지 못했다: {mpath} ({e})", file=sys.stderr)

    print("worktree_setup: cancel 완료")
    if removed_worktree:
        print(f"- removed worktree: {wt}")
    if removed_branch:
        print(f"- deleted branch:   {branch}")
    if removed_manifest:
        print(f"- removed manifest: {mpath}")
    return EXIT_OK


# ============================================================================
# finish — 마감 전이 (워크트리 안에서)
# ============================================================================
INTENT_ITEM_LINE = re.compile(r"^- ((?:FR|E|X)-\d+)\.")


def _clear_task_marks(text: str, task_id: str) -> tuple[str, list[str], list[str]]:
    """이 Task 의 진행 표시를 지우고, 이 Task 의 `삭제 예정` 항목 줄을 지운다.

    (새 텍스트, 표시를 지운 항목 ID, 줄을 지운 항목 ID) 를 돌려준다. 다른 Task 의 표시는 건드리지 않는다.
    줄을 지워 섹션에 남는 본문이 없으면 그 자리에 `none` 을 남긴다 — Intent 는 빈 섹션 대신 none 을 쓴다.
    줄바꿈은 원본 그대로다(CRLF 면 줄 끝 \\r 이 남는다).
    """
    mark_at_end = re.compile(rf"\s*\[{re.escape(task_id)} (진행 중|삭제 예정)\]\s*$")
    mark_any = re.compile(rf"\s*\[{re.escape(task_id)} (?:진행 중|삭제 예정)\]")
    lines = text.split("\n")
    live = [t for _, t in _dh._live_lines(text, 1)]   # 주석을 뺀 본문 — 같은 "\n" 기준이라 줄 수가 같다
    out: list[str] = []
    cleared: list[str] = []
    deleted: list[str] = []
    first_del: Optional[int] = None   # 이 섹션에서 처음 지운 줄이 out 에 들어갈 자리
    del_eol = ""
    has_live = False

    def close_section() -> None:
        if first_del is not None and not has_live:
            out.insert(first_del, "none" + del_eol)

    for raw, live_line in zip(lines, live):
        body = raw.rstrip("\r")
        eol = raw[len(body):]
        live_body = live_line.rstrip("\r").rstrip()
        if re.match(r"^#{1,6}\s", live_body) or re.match(r"^-{3,}$", live_body):   # 주석 안의 # 은 헤딩이 아니다
            close_section()
            first_del, del_eol, has_live = None, "", False
            out.append(raw)
            continue
        item = INTENT_ITEM_LINE.match(live_body)
        m = mark_at_end.search(live_body) if item else None
        if m is not None and m.group(1) == "삭제 예정":
            deleted.append(item.group(1))
            if first_del is None:
                first_del, del_eol = len(out), eol
            continue
        if m is not None:
            out.append(mark_any.sub("", body, count=1) + eol)
            cleared.append(item.group(1))
            has_live = True
            continue
        out.append(raw)
        if live_body.strip():
            has_live = True
    close_section()
    return "\n".join(out), cleared, deleted


def cmd_finish(args: argparse.Namespace) -> int:
    """마감 전이 — 진행 표시 정리 + Task in-dev → in-review + 카탈로그 재생성 + 커밋 1개.

    개발을 마친 세션이 워크트리 안에서 부른다. 문서를 고치는 유일한
    개발 단계 경로라서, 무엇을 바꾸는지 고정하고 다른 변경이 섞이지 않게 막는다.
    """
    cwd = Path.cwd()
    git_dir = _abs_git_path(cwd, "--git-dir")
    common_dir = _abs_git_path(cwd, "--git-common-dir")
    if git_dir is None or common_dir is None:
        _err("ERROR: git repository가 아닙니다.", EXIT_BLOCKED)
    if git_dir == common_dir:
        _err("§F finish 는 /forge-init 이 만든 워크트리 안에서 실행한다 — 여기는 메인 repo(또는 서브모듈)다.",
             EXIT_BLOCKED)
    wt = Path(_git(cwd, "rev-parse", "--show-toplevel").stdout.strip())

    mf = Path(args.manifest) if args.manifest else wt / MANIFEST_DIR / HANDOFF_NAME
    try:
        manifest = json.loads(mf.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as e:
        _err(f"§F 매니페스트를 읽지 못했다: {mf} ({e}) — /forge-init 이 만든 워크트리인지 확인한다.", EXIT_BLOCKED)
    task_id = str(manifest.get("task_id") or "") if isinstance(manifest, dict) else ""
    if not re.fullmatch(r"TSK-\d{3}", task_id):
        _err(f"§F 매니페스트에 Task ID 가 없다: {mf} — /forge-init 을 다시 실행한다.", EXIT_BLOCKED)

    # 매니페스트의 절대경로는 쓰지 않는다 — Task ID 로 워크트리 안의 문서를 다시 찾는다.
    task_rel = f"{_dh.TASK_DIR}/{task_id}.md"
    if not (wt / task_rel).is_file():
        _err(f"§F Task 가 워크트리에 없다: {task_rel}", EXIT_BLOCKED)
    task = _dh._parse_task((wt / task_rel).read_text(encoding="utf-8", errors="replace"))
    status = task.meta.get("상태", "").strip()
    result = {"task_id": task_id, "status": status, "already": False,
              "cleared": [], "deleted": [], "files": [], "committed": False}
    if status == "in-review":
        result["already"] = True
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_OK
    if status != "in-dev":
        _err(f"§F Task 상태가 '{status or '(없음)'}' — in-dev 일 때만 마감한다.", EXIT_BLOCKED)

    intents: list[tuple[str, str]] = []   # (Intent ID, 워크트리 기준 디스크 표기 경로)
    for intent_id in task.targets:
        p = _dh._intent_path(wt, intent_id)
        if p is None or not p.is_file():
            _err(f"§F 대상 Intent 가 워크트리에 없다: {intent_id}", EXIT_BLOCKED)
        intents.append((intent_id, p.relative_to(wt).as_posix()))
    task_cat_rel = f"{_dh.TASK_DIR}/{_dh.TASK_CATALOG_NAME}"
    int_cat_rels = sorted({
        f"{Path(rel).parts[0]}/{Path(rel).parts[1]}/{Path(rel).parts[1]}-INT-CATALOG.md" for _, rel in intents
    })
    touched = [task_rel, task_cat_rel, *(rel for _, rel in intents), *int_cat_rels]

    staged = [n for n in _git(wt, "diff", "--cached", "--name-only", "-z").stdout.split("\0") if n]
    if staged:
        _err("§F 스테이징된 변경이 있다 — 마감 커밋에 섞이지 않게 먼저 커밋하거나 내린다:\n"
             + "\n".join(f"  {n}" for n in staged[:10]), EXIT_BLOCKED)
    dirty = [n for n in _git(wt, "diff", "--name-only", "-z", "HEAD", "--",
                             *(f":(icase){rel}" for rel in touched)).stdout.split("\0") if n]
    if dirty:
        _err("§F 마감이 고칠 문서에 커밋 안 된 변경이 있다 — Task · Intent 는 개발 단계에서 고치지 않는다:\n"
             + "\n".join(f"  {n}" for n in dirty[:10]), EXIT_BLOCKED)

    for intent_id, rel in intents:
        text = _read_raw(wt / rel)
        new_text, cleared, deleted = _clear_task_marks(text, task_id)
        if new_text != text:
            _write_raw(wt / rel, new_text)
        result["cleared"] += [f"{intent_id} {x}" for x in cleared]
        result["deleted"] += [f"{intent_id} {x}" for x in deleted]
    if not _rewrite(wt / task_rel, lambda t: _set_table_row(t, "상태", "in-review", old_value="in-dev")):
        _err(f"ERROR: Task 상태 행을 바꾸지 못했다 ({task_rel}) — 메타 표의 `| 상태 | in-dev |` 를 확인한다.")

    to_stage = [task_rel, *(rel for _, rel in intents)]
    cat_rel = _refresh_task_catalog(wt)
    if cat_rel:
        to_stage.append(cat_rel)
    for _, rel in intents:   # Intent 줄이 지워지면 규모(FR 수)가 바뀐다 — App 카탈로그도 다시 쓴다
        int_cat = _refresh_int_catalog(wt, rel)
        if int_cat and int_cat not in to_stage:
            to_stage.append(int_cat)
    for rel in to_stage:
        # 커밋된 표기(docs·Docs)로 add 해야 tracked 파일이 스테이징된다.
        _git(wt, "add", _tree_rel(wt, "HEAD", rel) or rel)
    result["files"] = [n for n in _git(wt, "diff", "--cached", "--name-only", "-z").stdout.split("\0") if n]
    r = _git(wt, "commit", "-m", f"chore({task_id}): 상태 in-review")
    if r.returncode != 0:
        _err(f"ERROR: 상태 in-review 커밋 실패 ({task_rel}).\n  {r.stderr.strip()}")
    result["status"] = "in-review"
    result["committed"] = True

    if not args.quiet:
        print(f"[forge] task:     {task_id} in-dev → in-review")
        print(f"[forge] 표시 정리: {len(result['cleared'])}개, 삭제 줄 {len(result['deleted'])}개")
        for name in result["files"]:
            print(f"[forge] 커밋:     {name}")
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK


# ============================================================================
# CLI
# ============================================================================
def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="worktree_setup", description="forge 워크트리 셋업 helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="검증 게이트 + 워크트리 + 링크 + 복사 + 상태 전이")
    pi.add_argument("--doc", required=True, help="approved Task 문서 경로 (.task/TSK-<NNN>.md)")
    pi.add_argument("--name", default=None, help="slug 명시 (기본: Task 문서 ID)")
    pi.add_argument("--base", default=None,
                    help="워크트리 분기점 ref (기본: 현재 HEAD). 예: main, develop, origin/develop")
    pi.add_argument("--force", action="store_true", help="메인 repo dirty 검사 우회")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    pb = sub.add_parser("branches", help="base 후보 브랜치 나열 (로컬 + origin/*, JSON)")
    pb.add_argument("--doc", default=None, help="Task 경로 (추천 base·대상 브랜치 계산용)")
    pb.set_defaults(func=cmd_branches)

    pl = sub.add_parser("list", help="forge 워크트리 나열 (JSON)")
    pl.set_defaults(func=cmd_list)

    pc = sub.add_parser("cancel", help="워크트리 + 브랜치 정리 (서브모듈 메인 원본 보존)")
    pc.add_argument("slug", help="docName/slug (워크트리 .worktree/<slug>)")
    pc.add_argument("--force", action="store_true", help="dirty 워크트리 강제 제거")
    pc.set_defaults(func=cmd_cancel)

    pf = sub.add_parser("finish", help="(워크트리 안에서) 마감 전이 — 진행 표시 정리 + Task in-dev → in-review + 카탈로그 + 커밋")
    pf.add_argument("--manifest", default=None, help="매니페스트 경로 (기본: <워크트리>/.process/forge/handoff.json)")
    pf.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pf.set_defaults(func=cmd_finish)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
