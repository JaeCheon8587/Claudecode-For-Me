"""forge_scope.py 인라인 실행 경로(--scaffold-only / --record-step / --finalize) 통합 테스트.

자식 claude·dotnet 없이 검증하기 위해 `--single-step --prompt=...`(AC=`git diff --check`,
warmup skip)로 구동한다. forge_scope.py를 임시 git repo의 scripts/ 에 복사하면
ROOT(=__file__.parent.parent)가 임시 repo로 해석되어 워크트리·phase가 그 안에 생성된다.

테스트 "세션" 역할: 워크트리에 코드 + step{N}-status.json 을 직접 써서 record-step 을 호출한다.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FORGE = Path(__file__).resolve().parent / "forge_scope.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def _run_forge(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "FORGE_TRUST": "1"}
    return subprocess.run(
        [sys.executable, "scripts/forge_scope.py", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _last_json(stdout: str) -> dict:
    """stdout의 마지막 비어있지 않은 줄을 JSON 으로 파싱(매니페스트/result 출력)."""
    lines = [l for l in stdout.splitlines() if l.strip()]
    assert lines, f"stdout에 JSON 없음: {stdout!r}"
    return json.loads(lines[-1])


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    (r / "scripts").mkdir(parents=True)
    shutil.copy2(FORGE, r / "scripts" / "forge_scope.py")
    (r / "CLAUDE.md").write_text("# 프로젝트: testproj\n", encoding="utf-8")
    (r / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "tester")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    return r


def _scaffold(repo: Path, phase: str = "t1", prompt: str = "add hello") -> dict:
    res = _run_forge(
        repo, phase, "--single-step", f"--prompt={prompt}", "--scaffold-only",
        "--trust", "--yes", "--quiet",
    )
    assert res.returncode == 0, f"scaffold 실패: {res.stdout}\n{res.stderr}"
    return _last_json(res.stdout)


def _phase_dir(manifest: dict) -> Path:
    return Path(manifest["phase_dir"])


# --------------------------------------------------------------------------- #


def test_scaffold_only_manifest(repo: Path):
    m = _scaffold(repo)
    assert m["no_worktree"] is False
    wt = Path(m["worktree"])
    assert wt.is_dir() and wt.name == "t1" and wt.parent.name == ".worktrees"
    assert m["root_dirty_baseline"] == []  # .worktrees/ gitignore → ROOT clean
    assert len(m["steps"]) == 1
    s0 = m["steps"][0]
    assert s0["step"] == 0 and s0["status"] == "pending"
    assert Path(s0["step_file"]).is_file()  # 절대경로로 실제 존재


def test_scaffold_only_no_child_spawn(repo: Path):
    # scaffold-only 는 step 실행 commit 을 만들지 않는다(feat 브랜치엔 부트스트랩 커밋만).
    m = _scaffold(repo)
    wt = Path(m["worktree"])
    log = _git(wt, "log", "--oneline").stdout
    assert "step 0" not in log and "feat(" not in log


def _complete_step(repo: Path, m: dict, n: int, *, code: str = "hello.txt"):
    """세션 역할: 워크트리에 코드 파일 + step{n}-status.json(completed) 작성."""
    wt = Path(m["worktree"])
    (wt / code).write_text("hi\n", encoding="utf-8")
    pd = _phase_dir(m)
    (pd / f"step{n}-status.json").write_text(
        json.dumps({"status": "completed", "summary": f"step {n} done"}), encoding="utf-8"
    )


def test_record_step_happy(repo: Path):
    m = _scaffold(repo)
    _complete_step(repo, m, 0)
    res = _run_forge(repo, "t1", "--record-step=0", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert res.returncode == 0 and out["result"] == "completed"
    wt = Path(m["worktree"])
    # feat + chore 2 commit 생성
    subjects = _git(wt, "log", "--format=%s").stdout
    assert "feat(t1): step 0" in subjects
    assert "chore(t1): step 0 output" in subjects
    # index 전이
    idx = json.loads((_phase_dir(m) / "index.json").read_text(encoding="utf-8"))
    assert idx["steps"][0]["status"] == "completed"
    assert "completed_at" in idx["steps"][0]


def test_record_step_leak_guard(repo: Path):
    m = _scaffold(repo)
    _complete_step(repo, m, 0)
    # 세션이 메인 repo(ROOT)에 누수 — baseline 이후 신규 dirty
    (repo / "leaked.txt").write_text("oops\n", encoding="utf-8")
    res = _run_forge(repo, "t1", "--record-step=0", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert res.returncode != 0 and out["result"] == "error"
    assert "누수" in out["message"]


def test_record_step_no_change_after_committed(repo: Path):
    # step0 완료(커밋)로 워크트리 클린 후, 빈 step 으로 record → 무변경 error.
    m = _scaffold(repo)
    _complete_step(repo, m, 0)
    _run_forge(repo, "t1", "--record-step=0", "--trust", "--yes", "--quiet")
    wt = Path(m["worktree"])
    assert not _git(wt, "status", "--porcelain").stdout.strip()  # 클린 확인
    # step0 재기록 시도(아무 변경 없음) → 무변경 error
    res = _run_forge(repo, "t1", "--record-step=0", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert out["result"] == "error" and "변경 없음" in out["message"]


def test_record_step_backstop_counter(repo: Path):
    m = _scaffold(repo)
    wt = Path(m["worktree"])
    pd = _phase_dir(m)
    (wt / "wip.txt").write_text("partial\n", encoding="utf-8")  # 워크트리 dirty 유지

    def _attempt_error():
        pd.joinpath("step0-status.json").write_text(
            json.dumps({"status": "error", "error_message": "AC 실패"}), encoding="utf-8"
        )
        return _last_json(
            _run_forge(repo, "t1", "--record-step=0", "--max-attempts=2",
                       "--trust", "--yes", "--quiet").stdout
        )

    first = _attempt_error()
    assert first["result"] == "retry" and first["attempts"] == 1
    second = _attempt_error()
    assert second["result"] == "error" and second["attempts"] == 2
    idx = json.loads((pd / "index.json").read_text(encoding="utf-8"))
    assert idx["steps"][0]["status"] == "error"


def test_record_step_tdd_gate(repo: Path):
    # 워크트리 index.json 에 step1(pending) 추가 후, step0 미완 상태에서 step1 완료 시도 → 순서 거부.
    m = _scaffold(repo)
    wt = Path(m["worktree"])
    pd = _phase_dir(m)
    idx = json.loads((pd / "index.json").read_text(encoding="utf-8"))
    idx["steps"].append({"step": 1, "name": "second", "status": "pending"})
    (pd / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    (pd / "step1.md").write_text("# step1\n", encoding="utf-8")
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    (pd / "step1-status.json").write_text(
        json.dumps({"status": "completed", "summary": "s1"}), encoding="utf-8"
    )
    res = _run_forge(repo, "t1", "--record-step=1", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert out["result"] == "error" and "이전 step 미완" in out["message"]


def test_finalize_only_pending_errors(repo: Path):
    _scaffold(repo)
    res = _run_forge(repo, "t1", "--finalize", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert res.returncode != 0 and out["result"] == "error" and "미완" in out["message"]


def test_finalize_only_happy(repo: Path):
    m = _scaffold(repo)
    _complete_step(repo, m, 0)
    _run_forge(repo, "t1", "--record-step=0", "--trust", "--yes", "--quiet")
    res = _run_forge(repo, "t1", "--finalize", "--trust", "--yes", "--quiet")
    out = _last_json(res.stdout)
    assert res.returncode == 0 and out["result"] == "finalized" and out["phase"] == "t1"
    idx = json.loads((_phase_dir(m) / "index.json").read_text(encoding="utf-8"))
    assert "completed_at" in idx


def test_ddr_loop_import_preserved():
    # 부품 보존 회귀: ddr_loop.py 가 import 하는 심볼이 그대로 존재해야 한다.
    sys.path.insert(0, str(FORGE.parent))
    try:
        from forge_scope import ClaudeInvoker, DEFAULT_CHILD_TOOLS  # noqa: F401
    finally:
        sys.path.pop(0)
