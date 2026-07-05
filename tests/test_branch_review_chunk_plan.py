import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "branch_review_chunk_plan.py"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "branch-review-test@example.invalid")
    git(repo, "config", "user.name", "Branch Review Test")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "initial")
    return repo


def run_chunk_plan(repo: Path, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--ref", "HEAD~1", "--repo-root", str(repo), *extra],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def single_patch_path(output: str) -> Path:
    match = re.search(r"^patch: (.+)$", output, re.MULTILINE)
    assert match, output
    return Path(match.group(1).strip())


def test_top_level_build_excluded_but_nested_build_kept(tmp_path):
    repo = init_repo(tmp_path)
    (repo / "build").mkdir()
    (repo / "build" / "generated.js").write_text("generated\n", encoding="utf-8")
    (repo / "src" / "build").mkdir(parents=True)
    (repo / "src" / "build" / "helper.py").write_text("print('kept')\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "add generated and source build paths")

    output = run_chunk_plan(repo)
    patch = single_patch_path(output).read_text(encoding="utf-8")

    assert "변경 규모: 1 files" in output
    assert "src/build/helper.py" in patch
    assert "build/generated.js" not in patch


def test_rename_safe_patch_is_not_empty(tmp_path):
    repo = init_repo(tmp_path)
    old_file = repo / "old_name.txt"
    old_file.write_text("old\n", encoding="utf-8")
    git(repo, "add", "old_name.txt")
    git(repo, "commit", "-q", "-m", "add old file")

    git(repo, "mv", "old_name.txt", "new_name.txt")
    (repo / "new_name.txt").write_text("new\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "rename file")

    output = run_chunk_plan(repo)
    patch = single_patch_path(output).read_text(encoding="utf-8")

    assert "diff --git" in patch
    assert "old_name.txt" in patch
    assert "new_name.txt" in patch


def test_single_large_file_chunk_warns_about_cap_overflow(tmp_path):
    repo = init_repo(tmp_path)
    big = repo / "big.txt"
    big.write_text("".join(f"line {i}\n" for i in range(2001)), encoding="utf-8")
    git(repo, "add", "big.txt")
    git(repo, "commit", "-q", "-m", "add large file")

    output = run_chunk_plan(repo)

    assert "모드: chunk" in output
    assert "## Warnings" in output
    assert "big.txt" in output
    assert "청크 라인 cap" in output


def test_public_branch_review_contract_mentions_hardened_rules():
    skill = (REPO_ROOT / "skills" / "branch-review" / "SKILL.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "임의 축(bugs/style/spec/perf)에 CRITICAL" in skill
    assert "`--spec <path>`" in skill
    assert "chunk-<id>.log" in skill
    assert "임의 축 CRITICAL" in readme
    assert "[--spec <path>] [--resume]" in readme
