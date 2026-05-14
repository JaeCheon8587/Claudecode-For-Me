#!/usr/bin/env python3
"""
Hooks Setup — harness_framework tools/ 12개 파일을 사용자 프로젝트에 적응 배치한다.

Usage:
    python scripts/hooks_setup.py [--trust] [--yes] [--quiet]

Guard: FORGE_TRUST=1 or --trust 없으면 즉시 종료.
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
EXIT_OK, EXIT_ERR, EXIT_BLOCKED = 0, 1, 2

HOOKS: list[tuple[str, str]] = [
    ("Hooks.md", "doc"),
    ("ruff.toml", "config"),
    ("requirements-dev.txt", "config"),
    ("install-hooks.sh", "installer"),
    ("tools/hooks/pre-commit", "git-hook"),
    ("tools/hooks/pre-push", "git-hook"),
    ("tools/quality/secret-scan.sh", "quality"),
    ("tools/quality/lint.sh", "quality"),
    ("tools/quality/build.sh", "quality"),
    ("tools/quality/test.sh", "quality"),
    ("tools/quality/dependency-check.sh", "quality"),
    ("tools/quality/dependency_check.py", "quality"),
]

STATE_SCHEMA = 1
GLOBAL_TIMEOUT = 7200
PER_HOOK_TIMEOUT = 600


# ── 데이터 모델 ────────────────────────────────────────────────


@dataclass
class HookState:
    status: str = "pending"
    ts: str = ""
    error: str = ""


@dataclass
class SetupState:
    schema: int = STATE_SCHEMA
    started_at: str = ""
    items: dict[str, HookState] = field(default_factory=dict)


# ── 상태 직렬화 ────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(state_path: Path) -> SetupState:
    if not state_path.exists():
        return SetupState(started_at=_now_iso())
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if raw.get("schema") != STATE_SCHEMA:
            raise ValueError(f"schema mismatch: {raw.get('schema')}")
        items = {
            k: HookState(**v) if isinstance(v, dict) else HookState()
            for k, v in raw.get("items", {}).items()
        }
        return SetupState(
            schema=STATE_SCHEMA,
            started_at=raw.get("started_at", _now_iso()),
            items=items,
        )
    except Exception as exc:
        backup = state_path.with_suffix(".bak.json")
        state_path.rename(backup)
        print(f"[hooks-setup] state.json schema 오류 — 백업: {backup} ({exc})", file=sys.stderr)
        return SetupState(started_at=_now_iso())


def save_state(state_path: Path, state: SetupState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    raw: dict = {
        "schema": state.schema,
        "started_at": state.started_at,
        "items": {k: asdict(v) for k, v in state.items.items()},
    }
    state_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── 프로젝트 컨텍스트 수집 ──────────────────────────────────────


def collect_ctx(repo_root: Path) -> dict:
    ctx: dict = {
        "git_root": str(repo_root),
        "sln_files": [],
        "csproj_files": [],
        "scripts_py": [],
        "has_pyproject": False,
        "requirements_txt": [],
        "forge_scripts": [],
        "has_dotnet": False,
        "has_python": False,
    }

    ctx["sln_files"] = [str(p.relative_to(repo_root)) for p in repo_root.rglob("*.sln")]
    ctx["csproj_files"] = [str(p.relative_to(repo_root)) for p in repo_root.rglob("*.csproj")]
    ctx["has_dotnet"] = bool(ctx["sln_files"] or ctx["csproj_files"])

    scripts_dir = repo_root / "scripts"
    if scripts_dir.is_dir():
        ctx["scripts_py"] = [str(p.relative_to(repo_root)) for p in scripts_dir.glob("*.py")]
        ctx["forge_scripts"] = [str(p.relative_to(repo_root)) for p in scripts_dir.glob("forge_*.py")]

    ctx["has_pyproject"] = (repo_root / "pyproject.toml").exists()
    ctx["requirements_txt"] = [
        str(p.relative_to(repo_root)) for p in repo_root.glob("requirements*.txt")
    ]
    ctx["has_python"] = bool(
        ctx["scripts_py"] or ctx["has_pyproject"] or ctx["requirements_txt"]
    )

    return ctx


# ── プロンプト 빌더 ────────────────────────────────────────────


def build_prompt(target: str, role: str, template_text: str, ctx: dict) -> str:
    ctx_json = json.dumps(ctx, indent=2, ensure_ascii=False)
    return f"""\
You are setting up ONE file in the user's repository.

File path (target, relative to repo root): {target}
File role: {role}
Template content (harness_framework reference):
<<<TEMPLATE
{template_text}
TEMPLATE>>>

Project context (auto-detected JSON):
{ctx_json}

Task:
1. Adapt the template to this project. Replace hard-coded paths
   (e.g. Src/OrderManagingSystem.sln, scripts/forge_*.py, OrderManagingSystem host patterns)
   with the actual paths found in project context.
   If a language runtime (dotnet/python) is absent in ctx, remove the corresponding
   section but keep the file structurally valid (use early "exit 0" for shell scripts,
   keep module-level code intact for Python files).
   If BOTH dotnet and python are absent, remove both blocks; keep the file skeleton only.
2. Write the adapted content to {target} (create parent directories as needed).
3. Preserve the standard 3-line FAIL output format unchanged:
     FAIL: <check>
     target: <path>
     next: <cmd>
4. Preserve secret-scan and dependency-check skip-prohibition policy unchanged.
   Do NOT add any bypass or skip logic for these checks.
5. Do NOT modify other files. Do NOT run git commands.
6. After writing, print EXACTLY on its own line: SETUP_OK {target}
"""


# ── Claude subprocess 호출 ────────────────────────────────────


def _is_nested_under_claude() -> bool:
    for var in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_PROJECT_DIR"):
        if os.environ.get(var):
            return True
    if os.environ.get("AI_AGENT", "").startswith("claude-code"):
        return True
    return False


def invoke_claude(prompt: str, cwd: Path, timeout: int = PER_HOOK_TIMEOUT) -> tuple[int, str]:
    cmd = ["claude", "-p"]
    if not _is_nested_under_claude():
        cmd.append("--dangerously-skip-permissions")
    cmd += ["--output-format", "stream-json", "--max-turns", "8", "--quiet", "--yes"]

    try:
        result = subprocess.run(
            cmd + [prompt],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        combined = result.stdout + result.stderr
        return result.returncode, combined
    except FileNotFoundError:
        print(
            "FAIL: env\ntarget: claude (PATH 부재)\n"
            "next: Claude Code CLI 설치 후 PATH 등록",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERR)
    except subprocess.TimeoutExpired as exc:
        partial = ""
        if exc.stdout:
            partial = exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", errors="replace")
        return 124, partial


# ── 파일 검증 ─────────────────────────────────────────────────


def verify(target_path: Path) -> tuple[bool, str]:
    if not target_path.exists():
        return False, f"파일 없음: {target_path}"

    name = target_path.name
    suffix = target_path.suffix

    if suffix == ".sh" or (not suffix and not name.endswith(".py") and not name.endswith(".md") and not name.endswith(".txt") and not name.endswith(".toml")):
        # shell 스크립트 syntax check
        try:
            result = subprocess.run(
                ["bash", "-n", str(target_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode != 0:
                return False, f"bash -n 실패: {result.stderr.strip()}"
        except FileNotFoundError:
            pass  # bash 없는 환경(Windows CMD) — 검증 skip
    elif suffix == ".py":
        py_cmd = "python" if _which("python") else "python3"
        try:
            result = subprocess.run(
                [py_cmd, "-m", "py_compile", str(target_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode != 0:
                return False, f"py_compile 실패: {result.stderr.strip()}"
        except FileNotFoundError:
            pass

    return True, ""


def _which(cmd: str) -> bool:
    import shutil
    return shutil.which(cmd) is not None


# ── 단일 hook 처리 ────────────────────────────────────────────


def process_hook(
    target: str,
    role: str,
    ctx: dict,
    templates_dir: Path,
    repo_root: Path,
    quiet: bool = False,
) -> HookState:
    template_path = templates_dir / target
    if not template_path.exists():
        return HookState(status="error", ts=_now_iso(), error=f"템플릿 없음: {template_path}")

    template_text = template_path.read_text(encoding="utf-8", errors="replace")
    prompt = build_prompt(target, role, template_text, ctx)

    if not quiet:
        print(f"[hooks-setup] → {target} ({role})")

    rc, output = invoke_claude(prompt, repo_root)

    if rc == 124:
        return HookState(status="error", ts=_now_iso(), error=f"timeout ({PER_HOOK_TIMEOUT}s)")

    if f"SETUP_OK {target}" not in output:
        snippet = output[-300:] if len(output) > 300 else output
        return HookState(status="error", ts=_now_iso(), error=f"SETUP_OK {target} 없음. 출력 끝: {snippet!r}")

    target_path = repo_root / target
    ok, msg = verify(target_path)
    if not ok:
        return HookState(status="error", ts=_now_iso(), error=f"검증 실패: {msg}")

    if not quiet:
        print(f"[hooks-setup] ✓ {target}")
    return HookState(status="completed", ts=_now_iso())


# ── 안전 가드 ─────────────────────────────────────────────────


def trust_guard(args: argparse.Namespace) -> None:
    trust_env = os.environ.get("FORGE_TRUST", "").strip().lower()
    trusted = args.trust or trust_env in ("1", "true", "yes")
    if not trusted:
        print(
            "[hooks-setup] FORGE_TRUST=1 또는 --trust 없이 실행하면 종료합니다.\n"
            "  실행 예: FORGE_TRUST=1 python scripts/hooks_setup.py --yes --quiet\n"
            "  또는:   python scripts/hooks_setup.py --trust --yes --quiet\n"
            "  주의: FORGE_TRUST를 셸 rc 파일 등에 영구 설정하지 마세요.",
            file=sys.stderr,
        )
        sys.exit(EXIT_BLOCKED)


# ── 진입점 ────────────────────────────────────────────────────


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="harness_framework hooks 12개를 사용자 프로젝트에 적응 배치한다."
    )
    parser.add_argument("--trust", action="store_true", help="--dangerously-skip-permissions 옵트인 (또는 FORGE_TRUST=1)")
    parser.add_argument("--yes", action="store_true", help="확인 프롬프트 자동 승인")
    parser.add_argument("--quiet", action="store_true", help="진행 표시기 억제")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    trust_guard(args)

    # git repo root 감지
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path.cwd()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            repo_root = Path(result.stdout.strip())
        else:
            print("[hooks-setup] WARN: git repo 아님 — cwd를 root로 사용", file=sys.stderr)
            repo_root = Path.cwd()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("[hooks-setup] WARN: git 명령 실패 — cwd를 root로 사용", file=sys.stderr)
        repo_root = Path.cwd()

    # 템플릿 디렉토리 결정 (SKILL이 .hooks_setup_staging/ 로 복사)
    staging_templates = repo_root / ".hooks_setup_staging" / "templates" / "hooks"
    plugin_templates = ROOT / "templates" / "hooks"
    if staging_templates.exists():
        templates_dir = staging_templates
    elif plugin_templates.exists():
        templates_dir = plugin_templates
    else:
        print(
            f"FAIL: env\ntarget: templates/hooks/ (없음)\nnext: {staging_templates} 또는 {plugin_templates} 확인",
            file=sys.stderr,
        )
        return EXIT_ERR

    # 상태 파일
    state_path = repo_root / "phases" / "hooks-setup" / "state.json"
    state = load_state(state_path)

    ctx = collect_ctx(repo_root)
    if not args.quiet:
        has_dn = ctx["has_dotnet"]
        has_py = ctx["has_python"]
        print(f"[hooks-setup] 프로젝트 컨텍스트: dotnet={has_dn}, python={has_py}")

    import time
    global_start = time.time()

    errors: list[str] = []
    for target, role in HOOKS:
        if time.time() - global_start > GLOBAL_TIMEOUT:
            print("[hooks-setup] WARN: 전체 타임아웃 초과 — 중단", file=sys.stderr)
            break

        current = state.items.get(target, HookState())
        if current.status == "completed":
            if not args.quiet:
                print(f"[hooks-setup] SKIP (completed): {target}")
            continue

        hook_state = process_hook(target, role, ctx, templates_dir, repo_root, quiet=args.quiet)
        state.items[target] = hook_state
        save_state(state_path, state)

        if hook_state.status == "error":
            errors.append(f"{target}: {hook_state.error}")
            print(f"[hooks-setup] WARN: {target} 실패 — 계속 진행", file=sys.stderr)

    completed = sum(1 for v in state.items.values() if v.status == "completed")
    total = len(HOOKS)
    print(f"\n[hooks-setup] 완료: {completed}/{total}")

    if errors:
        print(f"[hooks-setup] 실패 {len(errors)}건:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"\n[hooks-setup] state.json: {state_path}", file=sys.stderr)
        print("[hooks-setup] 실패 항목은 재실행 시 자동 재시도됩니다.", file=sys.stderr)
        return EXIT_ERR

    print(f"[hooks-setup] state.json: {state_path}")
    print("[hooks-setup] 모든 파일 적응 완료.")
    print("[hooks-setup] install-hooks.sh 실행을 원하면 'bash tools/install-hooks.sh' 를 직접 실행하세요.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
