#!/usr/bin/env python3
"""worktree_setup — forge-scope 워크트리 셋업 helper.

오케스트레이션은 하지 않는다. 셋업·검증·정리만 담당하고, 고정 계약-TDD
파이프라인의 실제 코딩은 호출한 Claude Code 세션이 워크트리 안에서 인라인으로
수행한다.

Subcommands
-----------
- ``init``   : 검증 게이트 → 워크트리(.worktree/<slug>) 생성 → 서브모듈 링크 →
               가드레일 복사 → Intent 상태 전이(approved → in-dev) → JSON 매니페스트 출력.
- ``cancel`` : 서브모듈 링크 해제(메인 타깃 보존) → worktree remove → branch -D.

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

# 가드레일 복사 대상: .claude 전체가 아니라 .claude/rules 만.
GUARDRAIL_FILES = ["CLAUDE.md"]
GUARDRAIL_DIRS = [".claude/rules", "Docs", "docs"]


# ============================================================================
# 공통 git/링크 유틸 (forge_scope.py / forge_cancel.py 에서 포팅)
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


def _repo_root(start: Path) -> Optional[Path]:
    r = _git(start, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip())


def _slugify(stem: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return s or "task"


def _intent_branch(root: Path, intent_id: str, handoff_value: str) -> str:
    v = handoff_value.strip()
    if v and _git(root, "check-ref-format", "--branch", v).returncode == 0:
        return v
    return f"intent/{intent_id}"


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
INTENT_START_STATUSES: tuple[str, ...] = ("approved", "in-dev")


def _detect_input_kind(doc: Path, raw: str) -> str:
    if any(p.upper() == "INTENT" for p in doc.parts):
        return "INTENT"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*-INT-\d{3}", doc.stem):
        return "INTENT"
    return "LEGACY"


def _gate_intent(root: Path, doc: Path) -> list[str]:
    """Intent 승인·형식 게이트. 문제 목록(빈 목록 = 통과)."""
    problems: list[str] = []

    raw = doc.read_text(encoding="utf-8", errors="replace")
    status = _dh._parse_intent(raw).meta.get("상태", "").strip()
    if status not in INTENT_START_STATUSES:
        problems.append(f"Intent 상태가 '{status or '(없음)'}' — approved 여야 개발을 시작한다 (requirement-spec Phase 5 에서 승인).")

    for r in _dh._check_intent_file(root, doc):
        if r.level == "FAIL":
            problems.append(f"{r.code}: {r.message}")

    return problems


def _gate_start(root: Path, doc: Path) -> list[str]:
    """워크트리 시작 조건 — HEAD 존재 + Intent 가 HEAD 에 tracked."""
    if _git(root, "rev-parse", "--verify", "--quiet", "HEAD").returncode != 0:
        return ["커밋이 하나도 없다 — Intent 와 프로젝트 골격(소스·테스트·솔루션)을 먼저 커밋한다. 워크트리는 마지막 커밋을 복사한다."]
    try:
        rel = doc.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return [f"Intent 가 이 repo 밖에 있다: {doc}"]
    if _git(root, "cat-file", "-e", f"HEAD:{rel}").returncode != 0:
        return [f"Intent 가 마지막 커밋에 없다: {rel} — 먼저 커밋한다."]
    return []


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


def _ensure_worktree(root: Path, slug: str, branch: str, *, force: bool) -> tuple[Path, str, bool]:
    wt = root / ".worktree" / slug

    registered = _registered_worktree_path(root, branch)
    if registered is not None:
        if registered.resolve() != wt.resolve():
            _err(f"ERROR: branch '{branch}'가 다른 워크트리에 attach됨: {registered}\n"
                 "  Hint: worktree_setup.py cancel 로 정리하거나 다른 --name 사용.")
        if not registered.exists():
            _err(f"ERROR: 워크트리 등록됐으나 디렉토리 없음(stale): {registered}\n"
                 "  Hint: `git worktree prune` 후 재실행.")
        return wt, branch, False

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
    if exists:
        r = _git(root, "worktree", "add", str(wt), branch)
    else:
        r = _git(root, "worktree", "add", "-b", branch, str(wt))
    if r.returncode != 0:
        _err(f"ERROR: 워크트리 생성 실패 ({wt}).\n  {r.stderr.strip()}")
    return wt, branch, True


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
        src = root / rel
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


def _mark_in_dev(wt: Path, intent_rel: str, intent_id: str) -> bool:
    p = wt / intent_rel
    text = p.read_text(encoding="utf-8", errors="replace")
    new_text, n = re.subn(
        r"(?m)^\|\s*상태\s*\|\s*approved\s*\|\s*$",
        "| 상태 | in-dev |",
        text,
    )
    if n == 0:
        return False
    p.write_text(new_text, encoding="utf-8")
    _git(wt, "add", intent_rel)
    r = _git(wt, "commit", "-m", f"chore({intent_id}): 상태 in-dev")
    if r.returncode != 0:
        _err(f"ERROR: 상태 in-dev 커밋 실패 ({intent_rel}).\n  {r.stderr.strip()}")
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


def cmd_init(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다. `git init` 후 재시도.", EXIT_BLOCKED)

    doc = Path(args.doc)
    if not doc.is_absolute():
        doc = (Path.cwd() / doc).resolve()

    if not doc.exists():
        _err(f"§F 문서 없음: {doc}", EXIT_BLOCKED)

    raw = doc.read_text(encoding="utf-8", errors="replace")
    input_kind = _detect_input_kind(doc, raw)
    if input_kind != "INTENT":
        _err(
            "§F Work Packet·TASK 입력은 v3.58 에서 폐지됐다 — "
            "requirement-spec 으로 Intent 를 작성·승인한 뒤 그 경로를 넣는다.",
            EXIT_BLOCKED,
        )

    problems = _gate_intent(root, doc) + _gate_start(root, doc)
    if problems:
        _err("§F Intent 게이트 미통과:\n" + "\n".join(f"  - {p}" for p in problems), EXIT_BLOCKED)

    intent = _dh._parse_intent(raw)
    intent_id = intent.meta.get("문서 ID", "").strip() or doc.stem
    slug = _slugify(args.name or intent_id)
    branch = _intent_branch(root, intent_id, intent.handoff.get("브랜치명", ""))

    wt, branch, created = _ensure_worktree(root, slug, branch, force=args.force)

    log: list[str] = []
    _link_submodules(root, wt, log)
    copied, skipped = _copy_guardrails(root, wt)

    # _gate_start 와 같은 방식 — 게이트가 repo 내부임을 이미 보장했다.
    intent_rel = doc.resolve().relative_to(root.resolve()).as_posix()
    _ensure_gitignore(wt)

    status_committed = False
    if created:
        status_committed = _mark_in_dev(wt, intent_rel, intent_id)

    wt_intent = _dh._parse_intent(
        (wt / intent_rel).read_text(encoding="utf-8", errors="replace")
    )
    status = wt_intent.meta.get("상태", "")

    manifest = {
        "root": str(root),
        "worktree": str(wt),
        "branch": branch,
        "slug": slug,
        "intent": str(doc),
        "intent_worktree": str(wt / intent_rel),
        "intent_id": intent_id,
        "status": status,
        "created": created,
        "status_committed": status_committed,
        "acceptance": [{"id": it.id, "text": it.text} for it in wt_intent.items["A"]],
        "handoff": {
            k: wt_intent.handoff.get(k, "")
            for k in ("repo · app", "base branch", "브랜치명", "손대지 말 영역", "완료 보고 방식")
        },
        "copied": copied,
        "skipped": skipped,
        "submodule_log": log,
    }
    if not args.quiet:
        print(f"[forge] worktree: {wt}")
        print(f"[forge] branch:   {branch}")
        print(f"[forge] status:   {status}")
        if copied:
            print(f"[forge] 복사:     {', '.join(copied)}")
        if skipped:
            print(f"[forge] skip:     {', '.join(skipped)}")
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
    """forge 워크트리 나열 — .worktree/ 하위 + feat-<slug>·intent/… 브랜치인 것만."""
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    wt_base = (root / ".worktree").resolve()
    r = _git(root, "worktree", "list", "--porcelain")
    out: list[dict] = []
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
            if under and (br.startswith("feat-") or br.startswith("intent/")):
                out.append({"slug": cur.name, "branch": br, "worktree": str(cur)})
            cur = None
    print(json.dumps(out, ensure_ascii=False))
    return EXIT_OK


def cmd_cancel(args: argparse.Namespace) -> int:
    root = _repo_root(Path.cwd())
    if root is None:
        _err("ERROR: git repository가 아닙니다.")

    slug = _slugify(args.slug)
    wt = root / ".worktree" / slug
    branch = _worktree_branch(root, wt) or f"feat-{slug}"
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

    print("worktree_setup: cancel 완료")
    if removed_worktree:
        print(f"- removed worktree: {wt}")
    if removed_branch:
        print(f"- deleted branch:   {branch}")
    return EXIT_OK


# ============================================================================
# CLI
# ============================================================================
def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="worktree_setup", description="forge-scope 워크트리 셋업 helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="검증 게이트 + 워크트리 + 링크 + 복사 + 상태 전이")
    pi.add_argument("--doc", required=True, help="approved Intent 문서 경로 (docs/<App>/INTENT/<ID>.md)")
    pi.add_argument("--name", default=None, help="slug 명시 (기본: Intent 문서 ID)")
    pi.add_argument("--force", action="store_true", help="메인 repo dirty 검사 우회")
    pi.add_argument("--quiet", action="store_true", help="진행 로그 억제 (JSON만)")
    pi.set_defaults(func=cmd_init)

    pl = sub.add_parser("list", help="forge 워크트리 나열 (JSON)")
    pl.set_defaults(func=cmd_list)

    pc = sub.add_parser("cancel", help="워크트리 + 브랜치 정리 (서브모듈 메인 원본 보존)")
    pc.add_argument("slug", help="docName/slug (워크트리 .worktree/<slug>)")
    pc.add_argument("--force", action="store_true", help="dirty 워크트리 강제 제거")
    pc.set_defaults(func=cmd_cancel)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
