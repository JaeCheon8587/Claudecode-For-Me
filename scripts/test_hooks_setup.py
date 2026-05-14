"""pytest for scripts/hooks_setup.py — 빈 레포 / 충돌 / 멱등 / 롤백 검증."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import hooks_setup  # noqa: E402


@pytest.fixture
def plugin_root(monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(ROOT))
    return ROOT


@pytest.fixture
def user_repo(tmp_path, monkeypatch):
    repo = tmp_path / "user-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(repo), check=True)
    monkeypatch.chdir(repo)
    return repo


def run_main(args):
    return hooks_setup.main(args)


def test_dry_run_empty_repo(plugin_root, user_repo, capsys):
    rc = run_main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == hooks_setup.EXIT_OK
    assert "dry-run 모드" in out
    assert "tools/hooks/pre-commit" in out
    assert not (user_repo / "tools/hooks/pre-commit").exists()
    assert not (user_repo / hooks_setup.STATE_REL).exists()


def test_apply_empty_repo(plugin_root, user_repo, capsys):
    rc = run_main(["--apply"])
    capsys.readouterr()
    assert rc == hooks_setup.EXIT_OK
    assert (user_repo / "tools/hooks/pre-commit").exists()
    assert (user_repo / "tools/hooks/pre-push").exists()
    assert (user_repo / "tools/quality/lint.sh").exists()
    assert (user_repo / "tools/install-hooks.sh").exists()
    assert (user_repo / "ruff.toml").exists()
    assert (user_repo / "requirements-dev.txt").exists()
    assert (user_repo / ".gitattributes").exists()
    state_path = user_repo / hooks_setup.STATE_REL
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["manifest_version"] == "1.0.0"
    kinds = {a["kind"] for a in state["actions"]}
    assert "git_config_set" in kinds
    r = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=str(user_repo),
        capture_output=True,
        text=True,
    )
    assert r.stdout.strip() == "tools/hooks"


def test_apply_idempotent(plugin_root, user_repo, capsys):
    run_main(["--apply"])
    capsys.readouterr()
    rc = run_main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == hooks_setup.EXIT_OK
    assert "conflict=identical" in out
    assert "conflict=differs" not in out


def test_apply_skip_on_conflict_with_yes(plugin_root, user_repo, capsys):
    pre_commit = user_repo / "tools/hooks/pre-commit"
    pre_commit.parent.mkdir(parents=True, exist_ok=True)
    pre_commit.write_text("existing pre-commit\n", encoding="utf-8")

    rc = run_main(["--apply", "--yes"])
    capsys.readouterr()
    assert rc == hooks_setup.EXIT_OK
    assert pre_commit.read_text(encoding="utf-8") == "existing pre-commit\n"
    state = json.loads((user_repo / hooks_setup.STATE_REL).read_text(encoding="utf-8"))
    pre_commit_actions = [a for a in state["actions"] if a.get("path") == "tools/hooks/pre-commit"]
    assert pre_commit_actions == []


def test_apply_force_overwrite_with_backup(plugin_root, user_repo, capsys):
    pre_commit = user_repo / "tools/hooks/pre-commit"
    pre_commit.parent.mkdir(parents=True, exist_ok=True)
    pre_commit.write_bytes(b"existing pre-commit\n")

    rc = run_main(["--apply", "--force"])
    capsys.readouterr()
    assert rc == hooks_setup.EXIT_OK

    expected = (ROOT / "templates/hooks/tools/hooks/pre-commit").read_bytes()
    assert pre_commit.read_bytes() == expected

    state = json.loads((user_repo / hooks_setup.STATE_REL).read_text(encoding="utf-8"))
    pre_commit_actions = [a for a in state["actions"] if a.get("path") == "tools/hooks/pre-commit"]
    assert len(pre_commit_actions) == 1
    backup_rel = pre_commit_actions[0]["backup"]
    assert backup_rel is not None
    backup_path = user_repo / backup_rel
    assert backup_path.exists()
    assert backup_path.read_bytes() == b"existing pre-commit\n"


def test_rollback_empty_repo(plugin_root, user_repo, capsys):
    run_main(["--apply"])
    capsys.readouterr()
    rc = run_main(["--rollback"])
    capsys.readouterr()
    assert rc == hooks_setup.EXIT_OK
    assert not (user_repo / "tools/hooks/pre-commit").exists()
    assert not (user_repo / "tools/install-hooks.sh").exists()
    assert not (user_repo / hooks_setup.STATE_REL).exists()
    r = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=str(user_repo),
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0 or r.stdout.strip() == ""


def test_rollback_restores_backup(plugin_root, user_repo, capsys):
    pre_commit = user_repo / "tools/hooks/pre-commit"
    pre_commit.parent.mkdir(parents=True, exist_ok=True)
    pre_commit.write_bytes(b"original user pre-commit\n")

    run_main(["--apply", "--force"])
    capsys.readouterr()
    assert pre_commit.read_bytes() != b"original user pre-commit\n"

    run_main(["--rollback"])
    capsys.readouterr()
    assert pre_commit.read_bytes() == b"original user pre-commit\n"


def test_gitattributes_append_fragment(plugin_root, user_repo, capsys):
    ga = user_repo / ".gitattributes"
    ga.write_text("*.png binary\n", encoding="utf-8")

    rc = run_main(["--apply", "--yes"])
    capsys.readouterr()
    assert rc == hooks_setup.EXIT_OK
    content = ga.read_text(encoding="utf-8")
    assert "*.png binary" in content
    assert "harness_framework hooks" in content


def test_dry_run_does_not_modify(plugin_root, user_repo):
    run_main(["--dry-run"])
    assert not (user_repo / "tools").exists()
    r = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=str(user_repo),
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0


def test_yes_and_force_mutex(plugin_root, user_repo, capsys):
    rc = run_main(["--apply", "--yes", "--force"])
    out = capsys.readouterr().out
    assert rc == hooks_setup.EXIT_ERR
    assert "동시 사용 불가" in out


def test_fail_outside_git_repo(tmp_path, monkeypatch, plugin_root, capsys):
    non_git = tmp_path / "plain"
    non_git.mkdir()
    monkeypatch.chdir(non_git)
    rc = run_main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == hooks_setup.EXIT_ERR
    assert "git" in out.lower()
