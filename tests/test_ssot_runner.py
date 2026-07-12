from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ssot_runner_v6.py"
SPEC = importlib.util.spec_from_file_location("ssot_runner_v6_under_test", SCRIPT)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

APP = "Sample"
TASK = "Docs/Sample/TASK/Sample-TASK-001.md"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(tmp_path: Path, helper_text: str = "print('Summary: 7 PASS, 0 WARN, 0 FAIL')\n") -> tuple[Path, Path]:
    repo = tmp_path
    write(repo / "scripts/docs_helpers.py", helper_text)
    write(
        repo / TASK,
        "# Sample TASK\n\n| 항목 | 값 |\n|---|---|\n| 상태 | Ready |\n\n"
        "## 목표\nchange FC\n",
    )
    write(repo / "Docs/Sample/Sample-PRD.md", "# PRD\n")
    write(repo / "Docs/Sample/Sample-FC.md", "# FC\nold\n")
    write(repo / "Docs/Sample/Sample-ARCHITECTURE.md", "# Architecture\n")
    write(
        repo / "Docs/Sample/Sample-ADR-CATALOG.md",
        "# Catalog\n\n## Accepted\n\n| ADR | Title |\n|---|---|\n| Sample-ADR-001 | Base |\n",
    )
    write(repo / "Docs/Sample/FRD/Sample-FRD-001.md", "# FRD\n| 기능 ID | F001 |\n")
    write(repo / "Docs/Sample/ADR/Sample-ADR-001.md", "# ADR\n| 상태 | Accepted |\n")
    process = repo / ".process" / "Sample-TASK-001"
    runner.init_run(repo, TASK, APP, process)
    return repo, process


def rel(repo: Path, path: str | Path) -> str:
    return Path(path).resolve().relative_to(repo.resolve()).as_posix()


def envelope(
    repo: Path,
    dispatch: dict[str, object],
    status: str,
    *,
    failure_class: str = "NONE",
    changed: list[str] | None = None,
    affected: list[str] | None = None,
    question_id: str | None = None,
    question: str | None = None,
    result_path: Path | None = None,
) -> Path:
    value = {
        "contract_version": 6,
        "dispatch_id": dispatch["dispatch_id"],
        "stage": dispatch["stage"],
        "role": dispatch["role"],
        "mode": dispatch["mode"],
        "status": status,
        "artifact": rel(repo, str(dispatch["artifact"])),
        "failure_class": failure_class,
        "question_id": question_id,
        "question": question,
        "changed": changed or [],
        "affected_paths": affected or [],
        "input_digest": dispatch["input_digest"],
        "actual_model": f"test-{dispatch['model']}",
    }
    path = result_path or Path(str(dispatch["result_path"]))
    write(path, json.dumps(value, ensure_ascii=False))
    return path


def skip(kind: str, *, authorities: list[str] | None = None) -> dict[str, object]:
    return {"ssot_type": kind, "reason": f"{kind} complete", "reused_authorities": authorities or []}


def action(
    action_id: str,
    kind: str,
    path: str,
    *,
    operation: str = "UPDATE",
    relations: list[str] | None = None,
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "ssot_type": kind,
        "action": operation,
        "path": path,
        "edit_scope": "apply the TASK fact",
        "reason": "current SSOT is incomplete",
        "fact_ids": ["FACT-001"],
        "relation_ids": relations or [],
    }


def proposal(
    dispatch: dict[str, object],
    *,
    disposition: str = "ACTIVE",
    actions: list[dict[str, object]] | None = None,
    relations: list[dict[str, object]] | None = None,
    risk_flags: list[str] | None = None,
) -> dict[str, object]:
    actions = actions or []
    action_types = {str(row["ssot_type"]) for row in actions}
    return {
        "contract_version": 6,
        "proposal_id": dispatch["dispatch_id"],
        "disposition": disposition,
        "facts": [{"fact_id": "FACT-001", "statement": "change required", "evidence": ["TASK §1"]}],
        "actions": actions,
        "skips": [skip(kind) for kind in runner.SSOT_TYPES if kind not in action_types],
        "relations": relations or [],
        "risk_flags": risk_flags or [],
        "questions": [],
    }


def accept_thinker(repo: Path, process: Path, value: dict[str, object]) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "thinker"
    value["proposal_id"] = dispatch["dispatch_id"]
    write(Path(str(dispatch["artifact"])), json.dumps(value, ensure_ascii=False))
    runner.accept_result(process, envelope(repo, dispatch, "READY"))
    return dispatch


def accept_critic(repo: Path, process: Path, verdict: str = "APPROVE") -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "plan_critic"
    state = runner.status(process)
    critique = {
        "contract_version": 6,
        "critique_id": dispatch["dispatch_id"],
        "proposal_sha256": state["proposal_sha256"],
        "verdict": verdict,
        "defects": [] if verdict == "APPROVE" else [{
            "defect_id": "DEF-001", "class": "PLAN", "affected_paths": [],
            "description": "proposal is incomplete", "evidence": ["TASK §1"],
        }],
        "risk_level": "LOW",
        "question_id": None,
        "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(critique, ensure_ascii=False))
    status = "PASS" if verdict == "APPROVE" else "FAIL"
    failure = "NONE" if verdict == "APPROVE" else "PLAN"
    runner.accept_result(process, envelope(repo, dispatch, status, failure_class=failure))
    return dispatch


def prepare_fc_update(repo: Path, process: Path) -> None:
    dispatch = runner.next_action(process)
    value = proposal(
        dispatch,
        actions=[action("ACT-001", "FC", "Docs/Sample/Sample-FC.md")],
    )
    accept_thinker(repo, process, value)
    accept_critic(repo, process)


def accept_editor(repo: Path, process: Path, content: str) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "editor"
    write(Path(str(dispatch["staged_path"])), content)
    write(Path(str(dispatch["artifact"])), "staged one path\n")
    runner.accept_result(
        process,
        envelope(repo, dispatch, "PASS", changed=[str(dispatch["affected_path"])]),
    )
    return dispatch


def accept_outcome(repo: Path, process: Path, verdict: str = "PASS") -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "outcome_critic"
    state = runner.status(process)
    review = {
        "contract_version": 6,
        "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": verdict,
        "failure_class": "NONE" if verdict == "PASS" else "EXECUTION",
        "defects": [],
        "question_id": None,
        "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review, ensure_ascii=False))
    runner.accept_result(
        process,
        envelope(repo, dispatch, verdict, failure_class="NONE" if verdict == "PASS" else "EXECUTION"),
    )
    return dispatch


def test_init_creates_v6_evidence_and_runner_generated_prompt(tmp_path: Path):
    _, process = make_repo(tmp_path)
    state = runner.status(process)
    assert state["contract_version"] == 6
    assert state["current_stage"] == "think"
    assert (process / "source.json").is_file()
    assert (process / "authority.json").is_file()
    assert (process / "document-index.json").is_file()
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "thinker"
    assert dispatch["model"] == "opus"
    assert Path(str(dispatch["prompt_path"])).is_file()
    assert dispatch["template_sha256"]
    assert dispatch["input_digest"]


def test_active_update_stays_staged_until_outcome_pass_then_runner_commits(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    before = (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8")
    accept_editor(repo, process, "# FC\nnew\n")
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == before
    assert (process / "staging/Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nnew\n"
    accept_outcome(repo, process)
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nnew\n"
    assert runner.status(process)["terminal_result"] == "DONE"
    assert (process / "commit-manifest.json").is_file()


def test_absolute_in_repo_action_is_normalized_before_contract_freeze(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    absolute = str((repo / "Docs/Sample/Sample-FC.md").resolve())
    accept_thinker(repo, process, proposal(
        dispatch, actions=[action("ACT-001", "FC", absolute)]
    ))
    normalized = json.loads(Path(runner.status(process)["proposal_path"]).read_text(encoding="utf-8"))
    assert normalized["actions"][0]["path"] == "Docs/Sample/Sample-FC.md"
    accept_critic(repo, process)
    editor = runner.next_action(process)
    assert Path(str(editor["staged_path"])).is_relative_to(process / "staging")
    assert editor["affected_path"] == "Docs/Sample/Sample-FC.md"


def test_accept_result_requires_exact_dispatched_result_path(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, disposition="NOOP")
    write(Path(str(dispatch["artifact"])), json.dumps(value))
    rogue = process / "results/rogue.json"
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY", result_path=rogue))
    assert raised.value.code == "RESULT_PATH_MISMATCH"
    assert runner.next_action(process)["dispatch_id"] == dispatch["dispatch_id"]


def test_frd_create_without_fc_trace_is_rejected_before_critic(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(
        dispatch,
        actions=[action("ACT-001", "FRD", "Docs/Sample/FRD/Sample-FRD-002.md", operation="CREATE")],
    )
    write(Path(str(dispatch["artifact"])), json.dumps(value))
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY"))
    assert raised.value.code == "PLAN_INVARIANT_FAILED"
    assert not (process / "approved-contract.json").exists()


def test_plan_critic_rejection_returns_to_fresh_thinker_revision(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    accept_thinker(
        repo,
        process,
        proposal(dispatch, actions=[action("ACT-001", "FC", "Docs/Sample/Sample-FC.md")]),
    )
    accept_critic(repo, process, "REJECT")
    next_dispatch = runner.next_action(process)
    assert next_dispatch["role"] == "thinker"
    assert next_dispatch["mode"] == "revise"
    assert runner.status(process)["plan_revisions"] == 1
    assert not (process / "staging").exists()


def test_noop_finishes_after_plan_critique_without_editor(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    accept_thinker(repo, process, proposal(dispatch, disposition="NOOP"))
    accept_critic(repo, process)
    done = runner.next_action(process)
    assert done["action"] == "done"
    assert done["terminal_result"] == "NOOP"
    assert runner.report(process).splitlines()[-1] == "Next: work-packet-write"
    assert not (process / "staging").exists()


def test_obsolete_requires_user_gate_and_stops_downstream(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    accept_thinker(repo, process, proposal(dispatch, disposition="OBSOLETE"))
    accept_critic(repo, process)
    ask = runner.next_action(process)
    assert ask["action"] == "ask_user"
    runner.resolve_block(process, str(ask["question_id"]), choice="APPROVE")
    assert runner.status(process)["terminal_result"] == "OBSOLETE"
    assert runner.report(process).splitlines()[-1] == "Next: STOP"


def test_risk_approval_is_bound_to_exact_proposal_bytes(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    accept_thinker(repo, process, proposal(dispatch, disposition="OBSOLETE"))
    accept_critic(repo, process)
    ask = runner.next_action(process)
    proposal_path = Path(runner.status(process)["proposal_path"])
    mutated = json.loads(proposal_path.read_text(encoding="utf-8"))
    mutated["facts"][0]["statement"] = "silently changed after approval prompt"
    write(proposal_path, json.dumps(mutated))
    with pytest.raises(runner.ContractError) as raised:
        runner.resolve_block(process, str(ask["question_id"]), choice="APPROVE")
    assert raised.value.code == "STALE_APPROVAL"
    assert runner.status(process)["run_status"] == "waiting_user"
    decisions = json.loads((process / "decision.json").read_text(encoding="utf-8"))
    assert decisions["decisions"] == []


def test_role_cannot_modify_runner_control_state(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    write(Path(str(dispatch["artifact"])), json.dumps(proposal(dispatch, disposition="NOOP")))
    state = json.loads((process / "state.json").read_text(encoding="utf-8"))
    state["last_result"] = "tampered by role"
    write(process / "state.json", json.dumps(state))
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY"))
    assert raised.value.code == "PROCESS_TAMPERED"


def test_role_cannot_create_untracked_source_file(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    write(Path(str(dispatch["artifact"])), json.dumps(proposal(dispatch, disposition="NOOP")))
    write(repo / "src/rogue.py", "print('unauthorized')\n")
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY"))
    assert raised.value.code == "LIVE_WRITE_PROHIBITED"


def test_malformed_proposal_nested_types_are_contract_rejections(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, disposition="NOOP")
    value["facts"][0]["fact_id"] = []
    write(Path(str(dispatch["artifact"])), json.dumps(value))
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY"))
    assert raised.value.code == "PROPOSAL_FACT"
    repeated = runner.next_action(process)
    assert repeated["dispatch_id"] == dispatch["dispatch_id"]
    assert repeated["last_rejection"]["error_code"] == "PROPOSAL_FACT"


def test_frd_create_with_stale_fc_trace_routes_only_relation_paths_to_repair(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    write(repo / "Docs/Sample/Sample-FC.md", "# FC\n| F014 | missing | 미작성/추후 |\n")
    dispatch = runner.next_action(process)
    relation = {
        "relation_id": "REL-001", "kind": "FC_FRD_TRACE",
        "source_path": "Docs/Sample/Sample-FC.md",
        "target_path": "Docs/Sample/FRD/Sample-FRD-014.md",
        "feature_id": "F014", "authority_ids": [],
        "outcome": "CREATE_AND_TRACE",
        "requirement": "FC points to FRD acceptance and tests",
        "verification": "MECHANICAL",
    }
    actions = [
        action("ACT-001", "FC", "Docs/Sample/Sample-FC.md", relations=["REL-001"]),
        action("ACT-002", "FRD", "Docs/Sample/FRD/Sample-FRD-014.md", operation="CREATE", relations=["REL-001"]),
    ]
    accept_thinker(repo, process, proposal(dispatch, actions=actions, relations=[relation]))
    accept_critic(repo, process)
    ask = runner.next_action(process)
    runner.resolve_block(process, str(ask["question_id"]), choice="APPROVE")
    accept_editor(repo, process, "# FC\nchanged\n| F014 | still missing | 미작성/추후 |\n")
    accept_editor(repo, process, "# Sample-FRD-014\n| 기능 ID | F014 |\n## 17. 수용 기준\n## 18. 테스트 관점\n")
    state = runner.status(process)
    assert state["current_stage"] == "edit"
    assert state["next_mode"] == "repair"
    assert set(state["editor_queue"]) == {
        "Docs/Sample/Sample-FC.md", "Docs/Sample/FRD/Sample-FRD-014.md"
    }
    assert "old" in (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") or "missing" in (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8")


def test_adr_reuse_rejects_unresolved_frd_placeholder(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    write(repo / "Docs/Sample/FRD/Sample-FRD-001.md", "# FRD\n| 기능 ID | F001 |\n| ADR | 검토 필요 |\n")
    dispatch = runner.next_action(process)
    relation = {
        "relation_id": "REL-ADR", "kind": "ADR_DISPOSITION",
        "source_path": "Docs/Sample/FRD/Sample-FRD-001.md",
        "target_path": None, "feature_id": "F001",
        "authority_ids": ["Sample-ADR-001"], "outcome": "REUSE_EXISTING",
        "requirement": "FRD records reused ADR and resolved catalog outcome",
        "verification": "MECHANICAL",
    }
    value = proposal(
        dispatch,
        actions=[action("ACT-001", "FRD", "Docs/Sample/FRD/Sample-FRD-001.md", relations=["REL-ADR"])],
        relations=[relation],
    )
    accept_thinker(repo, process, value)
    accept_critic(repo, process)
    accept_editor(repo, process, "# FRD changed\n| 기능 ID | F001 |\n| ADR | 검토 필요 |\n")
    checks = json.loads((process / "checks/summary.json").read_text(encoding="utf-8"))
    assert checks["status"] == "FAIL"
    assert checks["relations"]["failures"][0]["code"] == "STALE_ADR_PLACEHOLDER"
    assert runner.status(process)["next_mode"] == "repair"


def test_outcome_pass_cannot_override_failed_mechanical_check(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    checks = json.loads((process / "checks/summary.json").read_text(encoding="utf-8"))
    checks["status"] = "FAIL"
    write(process / "checks/summary.json", json.dumps(checks))
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "outcome_critic"
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    assert raised.value.code in {"STALE_DISPATCH", "MECHANICAL_GATE_FAILED"}
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"


def test_live_target_change_before_commit_causes_conflict_without_overwrite(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nstaged\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    write(repo / "Docs/Sample/Sample-FC.md", "# FC\nuser change\n")
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    assert raised.value.code == "LIVE_WRITE_PROHIBITED"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nuser change\n"
    assert not (process / "commit-manifest.json").exists()


def test_commit_rechecks_approved_contract_hash_after_outcome_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_commit = globals_["_commit"]

    def tamper_then_commit(process_arg: Path, state_arg: dict[str, object]) -> None:
        contract_path = process_arg / "approved-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["relations"] = [{"tampered": True}]
        write(contract_path, json.dumps(contract))
        original_commit(process_arg, state_arg)

    monkeypatch.setitem(globals_, "_commit", tamper_then_commit)
    runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    state = runner.status(process)
    assert state["terminal_result"] == "VERIFY_FAILED"
    assert state["final_audit"] == "APPROVED_CONTRACT_TAMPERED"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"


def test_dispatch_receipt_records_model_template_and_input_hashes(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, disposition="NOOP")
    write(Path(str(dispatch["artifact"])), json.dumps(value))
    runner.accept_result(process, envelope(repo, dispatch, "READY"))
    receipt = json.loads((process / f"receipts/{dispatch['dispatch_id']}.json").read_text(encoding="utf-8"))
    assert receipt["requested_model"] == "opus"
    assert receipt["actual_model"] == "test-opus"
    assert receipt["template_sha256"] == dispatch["template_sha256"]
    assert receipt["input_digest"] == dispatch["input_digest"]


def test_staging_mutation_after_outcome_dispatch_invalidates_result(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    write(process / "staging/Docs/Sample/Sample-FC.md", "# FC\nmutated after review dispatch\n")
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    assert raised.value.code == "STALE_DISPATCH"
    repeated = runner.next_action(process)
    assert repeated["role"] == "outcome_critic"
    assert repeated["dispatch_id"] != dispatch["dispatch_id"]
    assert repeated["last_rejection"]["error_code"] == "STALE_DISPATCH"
    assert not (process / "commit-manifest.json").exists()


def test_task_mutation_invalidates_active_planning_dispatch(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, disposition="NOOP")
    write(Path(str(dispatch["artifact"])), json.dumps(value))
    write(repo / TASK, "# changed TASK\n")
    with pytest.raises(runner.ContractError) as raised:
        runner.accept_result(process, envelope(repo, dispatch, "READY"))
    assert raised.value.code == "STALE_DISPATCH"
    done = runner.next_action(process)
    assert done["action"] == "done"
    assert done["terminal_result"] == "VERIFY_FAILED"
    assert "SOURCE_CHANGED" in runner.report(process)


def test_commit_second_path_failure_rolls_back_first_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    actions = [
        action("ACT-001", "FC", "Docs/Sample/Sample-FC.md"),
        action("ACT-002", "ARCHITECTURE", "Docs/Sample/Sample-ARCHITECTURE.md"),
    ]
    accept_thinker(repo, process, proposal(dispatch, actions=actions))
    accept_critic(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    accept_editor(repo, process, "# Architecture\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_replace = globals_["_replace_commit_target"]
    calls = {"count": 0}

    def fail_second(temp: Path, target: Path) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected second-path failure")
        original_replace(temp, target)

    monkeypatch.setitem(globals_, "_replace_commit_target", fail_second)
    runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    state = runner.status(process)
    assert state["terminal_result"] == "COMMIT_FAILED_ROLLED_BACK"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"
    assert (repo / "Docs/Sample/Sample-ARCHITECTURE.md").read_text(encoding="utf-8") == "# Architecture\n"
    journal = json.loads((process / "commit-journal.json").read_text(encoding="utf-8"))
    assert journal["status"] == "ROLLED_BACK"
    assert not list((repo / "Docs/Sample").glob(".*.tmp"))
    assert runner.report(process).splitlines()[-1] == "Next: STOP"


def test_resume_rolls_back_crash_after_replace_before_journal_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_replace = globals_["_replace_commit_target"]
    crashed = {"value": False}

    def crash_once_after_replace(temp: Path, target: Path) -> None:
        original_replace(temp, target)
        if not crashed["value"]:
            crashed["value"] = True
            raise SystemExit(91)

    monkeypatch.setitem(globals_, "_replace_commit_target", crash_once_after_replace)
    with pytest.raises(SystemExit):
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    assert runner.status(process)["run_status"] == "committing"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nnew\n"
    journal = json.loads((process / "commit-journal.json").read_text(encoding="utf-8"))
    assert journal["entries"][0]["phase"] == "REPLACING"
    done = runner.next_action(process)
    assert done["terminal_result"] == "COMMIT_FAILED_ROLLED_BACK"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"


def test_resume_rolls_forward_committed_journal_before_state_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_finalize = globals_["_finalize"]
    crashed = {"value": False}

    def crash_once_before_final_state(process_arg: Path, state_arg: dict[str, object], terminal: str, audit: str) -> None:
        if terminal == "DONE" and not crashed["value"]:
            crashed["value"] = True
            raise SystemExit(92)
        original_finalize(process_arg, state_arg, terminal, audit)

    monkeypatch.setitem(globals_, "_finalize", crash_once_before_final_state)
    with pytest.raises(SystemExit):
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    assert runner.status(process)["run_status"] == "committing"
    assert json.loads((process / "commit-journal.json").read_text(encoding="utf-8"))["status"] == "COMMITTED"
    done = runner.next_action(process)
    assert done["terminal_result"] == "DONE"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nnew\n"


def test_recovery_preserves_third_party_change_and_requires_manual_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_replace = globals_["_replace_commit_target"]
    crashed = {"value": False}

    def crash_once_after_replace(temp: Path, target: Path) -> None:
        original_replace(temp, target)
        if not crashed["value"]:
            crashed["value"] = True
            raise SystemExit(93)

    monkeypatch.setitem(globals_, "_replace_commit_target", crash_once_after_replace)
    with pytest.raises(SystemExit):
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    write(repo / "Docs/Sample/Sample-FC.md", "# FC\nuser emergency edit\n")
    done = runner.next_action(process)
    assert done["terminal_result"] == "RECOVERY_REQUIRED"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nuser emergency edit\n"


def test_recovery_lock_contention_is_retryable_not_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    dispatch = runner.next_action(process)
    state = runner.status(process)
    review = {
        "contract_version": 6, "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS", "failure_class": "NONE", "defects": [],
        "question_id": None, "question": None,
    }
    write(Path(str(dispatch["artifact"])), json.dumps(review))
    globals_ = runner._commit.__globals__
    original_replace = globals_["_replace_commit_target"]
    crashed = {"value": False}

    def crash_once_after_replace(temp: Path, target: Path) -> None:
        original_replace(temp, target)
        if not crashed["value"]:
            crashed["value"] = True
            raise SystemExit(94)

    monkeypatch.setitem(globals_, "_replace_commit_target", crash_once_after_replace)
    with pytest.raises(SystemExit):
        runner.accept_result(process, envelope(repo, dispatch, "PASS"))
    commit_lock = repo / ".process/.ssot-write-Sample.commit.lock"
    with globals_["_advisory_file_lock"](commit_lock, "TEST_LOCK"):
        retry = runner.next_action(process)
    assert retry["action"] == "retry"
    assert retry["reason"] == "COMMIT_LOCKED"
    assert runner.status(process)["run_status"] == "committing"
    done = runner.next_action(process)
    assert done["terminal_result"] == "COMMIT_FAILED_ROLLED_BACK"
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"


def test_v5_process_is_not_loaded_by_v6_api(tmp_path: Path):
    _, process = make_repo(tmp_path)
    state = json.loads((process / "state.json").read_text(encoding="utf-8"))
    state["contract_version"] = 5
    write(process / "state.json", json.dumps(state))
    with pytest.raises(runner.ContractError) as raised:
        runner.status(process)
    assert raised.value.code == "CONTRACT_VERSION_MISMATCH"


def test_authority_parser_keeps_structured_supersession_evidence(tmp_path: Path):
    repo, _ = make_repo(tmp_path)
    write(repo / TASK, "# TASK\n\n| 상태 | Draft |\n\nBasis SAMPLE-ADR-001.\n")
    write(repo / "Docs/Sample/ADR/Sample-ADR-001.md", "# ADR 1\n| 상태 | Superseded (by Sample-ADR-002) |\n")
    write(repo / "Docs/Sample/ADR/Sample-ADR-002.md", "# ADR 2\n| 상태 | Accepted |\n- **supersedes**: Sample-ADR-001\n")
    process = repo / ".process" / "authority"
    runner.init_run(repo, TASK, APP, process)
    authority = json.loads((process / "authority.json").read_text(encoding="utf-8"))
    assert authority["chains"]["Sample-ADR-001"] == ["Sample-ADR-001", "Sample-ADR-002"]
    assert authority["terminal_candidates"]["Sample-ADR-001"] == ["Sample-ADR-002"]
    assert authority["conflicts"] == []


def test_report_detects_committed_output_tampering(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    accept_outcome(repo, process)
    write(repo / "Docs/Sample/Sample-FC.md", "tampered\n")
    with pytest.raises(runner.ContractError) as raised:
        runner.report(process)
    assert raised.value.code == "REPORT_OUTPUT_TAMPERED"


def test_preexisting_helper_failure_is_not_misattributed_to_staged_change(tmp_path: Path):
    helper = "import sys\nprint('FAIL PREEXIST Docs/Sample/Sample-ADR-CATALOG.md existing catalog issue')\nprint('Summary: 0 PASS, 0 WARN, 1 FAIL')\nsys.exit(1)\n"
    repo, process = make_repo(tmp_path, helper)
    baseline = json.loads((process / "checks/baseline-docs-helper.json").read_text(encoding="utf-8"))
    assert baseline["status"] == "FAIL"
    prepare_fc_update(repo, process)
    accept_editor(repo, process, "# FC\nnew\n")
    checks = json.loads((process / "checks/summary.json").read_text(encoding="utf-8"))
    assert checks["docs_helper"]["status"] == "FAIL"
    assert checks["docs_helper"]["effective_status"] == "PASS"
    assert checks["docs_helper"]["new_failures"] == []
    accept_outcome(repo, process)
    assert runner.status(process)["terminal_result"] == "DONE"


def test_helper_failure_without_stable_failure_identity_fails_init(tmp_path: Path):
    helper = "import sys\nprint('helper infrastructure failed')\nsys.exit(1)\n"
    with pytest.raises(runner.ContractError) as raised:
        make_repo(tmp_path, helper)
    assert raised.value.code == "HELPER_INFRA_FAILURE"


def test_generic_helper_failure_cannot_be_waived_as_preexisting(tmp_path: Path):
    helper = "import sys\nprint('FAIL GENERIC invariant')\nprint('Summary: 0 PASS, 0 WARN, 1 FAIL')\nsys.exit(1)\n"
    with pytest.raises(runner.ContractError) as raised:
        make_repo(tmp_path, helper)
    assert raised.value.code == "HELPER_INFRA_FAILURE"


def test_baseline_helper_mutation_is_isolated_from_live_docs(tmp_path: Path):
    helper = (
        "from pathlib import Path\nimport sys\n"
        "root=Path(sys.argv[sys.argv.index('--repo')+1])\n"
        "(root/'Docs/Sample/Sample-FC.md').write_text('mutated by helper\\n', encoding='utf-8')\n"
        "print('Summary: 7 PASS, 0 WARN, 0 FAIL')\n"
    )
    with pytest.raises(runner.ContractError) as raised:
        make_repo(tmp_path, helper)
    assert raised.value.code == "HELPER_MUTATED_DOCS"
    assert (tmp_path / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"


def test_helper_version_drift_blocks_without_sonnet_repair_loop(tmp_path: Path):
    repo, process = make_repo(tmp_path)
    prepare_fc_update(repo, process)
    write(repo / "scripts/docs_helpers.py", "print('Summary: 8 PASS, 0 WARN, 0 FAIL')\n")
    accept_editor(repo, process, "# FC\nnew\n")
    state = runner.status(process)
    assert state["terminal_result"] == "VERIFY_FAILED"
    assert state["final_audit"] == "DOCS_HELPER_UNSTABLE"
    assert state["repair_attempts"] == {}
    assert (repo / "Docs/Sample/Sample-FC.md").read_text(encoding="utf-8") == "# FC\nold\n"
