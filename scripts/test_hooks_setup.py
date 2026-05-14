#!/usr/bin/env python3
"""
hooks_setup.py 단위 + 통합 테스트.

실행: pytest scripts/test_hooks_setup.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ 를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hooks_setup import (
    HOOKS,
    STATE_SCHEMA,
    HookState,
    SetupState,
    build_prompt,
    collect_ctx,
    load_state,
    process_hook,
    save_state,
    trust_guard,
    verify,
)


# ── 단위: HOOKS 무결성 ─────────────────────────────────────────


def test_hooks_list_count():
    assert len(HOOKS) == 12


def test_hooks_no_duplicates():
    paths = [h[0] for h in HOOKS]
    assert len(paths) == len(set(paths))


def test_hooks_valid_roles():
    valid_roles = {"doc", "config", "installer", "git-hook", "quality"}
    for path, role in HOOKS:
        assert role in valid_roles, f"{path} has unexpected role: {role}"


def test_hooks_order_starts_with_docs():
    assert HOOKS[0] == ("Hooks.md", "doc")


def test_hooks_ends_with_dependency_check_py():
    assert HOOKS[-1] == ("tools/quality/dependency_check.py", "quality")


# ── 단위: 상태 직렬화 round-trip ──────────────────────────────


def test_state_roundtrip(tmp_path):
    state_path = tmp_path / "state.json"
    state = SetupState(
        started_at="2026-01-01T00:00:00+00:00",
        items={
            "Hooks.md": HookState(status="completed", ts="2026-01-01T00:01:00+00:00"),
            "ruff.toml": HookState(status="pending"),
        },
    )
    save_state(state_path, state)
    loaded = load_state(state_path)

    assert loaded.schema == STATE_SCHEMA
    assert loaded.started_at == "2026-01-01T00:00:00+00:00"
    assert loaded.items["Hooks.md"].status == "completed"
    assert loaded.items["ruff.toml"].status == "pending"


def test_load_state_missing(tmp_path):
    state_path = tmp_path / "nonexistent.json"
    state = load_state(state_path)
    assert state.schema == STATE_SCHEMA
    assert state.started_at != ""
    assert state.items == {}


def test_load_state_schema_mismatch_creates_backup(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"schema": 99, "items": {}}), encoding="utf-8")
    state = load_state(state_path)
    assert state.schema == STATE_SCHEMA
    backup = tmp_path / "state.bak.json"
    assert backup.exists()


# ── 단위: build_prompt ─────────────────────────────────────────


def test_build_prompt_contains_target():
    ctx = {"has_dotnet": False, "has_python": True}
    prompt = build_prompt("tools/hooks/pre-commit", "git-hook", "#!/bin/bash\necho hi", ctx)
    assert "tools/hooks/pre-commit" in prompt
    assert "git-hook" in prompt
    assert "SETUP_OK tools/hooks/pre-commit" in prompt


def test_build_prompt_contains_template():
    ctx = {}
    template = "#!/bin/bash\nSLN='Src/OrderManagingSystem.sln'"
    prompt = build_prompt("tools/quality/lint.sh", "quality", template, ctx)
    assert template in prompt


def test_build_prompt_contains_ctx_json():
    ctx = {"has_dotnet": True, "sln_files": ["MySolution.sln"]}
    prompt = build_prompt("Hooks.md", "doc", "content", ctx)
    assert "MySolution.sln" in prompt


def test_build_prompt_preserves_policy_wording():
    ctx = {}
    prompt = build_prompt("tools/quality/secret-scan.sh", "quality", "", ctx)
    assert "secret-scan" in prompt
    assert "dependency-check" in prompt
    assert "skip" in prompt.lower()


# ── 단위: collect_ctx ─────────────────────────────────────────


def test_collect_ctx_empty_dir(tmp_path):
    ctx = collect_ctx(tmp_path)
    assert ctx["sln_files"] == []
    assert ctx["csproj_files"] == []
    assert ctx["has_dotnet"] is False
    assert ctx["has_python"] is False


def test_collect_ctx_with_sln(tmp_path):
    sln = tmp_path / "MyApp.sln"
    sln.write_text("", encoding="utf-8")
    ctx = collect_ctx(tmp_path)
    assert "MyApp.sln" in ctx["sln_files"]
    assert ctx["has_dotnet"] is True


def test_collect_ctx_with_python(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "main.py").write_text("", encoding="utf-8")
    ctx = collect_ctx(tmp_path)
    assert ctx["has_python"] is True
    assert any("main.py" in p for p in ctx["scripts_py"])


def test_collect_ctx_forge_scripts(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "forge_scope.py").write_text("", encoding="utf-8")
    ctx = collect_ctx(tmp_path)
    assert any("forge_scope.py" in p for p in ctx["forge_scripts"])


# ── 단위: trust_guard ─────────────────────────────────────────


def test_trust_guard_exits_without_trust():
    import argparse
    args = argparse.Namespace(trust=False)
    with patch.dict("os.environ", {"FORGE_TRUST": ""}, clear=False):
        with pytest.raises(SystemExit) as exc_info:
            trust_guard(args)
        assert exc_info.value.code == 2


def test_trust_guard_passes_with_flag():
    import argparse
    args = argparse.Namespace(trust=True)
    with patch.dict("os.environ", {"FORGE_TRUST": ""}, clear=False):
        trust_guard(args)  # 예외 없이 통과


def test_trust_guard_passes_with_env():
    import argparse
    args = argparse.Namespace(trust=False)
    with patch.dict("os.environ", {"FORGE_TRUST": "1"}, clear=False):
        trust_guard(args)  # 예외 없이 통과


# ── 단위: verify ──────────────────────────────────────────────


def test_verify_missing_file(tmp_path):
    ok, msg = verify(tmp_path / "nonexistent.sh")
    assert not ok
    assert "없음" in msg


def test_verify_existing_non_script(tmp_path):
    f = tmp_path / "Hooks.md"
    f.write_text("# Docs", encoding="utf-8")
    ok, msg = verify(f)
    assert ok
    assert msg == ""


def test_verify_valid_py(tmp_path):
    f = tmp_path / "dep.py"
    f.write_text("x = 1\n", encoding="utf-8")
    ok, msg = verify(f)
    assert ok


def test_verify_invalid_py(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def foo(\n", encoding="utf-8")
    ok, msg = verify(f)
    assert not ok


# ── 통합: process_hook mock subprocess ────────────────────────


def _make_templates(tmp_path: Path) -> Path:
    templates_dir = tmp_path / "templates" / "hooks"
    templates_dir.mkdir(parents=True)
    for hook_path, _ in HOOKS:
        t = templates_dir / hook_path
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(f"# template for {hook_path}\n", encoding="utf-8")
    return templates_dir


def _mock_claude_writes_file(repo_root: Path, target: str, **kwargs):
    """subprocess.run mock: SETUP_OK 출력 + 실제 파일 작성 시뮬레이션."""
    target_path = repo_root / target
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(f"# adapted content for {target}\n", encoding="utf-8")
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = f"SETUP_OK {target}\n"
    mock.stderr = ""
    return mock


def test_process_hook_success(tmp_path):
    templates_dir = _make_templates(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    ctx = {"has_dotnet": False, "has_python": False}

    target, role = "Hooks.md", "doc"

    with patch("hooks_setup.subprocess.run") as mock_run:
        mock_run.side_effect = lambda cmd, **kw: _mock_claude_writes_file(repo_root, target)
        result = process_hook(target, role, ctx, templates_dir, repo_root, quiet=True)

    assert result.status == "completed"
    assert (repo_root / target).exists()


def test_process_hook_timeout(tmp_path):
    templates_dir = _make_templates(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    ctx = {}

    target, role = "ruff.toml", "config"

    with patch("hooks_setup.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)
        result = process_hook(target, role, ctx, templates_dir, repo_root, quiet=True)

    assert result.status == "error"
    assert "timeout" in result.error


def test_process_hook_missing_setup_ok(tmp_path):
    templates_dir = _make_templates(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    ctx = {}

    target, role = "requirements-dev.txt", "config"

    with patch("hooks_setup.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "some output that lacks the sentinel"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        result = process_hook(target, role, ctx, templates_dir, repo_root, quiet=True)

    assert result.status == "error"
    assert f"SETUP_OK {target}" in result.error


# ── 통합: 전체 12개 루프 시뮬레이션 ──────────────────────────────


def test_full_run_completes_all(tmp_path):
    templates_dir = _make_templates(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    ctx = {"has_dotnet": False, "has_python": True, "scripts_py": ["scripts/main.py"], "forge_scripts": [], "sln_files": [], "csproj_files": [], "has_pyproject": False, "requirements_txt": [], "git_root": str(repo_root)}

    state_path = repo_root / "phases" / "hooks-setup" / "state.json"

    import re as _re

    def mock_run_side_effect(cmd, **kw):
        # git 명령
        if cmd and cmd[0] == "git":
            m = MagicMock()
            m.returncode = 0
            m.stdout = str(repo_root)
            m.stderr = ""
            return m
        # bash -n (verify) — 성공으로 처리
        if cmd and cmd[0] == "bash":
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m
        # python -m py_compile (verify) — 성공으로 처리
        if cmd and cmd[0] in ("python", "python3") and "-m" in cmd and "py_compile" in cmd:
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m
        # claude 명령 — 프롬프트 헤더에서 target 정확히 추출
        args_list = cmd
        prompt_arg = args_list[-1] if args_list else ""
        header_match = _re.search(
            r"File path \(target, relative to repo root\): (.+)", prompt_arg
        )
        if header_match:
            target_from_prompt = header_match.group(1).strip()
            return _mock_claude_writes_file(repo_root, target_from_prompt)
        m = MagicMock()
        m.returncode = 0
        m.stdout = "SETUP_OK unknown\n"
        m.stderr = ""
        return m

    with (
        patch("hooks_setup.subprocess.run", side_effect=mock_run_side_effect),
        patch("hooks_setup.collect_ctx", return_value=ctx),
        patch.dict("os.environ", {"FORGE_TRUST": "1"}),
    ):
        from hooks_setup import main
        rc = main(["--trust", "--yes", "--quiet", f"--templates={templates_dir}"] if False else ["--trust", "--yes", "--quiet"])

    state = load_state(state_path)
    completed = [k for k, v in state.items.items() if v.status == "completed"]
    assert len(completed) == 12


# ── 통합: 재실행 시 completed skip ────────────────────────────


def test_rerun_skips_completed(tmp_path):
    state_path = tmp_path / "state.json"
    state = SetupState(started_at="2026-01-01T00:00:00+00:00")
    for hook_path, _ in HOOKS:
        state.items[hook_path] = HookState(status="completed", ts="2026-01-01T00:01:00+00:00")
    save_state(state_path, state)

    loaded = load_state(state_path)
    to_process = [k for k, v in loaded.items.items() if v.status != "completed"]
    assert len(to_process) == 0


def test_rerun_retries_error(tmp_path):
    state_path = tmp_path / "state.json"
    state = SetupState(started_at="2026-01-01T00:00:00+00:00")
    for hook_path, _ in HOOKS:
        state.items[hook_path] = HookState(status="completed", ts="2026-01-01T00:01:00+00:00")
    state.items["Hooks.md"] = HookState(status="error", error="이전 오류")
    save_state(state_path, state)

    loaded = load_state(state_path)
    to_process = [k for k, v in loaded.items.items() if v.status != "completed"]
    assert to_process == ["Hooks.md"]
