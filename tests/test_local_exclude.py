"""docs_helpers.py ensure-exclude — 설계 문서(문서 폴더 · intent/ · .task/)는 커밋하지 않는다.

공유 .gitignore 대신 이 clone 의 info/exclude 에 올린다. linked worktree 도 같은 파일을 쓴다.
"""
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import docs_helpers as dh  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "exclude-test@example.invalid")
    git(tmp_path, "config", "user.name", "Exclude Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def exclude_lines(repo: Path) -> list[str]:
    return (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()


def test_adds_entries_once(repo: Path, capsys):
    assert dh.main(["ensure-exclude", "--repo", str(repo)]) == 0
    assert capsys.readouterr().out.startswith("ADDED ")

    assert dh.main(["ensure-exclude", "--repo", str(repo)]) == 0
    assert capsys.readouterr().out.startswith("OK ")

    lines = exclude_lines(repo)
    for entry in dh.LOCAL_EXCLUDE_ENTRIES:
        assert lines.count(entry) == 1, entry
    assert lines.count(dh.LOCAL_EXCLUDE_HEADER) == 1


def test_hides_docs_intents_and_tasks_but_not_nested_folders(repo: Path):
    write(repo / "docs" / "LOADER" / "LOADER-PRD.md")
    write(repo / "intent" / "intent-app-catalog.md")
    write(repo / "intent" / "loader" / "loader-int-001.md")
    write(repo / ".task" / "tsk-001.md")
    write(repo / ".process" / "worktree" / "x.json")
    write(repo / "src" / "docs" / "guide.md")     # 레포 루트의 문서 폴더만 숨긴다
    write(repo / "src" / "intent" / "parser.cs")  # 소스 안의 같은 이름 폴더는 숨기지 않는다

    dh.ensure_local_exclude(repo)

    status = git(repo, "status", "--porcelain", "-uall")
    assert status.split() == ["??", "src/docs/guide.md", "??", "src/intent/parser.cs"]
    git(repo, "add", "-A")
    assert git(repo, "diff", "--cached", "--name-only").split() == ["src/docs/guide.md", "src/intent/parser.cs"]


def test_capital_docs_folder_is_hidden_too(repo: Path):
    write(repo / "Docs" / "LOADER" / "LOADER-PRD.md")

    dh.ensure_local_exclude(repo)

    assert git(repo, "status", "--porcelain", "-uall") == ""


def test_appends_after_content_without_trailing_newline(repo: Path):
    (repo / ".git" / "info" / "exclude").write_text("*.log", encoding="utf-8")

    result = dh.ensure_local_exclude(repo)

    lines = exclude_lines(repo)
    assert lines[0] == "*.log"
    assert result["added"] == list(dh.LOCAL_EXCLUDE_ENTRIES)
    assert all(entry in lines for entry in dh.LOCAL_EXCLUDE_ENTRIES)


def test_linked_worktree_shares_main_exclude(repo: Path, tmp_path: Path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "w", str(wt))

    result = dh.ensure_local_exclude(wt)

    assert Path(result["exclude"]).resolve() == (repo / ".git" / "info" / "exclude").resolve()
    write(wt / ".task" / "tsk-001.md")
    write(wt / "intent" / "loader" / "loader-int-001.md")
    assert git(wt, "status", "--porcelain", "-uall") == ""


def test_reports_tracked_intents(repo: Path):
    write(repo / "intent" / "loader" / "loader-int-001.md")
    git(repo, "add", "intent")
    git(repo, "commit", "-q", "-m", "committed intent")
    assert dh.ensure_local_exclude(repo)["tracked"] == ["intent/loader/loader-int-001.md"]


def test_reports_tracked_docs(repo: Path, capsys):
    write(repo / "docs" / "a.md")
    git(repo, "add", "docs/a.md")
    git(repo, "commit", "-q", "-m", "legacy docs")

    assert dh.ensure_local_exclude(repo)["tracked"] == ["docs/a.md"]
    assert dh.main(["ensure-exclude", "--repo", str(repo)]) == 0
    assert "WARN TRACKED docs/a.md" in capsys.readouterr().out


def test_not_a_git_repo_fails(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert dh.main(["ensure-exclude", "--repo", str(tmp_path)]) == 2
    assert "FAIL EXCLUDE" in capsys.readouterr().err
