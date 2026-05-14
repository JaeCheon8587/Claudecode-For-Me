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


def _detect_kind(phase: str, requested: Optional[str]) -> str:
    if requested:
        if requested not in VALID_KINDS:
            _err(f"알 수 없는 kind입니다: {requested}")
        return requested

    found = [kind for kind in sorted(VALID_KINDS) if _phase_path(kind, phase).exists()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        _err("--kind full 또는 --kind scoped 중 하나를 명시하세요. 양쪽에 phase가 있습니다.")
    _err(f"phase 산출물을 찾을 수 없습니다: phases/full|scoped/{phase}")


def _branch_exists(branch: str) -> bool:
    return _git(["rev-parse", "--verify", "--quiet", branch], check=False).returncode == 0


def _current_branch() -> str:
    result = _git(["branch", "--show-current"])
    return result.stdout.strip()


def _worktree_dirty() -> bool:
    result = _git(["status", "--porcelain"])
    return bool(result.stdout.strip())


def _select_base(preferred: Optional[str]) -> str:
    candidates = [preferred] if preferred else ["master", "main"]
    for branch in candidates:
        if branch and _branch_exists(branch):
            return branch
    _err("--base를 명시하세요. master/main 브랜치를 찾을 수 없습니다.")


def _delete_phase_dir(path: Path) -> None:
    resolved = path.resolve()
    phases_root = (ROOT / "phases").resolve()
    if phases_root not in resolved.parents:
        _err(f"phase 디렉토리가 phases/ 밖을 가리킵니다: {path}")
    shutil.rmtree(resolved)


def _update_top_index(kind: str, phase: str) -> bool:
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


def _summarize(branch: str, base: str, phase_path: Path) -> None:
    print("Forge cancel target")
    print(f"- branch: {branch}")
    print(f"- base: {base}")
    print(f"- phase dir: {phase_path.relative_to(ROOT).as_posix()}")
    count = _git(["rev-list", "--count", f"{base}..{branch}"], check=False)
    if count.returncode == 0:
        print(f"- commits to drop: {count.stdout.strip()}")


def cancel(args: argparse.Namespace) -> int:
    _validate_phase_name(args.phase_dir)
    kind = _detect_kind(args.phase_dir, args.kind)
    branch = f"feat-{args.phase_dir}"
    phase_path = _phase_path(kind, args.phase_dir)
    base = _select_base(args.base)

    if not _branch_exists(branch):
        _err(f"취소 대상 브랜치를 찾을 수 없습니다: {branch}")

    current = _current_branch()
    dirty = _worktree_dirty()
    if dirty and current != branch:
        _err("현재 작업 트리가 dirty이고 취소 대상 브랜치가 아닙니다. 사용자 변경 보호를 위해 중단합니다.")

    _summarize(branch, base, phase_path)
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
    removed_from_index = _update_top_index(kind, args.phase_dir)

    print("Forge cancel completed")
    print(f"- deleted branch: {branch}")
    print(f"- deleted phase dir: {phase_path.relative_to(ROOT).as_posix()}")
    if removed_from_index:
        print(f"- updated top index: phases/{kind}/index.json")
    return EXIT_OK


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
