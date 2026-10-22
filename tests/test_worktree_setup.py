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
import worktree_setup as _ws  # noqa: E402  (단위 테스트용 — CLI 는 SCRIPT 로 띄운다)


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


TASK_REL = ".task/TSK-001.md"
TASK_CATALOG_REL = ".task/task-catalog.md"
INTENT_REL = "docs/Demo/INTENT/Demo-INT-001.md"
CATALOG_REL = "docs/Demo/Demo-INT-CATALOG.md"

# 대상 Intent — 기능 문서(상시). TSK-001 이 바꾸는 항목 끝에 진행 표시가 붙어 있다
# (신규 · 변경 = 진행 중, 삭제 = 삭제 예정). FR 삭제가 있어서 마감 뒤 INT 카탈로그의 규모(FR 수)가 바뀐다.
INTENT_TEXT = """# Demo-INT-001 — 업로드

| 항목 | 값 |
|---|---|
| 문서 ID | Demo-INT-001 |
| 기능 ID | F001 |
| 상태 | active |
| 작성 | tester · 2026-10-01 |
| 관련 Intent | none |

## Part 1 — 기능 정의

### Problem
문제 설명.

### Outcome
결과 설명.

- Out of scope: 여러 파일 동시 업로드

### Affected
업로드 기능 영역.

### Constraints
- C1. 제약 조건

### Decisions
- D1. 결정 — 근거: 근거 — 기각 대안: 대안

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)
- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1) [TSK-001 진행 중]
- FR-3. 업로드 응답에 처리 시간을 밀리초로 담는다. (D1) [TSK-001 진행 중]
- FR-4. 업로드 응답에 응답 필드 `serverName` 으로 처리한 서버 이름을 담는다. (D1) [TSK-001 삭제 예정]

### Edge cases
- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-001 삭제 예정]

### Error cases
- X-1. 빈 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)
"""

# 승인된 Task — Scope 는 위 Intent 항목의 사본이다 (진행 표시 제외).
TASK_TEXT = """# TSK-001 — 업로드 응답 정리

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-001 |
| 유형 | 기능개발 |
| 상태 | approved |
| 대상 Intent | Demo-INT-001 |
| 작성 | tester · 2026-10-22 |
| 승인 | tester · 2026-10-22 |
| 검증 | SKIPPED — 수동 작성 |

## Goal
- 계기: 재시도가 있었는지 응답에서 알 수 없고, 서버 이름은 아무도 쓰지 않는다.
- 완료 상태: 응답에서 재시도 횟수와 밀리초 처리 시간을 보고, 서버 이름은 더 이상 오지 않는다.

## Scope
- 신규 · Demo-INT-001 FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)
- 변경 · Demo-INT-001 FR-3. 업로드 응답에 처리 시간을 밀리초로 담는다. (D1)
  - 이전: 업로드 응답에 처리 시간을 초로 담는다. (D1)
- 삭제 · Demo-INT-001 FR-4. 업로드 응답에 응답 필드 `serverName` 으로 처리한 서버 이름을 담는다. (D1)
- 삭제 · Demo-INT-001 E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1)

- Out of scope: 화면 표시

## Acceptance
- [ ] A-1. 업로드 응답에 응답 필드 `retryCount` 가 있다. (Demo-INT-001 FR-2)
- [ ] A-2. 처리 시간이 밀리초로 온다. (Demo-INT-001 FR-3)
- [ ] A-3. 업로드 응답에 응답 필드 `serverName` 이 없다. (Demo-INT-001 FR-4)
- [ ] A-4. 같은 파일을 두 번 올리면 두 번 저장된다. (Demo-INT-001 E-1, R-1)

## Verification
- 업로드 자동 테스트로 A-1 ~ A-4 를 확인한다.

## Risks
- R-1. 이미 저장된 중복 파일은 그대로 남는다 → 배포 안내에 적는다.

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | forge-test · Demo |
| base branch | main |
| 브랜치명 | task/TSK-001 |
| 손대지 말 영역 | docs/Demo |
| 완료 보고 방식 | 채팅 요약 |
"""


def _meta_row(text: str, key: str, value: str) -> str:
    """`| key | … |` 첫 행의 값을 바꾼다 (줄 끝 \\r 보존)."""
    assert f"| {key} |" in text, key
    return re.sub(rf"(?m)^\| {re.escape(key)} \| [^\r\n]*", lambda m: f"| {key} | {value} |", text, count=1)


def _write(path: Path, text: str, eol: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", eol).encode("utf-8"))
    return path


def write_intent(repo: Path, docs_dir: str = "docs", eol: str = "\n", replace: dict | None = None) -> Path:
    text = INTENT_TEXT
    for old, new in (replace or {}).items():
        assert old in text, f"replace target not found: {old!r}"
        text = text.replace(old, new)
    return _write(repo / docs_dir / "Demo" / "INTENT" / "Demo-INT-001.md", text, eol)


def write_catalogs(repo: Path) -> None:
    """/forge-init §3 처럼 승인 커밋 직전에 생성물 두 개를 다시 만든다."""
    assert _dh.main(["intent-catalog", "--repo", str(repo), "--app", "Demo", "--write"]) == 0
    assert _dh.main(["task-catalog", "--repo", str(repo), "--write"]) == 0


def write_task(
    repo: Path,
    status: str = "approved",
    docs_dir: str = "docs",
    eol: str = "\n",
    intent: dict | None = None,
    catalogs: bool = True,
    **rows: str,
) -> Path:
    """Task(.task/TSK-001.md) + 대상 Intent (+ 카탈로그 2종). rows 는 메타 · Handoff 행 값, intent 는 Intent 본문 str.replace 쌍."""
    write_intent(repo, docs_dir=docs_dir, eol=eol, replace=intent)
    text = _meta_row(TASK_TEXT, "상태", status)
    for key, value in rows.items():
        text = _meta_row(text, key, value)
    task = _write(repo / TASK_REL, text, eol)
    if catalogs:
        write_catalogs(repo)
    return task


def set_row(doc: Path, key: str, value: str) -> None:
    doc.write_bytes(_meta_row(doc.read_bytes().decode("utf-8"), key, value).encode("utf-8"))


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_bytes().decode("utf-8")
    assert old in text, old
    path.write_bytes(text.replace(old, new, 1).encode("utf-8"))


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


def commit_subject(repo: Path) -> str:
    # 한글 subject — run_git 의 기본 인코딩으로는 못 읽는다
    r = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.stdout.strip()


def head_commit_files(repo: Path) -> list[str]:
    out = run_git(repo, "show", "--name-only", "--format=", "HEAD").stdout
    return sorted(line for line in out.splitlines() if line)


def task_catalog_row(text: str, task_id: str = "TSK-001") -> str:
    return next((line for line in text.splitlines() if line.startswith(f"| [{task_id}](")), "")


def test_approved_task_fixture_is_clean(tmp_path: Path):
    task = write_task(tmp_path)
    results = _dh._check_task_file(tmp_path, task)
    bad = [f"{r.level} {r.code}: {r.message}" for r in results if r.level != "PASS"]
    assert not bad, bad
    assert _dh.main(["check", "--repo", str(tmp_path), "--app", "Demo"]) == 0


def test_approved_committed_task_creates_worktree(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["task_id"] == "TSK-001"
    assert Path(manifest["worktree"]).exists()


def test_in_dev_committed_task_creates_worktree(git_repo: Path):
    task = write_task(git_repo, status="in-dev")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr


def test_draft_task_blocks_before_worktree_creation(git_repo: Path):
    task = write_task(git_repo, status="draft")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 2
    assert "approved" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_approved_task_with_failed_verification_blocks(git_repo: Path):
    task = write_task(git_repo, 검증="FAIL — code PASS · llm FAIL · 3/3")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 2
    assert "TSK_APPROVED_GATE" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_scope_that_no_longer_matches_intent_blocks(git_repo: Path):
    """게이트는 형식만 보지 않는다 — 승인 뒤 Intent 가 바뀌어 Scope 사본과 어긋나면 막는다."""
    task = write_task(git_repo, intent={"처리 시간을 밀리초로": "처리 시간을 마이크로초로"})
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 2
    assert "TSK_SCOPE_MATCH" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_missing_target_intent_blocks(git_repo: Path):
    task = write_task(git_repo)
    (git_repo / INTENT_REL).unlink()
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 2
    assert "TSK_INTENT_EXISTS" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_intent_input_is_rejected(git_repo: Path):
    """Intent 는 기능 문서다 — 개발 입력은 그 Intent 의 바뀐 항목을 옮겨 승인한 Task 다."""
    write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, git_repo / INTENT_REL)

    assert result.returncode == 2
    assert "기능 문서" in result.stderr
    assert ".task/TSK-NNN.md" in result.stderr
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


def test_legacy_task_input_is_rejected(git_repo: Path):
    """0.x 의 문서 폴더 아래 작업 문서 — 레포 루트 .task/ 의 TSK-<NNN>.md 가 아니면 Task 가 아니다."""
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
    task = write_task(repo)

    for extra in ([], ["--force"]):
        result = run_init(repo, task, *extra)
        assert result.returncode == 2
        assert "커밋이 하나도 없다" in result.stderr


def test_uncommitted_task_blocks_with_and_without_force(git_repo: Path):
    task = write_task(git_repo)

    for extra in ([], ["--force"]):
        result = run_init(git_repo, task, *extra)
        assert result.returncode == 2
        assert "마지막 커밋에 없다" in result.stderr


def test_uncommitted_intent_edit_blocks(git_repo: Path):
    """워크트리에는 커밋된 Intent 가 들어간다 — 디스크에서만 고친 Intent 로는 시작하지 않는다(--force 무관)."""
    task = write_task(git_repo)
    commit_all(git_repo)
    replace_in(git_repo / INTENT_REL, "문제 설명.", "문제 설명을 보강했다.")

    result = run_init(git_repo, task, "--force")

    assert result.returncode == 2
    assert "Intent 가 마지막 커밋의 사본과 다르다" in result.stderr
    assert INTENT_REL in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_default_branch_is_task_id(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["branch"] == "task/TSK-001"


def test_handoff_branch_name_is_used(git_repo: Path):
    task = write_task(git_repo, 브랜치명="feature/upload-response")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["branch"] == "feature/upload-response"
    assert run_git(git_repo, "rev-parse", "--verify", "refs/heads/feature/upload-response").returncode == 0


def test_handoff_branch_name_fallback_when_not_a_ref(git_repo: Path):
    task = write_task(git_repo, 브랜치명="없음 — main 작업 트리에서 직접 작업")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["branch"] == "task/TSK-001"


def test_branch_attached_elsewhere_hint_has_no_name_option(git_repo: Path, tmp_path: Path):
    doc = write_task(git_repo)
    commit_all(git_repo)
    run_git(git_repo, "branch", "task/TSK-001")
    other = tmp_path / "elsewhere"
    run_git(git_repo, "worktree", "add", str(other), "task/TSK-001")

    r = run_init(git_repo, doc)

    assert r.returncode != 0
    assert "git worktree remove" in r.stderr
    assert "--name 으로는 피할 수 없다" in r.stderr
    assert "다른 --name 사용" not in r.stderr


def test_first_init_marks_in_dev_and_commits(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert "| 상태 | in-dev |" in Path(manifest["task_worktree"]).read_text(encoding="utf-8")
    assert commit_subject(wt) == "chore(TSK-001): 상태 in-dev"
    # Intent 는 바뀌지 않는다 — 진행 표시는 승인 커밋에 이미 있다. 그래서 INT 카탈로그도 동봉하지 않는다.
    assert head_commit_files(wt) == [TASK_REL, TASK_CATALOG_REL]
    assert "| in-dev |" in task_catalog_row((wt / TASK_CATALOG_REL).read_text(encoding="utf-8"))
    assert "| 상태 | approved |" in task.read_text(encoding="utf-8")
    assert manifest["created"] is True
    assert manifest["status_committed"] is True
    assert manifest["status"] == "in-dev"


def test_second_init_resumes_without_status_commit(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    first = run_init(git_repo, task)
    assert first.returncode == 0, first.stderr
    wt = Path(manifest_from(first)["worktree"])
    commits_before = run_git(wt, "rev-list", "--count", "HEAD").stdout.strip()

    second = run_init(git_repo, task)

    assert second.returncode == 0, second.stderr
    manifest = manifest_from(second)
    assert manifest["created"] is False
    assert manifest["status_committed"] is False
    assert run_git(wt, "rev-list", "--count", "HEAD").stdout.strip() == commits_before
    assert "| 상태 | in-dev |" in Path(manifest["task_worktree"]).read_text(encoding="utf-8")


MANIFEST_KEYS = {
    "root", "worktree", "branch", "base", "base_commit", "base_applied",
    "slug", "task", "task_worktree", "task_id", "intents",
    "status", "created", "status_committed",
    "scope", "acceptance", "handoff", "copied", "skipped", "submodule_log",
    "manifests",
}


def test_manifest_shape_and_no_process_scaffold(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert set(manifest) == MANIFEST_KEYS
    assert Path(manifest["task_worktree"]) == wt / TASK_REL
    [intent] = manifest["intents"]
    assert intent["id"] == "Demo-INT-001"
    assert Path(intent["path"]).resolve() == (git_repo / INTENT_REL).resolve()
    assert Path(intent["worktree_path"]) == wt / INTENT_REL
    assert [(s["kind"], s["key"]) for s in manifest["scope"]] == [
        ("신규", "Demo-INT-001 FR-2"),
        ("변경", "Demo-INT-001 FR-3"),
        ("삭제", "Demo-INT-001 FR-4"),
        ("삭제", "Demo-INT-001 E-1"),
    ]
    assert manifest["scope"][0]["text"] == "업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)"
    assert manifest["acceptance"][0] == {
        "id": "A-1", "text": "업로드 응답에 응답 필드 `retryCount` 가 있다.", "refs": ["Demo-INT-001 FR-2"],
    }
    assert manifest["acceptance"][3]["refs"] == ["Demo-INT-001 E-1", "R-1"]
    assert set(manifest["handoff"]) == {"repo · app", "base branch", "브랜치명", "손대지 말 영역", "완료 보고 방식"}
    assert not (wt / ".process" / manifest["slug"]).exists()


def test_list_includes_task_worktrees(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    assert run_init(git_repo, task).returncode == 0

    result = run_script(git_repo, "list")

    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout.strip())
    assert any(e["branch"] == "task/TSK-001" for e in entries)


def test_list_scan_fallback_finds_task_branch(git_repo: Path):
    """메인 매니페스트가 없어도(지워졌거나 매니페스트 이전 워크트리) task/ 브랜치 워크트리는 목록에 오른다."""
    task = write_task(git_repo)
    commit_all(git_repo)
    slug = manifest_from(run_init(git_repo, task))["slug"]
    (git_repo / ".process" / "forge" / f"{slug}.json").unlink()

    result = run_script(git_repo, "list")

    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout.strip())
    assert [(e["slug"], e["branch"], e["source"]) for e in entries] == [(slug, "task/TSK-001", "scan")]


def test_cancel_removes_task_worktree_and_branch(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    init_result = run_init(git_repo, task)
    assert init_result.returncode == 0, init_result.stderr
    slug = manifest_from(init_result)["slug"]

    result = run_script(git_repo, "cancel", slug)

    assert result.returncode == 0, result.stderr
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/heads/task/TSK-001"],
        cwd=git_repo, capture_output=True, text=True,
    )
    assert probe.returncode != 0
    assert not (git_repo / ".worktree" / slug).exists()


# ============================================================================
# base 브랜치 선택 (branches 서브커맨드 · init --base)
# ============================================================================
def catalog_row(text: str, intent_id: str) -> str:
    """INT 카탈로그 본문에서 해당 Intent 의 행 1줄을 뽑는다 (없으면 빈 문자열)."""
    for line in text.splitlines():
        if line.startswith(f"| [{intent_id}](INTENT/"):
            return line
    return ""


def current_branch(repo: Path) -> str:
    return run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def make_branch_with_extra_commit(repo: Path, name: str, filename: str) -> str:
    """현재 HEAD 에서 name 브랜치를 만들고 전용 커밋 1개를 얹은 뒤 원래 브랜치로 돌아온다."""
    origin_branch = current_branch(repo)
    run_git(repo, "checkout", "-q", "-b", name)
    (repo / filename).write_text(f"only on {name}\n", encoding="utf-8")
    run_git(repo, "add", filename)
    run_git(repo, "commit", "-q", "-m", f"{name} only")
    sha = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    run_git(repo, "checkout", "-q", origin_branch)
    return sha


def branches_of(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_branches_lists_local_and_remote(git_repo: Path):
    write_task(git_repo)
    commit_all(git_repo)
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")
    poc_sha = make_branch_with_extra_commit(git_repo, "poc", "poc-only.txt")
    run_git(git_repo, "update-ref", "refs/remotes/origin/poc-remote", poc_sha)

    result = run_script(git_repo, "branches")

    assert result.returncode == 0, result.stderr
    by_ref = {c["ref"]: c for c in branches_of(result)["candidates"]}
    assert by_ref["develop"]["kind"] == "local"
    assert by_ref["origin/poc-remote"]["kind"] == "remote"
    assert by_ref["develop"]["sha"] and by_ref["develop"]["date"]
    assert "origin" not in by_ref, "origin/HEAD 가 short name 'origin' 으로 새면 안 된다"


def test_branches_dedupes_identical_remote(git_repo: Path):
    write_task(git_repo)
    commit_all(git_repo)
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()
    main = current_branch(git_repo)
    run_git(git_repo, "update-ref", f"refs/remotes/origin/{main}", head)

    result = run_script(git_repo, "branches")

    refs = [c["ref"] for c in branches_of(result)["candidates"]]
    assert main in refs
    assert f"origin/{main}" not in refs


def test_branches_recommends_handoff_base(git_repo: Path):
    task = write_task(git_repo)
    set_row(task, "base branch", "develop")
    commit_all(git_repo)
    run_git(git_repo, "branch", "develop")

    result = run_script(git_repo, "branches", "--doc", str(task))

    assert result.returncode == 0, result.stderr
    data = branches_of(result)
    assert data["recommended"] == "develop"
    assert data["recommended_source"] == "handoff"
    assert data["recommended_exists"] is True
    assert data["candidates"][0]["ref"] == "develop", "추천이 맨 앞이어야 한다"
    assert data["target_branch"] == "task/TSK-001"


def test_branches_recommended_missing_is_flagged(git_repo: Path):
    task = write_task(git_repo)
    set_row(task, "base branch", "no-such-branch")
    commit_all(git_repo)

    result = run_script(git_repo, "branches", "--doc", str(task))

    assert result.returncode == 0, result.stderr
    data = branches_of(result)
    assert data["recommended"] == "no-such-branch"
    assert data["recommended_exists"] is False


def test_branches_reports_target_branch_exists(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    run_git(git_repo, "branch", "task/TSK-001")

    result = run_script(git_repo, "branches", "--doc", str(task))

    assert branches_of(result)["target_branch_exists"] is True


def test_branches_without_doc_falls_back_to_head(git_repo: Path):
    write_task(git_repo)
    commit_all(git_repo)

    result = run_script(git_repo, "branches")

    assert result.returncode == 0, result.stderr
    data = branches_of(result)
    assert data["recommended_source"] == "head"
    assert data["recommended"] == current_branch(git_repo)
    assert data["target_branch"] == ""


def test_branches_is_read_only(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    before = (
        run_git(git_repo, "status", "--porcelain").stdout,
        run_git(git_repo, "worktree", "list", "--porcelain").stdout,
        run_git(git_repo, "rev-parse", "HEAD").stdout,
    )

    assert run_script(git_repo, "branches", "--doc", str(task)).returncode == 0

    after = (
        run_git(git_repo, "status", "--porcelain").stdout,
        run_git(git_repo, "worktree", "list", "--porcelain").stdout,
        run_git(git_repo, "rev-parse", "HEAD").stdout,
    )
    assert before == after


def test_init_base_forks_selected_branch(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    develop_sha = make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")

    result = run_init(git_repo, task, "--base", "develop")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert (wt / "develop-only.txt").exists()
    assert manifest["base"] == "develop"
    assert manifest["base_commit"] == develop_sha
    assert manifest["base_applied"] is True
    probe = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "develop", "HEAD"],
        cwd=wt, capture_output=True, text=True,
    )
    assert probe.returncode == 0


def test_init_without_base_keeps_head_behavior(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["base"] == ""
    assert manifest["base_commit"] == ""
    assert manifest["base_applied"] is False
    assert not (Path(manifest["worktree"]) / "develop-only.txt").exists()


def test_init_base_unknown_ref_exits_1(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task, "--base", "no-such-branch")

    assert result.returncode == 1, result.stderr
    assert "no-such-branch" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_rejects_pipe_char(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task, "--base", "a|b")

    assert result.returncode == 1, result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_without_task_exits_2(git_repo: Path):
    run_git(git_repo, "branch", "pre")   # Task 커밋 이전 분기점
    task = write_task(git_repo)
    commit_all(git_repo)

    result = run_init(git_repo, task, "--base", "pre")

    assert result.returncode == 2, result.stderr
    assert "pre" in result.stderr and TASK_REL in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_without_intent_exits_2(git_repo: Path):
    """Task 만 있고 대상 Intent 는 없는 분기점 — 워크트리의 개발 세션이 Intent 를 읽지 못한다."""
    task = write_task(git_repo)
    run_git(git_repo, "add", TASK_REL)
    run_git(git_repo, "commit", "-q", "-m", "task only")
    run_git(git_repo, "branch", "pre")
    commit_all(git_repo)

    result = run_init(git_repo, task, "--base", "pre")

    assert result.returncode == 2, result.stderr
    assert "Intent 가 base 'pre'에 없다" in result.stderr and INTENT_REL in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_with_divergent_task_exits_2(git_repo: Path):
    task = write_task(git_repo, status="draft")
    commit_all(git_repo)
    run_git(git_repo, "branch", "develop")    # develop 사본 = draft
    write_task(git_repo)                      # 디스크 = approved, 커밋하지 않음

    result = run_init(git_repo, task, "--base", "develop", "--force")

    assert result.returncode == 2, result.stderr
    assert "Task 가 base 'develop'의 사본과 다르다" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_with_divergent_intent_exits_2(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    run_git(git_repo, "branch", "develop")    # develop 사본 = 고치기 전 Intent
    replace_in(git_repo / INTENT_REL, "문제 설명.", "문제 설명을 보강했다.")
    commit_all(git_repo, "docs: Intent 보강")  # 현재 브랜치에만 있다

    result = run_init(git_repo, task, "--base", "develop")

    assert result.returncode == 2, result.stderr
    assert "Intent 가 base 'develop'의 사본과 다르다" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_base_written_into_handoff_commit(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")
    base_commits = int(run_git(git_repo, "rev-list", "--count", "develop").stdout.strip())

    result = run_init(git_repo, task, "--base", "develop")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    text = Path(manifest["task_worktree"]).read_text(encoding="utf-8")
    assert "| base branch | develop |" in text
    assert "| 상태 | in-dev |" in text
    assert manifest["handoff"]["base branch"] == "develop"
    # 전이 커밋 1개에 Task + task-catalog 2파일이 동봉된다 (.gitignore 는 의도적으로 미커밋).
    assert int(run_git(wt, "rev-list", "--count", "HEAD").stdout.strip()) == base_commits + 1
    assert head_commit_files(wt) == [TASK_REL, TASK_CATALOG_REL]
    assert commit_subject(wt) == "chore(TSK-001): 상태 in-dev"
    # task-catalog 가 실제로 in-dev 를 담고 끝줄이 tasks 집계다
    catalog = (wt / TASK_CATALOG_REL).read_text(encoding="utf-8")
    row = task_catalog_row(catalog)
    assert "| in-dev |" in row, catalog
    assert catalog.strip().splitlines()[-1] == "tasks: 1", catalog


def test_init_existing_branch_ignores_base(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")
    run_git(git_repo, "branch", "task/TSK-001")   # 브랜치 선점

    result = run_init(git_repo, task, "--base", "develop")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["base"] == "develop"
    assert manifest["base_applied"] is False
    assert not (Path(manifest["worktree"]) / "develop-only.txt").exists()


def test_init_remote_base_has_no_upstream(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()
    run_git(git_repo, "update-ref", "refs/remotes/origin/poc", head)

    result = run_init(git_repo, task, "--base", "origin/poc")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["base_applied"] is True
    probe = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=Path(manifest["worktree"]), capture_output=True, text=True,
    )
    assert probe.returncode != 0, "--no-track 이 적용돼 upstream 이 없어야 한다"


# ============================================================================
# _refresh_int_catalog (파생 카탈로그 재생성 · 경로 가드)
# ============================================================================
@pytest.mark.parametrize("bad_rel", [
    "docs/Demo/Demo-INT-001.md",          # 세그먼트 부족 (INTENT/ 없음)
    "docs/Demo/TASK/Demo-INT-001.md",     # 세번째 세그먼트가 INTENT 가 아님
])
def test_refresh_int_catalog_rejects_non_intent_path(tmp_path: Path, bad_rel: str):
    write_intent(tmp_path)

    assert _ws._refresh_int_catalog(tmp_path, bad_rel) is None
    assert not (tmp_path / CATALOG_REL).exists()


def test_refresh_int_catalog_writes_catalog_for_intent_path(tmp_path: Path):
    write_intent(tmp_path)

    rel = _ws._refresh_int_catalog(tmp_path, INTENT_REL)

    assert rel == CATALOG_REL
    catalog = (tmp_path / rel).read_text(encoding="utf-8")
    assert catalog_row(catalog, "Demo-INT-001"), catalog
    assert catalog.strip().splitlines()[-1] == "intents: 1"


# ============================================================================
# 매니페스트 · cwd 독립성
#
# `init` 은 고른 base·만든 브랜치·워크트리 경로를 알고 있다. 그걸 파일로 남기지
# 않으면 cancel·list 가 나중에 slug 로부터 브랜치를 추측하게 되고, 기본 브랜치가
# task/<ID> 인 지금은 그 추측(feat-<slug>)이 항상 틀린다.
# ============================================================================
def test_init_writes_manifest_to_worktree_and_main(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)

    manifest = manifest_from(run_init(git_repo, task))

    wt_manifest = Path(manifest["worktree"]) / ".process" / "forge" / "handoff.json"
    main_manifest = git_repo / ".process" / "forge" / f"{manifest['slug']}.json"
    assert wt_manifest.is_file(), "워크트리 인수인계 사본이 없다"
    assert main_manifest.is_file(), "메인 repo 조회용 사본이 없다"

    a = json.loads(wt_manifest.read_text(encoding="utf-8"))
    b = json.loads(main_manifest.read_text(encoding="utf-8"))
    assert a == b
    assert a["branch"] == manifest["branch"] == "task/TSK-001"
    assert a["worktree"] == manifest["worktree"]
    assert sorted(manifest["manifests"]) == sorted([str(wt_manifest), str(main_manifest)])


def test_init_leaves_main_gitignore_untouched(git_repo: Path):
    """메인 .gitignore 를 고치면 ` M .gitignore` 가 남아 다음 init 이 dirty 로 막힌다.

    `?? .process/` 는 dirty 검사에서 이미 제외되므로 고칠 이유가 없다.
    """
    task = write_task(git_repo)
    (git_repo / ".gitignore").write_text(".process/\n", encoding="utf-8")
    commit_all(git_repo)
    before = (git_repo / ".gitignore").read_text(encoding="utf-8")

    assert run_init(git_repo, task).returncode == 0
    assert (git_repo / ".gitignore").read_text(encoding="utf-8") == before

    porcelain = run_git(git_repo, "status", "--porcelain").stdout
    assert ".gitignore" not in porcelain

    # 두 번째 init(resume)도 dirty 로 막히지 않는다.
    second = run_init(git_repo, task)
    assert second.returncode == 0, second.stderr
    assert manifest_from(second)["status_committed"] is False


def test_repo_root_resolves_main_repo_from_inside_worktree(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    worktree = Path(manifest_from(run_init(git_repo, task))["worktree"])

    # --show-toplevel 이면 워크트리 자신을 돌려줘 .worktree/<slug> 계산이 어긋난다.
    assert _ws._repo_root(worktree).resolve() == git_repo.resolve()
    assert _ws._repo_root(git_repo).resolve() == git_repo.resolve()


def test_list_works_from_inside_worktree(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    worktree = Path(manifest_from(run_init(git_repo, task))["worktree"])

    result = run_script(worktree, "list")

    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout.strip())
    assert [e["branch"] for e in entries] == ["task/TSK-001"]
    assert entries[0]["source"] == "manifest"


def test_cancel_uses_manifest_branch_not_feat_guess(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    manifest = manifest_from(run_init(git_repo, task))
    slug = manifest["slug"]

    result = run_script(git_repo, "cancel", slug)

    assert result.returncode == 0, result.stderr
    assert "task/TSK-001" in result.stdout
    assert "feat-" not in result.stdout
    assert not Path(manifest["worktree"]).exists()
    assert not (git_repo / ".process" / "forge" / f"{slug}.json").exists()
    branches = run_git(git_repo, "branch", "--format=%(refname:short)").stdout
    assert "task/TSK-001" not in branches.split()


def test_cancel_falls_back_to_reverse_index_without_manifest(git_repo: Path):
    task = write_task(git_repo)
    commit_all(git_repo)
    manifest = manifest_from(run_init(git_repo, task))
    slug = manifest["slug"]
    (git_repo / ".process" / "forge" / f"{slug}.json").unlink()

    result = run_script(git_repo, "cancel", slug)

    assert result.returncode == 0, result.stderr
    assert not Path(manifest["worktree"]).exists()


def test_cancel_fails_loudly_when_branch_cannot_be_determined(git_repo: Path):
    result = run_script(git_repo, "cancel", "no-such-slug")

    assert result.returncode != 0
    assert "특정할 수 없다" in result.stderr
    # 예전에는 feat-<slug> 로 추측해 "취소 대상 없음" 이라는 엉뚱한 사유를 냈다.
    assert "feat-no-such-slug" not in result.stderr


def test_guardrails_copy_claude_settings(git_repo: Path):
    """`.claude/` 를 gitignore 하는 repo 가 흔하다 — 그러면 settings.json 이 base 커밋에
    없어서 워크트리 체크아웃에 안 딸려온다. 권한 allowlist 없이 부팅한 워크트리 세션은
    첫 bash 호출부터 프롬프트가 뜨므로 가드레일로 복사해야 한다."""
    (git_repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    task = write_task(git_repo)
    commit_all(git_repo)

    settings = git_repo / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"permissions": {"allow": ["Bash(git status:*)"]}}\n', encoding="utf-8")

    manifest = manifest_from(run_init(git_repo, task))

    assert ".claude/settings.json" in manifest["copied"]
    copied = Path(manifest["worktree"]) / ".claude" / "settings.json"
    assert copied.is_file()
    assert "Bash(git status:*)" in copied.read_text(encoding="utf-8")


# ============================================================================
# finish — 마감 전이 (워크트리 안에서)
#
# 개발 단계에서 문서를 고치는 유일한 경로다. 이 Task 의 진행 표시를 지우고 삭제 예정 줄을 빼고,
# Task 를 in-dev → in-review 로 바꾸고, 카탈로그 2종을 다시 만들어 커밋 1개로 남긴다.
# ============================================================================
def init_worktree(repo: Path, **kwargs) -> tuple[dict, Path]:
    """승인 커밋까지 마친 레포에서 init — (매니페스트, 워크트리)."""
    task = write_task(repo, **kwargs)
    commit_all(repo)
    result = run_init(repo, task)
    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    return manifest, Path(manifest["worktree"])


def dev_commit(wt: Path) -> None:
    """개발 세션이 남기는 슬라이스 커밋 흉내."""
    (wt / "feature.txt").write_text("done\n", encoding="utf-8")
    run_git(wt, "add", "feature.txt")
    run_git(wt, "commit", "-q", "-m", "feat(TSK-001): S1")


def run_finish(wt: Path, *extra: str) -> subprocess.CompletedProcess:
    return run_script(wt, "finish", "--quiet", *extra)


def finish_result(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_finish_clears_marks_and_moves_task_to_in_review(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)

    result = run_finish(wt)

    assert result.returncode == 0, result.stderr
    out = finish_result(result)
    assert (out["task_id"], out["status"], out["already"], out["committed"]) == ("TSK-001", "in-review", False, True)
    assert out["cleared"] == ["Demo-INT-001 FR-2", "Demo-INT-001 FR-3"]
    assert out["deleted"] == ["Demo-INT-001 FR-4", "Demo-INT-001 E-1"]
    assert sorted(out["files"]) == sorted([TASK_REL, TASK_CATALOG_REL, INTENT_REL, CATALOG_REL])
    assert head_commit_files(wt) == sorted(out["files"])
    assert commit_subject(wt) == "chore(TSK-001): 상태 in-review"

    intent = (wt / INTENT_REL).read_text(encoding="utf-8")
    assert "[TSK-001" not in intent
    assert "- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)\n" in intent
    assert "- FR-4." not in intent and "- E-1." not in intent
    assert "### Edge cases\nnone\n\n### Error cases" in intent   # 섹션이 비면 none 을 남긴다
    assert "| 상태 | in-review |" in (wt / TASK_REL).read_text(encoding="utf-8")
    assert "| in-review |" in task_catalog_row((wt / TASK_CATALOG_REL).read_text(encoding="utf-8"))
    assert "| FR 3 · " in catalog_row((wt / CATALOG_REL).read_text(encoding="utf-8"), "Demo-INT-001")

    fails = [f"{r.code}: {r.message}" for r in _dh._check_task_file(wt, wt / TASK_REL) if r.level == "FAIL"]
    assert not fails, fails
    assert _dh.main(["check", "--repo", str(wt), "--app", "Demo"]) == 0
    # 메인 repo 의 문서는 그대로다 — 머지 전까지 승인 상태로 남는다.
    assert "[TSK-001 진행 중]" in (git_repo / INTENT_REL).read_text(encoding="utf-8")


@pytest.mark.parametrize("eol", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_finish_keeps_line_endings_and_other_task_marks(git_repo: Path, eol: str):
    x1 = "`UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)"
    manifest, wt = init_worktree(git_repo, eol=eol, intent={x1: x1 + " [TSK-002 진행 중]"})
    dev_commit(wt)

    result = run_finish(wt)

    assert result.returncode == 0, result.stderr
    intent = (wt / INTENT_REL).read_bytes()
    assert "(FR-1) [TSK-002 진행 중]".encode() in intent, "다른 Task 의 표시는 그 Task 가 지운다"
    assert b"[TSK-001" not in intent
    for rel in (INTENT_REL, TASK_REL):
        data = (wt / rel).read_bytes()
        lf, crlf = data.count(b"\n"), data.count(b"\r\n")
        assert crlf == (lf if eol == "\r\n" else 0), f"{rel}: 줄바꿈이 바뀌면 문서 전체가 diff 가 된다"


def test_finish_refuses_in_main_repo(git_repo: Path):
    init_worktree(git_repo)

    result = run_finish(git_repo)

    assert result.returncode == 2
    assert "워크트리 안에서" in result.stderr


def test_finish_refuses_task_not_in_dev(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    replace_in(wt / TASK_REL, "| 상태 | in-dev |", "| 상태 | approved |")
    run_git(wt, "commit", "-qam", "back to approved")

    result = run_finish(wt)

    assert result.returncode == 2
    assert "in-dev 일 때만" in result.stderr


def test_finish_refuses_staged_changes(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    (wt / "feature.txt").write_text("wip\n", encoding="utf-8")
    run_git(wt, "add", "feature.txt")

    result = run_finish(wt)

    assert result.returncode == 2
    assert "스테이징된 변경" in result.stderr and "feature.txt" in result.stderr
    assert "| 상태 | in-dev |" in (wt / TASK_REL).read_text(encoding="utf-8")


def test_finish_refuses_uncommitted_document_edits(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    replace_in(wt / INTENT_REL, "문제 설명.", "문제 설명을 보강했다.")

    result = run_finish(wt)

    assert result.returncode == 2
    assert "커밋 안 된 변경" in result.stderr and INTENT_REL in result.stderr
    assert "| 상태 | in-dev |" in (wt / TASK_REL).read_text(encoding="utf-8")
    assert "[TSK-001 진행 중]" in (wt / INTENT_REL).read_text(encoding="utf-8")


def test_finish_twice_reports_already(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    assert run_finish(wt).returncode == 0
    commits = run_git(wt, "rev-list", "--count", "HEAD").stdout.strip()

    second = run_finish(wt)

    assert second.returncode == 0, second.stderr
    out = finish_result(second)
    assert (out["status"], out["already"], out["committed"]) == ("in-review", True, False)
    assert run_git(wt, "rev-list", "--count", "HEAD").stdout.strip() == commits


def test_finish_reads_task_id_from_manifest(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    (wt / ".process" / "forge" / "handoff.json").unlink()

    missing = run_finish(wt)

    assert missing.returncode == 2
    assert "매니페스트" in missing.stderr

    main_copy = git_repo / ".process" / "forge" / f"{manifest['slug']}.json"
    result = run_finish(wt, "--manifest", str(main_copy))

    assert result.returncode == 0, result.stderr
    assert finish_result(result)["status"] == "in-review"


def test_clear_task_marks_keeps_other_tasks_and_crlf():
    text = (
        "### Functional requirements\r\n"
        "- FR-1. 가 (D1) [TSK-001 진행 중]\r\n"
        "- FR-2. 나 (D1) [TSK-002 진행 중]\r\n"
        "- FR-3. 다 (D1) [TSK-001 삭제 예정]\r\n"
        "\r\n"
        "### Edge cases\r\n"
        "- E-1. 라 (FR-1) [TSK-001 삭제 예정]\r\n"
        "\r\n"
        "### Error cases\r\n"
        "- X-1. 마 (FR-1) [TSK-002 삭제 예정]\r\n"
    )

    new, cleared, deleted = _ws._clear_task_marks(text, "TSK-001")

    assert (cleared, deleted) == (["FR-1"], ["FR-3", "E-1"])
    assert new == (
        "### Functional requirements\r\n"
        "- FR-1. 가 (D1)\r\n"
        "- FR-2. 나 (D1) [TSK-002 진행 중]\r\n"
        "\r\n"
        "### Edge cases\r\n"
        "none\r\n"
        "\r\n"
        "### Error cases\r\n"
        "- X-1. 마 (FR-1) [TSK-002 삭제 예정]\r\n"
    )


def test_clear_task_marks_ignores_headings_inside_comments():
    """주석 안의 `###` 은 헤딩이 아니다 — 섹션 경계로 보면 남은 항목이 있는데도 none 을 끼워 넣는다."""
    text = (
        "### Edge cases\n"
        "- E-1. 가 (FR-1) [TSK-001 삭제 예정]\n"
        "<!--\n"
        "### 예시\n"
        "-->\n"
        "- E-2. 나 (FR-1)\n"
    )

    new, cleared, deleted = _ws._clear_task_marks(text, "TSK-001")

    assert (cleared, deleted) == ([], ["E-1"])
    assert new == "### Edge cases\n<!--\n### 예시\n-->\n- E-2. 나 (FR-1)\n"


# ============================================================================
# 문서 폴더 대소문자 (docs · Docs)
#
# 레포마다 문서 폴더가 docs 또는 Docs 다 — 둘은 같은 폴더로 봐야 한다. git 은 경로를
# 대소문자 구분으로 비교하므로(`show <ref>:<path>` · pathspec · add) 표기를 하드코딩하면
# Docs 레포에서 카탈로그가 마감 커밋에서 빠지고, 탐색기에서 폴더 이름만 바꿔 디스크와
# 커밋의 표기가 어긋난 레포에서는 커밋된 Intent 를 "마지막 커밋에 없다" 로 막는다.
# Task 는 레포 루트 .task/ 라 표기 문제가 없다 — 대상 Intent 와 INT 카탈로그만 해당한다.
# ============================================================================
def case_insensitive_fs(path: Path) -> bool:
    probe = path / "case-probe"
    probe.mkdir()
    try:
        return (path / "CASE-PROBE").exists()
    finally:
        probe.rmdir()


@pytest.mark.parametrize("docs_dir", ["Docs", "docs"])
def test_either_docs_spelling_through_init_and_finish(git_repo: Path, docs_dir: str):
    """Intent 가 Docs/ · docs/ 어느 쪽에 있어도 in-dev 커밋은 Task 2파일이고, 마감 커밋은 그 표기 그대로
    Intent · INT 카탈로그를 담는다."""
    task = write_task(git_repo, docs_dir=docs_dir)
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    intent_rel = f"{docs_dir}/Demo/INTENT/Demo-INT-001.md"
    assert head_commit_files(wt) == [TASK_REL, TASK_CATALOG_REL]
    assert Path(manifest["intents"][0]["worktree_path"]).relative_to(wt).as_posix() == intent_rel
    assert _dh.main(["check", "--repo", str(wt), "--app", "Demo"]) == 0

    finished = run_finish(wt)

    assert finished.returncode == 0, finished.stderr
    assert head_commit_files(wt) == sorted(
        [TASK_REL, TASK_CATALOG_REL, intent_rel, f"{docs_dir}/Demo/Demo-INT-CATALOG.md"]
    )
    assert _dh.main(["check", "--repo", str(wt), "--app", "Demo"]) == 0


def test_init_when_intent_folder_case_differs_from_commit(git_repo: Path):
    """탐색기에서 docs → Docs 로 이름만 바꾸면 git 은 모른다(core.ignorecase) — 디스크는 Docs,
    커밋은 docs 다. 디스크 표기로 커밋을 찾으면 커밋된 대상 Intent 를 없다고 막는다."""
    if not case_insensitive_fs(git_repo):
        pytest.skip("대소문자 무시 FS(Windows·macOS)에서만 생기는 어긋남")
    task = write_task(git_repo)
    commit_all(git_repo)
    (git_repo / "docs").rename(git_repo / "docs-tmp")
    (git_repo / "docs-tmp").rename(git_repo / "Docs")
    assert run_git(git_repo, "status", "--porcelain").stdout == ""

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert head_commit_files(wt) == [TASK_REL, TASK_CATALOG_REL]
    worktree_intent = Path(manifest["intents"][0]["worktree_path"])
    assert worktree_intent.relative_to(wt).as_posix() == INTENT_REL   # 워크트리는 커밋된 표기로 체크아웃된다
    assert worktree_intent.is_file()


def test_finish_stages_int_catalog_tracked_under_other_spelling(git_repo: Path):
    """index 에 표기가 섞인 레포(Intent 는 Docs/…, 카탈로그는 docs/…) — 카탈로그를 Intent 쪽
    표기로 add 하면 tracked 파일이라 조용히 스테이징되지 않는다. 커밋된 표기로 add 해야 한다."""
    if not case_insensitive_fs(git_repo):
        pytest.skip("대소문자 무시 FS(Windows·macOS)에서만 한 폴더에 두 표기가 공존한다")
    task = write_task(git_repo)
    run_git(git_repo, "add", TASK_REL, TASK_CATALOG_REL, CATALOG_REL)
    run_git(git_repo, "-c", "core.ignorecase=false", "add", "Docs/Demo/INTENT/Demo-INT-001.md")
    run_git(git_repo, "commit", "-q", "-m", "mixed spelling")
    tracked = run_git(git_repo, "ls-files").stdout.split()
    assert "Docs/Demo/INTENT/Demo-INT-001.md" in tracked and CATALOG_REL in tracked
    assert run_git(git_repo, "status", "--porcelain").stdout == ""
    init_result = run_init(git_repo, task)
    assert init_result.returncode == 0, init_result.stderr
    wt = Path(manifest_from(init_result)["worktree"])

    result = run_finish(wt)

    assert result.returncode == 0, result.stderr
    assert head_commit_files(wt) == sorted(
        [TASK_REL, TASK_CATALOG_REL, "Docs/Demo/INTENT/Demo-INT-001.md", CATALOG_REL]
    )


@pytest.mark.parametrize("docs_dir", ["docs", "Docs"])
def test_guardrails_copy_docs_folder_once_in_disk_spelling(git_repo: Path, docs_dir: str):
    """docs·Docs 를 따로 세면 한 폴더가 다른 표기로 보고되거나 '복사' 와 'skip' 에 함께 오른다."""
    (git_repo / ".gitignore").write_text(f"{docs_dir}/local/\n", encoding="utf-8")
    task = write_task(git_repo, docs_dir=docs_dir)
    commit_all(git_repo)
    local = git_repo / docs_dir / "local" / "notes.md"
    local.parent.mkdir(parents=True)
    local.write_text("# local\n", encoding="utf-8")

    manifest = manifest_from(run_init(git_repo, task))

    reported = [e for e in manifest["copied"] + manifest["skipped"] if e.lower() == "docs/"]
    assert reported == [f"{docs_dir}/"]
    wt = Path(manifest["worktree"])
    assert docs_dir in os.listdir(wt)
    assert (wt / docs_dir / "local" / "notes.md").is_file()


def test_refresh_int_catalog_accepts_capital_docs(tmp_path: Path):
    write_intent(tmp_path, docs_dir="Docs")

    rel = _ws._refresh_int_catalog(tmp_path, "Docs/Demo/INTENT/Demo-INT-001.md")

    assert rel == "Docs/Demo/Demo-INT-CATALOG.md"
    assert catalog_row((tmp_path / rel).read_text(encoding="utf-8"), "Demo-INT-001")
