import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ext_dispatch.py"

CODER_RECEIPT = (
    "did the edit\n\n"
    "## RECEIPT\n"
    "STATUS: DONE\n"
    "CHANGED: doc/out.md\n"
    "SPEC: within TARGET FILES\n"
    "VERIFY: pytest -q -> PASS 3 passed\n"
)

EXPLORER_RECEIPT = (
    "read the code\n\n"
    "## RECEIPT\n"
    "STATUS: OK\n"
    "COVERAGE: read doc/out.md fully, skipped tests/\n"
    "CONFIDENCE: high - every fact quoted from an opened file\n"
    "UNCERTAIN: none\n"
    "FACTS FILE: out/report-facts.md\n"
    "KEY FACTS:\n"
    '- doc/out.md:1 [signature] - "# rendered"\n'
)


SCOUT_RECEIPT = (
    "looked around\n\n"
    "## RECEIPT\n"
    "FOUND:\n"
    '- src/a.py:10 [definition] - "def handle():"\n'
    '- src/b.py:22 [usage] - "handle()"\n'
    "RELATED:\n"
    '- src/a.py:3 - "from .x import handle"\n'
    "SEARCHED: rg handle across src/\n"
    "UNCERTAIN: none\n"
    "CONFIDENCE: high - both sites opened\n"
)


def receipt_body(raw: str) -> str:
    """리시트 마커 이후 본문 — _control_summary 단위 테스트 입력."""
    return raw.split("## RECEIPT", 1)[1].strip()


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


def make_mission_job(repo: Path, role: str = "scout", **extra) -> dict:
    job = {
        "report": str(repo / "out" / "report.md"),
        "role": role,
        "agent": "codex",
        "repo": str(repo),
        "mission": "find every call site of handle()",
    }
    job.update(extra)
    return job


def make_job(repo: Path, role: str = "coder") -> dict:
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


# ---------------------------------------------------------------- role registry

def test_registered_roles_are_labour_only(ext):
    """외부 위임은 '노동' 역할만 — 판단·저작 역할은 등록되지 않는다."""
    assert set(ext.REQUIRED_FIELDS) == {"scout", "explorer", "coder"}
    assert set(ext.DEFAULTS) == {"scout", "explorer", "coder"}
    assert ext.WRITE_ROLES == frozenset({"coder"})


def test_removed_scribe_role_is_rejected(ext, git_repo):
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT)
    res = ext._execute_job(make_job(git_repo, role="scribe"), False)
    assert res["exit"] == ext.EXIT_ERR
    assert res["status"] == "unknown role: scribe"


# ---------------------------------------------------------------- coder role

def test_coder_valid_receipt_within_scope(ext, git_repo):
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert res["status"] == "ok"
    assert Path(res["report"]).is_file()
    assert "VERIFY:" in res["receipt"]


def test_new_directory_target_is_not_a_false_violation(ext, git_repo):
    """porcelain 기본값은 untracked 새 디렉터리를 'doc/' 로 접는다 — TARGET
    FILES('doc/out.md')와 매칭되지 않아 거짓 exit 4 를 냈다 (-uall 회귀 가드)."""
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo, role="coder"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


def test_coder_change_outside_target_files_is_violation(ext, git_repo):
    def rogue(repo: Path) -> None:
        write_target(repo)
        (repo / "rogue.md").write_text("drive-by\n", encoding="utf-8")

    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=rogue)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_SPEC_VIOLATION
    assert "rogue.md" in res["status"]
    assert "script-verified" in res["receipt"]


def test_coder_receipt_missing_verify_field(ext, git_repo):
    receipt = CODER_RECEIPT.replace("VERIFY: pytest -q -> PASS 3 passed\n", "")
    ext.INVOKERS["codex"] = fake(receipt, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert "VERIFY" in res["status"]


# ---------------------------------------------------------------- explorer role

def test_explorer_valid_receipt(ext, git_repo):
    ext.INVOKERS["codex"] = fake(EXPLORER_RECEIPT)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "KEY FACTS:" in res["receipt"]


def test_explorer_multiword_field_is_validated(ext, git_repo):
    """'KEY FACTS' 는 공백 포함 라벨 — 부분 문자열 검증이 이를 놓치면 안 된다."""
    receipt = EXPLORER_RECEIPT.replace("KEY FACTS:\n", "FACTS:\n")
    ext.INVOKERS["codex"] = fake(receipt)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert "KEY FACTS" in res["status"]


def test_explorer_receipt_missing_confidence(ext, git_repo):
    receipt = EXPLORER_RECEIPT.replace(
        "CONFIDENCE: high - every fact quoted from an opened file\n", "")
    ext.INVOKERS["codex"] = fake(receipt)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert "CONFIDENCE" in res["status"]


def test_explorer_is_not_scope_checked(ext, git_repo):
    """읽기 전용 역할은 porcelain 대조를 타지 않는다 (WRITE_ROLES 제외).

    알려진 공백: 계약상 read-only 일 뿐 기계적 강제는 없다. scout 도 동일.
    강제하려면 targets=∅ + facts side file 면제로 대조를 돌려야 하는데,
    외부 CLI 가 repo 에 임시 파일을 남기면 전량 거짓 exit 4 가 되므로
    실측 없이는 켜지 않는다.
    """
    def rogue(repo: Path) -> None:
        (repo / "rogue.md").write_text("should have been read-only\n",
                                       encoding="utf-8")

    ext.INVOKERS["codex"] = fake(EXPLORER_RECEIPT, side_effect=rogue)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


# ------------------------------------------------- receipt truncation

def _long_facts(n: int) -> str:
    return "".join(
        f'- src/f{i}.py:{i} [signature] - "def f{i}():"\n' for i in range(n))


def test_short_fields_first_survive_truncation(ext, git_repo):
    """프리앰블이 규정한 필드 순서(짧은 필드 먼저, KEY FACTS 마지막)면
    40줄짜리 사실 목록도 30줄 절단을 통과한다."""
    receipt = (
        "read a lot\n\n"
        "## RECEIPT\n"
        "STATUS: OK\n"
        "COVERAGE: read 40 files\n"
        "CONFIDENCE: medium - aggregated per file\n"
        "KEY FACTS:\n" + _long_facts(40)
    )
    ext.INVOKERS["codex"] = fake(receipt)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "truncated" in res["receipt"]


def test_confidence_after_long_list_is_cut_and_fails(ext, git_repo):
    """역순(가변 목록 먼저)이면 CONFIDENCE 가 절단선 밖으로 밀려 거짓 exit 3.
    프리앰블의 '필드 순서는 load-bearing' 경고를 고정하는 회귀 가드."""
    receipt = (
        "read a lot\n\n"
        "## RECEIPT\n"
        "COVERAGE: read 40 files\n"
        "KEY FACTS:\n" + _long_facts(40) +
        "CONFIDENCE: medium - aggregated per file\n"
    )
    ext.INVOKERS["codex"] = fake(receipt)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT
    assert "CONFIDENCE" in res["status"]


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
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, rc=1, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


# ---------------------------------------------------------------- CLI surface

def test_cli_accepts_explorer_role_and_loads_preamble(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\nCONTEXT: src/a.py:1\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--spec", str(spec),
         "--report", str(tmp_path / "report.md"), "--role", "explorer",
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert "role=explorer" in proc.stdout
    assert "timeout=600s" in proc.stdout
    assert json.loads(proc.stdout.strip().splitlines()[-1])["role"] == "explorer"


def test_cli_rejects_removed_scribe_role(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--spec", str(spec),
         "--report", str(tmp_path / "report.md"), "--role", "scribe",
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr


# ------------------------------------------------- stdout 화물 분리 (요약)

def test_scout_summary_folds_cargo_into_counts(ext):
    """FOUND/RELATED 의 path:line 목록은 건수로 접히고 제어 필드는 원문 유지."""
    out = ext._control_summary("scout", receipt_body(SCOUT_RECEIPT))
    assert "src/a.py:10" not in out and "src/b.py:22" not in out
    assert "FOUND: 2 across 2 files" in out
    assert "RELATED: 1 across 1 file" in out
    assert "SEARCHED: rg handle across src/" in out
    assert "CONFIDENCE: high - both sites opened" in out
    assert "UNCERTAIN: none" in out


def test_explorer_summary_folds_key_facts(ext):
    out = ext._control_summary("explorer", receipt_body(EXPLORER_RECEIPT))
    assert "doc/out.md:1" not in out
    assert "KEY FACTS: 1 across 1 file" in out
    assert "FACTS FILE: out/report-facts.md" in out
    assert "STATUS: OK" in out


def test_coder_is_never_summarized(ext):
    """coder 리시트는 전부 제어 필드 — VERIFY/SPEC 판정이 호출측 몫이라 접지 않는다."""
    assert ext._control_summary("coder", receipt_body(CODER_RECEIPT)) is None


def test_summary_falls_back_when_shape_is_unknown(ext):
    """제어 필드를 하나도 못 찾으면 None → 호출측이 전문 출력. 정보 무손실 우선."""
    assert ext._control_summary("scout", "totally unexpected prose\n") is None


def test_summary_preserves_truncation_marker(ext):
    receipt = receipt_body(SCOUT_RECEIPT) + \
        "\n[ext] (receipt truncated to 30 lines)"
    out = ext._control_summary("scout", receipt)
    assert "(receipt truncated to 30 lines)" in out


def test_summary_keeps_aggregate_inline_value(ext):
    """8건 초과 집계 모드: 에이전트가 쓴 요약 문장을 살리고 줄 수만 덧붙인다."""
    receipt = (
        "FOUND: 42 usages across 6 files\n"
        '- src/a.py:1 [usage] - "handle()"\n'
        '- src/b.py:2 [usage] - "handle()"\n'
        "SEARCHED: rg handle\n"
        "CONFIDENCE: medium - aggregated per file\n"
    )
    out = ext._control_summary("scout", receipt)
    assert "FOUND: 42 usages across 6 files [2 lines]" in out


def test_print_receipt_summarizes_scout_success(ext, capsys):
    res = {"receipt": receipt_body(SCOUT_RECEIPT), "exit": ext.EXIT_OK,
           "role": "scout", "status": "ok", "report": "/x/out/report.md"}
    ext._print_receipt(res, full=False)
    out = capsys.readouterr().out
    assert "src/a.py:10" not in out
    assert "FOUND: 2 across 2 files" in out
    assert "data: /x/out/report.md" in out


def test_print_receipt_full_on_failure(ext, capsys):
    """실패는 항상 전문 — 진단에는 화물까지 필요하다."""
    res = {"receipt": receipt_body(SCOUT_RECEIPT),
           "exit": ext.EXIT_BAD_RECEIPT, "role": "scout",
           "status": "invalid: fields missing CONFIDENCE",
           "report": "/x/out/report.md"}
    ext._print_receipt(res, full=False)
    assert "src/a.py:10" in capsys.readouterr().out


def test_print_receipt_full_flag_restores_cargo(ext, capsys):
    res = {"receipt": receipt_body(SCOUT_RECEIPT), "exit": ext.EXIT_OK,
           "role": "scout", "status": "ok", "report": "/x/out/report.md"}
    ext._print_receipt(res, full=True)
    assert "src/a.py:10" in capsys.readouterr().out


def test_report_file_always_keeps_full_receipt(ext, git_repo):
    """요약은 stdout 전용 — REPORT 파일에는 화물이 전문으로 남아야 한다."""
    ext.INVOKERS["codex"] = fake(SCOUT_RECEIPT)
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    written = Path(res["report"]).read_text(encoding="utf-8")
    assert "src/a.py:10" in written and "src/b.py:22" in written


# ------------------------------------------------- 인라인 미션 모드

def test_inline_mission_synthesizes_spec_file(ext, git_repo):
    res = ext._execute_job(make_mission_job(git_repo), True)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    spec_path = Path(res["spec"])
    assert spec_path.name == "report-spec.md"
    text = spec_path.read_text(encoding="utf-8")
    assert "TASK: find every call site of handle()" in text
    assert "TIMEOUT: 300" in text and "LEDGER: none" in text
    assert f"REPORT: {res['report']}" in text
    assert "CONTEXT:" not in text  # --context 미지정 시 생략


def test_inline_mission_return_uses_full_contract(ext, git_repo):
    """RETURN 은 프리앰블 계약 전체 — REQUIRED_FIELDS(부분집합)를 쓰면 안 된다."""
    res = ext._execute_job(make_mission_job(git_repo), True)
    text = Path(res["spec"]).read_text(encoding="utf-8")
    assert "RETURN: FOUND / RELATED / SEARCHED / UNCERTAIN / CONFIDENCE" in text


def test_inline_mission_includes_context_when_given(ext, git_repo):
    res = ext._execute_job(
        make_mission_job(git_repo, role="explorer", context="src/a.py:10"),
        True)
    assert "CONTEXT: src/a.py:10" in Path(res["spec"]).read_text(
        encoding="utf-8")


def test_inline_mission_rejected_for_coder(ext, git_repo):
    """쓰기 역할은 TARGET FILES 고정이 계약 — 한 줄 미션으로 표현 불가."""
    res = ext._execute_job(make_mission_job(git_repo, role="coder"), True)
    assert res["exit"] == ext.EXIT_ERR
    assert "inline mission not allowed" in res["status"]
    assert not Path(res["spec"]).exists()


def test_spec_and_mission_are_exclusive(ext, git_repo):
    job = make_mission_job(git_repo)
    job["spec"] = str(git_repo / "spec.md")
    res = ext._execute_job(job, True)
    assert res["exit"] == ext.EXIT_ERR
    assert "mutually exclusive" in res["status"]


def test_job_without_spec_or_mission_is_rejected(ext, git_repo):
    job = make_mission_job(git_repo)
    del job["mission"]
    res = ext._execute_job(job, True)
    assert res["exit"] == ext.EXIT_ERR
    assert "either spec or mission" in res["status"]


def test_cli_inline_mission_dry_run(tmp_path):
    report = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--role", "scout",
         "--report", str(report), "--mission", "locate handle()",
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert Path(payload["spec"]).name == "report-spec.md"
    assert (tmp_path / "report-spec.md").is_file()


def test_cli_rejects_spec_and_mission_together(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--role", "scout",
         "--report", str(tmp_path / "report.md"), "--spec", str(spec),
         "--mission", "locate handle()", "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    assert "exactly one of --spec / --mission" in proc.stderr


def test_cli_rejects_neither_spec_nor_mission(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--role", "scout",
         "--report", str(tmp_path / "report.md"), "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    assert "exactly one of --spec / --mission" in proc.stderr


def test_cli_explorer_inline_mission_without_context_warns(tmp_path):
    """프리앰블의 시작점 게이트는 기계 판정 불가 — 경고만 내고 실행은 막지 않는다."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "run", "--role", "explorer",
         "--report", str(tmp_path / "report.md"), "--mission", "map job core",
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" in proc.stderr and "BLOCKED" in proc.stderr


def test_wave_manifest_accepts_mission_and_spec_jobs(tmp_path):
    """기존 spec job 과 mission job 이 한 manifest 에 섞여도 동작 (하위 호환)."""
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\nCONTEXT: src/a.py:1\n", encoding="utf-8")
    manifest = tmp_path / "wave.json"
    manifest.write_text(json.dumps({"jobs": [
        {"spec": str(spec), "report": str(tmp_path / "r1.md"),
         "role": "explorer"},
        {"mission": "locate handle()", "report": str(tmp_path / "r2.md"),
         "role": "scout"},
    ]}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "wave", "--manifest", str(manifest),
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"] == "ok"
    assert (tmp_path / "r2-spec.md").is_file()
