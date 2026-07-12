from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ssot_runner_v7.py"
SPEC = importlib.util.spec_from_file_location("ssot_runner_v7_under_test", SCRIPT)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

APP = "Sample"
TASK = "Docs/Sample/TASK/Sample-TASK-001.md"
FC_PATH = "Docs/Sample/Sample-FC.md"
FRD_PATH = "Docs/Sample/FRD/Sample-FRD-002.md"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def make_repo(
    tmp_path: Path, *, fc_text: str = "# FC\nold-value\n", fc_bytes: bytes | None = None,
) -> tuple[Path, Path]:
    repo = tmp_path
    write(repo / "CLAUDE.md", "# Repository rules\n\nPreserve DDD boundaries.\n")
    write(repo / "Docs/DOCUMENT_GUIDE.md", "# Document guide\n\nSSOT changes require evidence.\n")
    write(repo / "scripts/docs_helpers.py", "print('Summary: 7 PASS, 0 WARN, 0 FAIL')\n")
    write(
        repo / TASK,
        "# Sample TASK\n\n| 항목 | 값 |\n|---|---|\n| 상태 | Ready |\n\n"
        "## 목표\nchange FC and document weather behavior\n",
    )
    write(repo / "Docs/Sample/Sample-PRD.md", "# PRD\n")
    write(repo / FC_PATH, fc_text)
    if fc_bytes is not None:
        (repo / FC_PATH).write_bytes(fc_bytes)
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


def governance_id(process: Path) -> str:
    manifest = read_json(process / "governance.json")
    documents = manifest["documents"]
    assert isinstance(documents, list) and documents
    value = documents[0]["governance_id"]
    assert isinstance(value, str)
    return value


def skip(kind: str) -> dict[str, object]:
    return {"ssot_type": kind, "reason": f"{kind} is already complete", "reused_authorities": []}


def exact_update_action(process: Path, *, old: str = "old-value", value: str = "new-value") -> dict[str, object]:
    gov = governance_id(process)
    return {
        "action_id": "ACT-001",
        "ssot_type": "FC",
        "action": "UPDATE",
        "path": FC_PATH,
        "reason": "The current FC omits the approved fact.",
        "fact_ids": ["FACT-001"],
        "relation_ids": [],
        "governance_refs": [gov],
        "apply_mode": "RUNNER_PATCH",
        "mutations": [{
            "mutation_id": "MUT-001",
            "operation": "REPLACE_EXACT",
            "old": old,
            "anchor": None,
            "value": value,
            "expected_count": 1,
            "fact_ids": ["FACT-001"],
            "governance_refs": [gov],
        }],
        "render_blocks": [],
    }


def proposal(
    dispatch: dict[str, object],
    actions: list[dict[str, object]],
    *,
    relations: list[dict[str, object]] | None = None,
    risk_flags: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    kinds = {str(action["ssot_type"]) for action in actions}
    return {
        "contract_version": 7,
        "proposal_id": dispatch["dispatch_id"],
        "disposition": "ACTIVE",
        "facts": [{
            "fact_id": "FACT-001",
            "statement": "weather is required",
            "evidence": ["TASK §1"],
        }],
        "actions": actions,
        "skips": [skip(kind) for kind in runner.SSOT_TYPES if kind not in kinds],
        "relations": relations or [],
        "risk_flags": risk_flags or [],
        "questions": [],
        "unsupported_changes": [],
    }


def write_artifact(dispatch: dict[str, object], value: dict[str, object]) -> Path:
    path = Path(str(dispatch["artifact"]))
    write(path, json.dumps(value, ensure_ascii=False))
    return path


def accept_thinker(process: Path, value: dict[str, object]) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "thinker"
    value["proposal_id"] = dispatch["dispatch_id"]
    artifact = write_artifact(dispatch, value)
    runner.accept_artifact(process, artifact, "test-opus")
    return dispatch


def accept_plan_critic(process: Path, *, risk_level: str = "LOW") -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "plan_critic"
    state = runner.status(process)
    artifact = write_artifact(dispatch, {
        "contract_version": 7,
        "critique_id": dispatch["dispatch_id"],
        "proposal_sha256": state["proposal_sha256"],
        "preview_sha256": state["preview_sha256"],
        "verdict": "APPROVE",
        "defects": [],
        "risk_level": risk_level,
        "question_id": None,
        "question": None,
    })
    runner.accept_artifact(process, artifact, "test-opus")
    return dispatch


def outcome_artifact(process: Path, dispatch: dict[str, object]) -> Path:
    state = runner.status(process)
    return write_artifact(dispatch, {
        "contract_version": 7,
        "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS",
        "failure_class": "NONE",
        "defects": [],
        "question_id": None,
        "question": None,
    })


def reach_update_outcome(repo: Path, process: Path) -> dict[str, object]:
    first = runner.next_action(process)
    value = proposal(first, [exact_update_action(process)])
    value["proposal_id"] = first["dispatch_id"]
    runner.accept_artifact(process, write_artifact(first, value), "test-opus")
    accept_plan_critic(process)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "outcome_critic"
    assert (repo / FC_PATH).read_text(encoding="utf-8") == "# FC\nold-value\n"
    return dispatch


def rendered_create_plan(process: Path, dispatch: dict[str, object]) -> dict[str, object]:
    gov = governance_id(process)
    relation = {
        "relation_id": "REL-001",
        "kind": "FC_FRD_TRACE",
        "source_path": FC_PATH,
        "target_path": FRD_PATH,
        "feature_id": "F002",
        "authority_ids": [],
        "outcome": "CREATE",
        "requirement": "FC and FRD must trace each other.",
        "verification": "MECHANICAL",
    }
    fc = exact_update_action(
        process,
        value="old-value\n| F002 | Weather | Sample-FRD-002 §17 §18 |",
    )
    fc["relation_ids"] = ["REL-001"]
    frd = {
        "action_id": "ACT-002",
        "ssot_type": "FRD",
        "action": "CREATE",
        "path": FRD_PATH,
        "reason": "A permanent functional requirement is missing.",
        "fact_ids": ["FACT-001"],
        "relation_ids": ["REL-001"],
        "governance_refs": [gov],
        "apply_mode": "RUNNER_CREATE_WITH_RENDER",
        "mutations": [{
            "mutation_id": "MUT-002",
            "operation": "CREATE_EXACT",
            "old": None,
            "anchor": None,
            "value": "# FRD\n\n| 기능 ID | F002 |\n\n{{RENDER:RB-001}}\n",
            "expected_count": 0,
            "fact_ids": ["FACT-001"],
            "governance_refs": [gov],
        }],
        "render_blocks": [{
            "render_id": "RB-001",
            "placeholder": "{{RENDER:RB-001}}",
            "purpose": "Describe the approved weather behavior.",
            "fact_ids": ["FACT-001"],
            "governance_refs": [gov],
            "required_literals": ["weather"],
            "forbidden_literals": ["TASK"],
            "max_chars": 500,
        }],
    }
    return proposal(dispatch, [fc, frd], relations=[relation])


def reach_risk_gate(process: Path) -> dict[str, object]:
    dispatch = runner.next_action(process)
    value = rendered_create_plan(process, dispatch)
    runner.accept_artifact(process, write_artifact(dispatch, value), "test-opus")
    accept_plan_critic(process)
    blocked = runner.next_action(process)
    assert blocked["action"] == "ask_user"
    return blocked


def approve_risk(process: Path, blocked: dict[str, object], *, event_id: str = "evt-approval-1") -> None:
    request = blocked["approval_request"]
    assert isinstance(request, dict)
    runner.resolve_block(
        process,
        str(blocked["question_id"]),
        choice="APPROVE",
        actor_kind="user",
        source="interactive_user_prompt",
        event_id=event_id,
        nonce=str(request["nonce"]),
    )


def reach_renderer(process: Path) -> dict[str, object]:
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "renderer"
    return dispatch


def test_init_binds_governance_manifest_and_dispatch_inputs(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    manifest = read_json(process / "governance.json")
    assert manifest["contract_version"] == 7
    documents = manifest["documents"]
    assert isinstance(documents, list)
    displays = {row["display_path"] for row in documents}
    assert "CLAUDE.md" in displays
    assert "Docs/DOCUMENT_GUIDE.md" in displays
    assert all(row["governance_id"].startswith("GOV-") and len(row["sha256"]) == 64 for row in documents)

    dispatch = runner.next_action(process)
    assert "result_path" not in dispatch
    assert str(repo / "CLAUDE.md") in dispatch["input_hashes"]
    assert str(repo / "Docs/DOCUMENT_GUIDE.md") in dispatch["input_hashes"]
    assert str(process / "governance.json") in dispatch["input_hashes"]


def test_exact_update_is_compiled_and_committed_without_sonnet_dispatch(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    thinker = runner.next_action(process)
    value = proposal(thinker, [exact_update_action(process)])
    runner.accept_artifact(process, write_artifact(thinker, value), "test-opus")
    assert "-old-value" in (process / "compiled-preview.patch").read_text(encoding="utf-8")
    assert "+new-value" in (process / "compiled-preview.patch").read_text(encoding="utf-8")

    critic = accept_plan_critic(process)
    outcome = runner.next_action(process)
    assert [thinker["role"], critic["role"], outcome["role"]] == ["thinker", "plan_critic", "outcome_critic"]
    assert outcome["model"] == "opus"
    assert "result_path" not in outcome
    assert runner.status(process)["stage_results"]["render"]["result"] == "NOT_REQUIRED"

    runner.accept_artifact(process, outcome_artifact(process, outcome), "test-opus")
    assert runner.status(process)["terminal_result"] == "DONE"
    assert (repo / FC_PATH).read_text(encoding="utf-8") == "# FC\nnew-value\n"
    assert not any(read_json(path)["role"] == "renderer" for path in (process / "dispatches").glob("*.json"))


def test_exact_update_preserves_crlf_bytes(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path, fc_bytes=b"# FC\r\nold-value\r\n")
    outcome = reach_update_outcome(repo, process)
    preview = (process / "compiled-preview/staging" / FC_PATH).read_bytes()
    assert preview == b"# FC\r\nnew-value\r\n"
    runner.accept_artifact(process, outcome_artifact(process, outcome), "test-opus")
    assert (repo / FC_PATH).read_bytes() == b"# FC\r\nnew-value\r\n"


@pytest.mark.parametrize(
    ("fc_text", "needle", "found"),
    [
        ("# FC\nold-value\n", "not-present", "found 0"),
        ("# FC\nold-value\nold-value\n", "old-value", "found 2"),
    ],
)
def test_exact_mutation_zero_or_multiple_matches_rejects_before_critic(
    tmp_path: Path, fc_text: str, needle: str, found: str,
) -> None:
    _, process = make_repo(tmp_path, fc_text=fc_text)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, [exact_update_action(process, old=needle)])
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, value), "test-opus")
    assert caught.value.code == "MUTATION_PRECONDITION_FAILED"
    assert found in str(caught.value)
    assert not (process / "compiled-contract.json").exists()
    retry = runner.next_action(process)
    assert retry["role"] == "thinker"
    assert retry["dispatch_id"] != dispatch["dispatch_id"]


def test_renderer_has_json_only_contract_and_staging_write_is_discarded(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = reach_renderer(process)
    assert dispatch["staged_path"] is None
    assert dispatch["authorized_paths"] == []
    assert "result_path" not in dispatch
    assert "task" not in dispatch
    assert "approved_contract" not in dispatch
    assert str(repo / TASK) not in dispatch["input_hashes"]
    staged = process / "staging" / FRD_PATH
    base = staged.read_text(encoding="utf-8")
    write(staged, base + "\nMALICIOUS-STAGING-WRITE\n")
    write(process / "staging" / FC_PATH, "MALICIOUS-OTHER-PATH\n")
    artifact = write_artifact(dispatch, {
        "contract_version": 7,
        "render_spec_sha256": dispatch["render_spec_sha256"],
        "blocks": [{"render_id": "RB-001", "markdown": "weather details\n", "fact_ids": ["FACT-001"]}],
    })
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, artifact, "test-sonnet")
    assert caught.value.code in {"RENDERER_WRITE_PROHIBITED", "PROCESS_TAMPERED"}
    final_staged = staged.read_text(encoding="utf-8")
    assert "MALICIOUS-STAGING-WRITE" not in final_staged
    assert "{{RENDER:RB-001}}" not in final_staged
    assert "weather is required" in final_staged
    assert "MALICIOUS-OTHER-PATH" not in (process / "staging" / FC_PATH).read_text(encoding="utf-8")


def test_malformed_renderer_artifact_uses_deterministic_fallback(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = reach_renderer(process)
    artifact = write_artifact(dispatch, {
        "contract_version": 7,
        "render_spec_sha256": dispatch["render_spec_sha256"],
        "blocks": [],
    })
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, artifact, "test-sonnet")
    assert caught.value.code == "RENDER_BLOCK_COVERAGE"
    staged = (process / "staging" / FRD_PATH).read_text(encoding="utf-8")
    assert "{{RENDER:RB-001}}" not in staged
    assert "- weather is required" in staged
    state = runner.status(process)
    assert state["render_fallbacks"] == [FRD_PATH]
    assert state["stage_results"]["render"] == {"owner": "runner", "status": "done", "result": "FALLBACK"}
    assert runner.next_action(process)["role"] == "outcome_critic"


def test_governance_drift_invalidates_active_dispatch(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    write(repo / "Docs/DOCUMENT_GUIDE.md", "# changed governance\n")
    value = proposal(dispatch, [exact_update_action(process)])
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, value), "test-opus")
    assert caught.value.code in {"GOVERNANCE_CHANGED", "STALE_DISPATCH"}
    assert (repo / FC_PATH).read_text(encoding="utf-8") == "# FC\nold-value\n"


def test_noop_cannot_pass_after_a_skipped_ssot_changes(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    thinker = runner.next_action(process)
    noop = proposal(thinker, [])
    noop["disposition"] = "NOOP"
    runner.accept_artifact(process, write_artifact(thinker, noop), "test-opus")
    critic = runner.next_action(process)
    write(repo / FC_PATH, "# FC\nchanged-after-think\n")
    state = runner.status(process)
    artifact = write_artifact(critic, {
        "contract_version": 7,
        "critique_id": critic["dispatch_id"],
        "proposal_sha256": state["proposal_sha256"],
        "preview_sha256": state["preview_sha256"],
        "verdict": "APPROVE",
        "defects": [],
        "risk_level": "LOW",
        "question_id": None,
        "question": None,
    })
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, artifact, "test-opus")
    assert caught.value.code == "STALE_DISPATCH"
    assert runner.status(process)["terminal_result"] == "VERIFY_FAILED"


def test_version_history_mismatch_routes_to_plan_without_sonnet(tmp_path: Path) -> None:
    fc = (
        "# FC\n\n| 항목 | 값 |\n|---|---|\n| 버전 | 1.0 (Draft) |\n\n"
        "## 변경 이력\n| 버전 | 일자 | 변경 요약 | 작성자 |\n|---|---|---|---|\n"
        "| 1.0 | 2026-07-11 | old-value | tester |\n"
    )
    _, process = make_repo(tmp_path, fc_text=fc)
    dispatch = runner.next_action(process)
    action = exact_update_action(
        process,
        old="| 1.0 | 2026-07-11 | old-value | tester |",
        value="| 1.1 | 2026-07-11 | new-value | tester |",
    )
    value = proposal(dispatch, [action])
    runner.accept_artifact(process, write_artifact(dispatch, value), "test-opus")
    accept_plan_critic(process)
    retry = runner.next_action(process)
    assert retry["role"] == "thinker"
    checks = read_json(process / "checks/summary.json")
    assert checks["version_history"]["failures"][0]["code"] == "VERSION_HISTORY_MISMATCH"
    assert not any(read_json(path)["role"] == "renderer" for path in (process / "dispatches").glob("*.json"))


def test_governance_drift_at_commit_preflight_prevents_live_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = reach_update_outcome(repo, process)
    artifact = outcome_artifact(process, dispatch)
    original_commit = runner._commit

    def drift_then_commit(process_arg: Path, state: dict[str, object]) -> None:
        write(repo / "CLAUDE.md", "# governance drift during commit\n")
        original_commit(process_arg, state)

    monkeypatch.setattr(runner, "_commit", drift_then_commit)
    runner.accept_artifact(process, artifact, "test-opus")
    state = runner.status(process)
    assert state["terminal_result"] == "VERIFY_FAILED"
    assert state["final_audit"] == "GOVERNANCE_CHANGED"
    assert (repo / FC_PATH).read_text(encoding="utf-8") == "# FC\nold-value\n"


def test_rejected_artifact_creates_new_dispatch_packet_with_rejection(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    first = runner.next_action(process)
    invalid = proposal(first, [exact_update_action(process)])
    invalid["unexpected"] = True
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(first, invalid), "test-opus")
    assert caught.value.code == "PROPOSAL_SCHEMA"

    retry = runner.next_action(process)
    assert retry["dispatch_id"] != first["dispatch_id"]
    assert retry["dispatch_packet"] != first["dispatch_packet"]
    packet = read_json(Path(str(retry["dispatch_packet"])))
    rejection = packet["last_rejection"]
    assert rejection["dispatch_id"] == first["dispatch_id"]
    assert rejection["error_code"] == "PROPOSAL_SCHEMA"
    assert Path(str(retry["prompt_path"])).is_file()


def test_role_rejects_wrong_model_family(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    value = proposal(dispatch, [exact_update_action(process)])
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, value), "test-sonnet")
    assert caught.value.code == "RESULT_MODEL_MISMATCH"
    assert runner.next_action(process)["role"] == "thinker"


def test_high_risk_approval_requires_and_records_interactive_provenance(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    request = blocked["approval_request"]
    assert isinstance(request, dict)
    with pytest.raises(runner.ContractError) as caught:
        runner.resolve_block(process, str(blocked["question_id"]), choice="APPROVE")
    assert caught.value.code == "APPROVAL_PROVENANCE_REQUIRED"
    assert runner.status(process)["run_status"] == "waiting_user"

    approve_risk(process, blocked, event_id="evt-user-click-42")
    decision = read_json(process / "decision.json")["decisions"][-1]
    assert decision["actor_kind"] == "user"
    assert decision["source"] == "interactive_user_prompt"
    assert decision["event_id"] == "evt-user-click-42"
    assert decision["nonce"] == request["nonce"]
    assert runner.next_action(process)["role"] == "renderer"


def test_risk_approval_rejects_tampered_compiled_preview(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    write(process / "compiled-preview.patch", "tampered preview\n")
    approve_risk(process, blocked, event_id="evt-tampered-preview")
    state = runner.status(process)
    assert state["terminal_result"] == "VERIFY_FAILED"
    assert state["final_audit"] == "COMPILED_PREVIEW_CHANGED"
