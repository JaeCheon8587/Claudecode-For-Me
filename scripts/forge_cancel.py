#!/usr/bin/env python3
"""
Forge Cancel — forge-full/forge-scope 작업 산출물을 폐기한다.

Usage:
    python scripts/forge_cancel.py <phase-dir> [--kind full|scoped] [--base master] [--yes]
    python scripts/forge_cancel.py <phase-dir> --dry-run
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
PHASE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VALID_KINDS = frozenset({"full", "scoped"})
EXIT_OK, EXIT_ERR = 0, 1


def _err(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(EXIT_ERR)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["git", *args], check=check)


def _validate_phase_name(name: str) -> None:
    if not name or name in {".", ".."}:
        _err("phase-dir가 비어 있거나 안전하지 않습니다.")
    if "/" in name or "\\" in name:
        _err("phase-dir에는 경로 구분자를 사용할 수 없습니다.")
    if not PHASE_NAME_RE.match(name):
        _err(f"phase-dir 이름이 허용되지 않는 형식입니다: {name}")


def _phase_path(kind: str, phase: str) -> Path:
    return ROOT / "phases" / kind / phase


def _branch_exists(branch: str) -> bool:
    return _git(["rev-parse", "--verify", "--quiet", branch], check=False).returncode == 0


def _current_branch() -> str:
    result = _git(["branch", "--show-current"])
    return result.stdout.strip()


def _main_dirty() -> bool:
    result = _git(["status", "--porcelain"])
    return bool(result.stdout.strip())


def _worktree_path(phase: str) -> Path:
    return ROOT / ".worktrees" / phase


def _registered_worktree_path(branch: str) -> Optional[Path]:
    result = _git(["worktree", "list", "--porcelain"], check=False)
    if result.returncode != 0:
        return None
    current_path: Optional[Path] = None
    target_ref = f"refs/heads/{branch}"
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree ") :])
        elif line.startswith("branch ") and current_path is not None:
            if line[len("branch ") :].strip() == target_ref:
                return current_path
    return None


def _worktree_dirty(worktree: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return bool(result.stdout.strip())


def _delete_phase_dir(path: Path) -> None:
    """scoped 워크트리화 이후에는 호출되지 않는다 (full kind 폴백 전용)."""
    resolved = path.resolve()
    phases_root = (ROOT / "phases").resolve()
    if phases_root not in resolved.parents:
        _err(f"phase 디렉토리가 phases/ 밖을 가리킵니다: {path}")
    shutil.rmtree(resolved)


def _update_top_index(kind: str, phase: str) -> bool:
    """full kind 폴백 전용. scoped는 워크트리 제거로 자동 소멸한다."""
    top_index = ROOT / "phases" / kind / "index.json"
    if not top_index.exists():
        return False
    data = json.loads(top_index.read_text(encoding="utf-8"))
    phases = data.get("phases")
    if not isinstance(phases, list):
        return False
    next_phases = [item for item in phases if item.get("dir") != phase]
    if len(next_phases) == len(phases):
        return False
    data["phases"] = next_phases
    top_index.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _summarize_scoped(branch: str, worktree: Optional[Path]) -> None:
    print("Forge cancel target (scoped/worktree)")
    print(f"- branch: {branch}")
    if worktree is not None:
        print(f"- worktree: {worktree}")
    else:
        print("- worktree: (없음 — 브랜치만 정리)")
    count = _git(["rev-list", "--count", branch], check=False)
    if count.returncode == 0:
        print(f"- commits on branch: {count.stdout.strip()}")


def _cancel_scoped_inplace(args: argparse.Namespace, scoped_dir: Path) -> int:
    """--no-worktree 로 생성된 in-place scoped 산출물 정리.

    브랜치·워크트리가 없고 phases/scoped/<phase>/ 가 메인 repo에 직접 존재하는 경우.
    디렉토리 삭제 + phases/scoped/index.json 항목 제거만 수행한다 (브랜치 정리 없음).
    동명 feat-<phase> 브랜치가 별도로 존재하지 않는다고 가정한다 (존재 시 _cancel_scoped
    의 일반 경로로 라우팅됨).
    """
    print("Forge cancel target (scoped/in-place, no worktree)")
    print(f"- phase dir: {scoped_dir.relative_to(ROOT).as_posix()}")
    if args.dry_run:
        print("dry-run: 변경하지 않았습니다.")
        return EXIT_OK
    if not args.yes:
        _err("실제 삭제에는 --yes가 필요합니다.")
    _delete_phase_dir(scoped_dir)
    removed_from_index = _update_top_index("scoped", args.phase_dir)
    print("Forge cancel completed")
    print(f"- deleted phase dir: {scoped_dir.relative_to(ROOT).as_posix()}")
    if removed_from_index:
        print("- updated top index: phases/scoped/index.json")
    return EXIT_OK


def _cancel_scoped(args: argparse.Namespace) -> int:
    branch = f"feat-{args.phase_dir}"
    worktree = _worktree_path(args.phase_dir)
    registered = _registered_worktree_path(branch)

    # stale 워크트리 정리 (등록됐는데 디렉토리 없음)
    if registered is not None and not registered.exists():
        _git(["worktree", "prune"], check=False)
        registered = _registered_worktree_path(branch)

    branch_exists = _branch_exists(branch)
    if not branch_exists and registered is None and not worktree.exists():
        scoped_dir = _phase_path("scoped", args.phase_dir)
        if scoped_dir.exists():
            return _cancel_scoped_inplace(args, scoped_dir)
        _err(f"취소 대상이 없습니다: branch={branch}, worktree={worktree}")

    cwd_real = Path.cwd().resolve()
    if registered is not None:
        wt_real = registered.resolve()
        if cwd_real == wt_real or wt_real in cwd_real.parents:
            _err(
                "현재 cwd가 제거 대상 워크트리 내부입니다. 메인 repo로 이동 후 다시 실행하세요:\n"
                f"  cd {ROOT}"
            )

    _summarize_scoped(branch, registered or (worktree if worktree.exists() else None))
    if args.dry_run:
        print("dry-run: 변경하지 않았습니다.")
        return EXIT_OK
    if not args.yes:
        _err("실제 삭제에는 --yes가 필요합니다.")

    removed_worktree = False
    if registered is not None or worktree.exists():
        target = registered if registered is not None else worktree
        dirty = registered is not None and _worktree_dirty(registered)
        if (target / ".gitmodules").exists():
            subprocess.run(
                ["git", "submodule", "deinit", "-f", "--all"],
                cwd=target, capture_output=True, text=True,
            )
        cmd = ["worktree", "remove"]
        if dirty:
            cmd.append("--force")
        cmd.append(str(target))
        result = _git(cmd, check=False)
        if result.returncode != 0:
            _err(f"git worktree remove 실패: {result.stderr.strip()}")
        removed_worktree = True
        if worktree.exists():
            # git worktree remove가 .worktrees/<phase>/를 지우지 못한 케이스 (admin·perm).
            shutil.rmtree(worktree, ignore_errors=True)

    removed_branch = False
    if _branch_exists(branch):
        result = _git(["branch", "-D", branch], check=False)
        if result.returncode != 0:
            _err(f"git branch -D 실패: {result.stderr.strip()}")
        removed_branch = True

    print("Forge cancel completed")
    if removed_worktree:
        print(f"- removed worktree: {worktree.relative_to(ROOT).as_posix()}")
    if removed_branch:
        print(f"- deleted branch: {branch}")
    return EXIT_OK


def _cancel_full_legacy(args: argparse.Namespace) -> int:
    """forge-full(in-place 브랜치 모드) 폴백 — 기존 동작 그대로."""
    branch = f"feat-{args.phase_dir}"
    phase_path = _phase_path("full", args.phase_dir)

    candidates = [args.base] if args.base else ["master", "main"]
    base = next((b for b in candidates if b and _branch_exists(b)), None)
    if base is None:
        _err("--base를 명시하세요. master/main 브랜치를 찾을 수 없습니다.")

    if not _branch_exists(branch):
        _err(f"취소 대상 브랜치를 찾을 수 없습니다: {branch}")

    current = _current_branch()
    dirty = _main_dirty()
    if dirty and current != branch:
        _err("현재 작업 트리가 dirty이고 취소 대상 브랜치가 아닙니다. 사용자 변경 보호를 위해 중단합니다.")

    print("Forge cancel target (full/in-place)")
    print(f"- branch: {branch}")
    print(f"- base: {base}")
    print(f"- phase dir: {phase_path.relative_to(ROOT).as_posix()}")
    count = _git(["rev-list", "--count", f"{base}..{branch}"], check=False)
    if count.returncode == 0:
        print(f"- commits to drop: {count.stdout.strip()}")

    if args.dry_run:
        print("dry-run: 변경하지 않았습니다.")
        return EXIT_OK
    if not args.yes:
        _err("실제 삭제에는 --yes가 필요합니다.")

    if current == branch:
        if dirty:
            _git(["reset", "--hard", "HEAD"])
            _git(["clean", "-fd"])
        _git(["checkout", base])

    _git(["branch", "-D", branch])
    if phase_path.exists():
        _delete_phase_dir(phase_path)
    removed_from_index = _update_top_index("full", args.phase_dir)

    print("Forge cancel completed")
    print(f"- deleted branch: {branch}")
    print(f"- deleted phase dir: {phase_path.relative_to(ROOT).as_posix()}")
    if removed_from_index:
        print("- updated top index: phases/full/index.json")
    return EXIT_OK


def cancel(args: argparse.Namespace) -> int:
    _validate_phase_name(args.phase_dir)
    kind = _detect_kind_for_cancel(args.phase_dir, args.kind)
    if kind == "scoped":
        return _cancel_scoped(args)
    return _cancel_full_legacy(args)


def _detect_kind_for_cancel(phase: str, requested: Optional[str]) -> str:
    """워크트리 컨텍스트에서 kind를 추론한다.

    scoped는 phases 디렉토리가 워크트리 안에만 있으므로 메인 repo의 _phase_path()는
    신뢰할 수 없다. branch 존재 + 워크트리/.worktrees 디렉토리 흔적이 보이면 scoped로 판정.
    """
    if requested:
        if requested not in VALID_KINDS:
            _err(f"알 수 없는 kind입니다: {requested}")
        return requested

    branch = f"feat-{phase}"
    has_worktree = _registered_worktree_path(branch) is not None or _worktree_path(phase).exists()
    has_full_dir = _phase_path("full", phase).exists()
    has_scoped_dir = _phase_path("scoped", phase).exists()

    if has_worktree:
        return "scoped"
    if has_full_dir and not has_scoped_dir:
        return "full"
    if has_scoped_dir and not has_full_dir:
        return "scoped"
    if has_full_dir and has_scoped_dir:
        _err("--kind full 또는 --kind scoped 중 하나를 명시하세요. 양쪽에 phase가 있습니다.")
    if _branch_exists(branch):
        # 브랜치만 있고 디렉토리·워크트리 흔적 없음 → scoped 후처리(브랜치 정리)
        return "scoped"
    _err(f"phase 산출물을 찾을 수 없습니다: branch={branch}, .worktrees/{phase}, phases/full|scoped/{phase}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cancel a Forge phase and delete its branch/artifacts.")
    parser.add_argument("phase_dir", help="phase directory name, e.g. login-feature")
    parser.add_argument("--kind", choices=sorted(VALID_KINDS), help="phase namespace. Inferred when unique.")
    parser.add_argument(
        "--base", help="branch to checkout before deleting the forge branch. Default: master, then main."
    )
    parser.add_argument("--yes", action="store_true", help="perform destructive deletion")
    parser.add_argument("--dry-run", action="store_true", help="show target only")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    return cancel(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
