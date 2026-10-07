import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ddr_loop.py"


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "ddr-loop-test@example.invalid")
    run_git(tmp_path, "config", "user.name", "DDR Loop Test")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# Test repo\n", encoding="utf-8")
    run_git(tmp_path, "add", "README.md")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def commit_all(repo: Path, message: str = "docs") -> None:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-q", "-m", message)


INTENT_ID = "XLAB-INT-001"
INTENT_REL = f"docs/XLAB/INTENT/{INTENT_ID}.md"


def write_intent(repo: Path) -> Path:
    intent = repo / INTENT_REL
    intent.parent.mkdir(parents=True, exist_ok=True)
    intent.write_text(
        f"# {INTENT_ID} — 샘플\n\n## Part 2 — 작업 지시\n\n### Acceptance\n- [ ] A-1. pass (FR-1)\n",
        encoding="utf-8",
    )
    return intent


def create_forge_worktree(repo: Path, slug: str, branch: str) -> Path:
    wt = repo / ".worktree" / slug
    wt.parent.mkdir(parents=True, exist_ok=True)
    run_git(repo, "worktree", "add", "-b", branch, str(wt), "HEAD")
    return wt


def write_manifest(repo: Path, slug: str, **fields: object) -> Path:
    """forge-init 이 메인 repo 에 남기는 매니페스트(.process/forge/<slug>.json) 사본."""
    mf = repo / ".process" / "forge" / f"{slug}.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    return mf


def forge_setup(repo: Path, slug: str = INTENT_ID, branch: str = f"intent/{INTENT_ID}") -> tuple[Path, Path, str]:
    """Intent 커밋 → 워크트리 생성 → 매니페스트 기록. (wt, 워크트리 안 Intent, base_commit)"""
    intent = write_intent(repo)
    commit_all(repo, "docs: intent")
    base_commit = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    wt = create_forge_worktree(repo, slug, branch)
    intent_wt = wt / INTENT_REL
    write_manifest(
        repo, slug,
        branch=branch, worktree=str(wt), base="main", base_commit=base_commit,
        intent=str(intent), intent_worktree=str(intent_wt), intent_id=INTENT_ID,
    )
    return wt, intent_wt, base_commit


def run_init(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "init", "--quiet", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def manifest_from(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_init_without_docs_uses_manifest_intent(git_repo: Path):
    wt, intent_wt, base_commit = forge_setup(git_repo)

    result = run_init(git_repo, "--slug", INTENT_ID)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["branch"] == f"intent/{INTENT_ID}"
    assert manifest["worktree"] == str(wt.resolve())
    assert manifest["docs_source"] == "auto-intent"
    assert manifest["intent"] == str(intent_wt.resolve())
    assert manifest["docs"] == [str(intent_wt.resolve())]
    assert manifest["base"] == base_commit
    for retired in ("work_packet", "task_doc", "required_ssot", "forge_build_md"):
        assert retired not in manifest
    build_md = Path(manifest["build_md"]).read_text(encoding="utf-8")
    assert "비교 문서 source: `auto-intent`" in build_md
    assert f"- Intent: `.worktree/{INTENT_ID}/{INTENT_REL}`" in build_md
    assert f"- base ref(vs): `{base_commit}`" in build_md
    assert "Work Packet" not in build_md


def test_init_explicit_base_overrides_manifest_base_commit(git_repo: Path):
    forge_setup(git_repo)

    result = run_init(git_repo, "--slug", INTENT_ID, "--base", "develop")

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["base"] == "develop"


def test_init_with_explicit_docs_overrides_intent(git_repo: Path):
    forge_setup(git_repo)
    spec = git_repo / "docs" / "spec.md"
    spec.write_text("# spec\n", encoding="utf-8")

    result = run_init(git_repo, "--slug", INTENT_ID, "--docs", str(spec))

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["docs_source"] == "explicit"
    assert manifest["intent"] is None
    assert manifest["docs"] == [str(spec.resolve())]


def test_init_blocks_without_forge_init_manifest(git_repo: Path):
    write_intent(git_repo)
    commit_all(git_repo)
    create_forge_worktree(git_repo, "no-manifest", "feat-no-manifest")

    result = run_init(git_repo, "--slug", "no-manifest", "--docs", INTENT_REL)

    assert result.returncode == 2
    assert "forge-init 매니페스트" in result.stderr
    assert "/forge-init" in result.stderr


def test_init_without_docs_blocks_when_manifest_has_no_intent(git_repo: Path):
    forge_setup(git_repo)
    write_manifest(git_repo, INTENT_ID, branch=f"intent/{INTENT_ID}", base_commit="")

    result = run_init(git_repo, "--slug", INTENT_ID)

    assert result.returncode == 2
    assert "비교 문서 자동 구성 실패" in result.stderr
    assert "--docs <doc...>" in result.stderr
