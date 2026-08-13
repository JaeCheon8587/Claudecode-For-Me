import importlib.util
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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


# fact 검사기 fixture — 저장소의 살아있는 소스를 대조 대상으로 쓰지 않는다.
# v3.46.0 이 ext_dispatch.py 에 200줄을 더하자 기존 리시트의 라인 번호가 전부
# 어긋나 17/17 이 0/17 이 됐다. 대조 대상은 테스트가 직접 쓴다.
SOURCE_A = (
    "# header\n"          # 1
    "import os\n"         # 2
    "\n"                  # 3
    "def handle(x):\n"    # 4
    "    return x + 1\n"  # 5
    "\n"                  # 6
    "def other():\n"      # 7
    "    return handle(0)\n"  # 8
)


def write_source(repo: Path, rel: str = "src/a.py", text: str = SOURCE_A) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def scout_receipt(*found: str) -> str:
    bullets = "".join(f"{b}\n" for b in found)
    return ("looked around\n\n## RECEIPT\nFOUND:\n" + bullets +
            "SEARCHED: rg handle across src/\n"
            "UNCERTAIN: none\n"
            "CONFIDENCE: high - opened every hit\n")


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


def write_scout_sources(repo: Path) -> None:
    """SCOUT_RECEIPT 가 인용한 위치를 실재하게 만든다.

    fact 검사기가 붙은 뒤로는 리시트가 가리키는 파일이 실제로 있어야 한다 —
    없으면 반증된 주장(exit 7)이 되는 것이 옳은 동작이다.
    """
    (repo / "src").mkdir(parents=True, exist_ok=True)
    a = [""] * 12
    a[2] = "from .x import handle"   # :3
    a[9] = "def handle():"           # :10
    (repo / "src" / "a.py").write_text("\n".join(a) + "\n", encoding="utf-8")
    b = [""] * 24
    b[21] = "handle()"               # :22
    (repo / "src" / "b.py").write_text("\n".join(b) + "\n", encoding="utf-8")


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
    write_target(git_repo)   # EXPLORER_RECEIPT 가 인용한 doc/out.md:1
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

    write_target(git_repo)   # EXPLORER_RECEIPT 가 인용한 doc/out.md:1
    ext.INVOKERS["codex"] = fake(EXPLORER_RECEIPT, side_effect=rogue)
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]


# ------------------------------------------------- receipt truncation

def _long_facts(n: int) -> str:
    return "".join(
        f'- src/big.py:{i + 1} [signature] - "def f{i}():"\n' for i in range(n))


def write_big_source(repo: Path, n: int = 40) -> None:
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "big.py").write_text(
        "".join(f"def f{i}():\n" for i in range(n)), encoding="utf-8")


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
    write_big_source(git_repo)
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
    write_scout_sources(git_repo)
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


# ------------------------------------------------- fact 검사기 (4등급)

def test_facts_verified_pass(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"',
        '- src/a.py:5 [usage] - "return x + 1"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 2/2 facts" in res["receipt"]
    assert "0 drifted" in res["receipt"]


def test_drifted_line_number_is_corrected(ext, git_repo):
    """지배적 실패 모드는 날조가 아니라 드리프트다 — 자동 교정, 비치명."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:6 [definition] - "def handle(x):"'))   # 실제는 :4
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "src/a.py:4" in res["receipt"]      # 교정됨
    assert "src/a.py:6 [definition]" not in res["receipt"]
    assert "1 drifted" in res["receipt"]
    assert "~ src/a.py:6 -> :4" in res["receipt"]


def test_correction_is_written_to_report(ext, git_repo):
    """교정의 목적은 하위 스펙이 맞는 라인을 받는 것 — REPORT 에 반영돼야 한다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:6 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    written = Path(res["report"]).read_text(encoding="utf-8")
    assert "src/a.py:4 [definition]" in written


def test_fabricated_evidence_is_exit_7(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"',
        '- src/a.py:5 [usage] - "launch_missiles(everything)"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_FACTS_UNVERIFIED, res["status"]
    assert "facts-unverified" in res["status"]
    assert "! src/a.py:5" in res["receipt"]


def test_nonexistent_file_is_exit_7(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/nope.py:9 [usage] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_FACTS_UNVERIFIED
    assert "no such file" in res["receipt"]


def test_ambiguous_drift_is_not_guessed(ext, git_repo):
    """창 안 여러 줄이 매치되면 교정하지 않는다 — 잘못된 교정이 미교정보다 나쁘다.

    실측 근거: explorer facts 의 `str(repo))` 가 ±2 양쪽에 걸려, 가까운 쪽을
    고르는 방식이었다면 틀린 줄로 교정될 뻔했다.
    """
    write_source(git_repo, text="a\nreturn x\nb\nreturn x\nc\n")
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:3 [usage] - "return x"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_FACTS_UNVERIFIED
    assert "ambiguous" in res["receipt"]
    assert "src/a.py:3 [usage]" in res["receipt"]   # 원문 보존, 추측 안 함


def test_aggregate_bullets_count_as_unparsed(ext, git_repo):
    """8건 초과 집계 모드는 프리앰블이 허용한 포맷 — 반증 불가라 치명 아님."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(
        "looked around\n\n## RECEIPT\n"
        "FOUND: 42 usages across 6 files\n"
        "- src/a.py (12 hits) - representative: handle()\n"
        "SEARCHED: rg handle\n"
        "UNCERTAIN: none\n"
        "CONFIDENCE: medium - aggregated per file\n")
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "no checkable path:line facts" in res["receipt"]


def test_short_evidence_is_unparsed_not_failed(ext, git_repo):
    """짧은 조각은 어느 줄에나 걸려 반증력이 없다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt('- src/a.py:2 [usage] - "os"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 unparsed" in res["receipt"]


# ---------------------------------- 파서 회귀 (각각 없으면 전량 오탐하던 것)

def test_bare_filename_resolves_by_unique_basename(ext, git_repo):
    """explorer facts 는 `ext_dispatch.py:283` 처럼 루트에서 해석 안 되는
    맨 파일명을 쓴다 (실측 90/90). 이 처리가 없으면 정상 수확물이 전량 실패."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- a.py:4 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_duplicate_basename_is_unparsed_not_failed(ext, git_repo):
    write_source(git_repo, "src/a.py")
    write_source(git_repo, "lib/a.py")
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- a.py:4 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 unparsed" in res["receipt"]


@pytest.mark.parametrize("quoted", [
    '"def handle(x):"',      # 리시트 기본
    "`def handle(x):`",      # explorer facts 본문
    "'def handle(x):'",      # 실측 스모크 4회차
])
def test_all_observed_delimiters_are_accepted(ext, git_repo, quoted):
    """구분자는 실행마다 바뀐다 — 하나만 지원하면 그 실행의 커버리지가 0 이 된다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        f"- src/a.py:4 [definition] - {quoted}"))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_indented_receipt_is_parsed(ext, git_repo):
    """리시트 전체가 들여쓰여 오는 실행이 있다 (실측 스모크 4회차)."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(
        "looked\n\n## RECEIPT\n    FOUND:\n"
        '    - src/a.py:4 [definition] - "def handle(x):"\n'
        "    SEARCHED: rg handle\n    UNCERTAIN: none\n"
        "    CONFIDENCE: high - opened directly\n")
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_multiple_quotes_on_one_line(ext, git_repo):
    """explorer KEY FACTS 는 한 줄에 인용이 여러 개다 — "마지막 따옴표까지"
    규칙 하나면 두 인용을 이어붙여 실패한다 (실측 10/10 오탐)."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):" -> :5 "return x + 1"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_quote_wrapping_across_source_lines(ext, git_repo):
    """에이전트는 wrap 된 한 문장을 한 줄로 이어 인용한다 (실측 스모크).
    시작 줄만 대조하면 거짓 실패가 난다."""
    write_source(git_repo, text=(
        "x = 1\n"
        'stats = {"verified": 0, "drifted": [],\n'
        '         "total": 0}\n'))
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:2 [config] - `stats = {"verified": 0, "drifted": [], "total": 0}`'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_wrap_join_does_not_swallow_drift(ext, git_repo):
    """이어붙이기는 인용이 그 줄에서 시작할 때만 — 아니면 드리프트가 안 잡힌다."""
    write_source(git_repo, text="alpha\nbeta\ndef handle(x):\n")
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:2 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 drifted" in res["receipt"]
    assert "~ src/a.py:2 -> :3" in res["receipt"]


def test_syntactic_unit_reconstructed_across_wrap(ext, git_repo):
    """에이전트는 구문 단위를 인용한다 — 여는 괄호가 앞줄에서 딸려온다 (실측 스모크).
    텍스트가 거기 실재하면 통과여야 한다."""
    write_source(git_repo, text=(
        "cache[key] = (hits[0], 'ok') if len(hits) == 1 else (\n"
        "    None, 'absent' if not hits else 'ambiguous')\n"))
    ext.INVOKERS["codex"] = fake(scout_receipt(
        "- src/a.py:2 [flow] - `(None, 'absent' if not hits else 'ambiguous')`"))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_loose_match_still_falsifies_fabrication(ext, git_repo):
    """공백 무시 관문이 날조까지 통과시키면 안 된다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [usage] - "launch_missiles( everything )"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_FACTS_UNVERIFIED


def test_line_range_notation_is_parsed(ext, git_repo):
    """`:98-100` 의 하이픈이 구분자로 먹히면 뒤 숫자가 evidence 앞에 붙는다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4-5 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_omitted_path_inherits_previous_bullet(ext, git_repo):
    """에이전트가 목록 안에서 경로를 생략한다 (실측 스모크 — 10/11 이 unparsed 로
    떨어졌다). 같은 목록 안에서는 무모호하므로 상속한다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"',
        '- :5 [usage] - "return x + 1"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 2/2 facts" in res["receipt"]


def test_grouped_line_numbers_use_the_first(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4/5/7 [usage] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]


def test_leading_path_is_required_for_first_bullet(ext, git_repo):
    """상속할 앞 불릿이 없으면 판정 불가 — 아무 파일에나 붙이면 안 된다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt('- :5 [usage] - "return x + 1"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 unparsed" in res["receipt"]


def test_prose_evidence_is_unparsed_not_failed(ext, git_repo):
    """구분자 없는 서술은 축자 인용이 아니라 반증 불가 — 치명이면 안 된다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 - FOOTER_FIELDS injects the VERIFIED control field'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 unparsed" in res["receipt"]


def test_non_fact_bullets_are_unparsed(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"',
        '- Note: default exit is EXIT_ERR unless a branch overrides.'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]
    assert "1 unparsed" in res["receipt"]


# ---------------------------------- explorer facts 본문 · 기타

def test_explorer_facts_file_is_checked(ext, git_repo):
    """리시트 샘플은 거짓 안심을 준다 — 실측에서 리시트 10/10 인데 본문은 7/90
    오류였다. 하위 노드가 읽는 것은 본문 쪽이다."""
    write_source(git_repo)
    facts = git_repo / "out" / "report-facts.md"
    facts.parent.mkdir(parents=True, exist_ok=True)
    facts.write_text('- src/a.py:6 [signature] - `def handle(x):`\n',
                     encoding="utf-8")
    ext.INVOKERS["codex"] = fake(
        "read it\n\n## RECEIPT\n"
        "STATUS: OK\nCOVERAGE: read src/a.py\n"
        "CONFIDENCE: high - opened directly\nUNCERTAIN: none\n"
        f"FACTS FILE: {facts}\n"
        'KEY FACTS:\n- src/a.py:4 [signature] - "def handle(x):"\n')
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "facts file: 1/1" in res["receipt"]
    # 본문의 드리프트도 제자리에서 교정된다
    assert "src/a.py:4" in facts.read_text(encoding="utf-8")


def test_missing_facts_file_is_reported_not_fatal(ext, git_repo):
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(
        "read it\n\n## RECEIPT\n"
        "STATUS: OK\nCOVERAGE: read src/a.py\n"
        "CONFIDENCE: high - opened directly\nUNCERTAIN: none\n"
        "FACTS FILE: /nowhere/absent-facts.md\n"
        'KEY FACTS:\n- src/a.py:4 [signature] - "def handle(x):"\n')
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "FACTS FILE not found" in res["receipt"]


# ---------------------------------- 형식 붕괴 (실측: explorer 1회차 59/59 미검사)

def test_contract_mismatch_bullets_are_flagged_not_silent(ext, git_repo):
    """대시·인용부호 없는 컬럼 정렬 형식 — 실 explorer 가 낸 형식이다.

    파싱이 전량 실패하면 검사기는 아무것도 대조하지 못하는데, 예전에는 exit 0
    에 조용한 요약만 남아 건강한 실행과 구별되지 않았다.
    """
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        "- src/a.py:4  [definition]  def handle(x):",
        "- src/a.py:6  [usage]       return x + 1"))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK            # 사실이 틀렸다는 증거는 아니다
    assert "facts-unverifiable" in res["status"]
    assert "NOTHING CHECKED" in res["receipt"]
    assert "2 receipt fact bullets" in res["receipt"]


def test_aggregate_only_receipt_is_not_a_format_collapse(ext, git_repo):
    """집계·서술 불릿은 라인번호가 없다 — 프리앰블이 허용한 정상이므로
    형식 붕괴로 잡으면 오탐이다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(
        "looked around\n\n## RECEIPT\n"
        "FOUND: 42 usages across 6 files\n"
        "- src/a.py (12 hits) - representative: handle()\n"
        "- Note: dynamic dispatch not resolved.\n"
        "SEARCHED: rg handle\n"
        "UNCERTAIN: none\n"
        "CONFIDENCE: medium - aggregated per file\n")
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "NOTHING CHECKED" not in res["receipt"]
    assert "no checkable path:line facts" in res["receipt"]


def test_partial_parse_is_not_a_format_collapse(ext, git_repo):
    """한 건이라도 대조됐으면 커버리지 문제지 붕괴가 아니다 — unparsed 로 족하다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"',
        "- src/a.py:6  [usage]       return x + 1"))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "NOTHING CHECKED" not in res["receipt"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]
    assert "1 unparsed" in res["receipt"]


def test_facts_file_format_collapse_is_flagged(ext, git_repo):
    """리시트는 멀쩡한데 본문만 형식이 어긋난 경우 — 실측 explorer 1회차 그대로.

    하위 노드가 읽는 것은 본문 쪽이라 리시트만 보면 거짓 안심이 된다.
    """
    write_source(git_repo)
    facts = git_repo / "out" / "report-facts.md"
    facts.parent.mkdir(parents=True, exist_ok=True)
    facts.write_text("- src/a.py:4  [signature]  def handle(x):\n"
                     "- src/a.py:6  [usage]      return x + 1\n",
                     encoding="utf-8")
    ext.INVOKERS["codex"] = fake(
        "read it\n\n## RECEIPT\n"
        "STATUS: OK\nCOVERAGE: read src/a.py\n"
        "CONFIDENCE: high - opened directly\nUNCERTAIN: none\n"
        f"FACTS FILE: {facts}\n"
        'KEY FACTS:\n- src/a.py:4 [signature] - "def handle(x):"\n')
    res = ext._execute_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED: 1/1 facts" in res["receipt"]        # 리시트는 통과
    assert "facts file: NOTHING CHECKED" in res["receipt"]
    assert "facts-unverifiable" in res["status"]
    assert "facts file 2 bullets" in res["status"]


def test_format_collapse_never_masks_a_real_failure(ext, git_repo):
    """실패가 있으면 exit 7 이 우선이고, 붕괴 사실은 status 에 덧붙는다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def nonexistent_symbol_xyz():"',
        "- src/a.py:6  [usage]       return x + 1"))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_FACTS_UNVERIFIED
    assert res["status"].startswith("facts-unverified:")


def test_explorer_preamble_declares_facts_file_line_format(ext):
    """본문 형식 미지정이 실측 붕괴의 근본 원인이었다 — 계약에 박혀 있어야 한다."""
    text = (ROOT / "scripts" / "ext_preambles" / "explorer.md").read_text(
        encoding="utf-8")
    assert "FACTS FILE line format is MANDATORY" in text
    assert '- <path>:<line> [tag] — "<verbatim fragment>"' in text
    # KEY FACTS 예시가 한 줄이어야 한다 — 줄바꿈되면 계약 준수가 실패를 만든다
    assert ('- <path>:<line> [signature|call|branch|config|type|import|flow] '
            '— "<verbatim fragment>"') in text


def test_coder_is_not_fact_checked(ext, git_repo):
    """쓰기 역할의 검증은 porcelain 스코프 대조가 담당한다 (회귀 가드)."""
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=write_target)
    res = ext._execute_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "VERIFIED:" not in res["receipt"]


def test_verified_line_survives_control_summary(ext, capsys, git_repo):
    """요약 모드에서 접히면 검증 사실이 stdout 에서 사라진다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        '- src/a.py:4 [definition] - "def handle(x):"'))
    res = ext._execute_job(make_job(git_repo, role="scout"), False)
    ext._print_receipt(res, full=False)
    out = capsys.readouterr().out
    assert "VERIFIED: 1/1 facts" in out
    assert "src/a.py:4" not in out          # 화물은 여전히 접힌다


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


# ------------------------------------------------- wave 실패 격리 · 계약

def test_wave_isolates_crashing_job(tmp_path):
    """job 1개의 예외가 형제 job 의 결과와 마지막 줄 JSON 을 삼키면 안 된다.

    future.result() 가 예외를 재발생시키고 with 블록의 shutdown(wait=True) 때문에
    나머지 job 이 다 끝날 때까지 기다린 뒤 죽는다 — wall-clock 은 전액 지불하고
    출력은 0 이 된다.
    """
    manifest = tmp_path / "wave.json"
    manifest.write_text(json.dumps({"jobs": [
        {"mission": "locate handle()", "report": str(tmp_path / "r1.md"),
         "role": "scout"},
        {"mission": "no report key", "role": "scout"},          # ← 불량 job
    ]}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "wave", "--manifest", str(manifest),
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"] == "partial"
    assert payload["jobs"][0]["exit"] == 0
    assert payload["jobs"][1]["exit"] == 1
    assert "missing required key: report" in payload["jobs"][1]["status"]
    assert (tmp_path / "r1-spec.md").is_file()   # 정상 job 은 끝까지 갔다


def test_wave_non_dict_job_is_rejected(tmp_path):
    """`isinstance(jobs, list)` 는 원소 타입을 보지 않는다."""
    manifest = tmp_path / "wave.json"
    manifest.write_text(json.dumps({"jobs": ["not-a-job"]}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "wave", "--manifest", str(manifest),
         "--dry-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "job must be an object" in payload["jobs"][0]["status"]


def test_manifest_error_still_emits_json(tmp_path):
    """계약은 '마지막 줄 JSON' — 오류 경로에서도 지켜져야 한다."""
    manifest = tmp_path / "wave.json"
    manifest.write_text("{ not json", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "wave", "--manifest", str(manifest)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"].startswith("error:")


def test_git_porcelain_survives_missing_cwd(ext, tmp_path):
    """subprocess.run 은 cwd 부재·실행파일 부재를 rc 가 아니라 예외로 낸다."""
    assert ext._git_porcelain(str(tmp_path / "does-not-exist")) is None


def test_no_git_snapshot_is_not_fatal(ext, tmp_path):
    """스냅샷을 못 뜨면 스코프 미검증으로 강등되고 job 자체는 성공한다."""
    spec = tmp_path / "spec.md"
    spec.write_text("TASK: x\nTARGET FILES:\n- doc/out.md\nLEDGER: none\n",
                    encoding="utf-8")
    job = {"spec": str(spec), "report": str(tmp_path / "out" / "r.md"),
           "role": "coder", "agent": "codex", "repo": str(tmp_path)}
    ext.INVOKERS["codex"] = fake(CODER_RECEIPT)
    res = ext._run_job(job, False)          # tmp_path 는 git 저장소가 아니다
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "not script-verified" in res["status"]


def test_timeout_path(ext, git_repo):
    """EXIT_TIMEOUT(5) 은 이 스위트에 테스트가 0건이었다."""
    def _invoke(prompt, model, effort, timeout, cwd):
        raise subprocess.TimeoutExpired("codex", timeout, output="partial out")

    ext.INVOKERS["codex"] = _invoke
    res = ext._run_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_TIMEOUT
    assert res["status"] == "timeout"
    raw = Path(res["raw"]).read_text(encoding="utf-8")
    assert "partial out" in raw and "TIMEOUT after" in raw


# ------------------------------------------------- 스코프 대조 양방향

def test_concurrent_coders_do_not_cross_contaminate(ext, git_repo):
    """동시 coder 2개가 서로의 변경을 자기 위반으로 집계하면 안 된다.

    스냅샷 대상은 repo 전역인데 job 마다 독립적으로 뜬다 — 창이 겹치면 A 의
    차집합에 B 의 변경이 섞여 둘 다 거짓 exit 4 가 난다. 그것도 리시트에
    `script-verified` 라벨을 달고 나가므로 오케스트레이터가 의심할 근거가 없다.

    게이트는 두 실행 창을 강제로 겹쳐 실패를 결정적으로 만든다. 락이 들어오면
    뒤 job 이 대기하므로 앞 job 은 1초 타임아웃 후 그냥 진행한다 — Barrier 를
    쓰면 락과 교착하므로 Event + timeout 이어야 한다.
    """
    for name in ("a", "b"):
        (git_repo / f"spec-{name}.md").write_text(
            f"TASK: write {name}\nTARGET FILES:\n- doc/{name}.md\n"
            "LEDGER: none\n", encoding="utf-8")
    events = {"a": threading.Event(), "b": threading.Event()}

    def _invoke(prompt, model, effort, timeout, cwd):
        name = "a" if "write a" in prompt else "b"
        target = Path(cwd) / "doc" / f"{name}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {name}\n", encoding="utf-8")
        events[name].set()
        events["b" if name == "a" else "a"].wait(timeout=1.0)
        return ("did it\n\n## RECEIPT\nSTATUS: DONE\n"
                f"CHANGED: doc/{name}.md\nSPEC: within TARGET FILES\n"
                "VERIFY: pytest -q -> PASS\n"), "", 0

    ext.INVOKERS["codex"] = _invoke
    jobs = [{"spec": str(git_repo / f"spec-{n}.md"),
             "report": str(git_repo / "out" / f"{n}.md"),
             "role": "coder", "agent": "codex", "repo": str(git_repo)}
            for n in ("a", "b")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ext._run_job, j, False) for j in jobs]
        results = [f.result() for f in futures]
    assert [r["exit"] for r in results] == [ext.EXIT_OK, ext.EXIT_OK], \
        [r["status"] for r in results]


def test_pre_dirty_file_modified_outside_scope_is_violation(ext, git_repo):
    """이미 dirty 인 파일의 추가 수정도 스코프 위반이다.

    porcelain 엔트리는 실행 전후 모두 ' M' 이라 집합 차집합으로는 잡히지 않는다.
    exit 4 가 '깨끗한 워킹트리' 라는 어디에도 적히지 않은 전제 위에 서 있던 지점.
    """
    stray = git_repo / "README.md"                  # 추적 중인 파일
    stray.write_text("# Test repo\nlocal edit\n", encoding="utf-8")

    def rogue(repo: Path) -> None:
        write_target(repo)                          # TARGET FILES 안
        (repo / "README.md").write_text(            # TARGET 밖 + 이미 dirty
            "# Test repo\nlocal edit\nagent edit\n", encoding="utf-8")

    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=rogue)
    res = ext._run_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_SPEC_VIOLATION, res["status"]
    assert "README.md" in res["status"]


# ------------------------------------------------- fact 경로 봉쇄

def test_fact_path_outside_repo_is_unparsed(ext, git_repo, tmp_path_factory):
    """저장소 밖 경로는 열지 않는다 — 내용이 리시트·리포트로 새면 안 된다.

    대조 실패 시 _classify_fact 가 그 줄의 내용 60자를 판정문에 싣고, exit 7 은
    요약이 아니라 리시트 전문을 stdout 으로 내보낸다. 봉쇄가 없으면 이 경로가
    임의 파일 내용 유출 통로가 된다.

    git_repo 픽스처가 tmp_path 를 그대로 돌려주므로, 저장소 밖 위치는
    tmp_path_factory 로 따로 만들어야 한다.
    """
    outside = tmp_path_factory.mktemp("outside")
    secret = outside / "secret.txt"
    secret.write_text("SUPER_SECRET_TOKEN_VALUE\n", encoding="utf-8")
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(scout_receipt(
        f'- {secret}:1 [config] - "quote that does not match"'))
    res = ext._run_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 unparsed" in res["receipt"]
    assert "SUPER_SECRET_TOKEN_VALUE" not in res["receipt"]
    assert "SUPER_SECRET_TOKEN_VALUE" not in Path(res["report"]).read_text(
        encoding="utf-8")


def test_facts_file_outside_report_dir_is_ignored(ext, git_repo):
    """FACTS FILE 선언이 report 디렉터리 밖이면 무시하고 유도 경로로 폴백한다.

    victim 은 repo 안이라 repo 경계로는 막히지 않는다 — 경계가 report.parent
    여야 하는 이유가 이 케이스다. 프리앰블은 REPORT 에서 유도하라고 규정하므로
    정상 선언은 항상 그 안이다.
    """
    write_source(git_repo)
    victim = git_repo / "docs" / "architecture.md"
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text('- src/a.py:6 [signature] - `def handle(x):`\n',
                      encoding="utf-8")          # :6 은 드리프트 (실제 :4)
    before = victim.read_bytes()
    ext.INVOKERS["codex"] = fake(
        "read it\n\n## RECEIPT\n"
        "STATUS: OK\nCOVERAGE: read src/a.py\n"
        "CONFIDENCE: high - opened directly\nUNCERTAIN: none\n"
        f"FACTS FILE: {victim}\n"
        'KEY FACTS:\n- src/a.py:4 [signature] - "def handle(x):"\n')
    res = ext._run_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert victim.read_bytes() == before          # 프로젝트 문서 무손상
    assert "outside report dir, ignored" in res["receipt"]


def test_scope_unverifiable_when_digest_fails(ext, git_repo, monkeypatch):
    """지문을 못 뜬 경로는 통과시키지도 위반으로 잡지도 않고 선언한다.

    실환경 IO 오류에서만 발동하는 분기라 monkeypatch 로 강제한다.
    """
    (git_repo / "README.md").write_text("# Test repo\nlocal edit\n",
                                        encoding="utf-8")
    monkeypatch.setattr(ext, "_file_digest", lambda p: None)

    def rogue(repo: Path) -> None:
        write_target(repo)
        (repo / "README.md").write_text(
            "# Test repo\nlocal edit\nagent edit\n", encoding="utf-8")

    ext.INVOKERS["codex"] = fake(CODER_RECEIPT, side_effect=rogue)
    res = ext._run_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "scope partially unverified" in res["status"]
    assert "partially unverified" in res["receipt"]


# ------------------------------------------------- 파서 · 표기 (묶음 D)

@pytest.mark.parametrize("notation", ["4-5", "4/5/7", "4,5"])
def test_drift_correction_collapses_multi_line_notation(ext, git_repo,
                                                        notation):
    """교정이 첫 숫자만 치환하면 `:7-5` 같은 깨진 표기가 하위 스펙으로 간다.

    근거가 확인된 위치는 한 곳뿐이라 범위를 유지할 정보가 없다 — 단일 번호로
    접는 것이 맞다. 계약은 교정된 번호를 "what reaches your next spec" 으로
    규정하므로, 해석 불가한 표기는 JUDGMENT-FREE 게이트의 edit point 정밀도를
    만족하지 못한다.
    """
    write_source(git_repo, text="a\nb\nc\nd\ne\nf\ndef handle(x):\n")
    ext.INVOKERS["codex"] = fake(scout_receipt(
        f'- src/a.py:{notation} [definition] - "def handle(x):"'))
    res = ext._run_job(make_job(git_repo, role="scout"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "1 drifted" in res["receipt"]
    assert "src/a.py:7 [definition]" in res["receipt"]
    assert "src/a.py:7-" not in res["receipt"]
    assert "src/a.py:7/" not in res["receipt"]
    assert "src/a.py:7," not in res["receipt"]


def test_facts_file_none_is_not_an_error(ext, git_repo):
    """프리앰블은 BLOCKED 반환에도 모든 필드를 요구하고 `FACTS FILE: none` 을
    허용한다. 계약을 정확히 지킨 반환이 결함처럼 보이면 안 된다."""
    write_source(git_repo)
    ext.INVOKERS["codex"] = fake(
        "blocked\n\n## RECEIPT\n"
        "STATUS: BLOCKED - mission unbounded, needs scout first\n"
        "COVERAGE: nothing read - blocked\n"
        "CONFIDENCE: low - blocked\n"
        "UNCERTAIN: none\n"
        "FACTS FILE: none\n"
        "KEY FACTS: none\n")
    res = ext._run_job(make_job(git_repo, role="explorer"), False)
    assert res["exit"] == ext.EXIT_OK, res["status"]
    assert "FACTS FILE not found" not in res["receipt"]


def test_field_label_must_start_a_line(ext, git_repo):
    """산문 안의 라벨은 필드가 아니다 — 부분 문자열 검색이면 거짓 통과한다."""
    ext.INVOKERS["codex"] = fake(
        "did the edit\n\n## RECEIPT\n"
        "STATUS: DONE\n"
        "CHANGED: doc/out.md\n"
        "SPEC: within TARGET FILES\n"
        "NOTE: I could not run VERIFY: the harness blocked it\n",
        side_effect=write_target)
    res = ext._run_job(make_job(git_repo), False)
    assert res["exit"] == ext.EXIT_BAD_RECEIPT, res["status"]
    assert "VERIFY" in res["status"]


def test_fold_cargo_counts_grouped_line_numbers_as_one_file(ext):
    """`:4/5/7` 에서 loc 이 `a.py:4/5` 로 잡히면 한 파일이 여럿으로 세어진다."""
    receipt = (
        "FOUND:\n"
        '- src/a.py:4/5/7 [usage] - "handle()"\n'
        '- src/a.py:12 [usage] - "handle()"\n'
        "SEARCHED: rg handle\n"
        "UNCERTAIN: none\n"
        "CONFIDENCE: high - opened directly\n"
    )
    assert "FOUND: 2 across 1 file" in ext._control_summary("scout", receipt)
