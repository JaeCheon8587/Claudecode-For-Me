#!/usr/bin/env python3
"""hooks-setup: harness_framework hooks를 사용자 레포에 멱등 배치.

Usage:
    python scripts/hooks_setup.py [--dry-run | --apply | --rollback] [--yes] [--force]

Modes:
    --dry-run  (default) 변경 계획만 출력. 파일 미변경.
    --apply    실제 배치 + 백업 + state.json 기록.
    --rollback state.json 기반 역적용. 백업 복원 + 파일 제거 + git config 원복.

Flags:
    --yes      충돌 prompt를 모두 자동 skip (안전 기본).
    --force    충돌 prompt를 모두 자동 overwrite (위험).

환경변수:
    CLAUDE_PLUGIN_ROOT   templates/hooks_manifest.json 위치 추적용. 미설정 시 __file__ 기반.
    HOOKS_SETUP_DEBUG=1  상세 로그.
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import argparse
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEBUG = os.environ.get("HOOKS_SETUP_DEBUG") == "1"
EXIT_OK, EXIT_ERR, EXIT_ABORT = 0, 1, 2
MANIFEST_REL = "templates/hooks_manifest.json"
TEMPLATES_REL = "templates"
STATE_REL = ".hooks-setup/state.json"
BACKUP_DIR_REL = ".hooks-setup/backups"


def log(msg: str) -> None:
    print(msg, flush=True)


def dbg(msg: str) -> None:
    if DEBUG:
        print(f"[debug] {msg}", file=sys.stderr, flush=True)


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        p = Path(env).resolve()
        if (p / MANIFEST_REL).exists():
            return p
    fallback = Path(__file__).resolve().parent.parent
    if (fallback / MANIFEST_REL).exists():
        return fallback
    raise FileNotFoundError(
        f"templates/hooks_manifest.json 위치를 찾을 수 없음. CLAUDE_PLUGIN_ROOT={env!r}, fallback={fallback}"
    )


def load_manifest(plugin_root: Path) -> dict:
    with (plugin_root / MANIFEST_REL).open("r", encoding="utf-8") as f:
        return json.load(f)


def find_user_repo() -> Path:
    cwd = Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git 레포지토리가 아님 (cwd={cwd}). 'git init' 후 재실행 필요."
        )
    return Path(result.stdout.strip()).resolve()


@dataclass
class FileAction:
    kind: str  # write_file | append_fragment
    src: Path
    dst_rel: str
    executable: bool
    on_conflict: str
    conflict: str = "none"  # none | identical | differs | partial_fragment
    decision: str = "install"  # install | skip | overwrite | append
    fragment_marker: str | None = None


@dataclass
class GitConfigAction:
    kind: str = "git_config_set"
    key: str = ""
    value: str = ""
    scope: str = "local"
    previous: str | None = None
    on_conflict: str = "prompt"
    conflict: str = "none"
    decision: str = "install"


@dataclass
class PlannedRun:
    file_actions: list[FileAction] = field(default_factory=list)
    git_actions: list[GitConfigAction] = field(default_factory=list)


def get_git_config(repo: Path, key: str) -> str | None:
    r = subprocess.run(
        ["git", "config", "--local", "--get", key],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return r.stdout.strip() or None
    return None


def set_git_config(repo: Path, key: str, value: str) -> None:
    subprocess.run(
        ["git", "config", "--local", key, value],
        cwd=str(repo),
        check=True,
    )


def unset_git_config(repo: Path, key: str) -> None:
    subprocess.run(
        ["git", "config", "--local", "--unset", key],
        cwd=str(repo),
        capture_output=True,
    )


def plan(repo: Path, plugin_root: Path, manifest: dict) -> PlannedRun:
    run = PlannedRun()
    templates_root = plugin_root / TEMPLATES_REL

    for entry in manifest["files"]:
        src = templates_root / entry["src"]
        if not src.exists():
            raise FileNotFoundError(f"manifest source missing: {src}")
        dst = repo / entry["dst"]
        on_conflict = entry.get("on_conflict", "prompt")
        kind = "append_fragment" if on_conflict == "append_fragment" else "write_file"
        action = FileAction(
            kind=kind,
            src=src,
            dst_rel=entry["dst"],
            executable=entry.get("executable", False),
            on_conflict=on_conflict,
            fragment_marker=entry.get("fragment_marker"),
        )
        if not dst.exists():
            action.conflict = "none"
            action.decision = "install"
        else:
            existing = dst.read_bytes()
            new = src.read_bytes()
            if existing == new:
                action.conflict = "identical"
                action.decision = "skip"
            elif kind == "append_fragment" and action.fragment_marker and action.fragment_marker.encode("utf-8") in existing:
                action.conflict = "partial_fragment"
                action.decision = "skip"
            else:
                action.conflict = "differs"
                action.decision = "prompt"  # resolved at apply time
        run.file_actions.append(action)

    for post in manifest.get("post_install", []):
        if post.get("type") == "git_config":
            key = post["key"]
            value = post["value"]
            prev = get_git_config(repo, key)
            ga = GitConfigAction(
                key=key,
                value=value,
                scope=post.get("scope", "local"),
                previous=prev,
                on_conflict=post.get("on_conflict", "prompt"),
            )
            if prev is None:
                ga.conflict = "none"
                ga.decision = "install"
            elif prev == value:
                ga.conflict = "identical"
                ga.decision = "skip"
            else:
                ga.conflict = "differs"
                ga.decision = "prompt"
            run.git_actions.append(ga)
    return run


def print_plan(run: PlannedRun, repo: Path) -> None:
    log("")
    log(f"=== hooks-setup 계획 (repo: {repo}) ===")
    log("")
    log("[파일 배치]")
    for a in run.file_actions:
        marker = {
            "none": "+",
            "identical": "=",
            "differs": "!",
            "partial_fragment": "=",
        }.get(a.conflict, "?")
        log(f"  {marker} {a.dst_rel}  ({a.kind}, conflict={a.conflict}, decision={a.decision})")
    log("")
    log("[git config]")
    for ga in run.git_actions:
        marker = {"none": "+", "identical": "=", "differs": "!"}.get(ga.conflict, "?")
        log(f"  {marker} {ga.key} = {ga.value!r}  (previous={ga.previous!r}, decision={ga.decision})")
    log("")
    log("범례: + 신규설치  = 동일/건너뜀  ! 충돌(apply 시 결정)")
    log("")


def resolve_conflict_prompt(label: str, options: list[str], default: str, *, yes: bool, force: bool) -> str:
    if force:
        return "overwrite" if "overwrite" in options else default
    if yes:
        return default
    while True:
        prompt = f"[충돌] {label} — {'/'.join(options)} (default={default}): "
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            return default
        if not ans:
            return default
        for opt in options:
            if opt.startswith(ans) or ans == opt:
                return opt
        log(f"  '{ans}' 인식 안됨. 다시 입력.")


def make_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as e:
        dbg(f"chmod 실패 (무시): {path} {e}")


def atomic_write_bytes(dst: Path, data: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dst.name + ".", dir=str(dst.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def backup_file(repo: Path, dst_rel: str, stamp: str) -> str:
    src = repo / dst_rel
    backup_rel = f"{BACKUP_DIR_REL}/{dst_rel}.{stamp}.bak"
    backup_path = repo / backup_rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, backup_path)
    return backup_rel


def apply_run(
    repo: Path,
    plugin_root: Path,
    manifest: dict,
    run: PlannedRun,
    *,
    yes: bool,
    force: bool,
) -> dict:
    stamp = now_stamp()
    state = {
        "manifest_version": manifest["version"],
        "applied_at": stamp,
        "plugin_root": str(plugin_root),
        "actions": [],
    }

    for a in run.file_actions:
        if a.decision == "skip":
            log(f"  skip   {a.dst_rel}")
            continue

        if a.conflict == "differs":
            if a.kind == "append_fragment":
                a.decision = resolve_conflict_prompt(
                    f"{a.dst_rel} 존재 — fragment append",
                    ["append", "skip"],
                    "append",
                    yes=yes,
                    force=force,
                )
            else:
                a.decision = resolve_conflict_prompt(
                    f"{a.dst_rel} 존재, 내용 다름",
                    ["overwrite", "skip"],
                    "skip",
                    yes=yes,
                    force=force,
                )

        if a.decision == "skip":
            log(f"  skip   {a.dst_rel}")
            continue

        dst = repo / a.dst_rel
        backup_rel = None

        new_data = a.src.read_bytes()

        if a.kind == "append_fragment":
            if dst.exists():
                backup_rel = backup_file(repo, a.dst_rel, stamp)
                existing = dst.read_bytes()
                sep = b"" if existing.endswith(b"\n") else b"\n"
                merged = existing + sep + new_data
                atomic_write_bytes(dst, merged)
            else:
                atomic_write_bytes(dst, new_data)
            log(f"  {'append ' if backup_rel else 'create '} {a.dst_rel}")
        else:
            if dst.exists():
                backup_rel = backup_file(repo, a.dst_rel, stamp)
            atomic_write_bytes(dst, new_data)
            if a.executable:
                make_executable(dst)
            log(f"  {'overwrite' if backup_rel else 'create   '} {a.dst_rel}")

        state["actions"].append({
            "kind": a.kind,
            "path": a.dst_rel,
            "backup": backup_rel,
            "executable": a.executable,
            "existed_before": backup_rel is not None,
            "fragment_marker": a.fragment_marker,
        })

    for ga in run.git_actions:
        if ga.decision == "skip":
            log(f"  skip   git config {ga.key}")
            continue
        if ga.conflict == "differs":
            ga.decision = resolve_conflict_prompt(
                f"git config {ga.key} 기존={ga.previous!r} 신규={ga.value!r}",
                ["overwrite", "skip"],
                "skip",
                yes=yes,
                force=force,
            )
            if ga.decision == "skip":
                log(f"  skip   git config {ga.key}")
                continue
        set_git_config(repo, ga.key, ga.value)
        log(f"  set    git config {ga.key} = {ga.value}")
        state["actions"].append({
            "kind": "git_config_set",
            "key": ga.key,
            "value": ga.value,
            "previous": ga.previous,
            "scope": ga.scope,
        })

    state_path = repo / STATE_REL
    state_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(state_path, json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8"))
    log("")
    log(f"state 저장: {state_path}")
    log("다음 단계: bash tools/install-hooks.sh  (prerequisite 점검 + chmod +x)")
    return state


def rollback(repo: Path) -> int:
    state_path = repo / STATE_REL
    if not state_path.exists():
        log(f"state 없음: {state_path} — 롤백 불가")
        return EXIT_ERR

    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    log(f"=== 롤백 (manifest_version={state.get('manifest_version')}) ===")
    actions = list(reversed(state.get("actions", [])))
    errors = 0

    for act in actions:
        kind = act.get("kind")
        if kind == "write_file" or kind == "append_fragment":
            path = repo / act["path"]
            backup_rel = act.get("backup")
            if backup_rel:
                backup_path = repo / backup_rel
                if backup_path.exists():
                    shutil.copy2(backup_path, path)
                    log(f"  restore {act['path']}  <- {backup_rel}")
                else:
                    log(f"  warn   backup missing: {backup_rel}")
                    errors += 1
            else:
                if path.exists():
                    try:
                        path.unlink()
                        log(f"  remove  {act['path']}")
                    except OSError as e:
                        log(f"  warn   unlink 실패: {act['path']} {e}")
                        errors += 1
        elif kind == "git_config_set":
            key = act["key"]
            prev = act.get("previous")
            if prev is None:
                unset_git_config(repo, key)
                log(f"  unset  git config {key}")
            else:
                set_git_config(repo, key, prev)
                log(f"  reset  git config {key} = {prev}")

    backup_root = repo / BACKUP_DIR_REL
    try:
        state_path.unlink()
        log(f"  remove {STATE_REL}")
    except OSError:
        pass
    if backup_root.exists():
        log(f"  hint   백업 보존: {BACKUP_DIR_REL}/ (수동 정리 가능)")

    if errors:
        log(f"롤백 완료 (경고 {errors}건)")
        return EXIT_ERR
    log("롤백 완료")
    return EXIT_OK


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="hooks_setup.py", description="harness_framework hooks 배치")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="mode", action="store_const", const="dry-run")
    mode.add_argument("--apply", dest="mode", action="store_const", const="apply")
    mode.add_argument("--rollback", dest="mode", action="store_const", const="rollback")
    p.set_defaults(mode="dry-run")
    p.add_argument("--yes", action="store_true", help="충돌 시 자동 skip")
    p.add_argument("--force", action="store_true", help="충돌 시 자동 overwrite (위험)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.yes and args.force:
        log("error: --yes 와 --force 동시 사용 불가")
        return EXIT_ERR

    try:
        plugin_root = resolve_plugin_root()
        manifest = load_manifest(plugin_root)
        repo = find_user_repo()
    except (FileNotFoundError, RuntimeError) as e:
        log(f"error: {e}")
        return EXIT_ERR

    log(f"plugin_root: {plugin_root}")
    log(f"manifest    : v{manifest['version']}")
    log(f"user_repo   : {repo}")

    if args.mode == "rollback":
        return rollback(repo)

    run = plan(repo, plugin_root, manifest)
    print_plan(run, repo)

    if args.mode == "dry-run":
        log("dry-run 모드 — 변경 없음. 실제 배치는 --apply 로 재실행.")
        return EXIT_OK

    log("=== 배치 시작 ===")
    apply_run(repo, plugin_root, manifest, run, yes=args.yes, force=args.force)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
