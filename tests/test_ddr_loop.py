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


def write_docs(repo: Path, nnn: str = "001") -> tuple[Path, Path, Path]:
    task = repo / "docs" / "XLAB" / "TASK" / f"XLAB-TASK-{nnn}.md"
    frd = repo / "docs" / "XLAB" / "FRD" / f"XLAB-FRD-{nnn}.md"
    wp = repo / "docs" / "XLAB" / "WORK_PACKET" / f"XLAB-WP-{nnn}.md"
    task.parent.mkdir(parents=True, exist_ok=True)
    frd.parent.mkdir(parents=True, exist_ok=True)
    wp.parent.mkdir(parents=True, exist_ok=True)
    task.write_text(f"# XLAB-TASK-{nnn}\n\n## 9. 완료 기준\n- pass\n", encoding="utf-8")
    frd.write_text(f"# XLAB-FRD-{nnn}\n\n## 1. 기준\n- pass\n", encoding="utf-8")
    wp.write_text(
        f"""# XLAB-WP-{nnn}

| 항목 | 값 |
|---|---|
| 문서 ID | XLAB-WP-{nnn} |
| 상태 | Ready |
| 연결 TASK | [XLAB-TASK-{nnn}](../TASK/XLAB-TASK-{nnn}.md) |

## 2. TASK
| 구분 | 링크 | 사용 목적 |
|---|---|---|
| Scope Authority | [XLAB-TASK-{nnn}](../TASK/XLAB-TASK-{nnn}.md) | 범위 |

## 4. Required SSOT Execution Matrix
| SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority |
|---|---|---|---|---|---|---|
| FRD | UPDATE | [XLAB-FRD-{nnn}](../FRD/XLAB-FRD-{nnn}.md) | §1 | 기준 | row 1 | Required |
""",
        encoding="utf-8",
    )
    return wp, task, frd


def create_forge_worktree(repo: Path, slug: str) -> Path:
    wt = repo / ".worktree" / slug
    wt.parent.mkdir(parents=True, exist_ok=True)
    run_git(repo, "worktree", "add", "-b", f"feat-{slug}", str(wt), "HEAD")
    return wt


def write_forge_build(wt: Path, slug: str, wp: Path, task: Path, repo: Path) -> None:
    proc = wt / ".process" / slug
    proc.mkdir(parents=True, exist_ok=True)
    wp_rel = wp.relative_to(repo).as_posix()
    task_rel = task.relative_to(repo).as_posix()
    (proc / "forge-scope-build.md").write_text(
        f"""# Build - {slug}

## 입력
- Work Packet: `{wp_rel}`
- TASK 문서: `{task_rel}`
- Legacy 입력 문서: `{wp_rel}`
- Required SSOT: _(filled by forge-scope session)_
- 빌드 타겟(.csproj): tests/Sample.Tests.csproj
""",
        encoding="utf-8",
    )


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


def test_init_without_docs_auto_uses_work_packet_task_and_required_ssot(git_repo: Path):
    slug = "XLAB-WP-001"
    wp, task, frd = write_docs(git_repo, "001")
    commit_all(git_repo)
    wt = create_forge_worktree(git_repo, slug)
    write_forge_build(wt, slug, wp, task, git_repo)

    result = run_init(git_repo, "--slug", slug)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["docs_source"] == "auto-work-packet"
    assert manifest["work_packet"] == str(wp.resolve())
    assert manifest["task_doc"] == str(task.resolve())
    assert manifest["required_ssot"] == [str(frd.resolve())]
    assert manifest["docs"] == [str(wp.resolve()), str(task.resolve()), str(frd.resolve())]
    build_md = Path(manifest["build_md"]).read_text(encoding="utf-8")
    assert "비교 문서 source: `auto-work-packet`" in build_md
    assert "Work Packet: `docs/XLAB/WORK_PACKET/XLAB-WP-001.md`" in build_md
    assert "TASK 문서: `docs/XLAB/TASK/XLAB-TASK-001.md`" in build_md
    assert "Required SSOT: docs/XLAB/FRD/XLAB-FRD-001.md" in build_md


def test_init_with_explicit_docs_keeps_legacy_override(git_repo: Path):
    slug = "manual-docs"
    _, task, _ = write_docs(git_repo, "002")
    commit_all(git_repo)
    create_forge_worktree(git_repo, slug)

    result = run_init(git_repo, "--slug", slug, "--docs", str(task))

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["docs_source"] == "explicit"
    assert manifest["work_packet"] is None
    assert manifest["task_doc"] is None
    assert manifest["required_ssot"] == []
    assert manifest["docs"] == [str(task.resolve())]


def test_init_without_docs_blocks_when_work_packet_metadata_missing(git_repo: Path):
    slug = "legacy-task"
    write_docs(git_repo, "003")
    commit_all(git_repo)
    create_forge_worktree(git_repo, slug)

    result = run_init(git_repo, "--slug", slug)

    assert result.returncode == 2
    assert "비교 문서 자동 구성 실패" in result.stderr
    assert "--docs <doc...>" in result.stderr
