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
    run_git(tmp_path, "config", "user.email", "worktree-test@example.invalid")
    run_git(tmp_path, "config", "user.name", "Worktree Test")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# Test repo\n", encoding="utf-8")
    run_git(tmp_path, "add", "README.md")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


TASK_REL = ".task/TSK-001.md"
TASK_CATALOG_REL = ".task/task-catalog.md"
INTENT_REL = "docs/Demo/INTENT/Demo-INT-001.md"
CATALOG_REL = "docs/Demo/Demo-INT-CATALOG.md"

# 대상 Intent — 기능 문서(상시). TSK-001 이 바꾸는 항목 끝에 진행 표시가 붙어 있다
# (신규 · 변경 = 진행 중, 삭제 = 삭제 예정). FR 삭제가 있어서 done 뒤 INT 카탈로그의 규모(FR 수)가 바뀐다.
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
| 선행 Task | none |
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
| repo · app | worktree-test · Demo |
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
    """/task-split 이 승인 뒤에 하듯 생성물 두 개를 다시 만든다."""
    assert _dh.main(["intent-catalog", "--repo", str(repo), "--app", "Demo", "--write"]) == 0
    assert _dh.main(["task-catalog", "--repo", str(repo), "--write"]) == 0


def write_task(
    repo: Path,
    status: str = "approved",
    docs_dir: str = "docs",
    eol: str = "\n",
    intent: dict | None = None,
    catalogs: bool = True,
    task_id: str = "TSK-001",
    **rows: str,
) -> Path:
    """Task(.task/<task_id>.md) + 대상 Intent (+ 카탈로그 2종). 커밋하지 않는다 — 문서는 로컬 정본이다.

    rows 는 메타 · Handoff 행 값, intent 는 Intent 본문 str.replace 쌍.
    """
    write_intent(repo, docs_dir=docs_dir, eol=eol, replace=intent)
    text = _meta_row(TASK_TEXT, "상태", status).replace("TSK-001", task_id)
    for key, value in rows.items():
        text = _meta_row(text, key, value)
    task = _write(repo / ".task" / f"{task_id}.md", text, eol)
    if catalogs:
        write_catalogs(repo)
    return task


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_bytes().decode("utf-8")
    assert old in text, old
    path.write_bytes(text.replace(old, new, 1).encode("utf-8"))


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


def run_init(repo: Path, name: str = "upload", *extra: str) -> subprocess.CompletedProcess:
    return run_script(repo, "init", name, "--quiet", *extra)


def manifest_from(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def main_manifest(repo: Path, slug: str = "upload") -> dict:
    return json.loads((repo / ".process" / "worktree" / f"{slug}.json").read_text(encoding="utf-8"))


def task_catalog_row(text: str, task_id: str = "TSK-001") -> str:
    return next((line for line in text.splitlines() if line.startswith(f"| [{task_id}](")), "")


def catalog_row(text: str, intent_id: str) -> str:
    """INT 카탈로그 본문에서 해당 Intent 의 행 1줄을 뽑는다 (없으면 빈 문자열)."""
    for line in text.splitlines():
        if line.startswith(f"| [{intent_id}](INTENT/"):
            return line
    return ""


def current_branch(repo: Path) -> str:
    return run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def branch_exists(repo: Path, branch: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo, capture_output=True, text=True,
    ).returncode == 0


def status_row(path: Path) -> str:
    return next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("| 상태 |"))


def test_approved_task_fixture_is_clean(tmp_path: Path):
    task = write_task(tmp_path)
    results = _dh._check_task_file(tmp_path, task)
    bad = [f"{r.level} {r.code}: {r.message}" for r in results if r.level != "PASS"]
    assert not bad, bad
    assert _dh.main(["check", "--repo", str(tmp_path), "--app", "Demo"]) == 0


# ============================================================================
# init — 이름 하나로 워크트리만 만든다 (Task 를 읽지 않는다)
# ============================================================================
def test_init_creates_worktree_on_work_branch(git_repo: Path):
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()

    result = run_init(git_repo)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert wt == git_repo / ".worktree" / "upload"
    assert wt.is_dir()
    assert manifest["branch"] == "work/upload"
    assert current_branch(wt) == "work/upload"
    assert manifest["base"] == current_branch(git_repo)   # --base 가 없으면 그때의 현재 브랜치
    assert manifest["base_commit"] == head
    assert (manifest["created"], manifest["base_applied"], manifest["tasks"]) == (True, True, [])


def test_init_does_not_need_any_task(git_repo: Path):
    """Task · 문서가 하나도 없어도 만든다 — 어떤 Task 를 개발할지는 개발 세션 프롬프트가 정한다."""
    result = run_init(git_repo)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert "docs/" in manifest["skipped"] and ".task/" in manifest["skipped"]


def test_init_branch_option_overrides_default(git_repo: Path):
    result = run_init(git_repo, "upload", "--branch", "feat/upload-retry")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["branch"] == "feat/upload-retry"
    assert manifest["slug"] == "upload"
    assert current_branch(Path(manifest["worktree"])) == "feat/upload-retry"


def test_init_rejects_name_without_usable_characters(git_repo: Path):
    result = run_init(git_repo, "업로드")

    assert result.returncode == 1
    assert "폴더 이름을 만들 수 없다" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_rejects_invalid_branch_name(git_repo: Path):
    result = run_init(git_repo, "upload", "--branch", "bad..name")

    assert result.returncode == 1
    assert "브랜치 이름" in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_zero_commit_repo_blocks_with_and_without_force(tmp_path: Path):
    run_git(tmp_path, "init", "-q")

    for extra in ((), ("--force",)):
        result = run_init(tmp_path, "upload", *extra)
        assert result.returncode == 2, result.stderr
        assert "커밋이 하나도 없다" in result.stderr
    assert not (tmp_path / ".worktree").exists()


def test_init_puts_docs_in_local_exclude(git_repo: Path):
    """문서 폴더 · .task/ 는 커밋하지 않는다 — 공유 .gitignore 대신 이 clone 의 info/exclude 에 올린다."""
    write_task(git_repo)

    result = run_init(git_repo)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    exclude = Path(manifest["exclude"])
    assert exclude.resolve() == (git_repo / ".git" / "info" / "exclude").resolve()
    lines = exclude.read_text(encoding="utf-8").splitlines()
    for entry in (".worktree/", ".process/", "/docs/", "/Docs/", "/.task/"):
        assert entry in lines
    assert manifest["exclude_added"]
    assert not (git_repo / ".gitignore").exists(), "공유 .gitignore 를 만들거나 고치지 않는다"
    assert run_git(git_repo, "status", "--porcelain").stdout == ""
    wt = Path(manifest["worktree"])
    run_git(wt, "add", "-A")   # 워크트리의 문서 사본도 같은 exclude 로 숨는다
    assert run_git(wt, "diff", "--cached", "--name-only").stdout == ""


def test_init_copies_docs_and_tasks_as_snapshot(git_repo: Path):
    task = write_task(git_repo)

    manifest = manifest_from(run_init(git_repo))

    wt = Path(manifest["worktree"])
    assert "docs/" in manifest["copied"] and ".task/" in manifest["copied"]
    for rel in (TASK_REL, TASK_CATALOG_REL, INTENT_REL, CATALOG_REL):
        assert (wt / rel).read_bytes() == (git_repo / rel).read_bytes(), rel
    for rel in ("docs", ".task"):
        assert not _ws._is_dir_link(wt / rel), "링크는 worktree remove --force 때 정본을 지운다 — 복사해야 한다"
    replace_in(task, "| 상태 | approved |", "| 상태 | in-review |")
    assert "| 상태 | approved |" in (wt / TASK_REL).read_text(encoding="utf-8"), "사본은 정본을 따라가지 않는다"


def test_second_init_resumes_keeps_tasks_and_copies_only_new_files(git_repo: Path):
    write_task(git_repo)
    first = manifest_from(run_init(git_repo))
    wt = Path(first["worktree"])
    recorded = main_manifest(git_repo)
    recorded["tasks"] = ["TSK-001"]   # finish 가 남긴 것처럼
    (git_repo / ".process" / "worktree" / "upload.json").write_text(json.dumps(recorded), encoding="utf-8")
    replace_in(git_repo / TASK_REL, "업로드 응답 정리", "업로드 응답 정리 (고침)")
    write_task(git_repo, task_id="TSK-002", catalogs=False)
    run_git(git_repo, "commit", "-q", "--allow-empty", "-m", "moved on")

    second = run_init(git_repo)

    assert second.returncode == 0, second.stderr
    manifest = manifest_from(second)
    assert (manifest["created"], manifest["base_applied"]) == (False, False)
    assert manifest["tasks"] == ["TSK-001"]
    assert (manifest["base"], manifest["base_commit"]) == (first["base"], first["base_commit"])
    assert (wt / ".task" / "TSK-002.md").is_file(), "새로 생긴 Task 파일은 복사된다"
    assert "(고침)" not in (wt / TASK_REL).read_text(encoding="utf-8"), "있는 파일은 덮지 않는다"


def test_init_new_branch_ignores_stale_manifest_tasks(git_repo: Path):
    """워크트리 · 브랜치를 손으로 지워 같은 이름의 옛 매니페스트만 남았어도, 새 브랜치는 그 tasks 를 잇지 않는다 —
    이으면 이 브랜치의 머지로 머지된 적 없는 Task 가 done 이 된다."""
    stale = git_repo / ".process" / "worktree" / "upload.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps({"slug": "upload", "branch": "work/upload", "base": "old-base",
                                 "base_commit": "0" * 40, "tasks": ["TSK-001"]}), encoding="utf-8")

    manifest = manifest_from(run_init(git_repo))

    assert manifest["base_applied"] is True
    assert manifest["tasks"] == []
    assert manifest["base"] == current_branch(git_repo)
    assert main_manifest(git_repo)["tasks"] == []


def test_init_dirty_main_blocks_unless_forced(git_repo: Path):
    (git_repo / "README.md").write_text("# changed\n", encoding="utf-8")

    blocked = run_init(git_repo)

    assert blocked.returncode == 1
    assert "dirty" in blocked.stderr and "README.md" in blocked.stderr
    assert not (git_repo / ".worktree" / "upload").exists()
    assert run_init(git_repo, "upload", "--force").returncode == 0


def test_tracked_docs_are_reported_not_blocking(git_repo: Path):
    """이미 커밋된 문서(정책 이전 레포)는 exclude 로 숨지 않는다 — 막지 않고 알린다."""
    write_task(git_repo)
    run_git(git_repo, "add", "-f", INTENT_REL)
    run_git(git_repo, "commit", "-q", "-m", "legacy: tracked intent")
    replace_in(git_repo / INTENT_REL, "문제 설명.", "문제 설명을 보강했다.")

    result = run_init(git_repo)

    assert result.returncode == 0, result.stderr
    assert manifest_from(result)["tracked_docs"] == [INTENT_REL]


def test_branch_attached_elsewhere_points_to_other_name(git_repo: Path, tmp_path: Path):
    run_git(git_repo, "worktree", "add", "-q", "-b", "work/upload", str(tmp_path / "elsewhere"))

    result = run_init(git_repo)

    assert result.returncode == 1
    assert "git worktree remove" in result.stderr
    assert "--branch" in result.stderr


MANIFEST_KEYS = {
    "root", "worktree", "branch", "base", "base_commit", "base_applied", "slug", "created", "tasks",
    "copied", "skipped", "submodule_log", "exclude", "exclude_added", "tracked_docs", "manifests",
}


def test_manifest_shape(git_repo: Path):
    write_task(git_repo)

    manifest = manifest_from(run_init(git_repo))

    assert set(manifest) == MANIFEST_KEYS
    for gone in ("task", "task_id", "intents", "scope", "acceptance", "handoff", "status"):
        assert gone not in manifest, "init 은 Task 를 읽지 않는다"


def test_init_writes_manifest_to_worktree_and_main(git_repo: Path):
    manifest = manifest_from(run_init(git_repo))

    wt_manifest = Path(manifest["worktree"]) / ".process" / "worktree" / "handoff.json"
    main_copy = git_repo / ".process" / "worktree" / "upload.json"
    assert wt_manifest.is_file(), "워크트리 인수인계 사본이 없다"
    assert main_copy.is_file(), "메인 repo 조회용 사본이 없다"
    a = json.loads(wt_manifest.read_text(encoding="utf-8"))
    b = json.loads(main_copy.read_text(encoding="utf-8"))
    assert a == b
    assert a["branch"] == manifest["branch"] == "work/upload"
    assert sorted(manifest["manifests"]) == sorted([str(wt_manifest), str(main_copy)])


def test_init_leaves_main_gitignore_untouched(git_repo: Path):
    (git_repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    run_git(git_repo, "add", ".gitignore")
    run_git(git_repo, "commit", "-q", "-m", "gitignore")
    before = (git_repo / ".gitignore").read_text(encoding="utf-8")
    write_task(git_repo)

    assert run_init(git_repo).returncode == 0
    assert (git_repo / ".gitignore").read_text(encoding="utf-8") == before
    assert run_git(git_repo, "status", "--porcelain").stdout == ""

    second = run_init(git_repo)   # resume 도 dirty 로 막히지 않는다
    assert second.returncode == 0, second.stderr


def test_guardrails_copy_claude_settings(git_repo: Path):
    """`.claude/` 를 gitignore 하는 repo 가 흔하다 — 그러면 settings.json 이 base 커밋에
    없어서 워크트리 체크아웃에 안 딸려온다. 권한 allowlist 없이 부팅한 워크트리 세션은
    첫 bash 호출부터 프롬프트가 뜨므로 가드레일로 복사해야 한다."""
    (git_repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    run_git(git_repo, "add", ".gitignore")
    run_git(git_repo, "commit", "-q", "-m", "gitignore")
    settings = git_repo / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"permissions": {"allow": ["Bash(git status:*)"]}}\n', encoding="utf-8")

    manifest = manifest_from(run_init(git_repo))

    assert ".claude/settings.json" in manifest["copied"]
    copied = Path(manifest["worktree"]) / ".claude" / "settings.json"
    assert "Bash(git status:*)" in copied.read_text(encoding="utf-8")


@pytest.mark.parametrize("docs_dir", ["docs", "Docs"])
def test_guardrails_copy_docs_folder_once_in_disk_spelling(git_repo: Path, docs_dir: str):
    """docs·Docs 를 따로 세면 한 폴더가 다른 표기로 보고되거나 '복사' 와 'skip' 에 함께 오른다."""
    write_task(git_repo, docs_dir=docs_dir)
    local = git_repo / docs_dir / "local" / "notes.md"
    local.parent.mkdir(parents=True)
    local.write_text("# local\n", encoding="utf-8")

    manifest = manifest_from(run_init(git_repo))

    reported = [e for e in manifest["copied"] + manifest["skipped"] if e.lower() == "docs/"]
    assert reported == [f"{docs_dir}/"]
    wt = Path(manifest["worktree"])
    assert docs_dir in os.listdir(wt)
    assert (wt / docs_dir / "local" / "notes.md").is_file()


# ============================================================================
# base 브랜치 선택 (branches 서브커맨드 · init --base)
# ============================================================================
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
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()
    main = current_branch(git_repo)
    run_git(git_repo, "update-ref", f"refs/remotes/origin/{main}", head)

    refs = [c["ref"] for c in branches_of(run_script(git_repo, "branches"))["candidates"]]

    assert main in refs
    assert f"origin/{main}" not in refs


def test_branches_puts_current_branch_first(git_repo: Path):
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")   # 더 최근 커밋

    data = branches_of(run_script(git_repo, "branches"))

    assert data["current"] == current_branch(git_repo)
    assert data["candidates"][0]["ref"] == data["current"]
    assert data["candidates"][0]["is_current"] is True
    assert set(data) == {"current", "target_branch", "target_branch_exists", "candidates"}


def test_branches_reports_target_branch(git_repo: Path):
    assert branches_of(run_script(git_repo, "branches"))["target_branch"] == ""
    data = branches_of(run_script(git_repo, "branches", "--name", "upload"))
    assert (data["target_branch"], data["target_branch_exists"]) == ("work/upload", False)

    run_git(git_repo, "branch", "work/upload")

    assert branches_of(run_script(git_repo, "branches", "--name", "upload"))["target_branch_exists"] is True
    custom = branches_of(run_script(git_repo, "branches", "--branch", "feat/x"))
    assert (custom["target_branch"], custom["target_branch_exists"]) == ("feat/x", False)


def test_branches_is_read_only(git_repo: Path):
    before = (
        run_git(git_repo, "status", "--porcelain").stdout,
        run_git(git_repo, "worktree", "list", "--porcelain").stdout,
        run_git(git_repo, "rev-parse", "HEAD").stdout,
    )

    assert run_script(git_repo, "branches", "--name", "upload").returncode == 0

    after = (
        run_git(git_repo, "status", "--porcelain").stdout,
        run_git(git_repo, "worktree", "list", "--porcelain").stdout,
        run_git(git_repo, "rev-parse", "HEAD").stdout,
    )
    assert before == after


def test_init_base_forks_selected_branch(git_repo: Path):
    develop_sha = make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")

    result = run_init(git_repo, "upload", "--base", "develop")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    wt = Path(manifest["worktree"])
    assert (wt / "develop-only.txt").exists()
    assert (manifest["base"], manifest["base_commit"], manifest["base_applied"]) == ("develop", develop_sha, True)
    probe = subprocess.run(["git", "merge-base", "--is-ancestor", "develop", "HEAD"], cwd=wt, capture_output=True)
    assert probe.returncode == 0


def test_init_without_base_forks_head(git_repo: Path):
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")

    manifest = manifest_from(run_init(git_repo))

    assert manifest["base"] == current_branch(git_repo)
    assert not (Path(manifest["worktree"]) / "develop-only.txt").exists()


@pytest.mark.parametrize("ref", ["no-such-branch", "a|b"])
def test_init_base_unknown_ref_exits_1(git_repo: Path, ref: str):
    result = run_init(git_repo, "upload", "--base", ref)

    assert result.returncode == 1, result.stderr
    assert ref in result.stderr
    assert not (git_repo / ".worktree").exists()


def test_init_existing_branch_ignores_base(git_repo: Path):
    make_branch_with_extra_commit(git_repo, "develop", "develop-only.txt")
    run_git(git_repo, "branch", "work/upload")   # 브랜치 선점

    result = run_init(git_repo, "upload", "--base", "develop")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert (manifest["base"], manifest["base_applied"]) == ("develop", False)
    assert not (Path(manifest["worktree"]) / "develop-only.txt").exists()


def test_init_remote_base_has_no_upstream(git_repo: Path):
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()
    run_git(git_repo, "update-ref", "refs/remotes/origin/poc", head)

    result = run_init(git_repo, "upload", "--base", "origin/poc")

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["base_applied"] is True
    probe = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=Path(manifest["worktree"]), capture_output=True, text=True,
    )
    assert probe.returncode != 0, "--no-track 이 적용돼 upstream 이 없어야 한다"


# ============================================================================
# list · cwd 독립성
# ============================================================================
def test_list_includes_manifest_worktrees(git_repo: Path):
    assert run_init(git_repo).returncode == 0

    result = run_script(git_repo, "list")

    assert result.returncode == 0, result.stderr
    [entry] = json.loads(result.stdout.strip())
    assert (entry["slug"], entry["branch"], entry["tasks"], entry["source"]) == ("upload", "work/upload", [], "manifest")
    assert entry["base"] == current_branch(git_repo)


def test_list_scan_fallback_finds_worktree_without_manifest(git_repo: Path):
    """메인 매니페스트를 잃어도 .worktree/ 바로 아래 워크트리는 목록에 오른다 — 브랜치 이름과 무관하다."""
    run_init(git_repo, "upload", "--branch", "feat/custom")
    (git_repo / ".process" / "worktree" / "upload.json").unlink()

    entries = json.loads(run_script(git_repo, "list").stdout.strip())

    assert [(e["slug"], e["branch"], e["source"]) for e in entries] == [("upload", "feat/custom", "scan")]


def test_repo_root_resolves_main_repo_from_inside_worktree(git_repo: Path):
    worktree = Path(manifest_from(run_init(git_repo))["worktree"])

    # --show-toplevel 이면 워크트리 자신을 돌려줘 .worktree/<slug> 계산이 어긋난다.
    assert _ws._repo_root(worktree).resolve() == git_repo.resolve()
    assert _ws._repo_root(git_repo).resolve() == git_repo.resolve()


def test_list_works_from_inside_worktree(git_repo: Path):
    worktree = Path(manifest_from(run_init(git_repo))["worktree"])

    entries = json.loads(run_script(worktree, "list").stdout.strip())

    assert [(e["branch"], e["source"]) for e in entries] == [("work/upload", "manifest")]


# ============================================================================
# finish — 마감 (워크트리 안에서). 메인 정본 Task approved → in-review, 커밋 없음
# ============================================================================
def init_worktree(repo: Path, name: str = "upload", *extra: str, **task_kwargs) -> tuple[dict, Path]:
    """로컬 정본 문서(Task + Intent + 카탈로그)를 둔 레포에서 init — (매니페스트, 워크트리)."""
    write_task(repo, **task_kwargs)
    result = run_init(repo, name, *extra)
    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    return manifest, Path(manifest["worktree"])


def dev_commit(wt: Path, name: str = "feature.txt") -> None:
    """개발 세션이 남기는 개발 커밋 흉내."""
    (wt / name).write_text("done\n", encoding="utf-8")
    run_git(wt, "add", name)
    run_git(wt, "commit", "-q", "-m", f"feat: {name}")


def run_finish(wt: Path, *task_ids: str) -> subprocess.CompletedProcess:
    return run_script(wt, "finish", *(task_ids or ("TSK-001",)), "--quiet")


def finish_result(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_finish_moves_main_task_to_in_review_without_commit(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    commits = run_git(wt, "rev-list", "--count", "HEAD").stdout.strip()

    result = run_finish(wt)

    assert result.returncode == 0, result.stderr
    out = finish_result(result)
    assert out["tasks"] == [{"id": "TSK-001", "status": "in-review", "already": False}]
    assert out["catalog"] == TASK_CATALOG_REL
    assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"
    assert "| in-review |" in task_catalog_row((git_repo / TASK_CATALOG_REL).read_text(encoding="utf-8"))
    assert main_manifest(git_repo)["tasks"] == ["TSK-001"]
    assert run_git(wt, "rev-list", "--count", "HEAD").stdout.strip() == commits, "문서는 커밋하지 않는다"
    # 진행 표시는 머지를 확인한 delete 가 지운다 — 마감은 리뷰 전이라 남는다.
    assert "[TSK-001 진행 중]" in (git_repo / INTENT_REL).read_text(encoding="utf-8")
    assert status_row(wt / TASK_REL) == "| 상태 | approved |", "워크트리 사본은 스냅샷이라 따라가지 않는다"
    fails = [f"{r.code}: {r.message}" for r in _dh._check_task_file(git_repo, git_repo / TASK_REL) if r.level == "FAIL"]
    assert not fails, fails
    assert _dh.main(["check", "--repo", str(git_repo), "--app", "Demo"]) == 0


def test_finish_keeps_main_task_line_endings(git_repo: Path):
    manifest, wt = init_worktree(git_repo, eol="\r\n")
    dev_commit(wt)

    assert run_finish(wt).returncode == 0

    data = (git_repo / TASK_REL).read_bytes()
    assert data.count(b"\r\n") == data.count(b"\n"), "줄바꿈이 바뀌면 문서 전체가 diff 가 된다"
    assert "| 상태 | in-review |\r\n".encode() in data


def test_finish_several_tasks_at_once(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    write_task(git_repo, task_id="TSK-002", catalogs=False)
    dev_commit(wt)

    result = run_finish(wt, "TSK-002", "TSK-001", "TSK-002")

    assert result.returncode == 0, result.stderr
    assert [t["id"] for t in finish_result(result)["tasks"]] == ["TSK-002", "TSK-001"]
    assert main_manifest(git_repo)["tasks"] == ["TSK-002", "TSK-001"]
    for task_id in ("TSK-001", "TSK-002"):
        assert status_row(git_repo / ".task" / f"{task_id}.md") == "| 상태 | in-review |"


def test_finish_writes_nothing_when_one_task_cannot_change(git_repo: Path):
    """둘째 Task 의 상태 행을 못 바꾸면 첫째도 바꾸지 않는다 — 반쯤 마감하면 다시 실행해도 풀 수 없다."""
    manifest, wt = init_worktree(git_repo)
    second = write_task(git_repo, task_id="TSK-002", catalogs=False)
    replace_in(second, "| 상태 | approved |", "  | 상태 | approved |")   # 파서는 읽지만 고쳐 쓰지 못한다
    dev_commit(wt)

    result = run_finish(wt, "TSK-001", "TSK-002")

    assert result.returncode == 1
    assert "아무 Task 도 바꾸지 않았다" in result.stderr
    assert status_row(git_repo / TASK_REL) == "| 상태 | approved |"
    assert main_manifest(git_repo)["tasks"] == []


def test_finish_refuses_in_main_repo(git_repo: Path):
    init_worktree(git_repo)

    result = run_finish(git_repo)

    assert result.returncode == 2
    assert "워크트리 안에서" in result.stderr


def test_finish_refuses_without_dev_commit(git_repo: Path):
    manifest, wt = init_worktree(git_repo)

    result = run_finish(wt)

    assert result.returncode == 2
    assert "개발 커밋이 없다" in result.stderr
    assert status_row(git_repo / TASK_REL) == "| 상태 | approved |"


@pytest.mark.parametrize("change", ["tracked", "untracked"])
def test_finish_refuses_uncommitted_changes(git_repo: Path, change: str):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    if change == "tracked":
        (wt / "README.md").write_text("# wip\n", encoding="utf-8")
    else:
        (wt / "wip.txt").write_text("wip\n", encoding="utf-8")

    result = run_finish(wt)

    assert result.returncode == 2
    assert "커밋 안 된 변경" in result.stderr
    assert ("README.md" if change == "tracked" else "wip.txt") in result.stderr
    assert status_row(git_repo / TASK_REL) == "| 상태 | approved |"


def test_finish_ignores_copied_guardrails(git_repo: Path):
    """init 이 복사해 넣은 untracked 가드레일(CLAUDE.md)은 개발 변경이 아니다."""
    (git_repo / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")   # 메인에서도 untracked
    manifest, wt = init_worktree(git_repo, "upload", "--force")
    assert "CLAUDE.md" in manifest["copied"]
    dev_commit(wt)

    result = run_finish(wt)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("status", ["draft", "done", "dropped"])
def test_finish_refuses_task_not_approved(git_repo: Path, status: str):
    manifest, wt = init_worktree(git_repo)
    replace_in(git_repo / TASK_REL, "| 상태 | approved |", f"| 상태 | {status} |")
    dev_commit(wt)

    result = run_finish(wt)

    assert result.returncode == 2
    assert "approved 일 때만" in result.stderr and status in result.stderr
    assert main_manifest(git_repo)["tasks"] == []


@pytest.mark.parametrize("task_id, message", [("TSK-009", "메인 정본에 없다"), ("TSK-1", "형식")])
def test_finish_refuses_unknown_or_malformed_task(git_repo: Path, task_id: str, message: str):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)

    result = run_finish(wt, task_id)

    assert result.returncode == 2
    assert message in result.stderr


def test_finish_twice_reports_already(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    assert run_finish(wt).returncode == 0

    second = run_finish(wt)

    assert second.returncode == 0, second.stderr
    assert finish_result(second)["tasks"] == [{"id": "TSK-001", "status": "in-review", "already": True}]
    assert main_manifest(git_repo)["tasks"] == ["TSK-001"]


def test_finish_refuses_task_finished_in_other_worktree(git_repo: Path):
    """다른 워크트리가 마감한 Task 를 이 워크트리에 기록하면 이 워크트리의 머지로 done 이 된다 —
    개발 커밋이 없는 빈 워크트리는 머지 게이트를 저절로 통과하므로 더 위험하다."""
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    assert run_finish(wt).returncode == 0
    other = Path(manifest_from(run_init(git_repo, "other"))["worktree"])

    result = run_finish(other)

    assert result.returncode == 2
    assert "다른 워크트리" in result.stderr
    assert main_manifest(git_repo, "other")["tasks"] == []


def test_finish_finds_main_manifest_by_worktree_path(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    (wt / ".process" / "worktree" / "handoff.json").unlink()

    assert run_finish(wt).returncode == 0
    assert main_manifest(git_repo)["tasks"] == ["TSK-001"]


def test_finish_without_any_manifest_blocks(git_repo: Path):
    manifest, wt = init_worktree(git_repo)
    dev_commit(wt)
    (wt / ".process" / "worktree" / "handoff.json").unlink()
    (git_repo / ".process" / "worktree" / "upload.json").unlink()

    result = run_finish(wt)

    assert result.returncode == 2
    assert "매니페스트" in result.stderr


# ============================================================================
# delete — 안전 게이트 · done 전이 · 정리 (메인 repo 에서)
# ============================================================================
def finished_worktree(repo: Path, **task_kwargs) -> tuple[dict, Path]:
    """init → 개발 커밋 → finish 까지 마친 워크트리."""
    manifest, wt = init_worktree(repo, **task_kwargs)
    dev_commit(wt)
    result = run_finish(wt)
    assert result.returncode == 0, result.stderr
    return manifest, wt


def merge(repo: Path, branch: str = "work/upload") -> None:
    run_git(repo, "merge", "--no-ff", "-q", "-m", f"merge {branch}", branch)


def run_delete(repo: Path, *extra: str) -> subprocess.CompletedProcess:
    return run_script(repo, "delete", "upload", *extra)


def test_delete_blocks_unmerged_branch(git_repo: Path):
    manifest, wt = finished_worktree(git_repo)

    result = run_delete(git_repo)

    assert result.returncode == 2
    assert "머지되지 않았다" in result.stderr and "--merged" in result.stderr and "--force" in result.stderr
    assert wt.is_dir() and branch_exists(git_repo, "work/upload")
    assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"


def test_delete_blocks_uncommitted_changes(git_repo: Path):
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    (wt / "wip.txt").write_text("wip\n", encoding="utf-8")

    result = run_delete(git_repo)

    assert result.returncode == 2
    assert "커밋 안 된 변경" in result.stderr and "wip.txt" in result.stderr
    assert wt.is_dir()


def test_delete_gate_ignores_guardrail_copies_but_not_new_claude_files(git_repo: Path):
    """init 이 복사한 가드레일 사본은 잃을 것이 아니지만, 개발 세션이 .claude/ 에 새로 만든 파일은 잃는다."""
    settings = git_repo / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}\n", encoding="utf-8")   # 메인에서도 untracked — 그래서 init 은 --force
    manifest, wt = init_worktree(git_repo, "upload", "--force")
    assert ".claude/settings.json" in manifest["copied"]
    (wt / ".claude" / "notes.md").write_text("session notes\n", encoding="utf-8")

    blocked = run_delete(git_repo)

    assert blocked.returncode == 2
    assert ".claude/notes.md" in blocked.stderr
    assert ".claude/settings.json" not in blocked.stderr
    (wt / ".claude" / "notes.md").unlink()
    (wt / ".claude" / "settings.json").write_text('{"edited": true}\n', encoding="utf-8")   # 고친 사본은 잃는 변경이다

    edited = run_delete(git_repo)

    assert edited.returncode == 2
    assert ".claude/settings.json" in edited.stderr
    (wt / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    assert run_delete(git_repo).returncode == 0


def test_delete_after_merge_closes_finished_tasks(git_repo: Path):
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert f"merged into:      {current_branch(git_repo)}" in result.stdout
    assert "TSK-001 done (Demo-INT-001: 표시 2 · 삭제 줄 2)" in result.stdout
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
    intent = (git_repo / INTENT_REL).read_text(encoding="utf-8")
    assert "[TSK-001" not in intent
    assert "- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)\n" in intent
    assert "- FR-4." not in intent and "- E-1." not in intent
    assert "### Edge cases\nnone\n\n### Error cases" in intent   # 섹션이 비면 none 을 남긴다
    assert "| done |" in task_catalog_row((git_repo / TASK_CATALOG_REL).read_text(encoding="utf-8"))
    assert "| FR 3 · " in catalog_row((git_repo / CATALOG_REL).read_text(encoding="utf-8"), "Demo-INT-001")
    fails = [f"{r.code}: {r.message}" for r in _dh._check_task_file(git_repo, git_repo / TASK_REL) if r.level == "FAIL"]
    assert not fails, fails
    assert _dh.main(["check", "--repo", str(git_repo), "--app", "Demo"]) == 0
    assert not wt.exists() and not branch_exists(git_repo, "work/upload")
    assert not (git_repo / ".process" / "worktree" / "upload.json").exists()
    assert run_git(git_repo, "status", "--porcelain").stdout == ""


@pytest.mark.parametrize("eol", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_delete_keeps_line_endings_and_other_task_marks(git_repo: Path, eol: str):
    x1 = "`UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)"
    manifest, wt = finished_worktree(git_repo, eol=eol, intent={x1: x1 + " [TSK-002 진행 중]"})
    merge(git_repo)

    assert run_delete(git_repo).returncode == 0

    intent = (git_repo / INTENT_REL).read_bytes()
    assert "(FR-1) [TSK-002 진행 중]".encode() in intent, "다른 Task 의 표시는 그 Task 가 지운다"
    assert b"[TSK-001" not in intent
    for rel in (INTENT_REL, TASK_REL):
        data = (git_repo / rel).read_bytes()
        lf, crlf = data.count(b"\n"), data.count(b"\r\n")
        assert crlf == (lf if eol == "\r\n" else 0), f"{rel}: 줄바꿈이 바뀌면 문서 전체가 diff 가 된다"


def test_delete_merged_flag_closes_tasks_without_ancestry(git_repo: Path):
    """squash 머지는 조상 검사로 안 잡힌다 — 사용자가 --merged 로 확인해 준다."""
    manifest, wt = finished_worktree(git_repo)
    run_git(git_repo, "merge", "--squash", "-q", "work/upload")
    run_git(git_repo, "commit", "-q", "-m", "squash work/upload")
    assert run_delete(git_repo).returncode == 2

    result = run_delete(git_repo, "--merged")

    assert result.returncode == 0, result.stderr
    assert "--merged (사용자 확인)" in result.stdout
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
    assert not branch_exists(git_repo, "work/upload")


def test_delete_force_discards_without_touching_docs(git_repo: Path):
    manifest, wt = finished_worktree(git_repo)
    (wt / "wip.txt").write_text("wip\n", encoding="utf-8")
    intent_before = (git_repo / INTENT_REL).read_bytes()

    result = run_delete(git_repo, "--force")

    assert result.returncode == 0, result.stderr
    assert "task 그대로:      TSK-001" in result.stdout
    assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"
    assert (git_repo / INTENT_REL).read_bytes() == intent_before
    assert not wt.exists() and not branch_exists(git_repo, "work/upload")


def test_delete_fresh_worktree_without_commits(git_repo: Path):
    """개발 커밋이 없으면 잃을 것이 없다 — 머지 게이트를 그대로 통과한다(브랜치 끝 = base)."""
    manifest = manifest_from(run_init(git_repo))

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert not Path(manifest["worktree"]).exists()
    assert "task" not in result.stdout.replace("worktree", "")


def test_delete_remote_base_also_checks_same_named_local_branch(git_repo: Path):
    """base 가 origin/poc 라도 로컬 poc 에 머지하고 아직 푸시하지 않았으면 머지된 것으로 본다."""
    head = run_git(git_repo, "rev-parse", "HEAD").stdout.strip()
    run_git(git_repo, "update-ref", "refs/remotes/origin/poc", head)
    run_git(git_repo, "branch", "poc")
    manifest, wt = init_worktree(git_repo, "upload", "--base", "origin/poc")
    dev_commit(wt)
    assert run_finish(wt).returncode == 0
    origin_branch = current_branch(git_repo)
    run_git(git_repo, "checkout", "-q", "poc")
    merge(git_repo)
    run_git(git_repo, "checkout", "-q", origin_branch)

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert "merged into:      poc" in result.stdout
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"


def test_delete_skips_recorded_task_that_is_not_in_review(git_repo: Path):
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    replace_in(git_repo / TASK_REL, "| 상태 | in-review |", "| 상태 | approved |")   # 리뷰에서 돌려보냈다

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert "task skip:        TSK-001 (approved — 마감하지 않았다)" in result.stdout
    assert "[TSK-001 진행 중]" in (git_repo / INTENT_REL).read_text(encoding="utf-8")


def test_delete_stops_before_removing_anything_when_status_row_cannot_change(git_repo: Path):
    """done 으로 못 바꾼 채 워크트리 · 매니페스트를 지우면 Task ID 기록이 사라져 다시 할 수 없다 — 먼저 멈춘다."""
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    replace_in(git_repo / TASK_REL, "| 상태 | in-review |", "  | 상태 | in-review |")   # 파서는 읽지만 고쳐 쓰지 못한다

    blocked = run_delete(git_repo)

    assert blocked.returncode == 2
    assert "상태 행을 done 으로 바꾸지 못했다" in blocked.stderr
    assert wt.is_dir() and branch_exists(git_repo, "work/upload")
    assert (git_repo / ".process" / "worktree" / "upload.json").is_file()
    assert "[TSK-001 진행 중]" in (git_repo / INTENT_REL).read_text(encoding="utf-8"), "done 이 아니면 표시를 지우지 않는다"
    replace_in(git_repo / TASK_REL, "  | 상태 | in-review |", "| 상태 | in-review |")

    result = run_delete(git_repo)   # 고친 뒤 다시 실행하면 이어서 끝낸다

    assert result.returncode == 0, result.stderr
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
    assert not wt.exists()


@pytest.mark.parametrize("flag", ["", "--force", "--merged"])
def test_delete_with_manifest_left_after_manual_removal(git_repo: Path, flag: str):
    """워크트리 · 브랜치를 손으로 지웠으면 매니페스트만 남는다 — 마감한 Task 가 기록돼 있으면 그 ID 의
    유일한 기록이므로 머지 여부를 묻는다(--merged = done, --force = 매니페스트만 지움)."""
    manifest, wt = finished_worktree(git_repo)
    run_git(git_repo, "worktree", "remove", "--force", str(wt))
    run_git(git_repo, "branch", "-D", "work/upload")
    mpath = git_repo / ".process" / "worktree" / "upload.json"

    result = run_delete(git_repo, *([flag] if flag else []))

    if not flag:
        assert result.returncode == 2
        assert "--merged" in result.stderr and "--force" in result.stderr
        assert mpath.is_file()
        return
    assert result.returncode == 0, result.stderr
    assert not mpath.exists()
    if flag == "--force":
        assert "task 그대로:      TSK-001" in result.stdout
        assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"
    else:
        assert "TSK-001 done" in result.stdout
        assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
        assert "[TSK-001" not in (git_repo / INTENT_REL).read_text(encoding="utf-8")


def test_delete_force_after_confirmed_merge_still_closes_tasks(git_repo: Path):
    """--force 는 게이트(남은 변경)만 넘는다 — 머지가 확인되면 done 전이는 그대로 한다."""
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    (wt / "scratch.txt").write_text("throwaway\n", encoding="utf-8")

    result = run_delete(git_repo, "--force")

    assert result.returncode == 0, result.stderr
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
    assert not wt.exists()


def test_delete_resumes_marker_cleanup_for_done_task(git_repo: Path):
    """앞선 delete 가 Task 를 done 으로 바꾼 뒤 멈췄으면, 다시 실행해 표시 정리를 이어서 끝낸다."""
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    replace_in(git_repo / TASK_REL, "| 상태 | in-review |", "| 상태 | done |")

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert "[TSK-001" not in (git_repo / INTENT_REL).read_text(encoding="utf-8")


def test_delete_stops_on_non_utf8_intent_without_writing(git_repo: Path):
    """UTF-8 이 아닌 Intent 는 정리하지 않는다 — Task 도 done 으로 바꾸지 않고 워크트리 · 브랜치도 지우지 않는다."""
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    intent = git_repo / INTENT_REL
    intent.write_bytes(intent.read_text(encoding="utf-8").encode("cp949", errors="replace"))
    before = intent.read_bytes()

    result = run_delete(git_repo)

    assert result.returncode == 2, result.stderr
    assert "UTF-8 로 읽을 수 없다" in result.stderr
    assert intent.read_bytes() == before
    assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"
    assert wt.exists() and branch_exists(git_repo, "work/upload")


def test_delete_stops_on_commented_marker_line(git_repo: Path):
    """진행 표시 줄에 HTML 주석이 섞여 있으면 아무것도 쓰지 않는다 — 줄째 지우면 주석 여닫이가 깨진다."""
    manifest, wt = finished_worktree(git_repo)
    merge(git_repo)
    replace_in(git_repo / INTENT_REL, "(FR-1) [TSK-001 삭제 예정]", "(FR-1) [TSK-001 삭제 예정] <!-- 메모")
    replace_in(git_repo / INTENT_REL, "### Error cases", "-->\n\n### Error cases")
    before = (git_repo / INTENT_REL).read_bytes()

    result = run_delete(git_repo)

    assert result.returncode == 2, result.stderr
    assert "HTML 주석" in result.stderr and "E-1" in result.stderr
    assert (git_repo / INTENT_REL).read_bytes() == before
    assert status_row(git_repo / TASK_REL) == "| 상태 | in-review |"
    assert wt.exists()


def test_delete_write_failure_stops_and_rerun_finishes(git_repo: Path, monkeypatch, capsys):
    """done 처리에서 바꿔 끼우다 멈추면(Windows 의 파일 잠금 등) 삭제를 멈춘다 — 다시 실행하면 이어서 끝낸다."""
    finished_worktree(git_repo)
    merge(git_repo)
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 2:   # Task 는 done 으로 바꿔 끼웠고 Intent 에서 멈춘다
            raise PermissionError(13, "다른 프로세스가 잡고 있다", str(dst))
        real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(SystemExit) as stop:
        _ws._close_or_stop(git_repo, ["TSK-001"])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert "쓰다가 멈춰 삭제를 멈춘다" in err and "다시 실행" in err, err
    intent = git_repo / INTENT_REL
    assert status_row(git_repo / TASK_REL) == "| 상태 | done |"
    assert "[TSK-001 " in intent.read_text(encoding="utf-8")
    assert not [p.name for p in intent.parent.iterdir() if p.name.endswith(".tmp")]

    monkeypatch.setattr(os, "replace", real)
    closed, skipped = _ws._close_or_stop(git_repo, ["TSK-001"])
    assert len(closed) == 1 and not skipped
    assert "[TSK-001 " not in intent.read_text(encoding="utf-8")
    catalog = git_repo / "docs" / "Demo" / "Demo-INT-CATALOG.md"
    assert catalog.is_file() and "TSK-001" not in catalog.read_text(encoding="utf-8")


def test_delete_rerun_rewrites_stale_catalogs(git_repo: Path):
    """앞선 delete 가 문서를 쓴 뒤 멈췄으면 카탈로그만 옛 상태다 — 다시 실행하면 바꿀 문서가 없어도 카탈로그를 다시 쓴다."""
    finished_worktree(git_repo)
    merge(git_repo)
    _ws._close_or_stop(git_repo, ["TSK-001"])
    catalogs = [git_repo / _dh.TASK_DIR / _dh.TASK_CATALOG_NAME, git_repo / "docs" / "Demo" / "Demo-INT-CATALOG.md"]
    good = [c.read_bytes() for c in catalogs]
    for c in catalogs:
        c.write_text("옛 카탈로그\n", encoding="utf-8")

    _ws._close_or_stop(git_repo, ["TSK-001"])

    assert [c.read_bytes() for c in catalogs] == good


def test_delete_uses_manifest_branch(git_repo: Path):
    run_init(git_repo, "upload", "--branch", "feat/custom")

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert "feat/custom" in result.stdout
    assert not branch_exists(git_repo, "feat/custom")
    assert not (git_repo / ".process" / "worktree" / "upload.json").exists()


def test_delete_falls_back_to_reverse_index_without_manifest(git_repo: Path):
    manifest = manifest_from(run_init(git_repo))
    (git_repo / ".process" / "worktree" / "upload.json").unlink()

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert not Path(manifest["worktree"]).exists()


def test_delete_fails_loudly_when_branch_cannot_be_determined(git_repo: Path):
    result = run_script(git_repo, "delete", "no-such-slug")

    assert result.returncode != 0
    assert "특정할 수 없다" in result.stderr


def test_delete_refuses_from_inside_the_worktree(git_repo: Path):
    manifest = manifest_from(run_init(git_repo))

    result = run_script(Path(manifest["worktree"]), "delete", "upload")

    assert result.returncode == 1
    assert "cwd" in result.stderr
    assert Path(manifest["worktree"]).is_dir()


# ============================================================================
# _refresh_int_catalog (단위)
# ============================================================================
@pytest.mark.parametrize("bad_rel", [
    "docs/Demo/Demo-INT-001.md",          # 세그먼트 부족 (INTENT/ 없음)
    "docs/Demo/TASK/Demo-INT-001.md",     # 세번째 세그먼트가 INTENT 가 아님
])
def test_refresh_int_catalog_rejects_non_intent_path(tmp_path: Path, bad_rel: str):
    write_intent(tmp_path)

    assert _ws._refresh_int_catalog(tmp_path, bad_rel) is None
    assert not (tmp_path / CATALOG_REL).exists()


@pytest.mark.parametrize("docs_dir", ["docs", "Docs"])
def test_refresh_int_catalog_writes_catalog_in_intent_spelling(tmp_path: Path, docs_dir: str):
    write_intent(tmp_path, docs_dir=docs_dir)

    rel = _ws._refresh_int_catalog(tmp_path, f"{docs_dir}/Demo/INTENT/Demo-INT-001.md")

    assert rel == f"{docs_dir}/Demo/Demo-INT-CATALOG.md"
    catalog = (tmp_path / rel).read_text(encoding="utf-8")
    assert catalog_row(catalog, "Demo-INT-001"), catalog
    assert catalog.strip().splitlines()[-1] == "intents: 1"


# ============================================================================
# 문서 폴더 대소문자 (docs · Docs)
#
# 레포마다 문서 폴더가 docs 또는 Docs 다 — 둘은 같은 폴더로 봐야 한다. 복사 · done 전이 ·
# 카탈로그 재생성이 디스크 표기를 그대로 써야 한다. Task 는 레포 루트 .task/ 라 표기 문제가 없다.
# ============================================================================
@pytest.mark.parametrize("docs_dir", ["Docs", "docs"])
def test_either_docs_spelling_through_init_finish_delete(git_repo: Path, docs_dir: str):
    manifest, wt = finished_worktree(git_repo, docs_dir=docs_dir)
    intent_rel = f"{docs_dir}/Demo/INTENT/Demo-INT-001.md"
    assert f"{docs_dir}/" in manifest["copied"]
    assert (wt / intent_rel).is_file()
    assert run_git(git_repo, "status", "--porcelain").stdout == ""
    merge(git_repo)

    result = run_delete(git_repo)

    assert result.returncode == 0, result.stderr
    assert "[TSK-001" not in (git_repo / intent_rel).read_text(encoding="utf-8")
    assert docs_dir in os.listdir(git_repo)
    assert _dh.main(["check", "--repo", str(git_repo), "--app", "Demo"]) == 0
