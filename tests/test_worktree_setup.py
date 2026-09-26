import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "worktree_setup.py"

sys.path.insert(0, str(ROOT / "scripts"))
import docs_helpers as _dh  # noqa: E402  (script 와 같은 scripts/ 디렉토리)


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "forge-test@example.invalid")
    run_git(tmp_path, "config", "user.name", "Forge Test")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# Test repo\n", encoding="utf-8")
    run_git(tmp_path, "add", "README.md")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def commit_all(repo: Path, message: str = "docs") -> None:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-q", "-m", message)


# tests/test_docs_helpers.py 의 INTENT_CANONICAL (app=Demo, nnn=001) 사본 —
# approved 변형 요건에 맞춰 Handoff 의 pending 을 실제 값으로 채웠다.
INTENT_TEXT = """# Demo-INT-001 — 샘플 기능 Intent

| 항목 | 값 |
|---|---|
| 문서 ID | Demo-INT-001 |
| 유형 | 기능개발 |
| 상태 | draft |
| 작성 | tester · 2026-09-15 |
| 승인 | pending |
| 관련 Intent | none |
| 검증 | pending |

## Part 1 — 기능 명세

### Problem
문제 설명.

### Outcome
결과 설명.

- Out of scope: 항목A, 항목B

### Affected
영향 설명.

### Constraints
- C1. 제약 조건 — `{code, message}` 포맷 유지

### Decisions
- D1. 결정 — 근거: 근거 — 기각 대안: 대안

### Open questions
none

---

## Part 2 — 작업 지시

### Functional requirements
- FR-1. 요구 문장 (D1)

### Edge cases
- E-1. a → b (FR-1)

### Error cases
- X-1. a → b (FR-1)

### Acceptance
- [ ] A-1. 완료 조건 (FR-1)

### Verification
- 확인 방법

### Risks
- 리스크

### Handoff
| 항목 | 값 |
|---|---|
| repo · app | forge-test · Demo |
| base branch | main |
| 브랜치명 | intent/Demo-INT-001 |
| 손대지 말 영역 | docs/Demo |
| 완료 보고 방식 | 완료 보고 |
"""


def _meta_row(text: str, key: str, value: str) -> str:
    return re.sub(rf"(?m)^\| {re.escape(key)} \| .*$", f"| {key} | {value} |", text, count=1)


def write_intent(repo: Path, status: str = "approved", **overrides: str) -> Path:
    text = INTENT_TEXT
    if status == "approved":
        text = _meta_row(text, "승인", "tester · 2026-09-26")
        text = _meta_row(text, "검증", "PASS — code PASS · llm PASS · 1/3")
    text = _meta_row(text, "상태", status)
    for key, value in overrides.items():
        text = _meta_row(text, key, value)
    intent = repo / "docs" / "Demo" / "INTENT" / "Demo-INT-001.md"
    intent.parent.mkdir(parents=True, exist_ok=True)
    intent.write_text(text, encoding="utf-8")
    return intent


def run_init(repo: Path, doc: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "init", "--doc", str(doc), "--quiet", *extra],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def run_script(repo: Path, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def manifest_from(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_approved_intent_variant_is_fail_free(tmp_path: Path):
    intent = write_intent(tmp_path)
    results = _dh._check_intent_file(tmp_path, intent)
    fails = [f"{r.code}: {r.message}" for r in results if r.level == "FAIL"]
    assert not fails, fails


def test_approved_committed_intent_creates_worktree(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["intent_id"] == "Demo-INT-001"
    assert Path(manifest["worktree"]).exists()


def test_in_dev_committed_intent_creates_worktree(git_repo: Path):
    intent = write_intent(git_repo, status="in-dev")
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr


def test_draft_intent_blocks_before_worktree_creation(git_repo: Path):
    intent = write_intent(git_repo, status="draft")
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 2
    assert "approved" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_approved_intent_with_failed_verification_blocks(git_repo: Path):
    intent = write_intent(git_repo, 검증="FAIL — code PASS · llm FAIL · 3/3")
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 2
    assert "INT_APPROVED_GATE" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_work_packet_input_is_rejected(git_repo: Path):
    wp = git_repo / "docs" / "X" / "WORK_PACKET" / "X-WP-001.md"
    wp.parent.mkdir(parents=True, exist_ok=True)
    wp.write_text("# X-WP-001\n", encoding="utf-8")
    commit_all(git_repo)

    result = run_init(git_repo, wp)

    assert result.returncode == 2
    assert "폐지" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_task_input_is_rejected(git_repo: Path):
    task = git_repo / "docs" / "X" / "TASK" / "X-TASK-001.md"
    task.parent.mkdir(parents=True, exist_ok=True)
    task.write_text("# X-TASK-001\n", encoding="utf-8")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 2
    assert "폐지" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_zero_commit_repo_blocks_with_and_without_force(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "forge-test@example.invalid")
    run_git(repo, "config", "user.name", "Forge Test")
    run_git(repo, "config", "commit.gpgsign", "false")
    run_git(repo, "config", "core.autocrlf", "false")
    intent = write_intent(repo)

    for extra in ([], ["--force"]):
        result = run_init(repo, intent, *extra)
        assert result.returncode == 2
        assert "커밋이 하나도 없다" in result.stderr


def test_uncommitted_intent_blocks_with_and_without_force(git_repo: Path):
    intent = write_intent(git_repo)

    for extra in ([], ["--force"]):
        result = run_init(git_repo, intent, *extra)
        assert result.returncode == 2
        assert "마지막 커밋에 없다" in result.stderr


def test_handoff_branch_name_is_used(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["branch"] == "intent/Demo-INT-001"
    assert run_git(git_repo, "rev-parse", "--verify", "refs/heads/intent/Demo-INT-001").returncode == 0


def test_handoff_branch_name_fallback_when_not_a_ref(git_repo: Path):
    intent = write_intent(git_repo, 브랜치명="없음 — main 작업 트리에서 직접 작업")
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["branch"] == "intent/Demo-INT-001"


def test_first_init_marks_in_dev_and_commits(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt_intent = Path(manifest["intent_worktree"])
    assert "| 상태 | in-dev |" in wt_intent.read_text(encoding="utf-8")
    subject = subprocess.run(
        ["git", "-C", str(manifest["worktree"]), "log", "-1", "--format=%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert subject.stdout.strip() == "chore(Demo-INT-001): 상태 in-dev"
    assert "| 상태 | approved |" in intent.read_text(encoding="utf-8")
    assert manifest["created"] is True
    assert manifest["status_committed"] is True
    assert manifest["status"] == "in-dev"


def test_second_init_resumes_without_status_commit(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)
    first = run_init(git_repo, intent)
    assert first.returncode == 0, first.stderr
    wt = Path(manifest_from(first)["worktree"])
    commits_before = run_git(wt, "rev-list", "--count", "HEAD").stdout.strip()

    second = run_init(git_repo, intent)

    assert second.returncode == 0, second.stderr
    manifest = manifest_from(second)
    assert manifest["created"] is False
    assert manifest["status_committed"] is False
    assert run_git(wt, "rev-list", "--count", "HEAD").stdout.strip() == commits_before
    assert "| 상태 | in-dev |" in Path(manifest["intent_worktree"]).read_text(encoding="utf-8")


MANIFEST_KEYS = {
    "root", "worktree", "branch", "slug", "intent", "intent_worktree",
    "intent_id", "status", "created", "status_committed",
    "acceptance", "handoff", "copied", "skipped", "submodule_log",
}


def test_manifest_shape_and_no_process_scaffold(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, intent)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert set(manifest) == MANIFEST_KEYS
    assert manifest["acceptance"][0]["id"] == "A-1"
    assert set(manifest["handoff"]) == {"repo · app", "base branch", "브랜치명", "손대지 말 영역", "완료 보고 방식"}
    assert not (Path(manifest["worktree"]) / ".process" / manifest["slug"]).exists()


def test_list_includes_intent_worktrees(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)
    assert run_init(git_repo, intent).returncode == 0

    result = run_script(git_repo, "list")

    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout.strip())
    assert any(e["branch"] == "intent/Demo-INT-001" for e in entries)


def test_cancel_removes_intent_worktree_and_branch(git_repo: Path):
    intent = write_intent(git_repo)
    commit_all(git_repo)
    init_result = run_init(git_repo, intent)
    assert init_result.returncode == 0, init_result.stderr
    slug = manifest_from(init_result)["slug"]

    result = run_script(git_repo, "cancel", slug)

    assert result.returncode == 0, result.stderr
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/heads/intent/Demo-INT-001"],
        cwd=git_repo, capture_output=True, text=True,
    )
    assert probe.returncode != 0
    assert not (git_repo / ".worktree" / slug).exists()
