import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ext_dispatch.py"

SCRIBE_RECEIPT = (
    "wrote the report\n\n"
    "## RECEIPT\n"
    "STATUS: DONE\n"
    "CHANGED: doc/out.md\n"
    "SPEC: within TARGET FILES\n"
    "SOURCES: quota offload claim -> reports/prior.md:12\n"
)


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def ext():
    spec = importlib.util.spec_from_file_location("ext_dispatch", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "ext-test@example.invalid")
    run_git(tmp_path, "config", "user.name", "Ext Test")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# Test repo\n", encoding="utf-8")
    run_git(tmp_path, "add", "README.md")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def make_job(repo: Path, role: str = "scribe") -> dict:
    spec = repo / "spec.md"
    spec.write_text(
        "TASK: render the report\n"
        "TARGET FILES:\n"
        "- doc/out.md\n"
        "CHANGE SPEC: transcribe reports/prior.md\n"
        "LEDGER: none\n",
        encoding="utf-8",
    )
    return {
        "spec": str(spec),
        "report": str(repo / "out" / "report.md"),
        "role": role,
        "agent": "codex",
        "repo": str(repo),
    }


def fake(stdout: str, stderr: str = "", rc: int = 0, side_effect=None):
    """INVOKERS['codex'] 대체 — side_effect(cwd) 로 작업 트리 변경을 흉내낸다."""

    def _invoke(prompt, model, effort, timeout, cwd):
        if side_effect is not None:
            side_effect(Path(cwd))
        return stdout, stderr, rc

    return _invoke


def write_target(repo: Path) -> None:
    target = repo / "doc" / "out.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# rendered\n", encoding="utf-8")


# ---------------------------------------------------------------- scribe role

def test_scribe_valid_receipt_within_scope(ext, git_repo):
    ext.INVOKERS["codex"] = fake(SCRIBE_RECEIPT, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert res["status"] == "ok"
    assert Path(res["report"]).is_file()
    assert "SOURCES:" in res["receipt"]


def test_new_directory_target_is_not_a_false_violation(ext, git_repo):
    """porcelain 기본값은 untracked 새 디렉터리를 'doc/' 로 접는다 — TARGET
    FILES('doc/out.md')와 매칭되지 않아 거짓 exit 4 를 냈다 (-uall 회귀 가드).
    coder 경로에도 동일한 결함이었으므로 coder 로 검증한다."""
    coder_receipt = SCRIBE_RECEIPT.replace(
        "SOURCES: quota offload claim -> reports/prior.md:12",
        "VERIFY: pytest -q -> PASS 3 passed")
    ext.INVOKERS["codex"] = fake(coder_receipt, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo, role="coder"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


def test_scribe_change_outside_target_files_is_violation(ext, git_repo):
    def rogue(repo: Path) -> None:
        write_target(repo)
        (repo / "rogue.md").write_text("drive-by\n", encoding="utf-8")

    ext.INVOKERS["codex"] = fake(SCRIBE_RECEIPT, side_effect=rogue)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_SPEC_VIOLATION
    assert "rogue.md" in res["status"]
    assert "script-verified" in res["receipt"]


def test_scribe_sources_overflow_file_is_exempt(ext, git_repo):
    def with_sources(repo: Path) -> None:
        write_target(repo)
        sources = repo / "out" / "report-sources.md"
        sources.parent.mkdir(parents=True, exist_ok=True)
        sources.write_text("claim -> reports/prior.md:12\n", encoding="utf-8")

    ext.INVOKERS["codex"] = fake(SCRIBE_RECEIPT, side_effect=with_sources)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


def test_scribe_receipt_missing_sources_field(ext, git_repo):
    receipt = SCRIBE_RECEIPT.replace(
        "SOURCES: quota offload claim -> reports/prior.md:12\n", "")
    ext.INVOKERS["codex"] = fake(receipt, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert "SOURCES" in res["status"]


# ------------------------------------------------- agent error (exit 6)

def test_nonzero_rc_without_receipt_is_agent_error(ext, git_repo):
    ext.INVOKERS["codex"] = fake("boom", rc=1)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_AGENT_ERROR
    assert res["status"].startswith("agent-error: exit 1")
    assert res["reason"] is None


def test_quota_signal_is_reported_as_reason(ext, git_repo):
    ext.INVOKERS["codex"] = fake(
        "", stderr="You have hit your usage limit for this month.", rc=1)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_AGENT_ERROR
    assert res["reason"] == "quota-signal: usage limit"
    assert "usage limit" in res["status"]


def test_zero_rc_without_receipt_stays_bad_receipt(ext, git_repo):
    """하위 호환 회귀 가드: rc==0 + 마커 부재는 여전히 exit 3."""
    ext.INVOKERS["codex"] = fake("no marker here", rc=0)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert res["status"] == "invalid: RECEIPT marker missing"


def test_valid_receipt_wins_over_nonzero_rc(ext, git_repo):
    """리시트가 있으면 rc 와 무관하게 기존 흐름 — 기존 exit code 의미 불변."""
    ext.INVOKERS["codex"] = fake(SCRIBE_RECEIPT, rc=1, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


# ---------------------------------------------------------------- CLI surface

def test_cli_accepts_scribe_role_and_loads_preamble(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\nTARGET FILES:\n- doc/out.md\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--spec", str(spec),
         "--report", str(tmp_path / "report.md"), "--role", "scribe",
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert "role=scribe" in proc.stdout
    assert "timeout=900s" in proc.stdout
    assert json.loads(proc.stdout.strip().splitlines()[-1])["role"] == "scribe"
