from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ssot_runner_v8.py"
SPEC = importlib.util.spec_from_file_location("ssot_runner_v8_under_test", SCRIPT)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "ssot_runner_wrapper_under_test", ROOT / "scripts" / "ssot_runner.py",
)
assert WRAPPER_SPEC and WRAPPER_SPEC.loader
wrapper = importlib.util.module_from_spec(WRAPPER_SPEC)
WRAPPER_SPEC.loader.exec_module(wrapper)

APP = "Sample"
TASK = "Docs/Sample/TASK/Sample-TASK-001.md"
FC_PATH = "Docs/Sample/Sample-FC.md"
FRD_PATH = "Docs/Sample/FRD/Sample-FRD-002.md"
FRD_TEMPLATE = "Docs/.templates/App/FRD/APP-FRD-001-TEMPLATE.md"

AUTHORITY_CHECKS = (
    "AUTH-TASK-GOVERNANCE",
    "AUTH-ADR-STATUS",
    "AUTH-DDD-LAYER",
    "AUTH-DOC-GOVERNANCE",
    "AUTH-SCOPE",
)
CHANGE_CHECKS = (
    "CHANGE-SIX-TYPE-COVERAGE",
    "CHANGE-CLAIM-BINDING",
    "CHANGE-PREVIEW-EXACTNESS",
    "CHANGE-CROSS-DOC",
    "CHANGE-NO-FULL-PROSE",
)
OUTCOME_CHECKS = (
    "OUTCOME-CLAIM-SATISFACTION",
    "OUTCOME-AUTHORITY-PRESERVATION",
    "OUTCOME-CROSS-DOC",
    "OUTCOME-RENDER-BOUNDS",
    "OUTCOME-MECHANICAL-GATES",
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def make_repo(tmp_path: Path, *, ddd_violation: bool = False) -> tuple[Path, Path]:
    repo = tmp_path
    write(repo / "CLAUDE.md", "# Repository rules\n\nPreserve the bound DDD rules.\n")
    write(
        repo / ".claude/rules/DDD_ARCHITECTURE_RULES.md",
        "# DDD rules\n\nHTTP/API client implementations belong in Infrastructure; "
        "Application contains ports only.\n",
    )
    write(repo / "Docs/DOCUMENT_GUIDE.md", "# Document guide\n\nSSOT changes require exact evidence.\n")
    write(repo / "scripts/docs_helpers.py", "print('Summary: 7 PASS, 0 WARN, 0 FAIL')\n")
    implementation = (
        "- Src/Sample/Application/External/WeatherApiClient.cs implements HttpClient calls.\n"
        if ddd_violation
        else "- Src/Sample/Infrastructure/External/WeatherApiClient.cs implements outbound calls.\n"
    )
    write(
        repo / TASK,
        "# Sample TASK\n\n## Goal\n\nCollect weather observations.\n\n## Implementation scope\n\n"
        + "- Src/Sample/Application/Port/Weather/IWeatherApiClient.cs defines the external port.\n"
        + "- Src/Sample/Application/Weather/WeatherPollingService.cs implements IHostedService.\n"
        + implementation,
    )
    write(repo / "Docs/Sample/Sample-PRD.md", "# PRD\n")
    write(repo / FC_PATH, "# FC\nold-value\n")
    write(repo / "Docs/Sample/Sample-ARCHITECTURE.md", "# Architecture\n")
    write(
        repo / "Docs/Sample/Sample-ADR-CATALOG.md",
        "# Catalog\n\n## Accepted\n\n| ADR | Status |\n|---|---|\n| Sample-ADR-001 | Accepted |\n",
    )
    write(repo / "Docs/Sample/FRD/Sample-FRD-001.md", "# Existing FRD\n\n| Feature | F001 |\n")
    write(
        repo / "Docs/Sample/ADR/Sample-ADR-001.md",
        "# Sample-ADR-001\n\n| Status | Accepted |\n\nBase infrastructure decision.\n",
    )
    canonical_sections = "\n".join(
        f"## {index}. {title}\n"
        for index, (_, _, title) in enumerate(runner.contract_v8.FRD_SECTION_SLOTS, start=1)
    )
    write(
        repo / FRD_TEMPLATE,
        f"# {{{{DOCUMENT_ID}}}}\n\n| Feature | {{{{FEATURE_ID}}}} |\n\n{canonical_sections}",
    )
    process = repo / ".process" / "Sample-TASK-001"
    runner.init_run(repo, TASK, APP, process)
    return repo, process


def write_artifact(dispatch: dict[str, object], value: dict[str, object]) -> Path:
    path = Path(str(dispatch["artifact"]))
    write(path, json.dumps(value, ensure_ascii=False))
    return path


def evidence_for_path(
    dispatch: dict[str, object], path: Path, *, contains: str | None = None,
) -> str:
    catalog = read_json(Path(str(dispatch["evidence_catalog"])))
    expected = path.resolve()
    documents = catalog["documents"]
    assert isinstance(documents, list)
    document = next(
        row for row in documents
        if isinstance(row, dict) and Path(str(row["path"])).resolve() == expected
    )
    for row in runner._catalog_entry_map(catalog).values():
        if not isinstance(row, dict) or row.get("document_id") != document["document_id"]:
            continue
        if contains is not None and contains not in str(row["quote"]):
            continue
        return str(row["evidence_id"])
    raise AssertionError(f"No meaningful evidence ID in {expected}; contains={contains!r}")


def evidence_row(dispatch: dict[str, object], evidence_id: str) -> dict[str, object]:
    catalog = read_json(Path(str(dispatch["evidence_catalog"])))
    return runner._catalog_entry_map(catalog)[evidence_id]


def bound_evidence(dispatch: dict[str, object], preferred: Path | None = None) -> str:
    hashes = dispatch["input_hashes"]
    assert isinstance(hashes, dict) and hashes
    candidates = [Path(str(path)) for path in hashes]
    if preferred is not None:
        preferred = preferred.resolve()
        candidates.sort(key=lambda path: path.resolve() != preferred)
    for path in candidates:
        if path.is_file():
            try:
                return evidence_for_path(dispatch, path)
            except AssertionError:
                continue
    raise AssertionError("Dispatch has no meaningful bound evidence")


def authority_certificate(
    dispatch: dict[str, object], *, failed_check: str | None = None,
) -> dict[str, object]:
    process = Path(str(dispatch["process"]))
    repo = Path(str(runner.status(process)["repo_root"]))
    task_scope = evidence_for_path(dispatch, repo / TASK, contains="Collect weather observations")
    task_implementation = evidence_for_path(dispatch, repo / TASK, contains="WeatherApiClient")
    repository_governance = evidence_for_path(dispatch, repo / "CLAUDE.md", contains="Preserve")
    authority_graph = evidence_for_path(dispatch, process / "authority.json", contains="contract_version")
    ddd_rule = evidence_for_path(
        dispatch,
        repo / ".claude/rules/DDD_ARCHITECTURE_RULES.md",
        contains="Infrastructure",
    )
    document_guide = evidence_for_path(
        dispatch, repo / "Docs/DOCUMENT_GUIDE.md", contains="SSOT changes",
    )
    catalog = evidence_for_path(
        dispatch, repo / "Docs/Sample/Sample-ADR-CATALOG.md", contains="Sample-ADR-001",
    )
    check_evidence = {
        "AUTH-TASK-GOVERNANCE": [task_scope, repository_governance],
        "AUTH-ADR-STATUS": [authority_graph, catalog],
        "AUTH-DDD-LAYER": [task_implementation, ddd_rule],
        "AUTH-DOC-GOVERNANCE": [document_guide],
        "AUTH-SCOPE": [task_scope],
    }
    decision_evidence = None
    if dispatch.get("decision_has_answers"):
        decision_evidence = evidence_for_path(
            dispatch, process / "decision.json", contains='"answer":',
        )
        check_evidence["AUTH-SCOPE"].append(decision_evidence)
    checks = [
        {
            "check_id": check_id,
            "verdict": "FAIL" if check_id == failed_check else "PASS",
            "finding": f"{check_id}를 결속된 증거로 검토했다.",
            "evidence_ids": check_evidence[check_id],
        }
        for check_id in AUTHORITY_CHECKS
    ]
    return {
        "contract_version": 8,
        "certificate_id": dispatch["dispatch_id"],
        "input_digest": dispatch["input_digest"],
        "verdict": "FAIL" if failed_check else "PASS",
        "checks": checks,
        "authority_facts": [{
            "authority_id": "AUTHORITY-001",
            "statement": "승인된 범위에는 날씨 관측값 수집이 포함된다.",
            "check_ids": ["AUTH-SCOPE"],
            "evidence_ids": [task_scope, *([decision_evidence] if decision_evidence else [])],
        }] if not failed_check else [],
        "prohibitions": [],
        "questions": [],
        "candidate_judgments": [{
            "candidate_id": candidate_id,
            "verdict": "FAIL" if failed_check == "AUTH-DDD-LAYER" else "PASS",
            "finding": "후보의 레이어 배치를 결속된 TASK와 DDD 규칙으로 판정했다.",
            "evidence_ids": [
                *next(
                    row["task_evidence_ids"]
                    for row in read_json(Path(str(dispatch["authority_candidates"]))) ["candidates"]
                    if row["candidate_id"] == candidate_id
                ),
                ddd_rule,
            ],
        } for candidate_id in dispatch.get("required_candidate_ids", [])],
        "supplemental_candidates": [],
    }


def accept_authority(process: Path) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "authority_critic"
    artifact = write_artifact(dispatch, authority_certificate(dispatch))
    runner.accept_artifact(process, artifact, "test-opus")
    return dispatch


def claim(dispatch: dict[str, object] | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "claim_id": "CLM-001",
        "kind": "REQUIREMENT",
        "statement": "시스템은 날씨 관측값을 수집한다.",
        "authority_ids": ["AUTHORITY-001"],
        "authority_check_ids": ["AUTH-SCOPE"],
        "target_types": list(runner.SSOT_TYPES),
    }
    if dispatch is None:
        value["evidence"] = [{"path": TASK, "line": 5, "quote": "Collect weather observations."}]
    else:
        repo = Path(str(runner.status(Path(str(dispatch["process"])))["repo_root"]))
        value["evidence_ids"] = [
            evidence_for_path(dispatch, repo / TASK, contains="Collect weather observations")
        ]
    return value


def skip(kind: str) -> dict[str, object]:
    return {
        "ssot_type": kind,
        "reason": f"{kind}에는 영구 문서 변경이 필요하지 않다.",
        "claim_ids": ["CLM-001"],
        "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
    }


def frd_create_action(*, with_render: bool = False) -> dict[str, object]:
    render_blocks: list[dict[str, object]] = []
    if with_render:
        render_blocks.append({
            "render_id": "RB-001",
            "section_id": "SEC-008",
            "purpose": "이미 승인된 수집 맥락을 한국어로 설명한다.",
            "claim_ids": ["CLM-001"],
            "required_literals": ["날씨"],
            "forbidden_literals": ["TASK", "TODO"],
            "max_chars": 400,
        })
    return {
        "action_id": "ACT-001",
        "ssot_type": "FRD",
        "action": "CREATE",
        "path": FRD_PATH,
        "reason": "승인된 기능에 대응하는 영구 FRD가 없다.",
        "claim_ids": ["CLM-001"],
        "relation_ids": ["REL-001"],
        "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        "apply_mode": "RUNNER_CREATE_FROM_CLAIMS",
        "mutations": [],
        "creation_spec": {
            "document_id": "Sample-FRD-002",
            "feature_id": "F002",
            "title": "날씨 관측값 수집",
            "template_path": FRD_TEMPLATE,
            "metadata": {"version": "0.1", "status": "Draft", "date": "2026-07-11"},
            "sections": [{
                "section_id": "SEC-008",
                "template_slot": "functional_requirements",
                "claim_ids": ["CLM-001"],
                "render_mode": "DETERMINISTIC",
            }],
        },
        "render_blocks": render_blocks,
    }


def fc_update_action() -> dict[str, object]:
    return {
        "action_id": "ACT-002",
        "ssot_type": "FC",
        "action": "UPDATE",
        "path": FC_PATH,
        "reason": "FC에 신규 FRD 추적 행이 필요하다.",
        "claim_ids": ["CLM-001"],
        "relation_ids": ["REL-001"],
        "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        "apply_mode": "RUNNER_PATCH",
        "mutations": [{
            "mutation_id": "MUT-001",
            "operation": "REPLACE_EXACT",
            "old": "old-value",
            "anchor": None,
            "value": "old-value\n| F002 | Weather observation collection | Sample-FRD-002 §17 §18 |",
            "expected_count": 1,
            "claim_ids": ["CLM-001"],
            "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        }],
        "creation_spec": None,
        "render_blocks": [],
    }


def active_frd_proposal(
    dispatch: dict[str, object], process: Path, *, with_render: bool = False,
) -> dict[str, object]:
    state = runner.status(process)
    action = frd_create_action(with_render=with_render)
    return {
        "contract_version": 8,
        "proposal_id": dispatch["dispatch_id"],
        "authority_certificate_sha256": state["authority_certificate_sha256"],
        "disposition": "ACTIVE",
        "claims": [claim(dispatch)],
        "actions": [action, fc_update_action()],
        "skips": [skip(kind) for kind in runner.SSOT_TYPES if kind not in {"FC", "FRD"}],
        "relations": [{
            "relation_id": "REL-001",
            "kind": "FC_FRD_TRACE",
            "source_path": FC_PATH,
            "target_path": FRD_PATH,
            "feature_id": "F002",
            "authority_ids": [],
            "outcome": "CREATE",
            "requirement": "FC와 FRD는 하나의 기능 추적 관계를 유지한다.",
            "verification": "MECHANICAL",
            "claim_ids": ["CLM-001"],
            "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        }],
        "risk_flags": [],
        "questions": [],
        "unsupported_changes": [],
    }


def accept_frd_thinker(process: Path, *, with_render: bool = False) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "thinker"
    proposal = active_frd_proposal(dispatch, process, with_render=with_render)
    runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")
    return dispatch


def accept_noop_thinker(process: Path) -> None:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "thinker"
    state = runner.status(process)
    proposal = {
        "contract_version": 8,
        "proposal_id": dispatch["dispatch_id"],
        "authority_certificate_sha256": state["authority_certificate_sha256"],
        "disposition": "NOOP",
        "claims": [],
        "actions": [],
        "skips": [{
            "ssot_type": kind,
            "reason": "현재 영구 SSOT에 결속된 TASK 결과가 이미 반영되어 있다.",
            "claim_ids": [],
            "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        } for kind in runner.SSOT_TYPES],
        "relations": [],
        "risk_flags": [],
        "questions": [],
        "unsupported_changes": [],
    }
    runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")


def blocked_thinker_proposal(
    dispatch: dict[str, object], process: Path,
) -> dict[str, object]:
    state = runner.status(process)
    repo = Path(str(state["repo_root"]))
    return {
        "contract_version": 8,
        "proposal_id": dispatch["dispatch_id"],
        "authority_certificate_sha256": state["authority_certificate_sha256"],
        "disposition": "BLOCKED",
        "claims": [],
        "actions": [],
        "skips": [{
            "ssot_type": kind,
            "reason": "계획을 계속하기 전에 요청된 결정을 권위 인증해야 한다.",
            "claim_ids": [],
            "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
        } for kind in runner.SSOT_TYPES],
        "relations": [],
        "risk_flags": [],
        "questions": [{
            "question_id": "AUTH-DECISION-001",
            "question": "이 SSOT 변경에는 어떤 권위 해석을 적용해야 합니까?",
            "evidence_ids": [evidence_for_path(
                dispatch, repo / TASK, contains="Collect weather observations",
            )],
        }],
        "unsupported_changes": [],
    }


def change_critique(process: Path, dispatch: dict[str, object]) -> dict[str, object]:
    state = runner.status(process)
    proposal = evidence_for_path(dispatch, Path(str(state["proposal_path"])), contains="proposal_id")
    authority = evidence_for_path(
        dispatch, Path(str(state["authority_certificate_path"])), contains="certificate_id",
    )
    compiled = evidence_for_path(
        dispatch, Path(str(state["compiled_contract_path"])), contains="compiled_contract_sha256",
    )
    receipts = evidence_for_path(
        dispatch,
        process / "compiled-preview/operation-receipts.json",
        contains="contract_version",
    )
    action_evidence = [
        evidence_for_path(
            dispatch, Path(str(state["proposal_path"])), contains=str(action_id),
        )
        for action_id in dispatch.get("required_action_ids", [])
    ]
    action_path_evidence = [
        evidence_for_path(
            dispatch,
            process / "compiled-preview/operation-receipts.json",
            contains=str(path),
        )
        for path in dispatch.get("required_action_paths", [])
    ]
    receipt_evidence = [
        evidence_for_path(
            dispatch,
            process / "compiled-preview/operation-receipts.json",
            contains=str(receipt_id),
        )
        for receipt_id in dispatch.get("required_receipt_ids", [])
    ]
    check_evidence = {
        "CHANGE-SIX-TYPE-COVERAGE": [proposal],
        "CHANGE-CLAIM-BINDING": [proposal, authority, *action_evidence],
        "CHANGE-PREVIEW-EXACTNESS": [
            compiled, receipts, *action_path_evidence, *receipt_evidence,
        ],
        "CHANGE-CROSS-DOC": [proposal, compiled],
        "CHANGE-NO-FULL-PROSE": [proposal, compiled, receipts],
    }
    return {
        "contract_version": 8,
        "critique_id": dispatch["dispatch_id"],
        "authority_certificate_sha256": state["authority_certificate_sha256"],
        "proposal_sha256": state["proposal_sha256"],
        "preview_sha256": state["preview_sha256"],
        "verdict": "APPROVE",
        "checks": [{
            "check_id": check_id,
            "verdict": "PASS",
            "finding": f"{check_id}가 컴파일 입력을 기준으로 통과했다.",
            "evidence_ids": check_evidence[check_id],
        } for check_id in CHANGE_CHECKS],
        "defects": [],
        "risk_level": "LOW",
        "question": None,
    }


def accept_change_critic(process: Path) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "change_critic"
    artifact = change_critique(process, dispatch)
    runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    return dispatch


def reach_risk_gate(process: Path, *, with_render: bool = False) -> dict[str, object]:
    accept_authority(process)
    accept_frd_thinker(process, with_render=with_render)
    accept_change_critic(process)
    blocked = runner.next_action(process)
    assert blocked["action"] == "ask_user"
    return blocked


def approve_risk(process: Path, blocked: dict[str, object]) -> None:
    request = blocked["approval_request"]
    assert isinstance(request, dict)
    runner.resolve_block(
        process,
        str(blocked["question_id"]),
        choice="APPROVE",
        actor_kind="user",
        source="interactive_user_prompt",
        event_id="evt-v8-risk-approval",
        nonce=str(request["nonce"]),
    )


def outcome_certificate(process: Path, dispatch: dict[str, object]) -> dict[str, object]:
    state = runner.status(process)
    approved = evidence_for_path(
        dispatch, process / "approved-contract.json", contains="compiled_contract_sha256",
    )
    authority = evidence_for_path(
        dispatch, Path(str(state["authority_certificate_path"])), contains="certificate_id",
    )
    staged_frd = evidence_for_path(
        dispatch, process / "staging" / FRD_PATH, contains="Sample-FRD-002",
    )
    staged_fc = evidence_for_path(dispatch, process / "staging" / FC_PATH, contains="F002")
    checks_summary = evidence_for_path(
        dispatch, process / "checks/summary.json", contains='"status": "PASS"',
    )
    render_receipt = evidence_for_path(
        dispatch, process / "render-receipt.json", contains='"result":',
    )
    check_evidence = {
        "OUTCOME-CLAIM-SATISFACTION": [approved, staged_frd, staged_fc],
        "OUTCOME-AUTHORITY-PRESERVATION": [approved, authority, staged_frd, staged_fc],
        "OUTCOME-CROSS-DOC": [approved, staged_frd, staged_fc],
        "OUTCOME-RENDER-BOUNDS": [approved, staged_frd, render_receipt],
        "OUTCOME-MECHANICAL-GATES": [checks_summary],
    }
    return {
        "contract_version": 8,
        "review_id": dispatch["dispatch_id"],
        "contract_sha256": state["approved_contract_sha256"],
        "verdict": "PASS",
        "failure_class": "NONE",
        "checks": [{
            "check_id": check_id,
            "verdict": "PASS",
            "finding": f"{check_id}가 staging 증거를 기준으로 통과했다.",
            "evidence_ids": check_evidence[check_id],
        } for check_id in OUTCOME_CHECKS],
        "defects": [],
        "question": None,
    }


def accept_outcome(process: Path) -> dict[str, object]:
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "outcome_critic"
    runner.accept_artifact(
        process,
        write_artifact(dispatch, outcome_certificate(process, dispatch)),
        "test-opus",
    )
    return dispatch


def test_authority_certificate_requires_every_mandatory_check(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact_value = authority_certificate(dispatch)
    artifact_value["checks"] = artifact_value["checks"][:-1]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact_value), "test-opus")
    assert caught.value.code == "CERTIFICATE_CHECK_COVERAGE"


def test_runner_expands_evidence_id_to_exact_bound_quote(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    catalog = read_json(Path(str(dispatch["evidence_catalog"])))
    assert "entries" not in catalog
    assert catalog["evidence_id_format"] == "DOC-<3 digits>-L<5 digit 1-based line>"
    artifact_value = authority_certificate(dispatch)
    runner.accept_artifact(process, write_artifact(dispatch, artifact_value), "test-opus")
    certificate = read_json(Path(str(runner.status(process)["authority_certificate_path"])))
    citation = certificate["checks"][0]["evidence"][0]
    assert citation == {
        "path": TASK,
        "line": 5,
        "quote": "Collect weather observations.",
    }
    assert citation["quote"] in (repo / TASK).read_text(encoding="utf-8").splitlines()[4]


def test_authority_certificate_rejects_unknown_evidence_id(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact_value = authority_certificate(dispatch)
    artifact_value["checks"][0]["evidence_ids"][0] = "DOC-999-L99999"
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact_value), "test-opus")
    assert caught.value.code == "EVIDENCE_ID_UNKNOWN"


def test_authority_certificate_rejects_self_attested_pass_without_evidence(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact_value = authority_certificate(dispatch)
    artifact_value["checks"][0]["evidence_ids"] = []
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact_value), "test-opus")
    assert caught.value.code == "EVIDENCE_ID_SCHEMA"


def test_authority_certificate_rejects_irrelevant_single_source_reused_for_every_check(
    tmp_path: Path,
) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact_value = authority_certificate(dispatch)
    irrelevant = evidence_for_path(dispatch, repo / TASK, contains="# Sample TASK")
    for check in artifact_value["checks"]:
        check["evidence_ids"] = [irrelevant]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact_value), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_SOURCE"


def test_authority_certificate_cannot_override_deterministic_detector(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path, ddd_violation=True)
    dispatch = runner.next_action(process)
    hard_checks = read_json(process / "authority-hard-checks.json")
    assert hard_checks["status"] == "FAIL"
    assert hard_checks["failures"][0]["check_id"] == "AUTH-DDD-LAYER"
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(
            process,
            write_artifact(dispatch, authority_certificate(dispatch)),
            "test-opus",
        )
    assert caught.value.code == "CERTIFICATE_CONTRADICTS_HARD_GATE"


def test_explicit_task_adr_is_always_bound_into_authority_packet(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    task = repo / TASK
    write(task, task.read_text(encoding="utf-8") + "\nAuthority basis: SAMPLE-ADR-001\n")
    process = repo / ".process/explicit-adr"
    runner.init_run(repo, TASK, APP, process)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "authority_critic"
    bound = {Path(str(path)).resolve() for path in dispatch["input_hashes"]}
    adr_path = (repo / "Docs/Sample/ADR/Sample-ADR-001.md").resolve()
    assert adr_path in bound
    assert {Path(str(path)).resolve() for path in dispatch["required_adr_paths"]} == {adr_path}

    artifact = authority_certificate(dispatch)
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_COVERAGE"

    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch)
    adr_check = next(row for row in artifact["checks"] if row["check_id"] == "AUTH-ADR-STATUS")
    adr_check["evidence_ids"].append(
        evidence_for_path(dispatch, adr_path, contains="Base infrastructure decision")
    )
    runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")


def test_authority_candidate_coverage_rejects_one_omitted_candidate(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch)
    assert artifact["candidate_judgments"]
    artifact["candidate_judgments"] = artifact["candidate_judgments"][:-1]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "AUTHORITY_CANDIDATE_COVERAGE"


def test_authority_candidate_inventory_extracts_client_port_and_service(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    inventory = read_json(Path(str(dispatch["authority_candidates"])))
    subjects = {row["subject"] for row in inventory["candidates"]}
    assert {"WeatherApiClient", "IWeatherApiClient", "WeatherPollingService"}.issubset(subjects)
    assert set(dispatch["required_candidate_ids"]) == {
        row["candidate_id"] for row in inventory["candidates"]
    }


def test_supplemental_candidate_participates_in_ddd_verdict(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch)
    artifact["verdict"] = "FAIL"
    ddd_check = next(row for row in artifact["checks"] if row["check_id"] == "AUTH-DDD-LAYER")
    ddd_check["verdict"] = "FAIL"
    artifact["supplemental_candidates"] = [{
        "subject": "새로운조립규칙",
        "kind": "COMPOSITION_REGISTRATION",
        "verdict": "FAIL",
        "finding": "추가로 발견한 조립 위치가 DDD 규칙과 충돌한다.",
        "reason": "러너의 정규식 후보 목록에 없던 의미 후보다.",
        "evidence_ids": [
            evidence_for_path(dispatch, repo / TASK, contains="Implementation scope"),
            evidence_for_path(
                dispatch,
                repo / ".claude/rules/DDD_ARCHITECTURE_RULES.md",
                contains="Infrastructure",
            ),
        ],
    }]
    runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert runner.status(process)["terminal_result"] == "REWRITE_REQUIRED"


def test_model_authored_natural_language_must_be_korean(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch)
    artifact["checks"][0]["finding"] = "This finding is written only in English."
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "KOREAN_LANGUAGE_REQUIRED"


def test_authority_rejects_direct_model_authored_quote(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch)
    artifact["checks"][0].pop("evidence_ids")
    artifact["checks"][0]["evidence"] = [{"path": TASK, "line": 5, "quote": "Collect weather observations."}]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "EVIDENCE_IDS_REQUIRED"


def test_ddd_detector_does_not_join_unrelated_application_and_infrastructure_lines(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / TASK,
        "# TASK\n\n- Src/Sample/Application/Ports/IWeatherPort.cs defines the port.\n"
        "- Src/Sample/Infrastructure/WeatherApiClient.cs implements HttpClient calls.\n",
    )
    checks = runner._authority_hard_checks(tmp_path, TASK)
    assert checks == {"contract_version": 8, "failures": [], "status": "PASS"}


def test_ddd_detector_binds_concrete_client_to_its_path_on_the_same_line(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / TASK,
        "# TASK\n\n- Src/Sample/Application/Ports/IWeatherPort.cs; "
        "Src/Sample/Infrastructure/WeatherApiClient.cs implements HttpClient calls.\n",
    )
    checks = runner._authority_hard_checks(tmp_path, TASK)
    assert checks == {"contract_version": 8, "failures": [], "status": "PASS"}


def test_ddd_application_http_client_failure_terminates_rewrite_required(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path, ddd_violation=True)
    dispatch = runner.next_action(process)
    artifact = authority_certificate(dispatch, failed_check="AUTH-DDD-LAYER")
    runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    state = runner.status(process)
    assert state["terminal_result"] == "REWRITE_REQUIRED"
    assert state["final_next"] == "task-write"
    assert runner.next_action(process)["action"] == "done"
    assert not (process / "proposals").exists()


def test_full_frd_create_exact_is_prohibited_even_with_creation_spec(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    dispatch = runner.next_action(process)
    proposal = active_frd_proposal(dispatch, process)
    proposal["actions"][0]["mutations"] = [{
        "mutation_id": "MUT-FULL-DOC",
        "operation": "CREATE_EXACT",
        "old": None,
        "anchor": None,
        "value": "# A complete model-authored FRD\n\n## 17. Acceptance\n\nInvented prose\n",
        "expected_count": 0,
        "claim_ids": ["CLM-001"],
        "authority_check_ids": ["AUTH-DOC-GOVERNANCE"],
    }]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")
    assert caught.value.code == "FRD_FULLTEXT_PROHIBITED"
    assert not (process / "compiled-preview" / FRD_PATH).exists()


def test_frd_create_rejects_legacy_template_redirect(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    legacy_template = "Docs/.templates/FRD-TEMPLATE.md"
    write(repo / legacy_template, "# redirect\n\n## 1. 기능 요약\n")
    accept_authority(process)
    dispatch = runner.next_action(process)
    assert dispatch["document_template"] == str((repo / FRD_TEMPLATE).resolve())
    assert str((repo / FRD_TEMPLATE).resolve()) in dispatch["input_hashes"]
    proposal = active_frd_proposal(dispatch, process)
    proposal["actions"][0]["creation_spec"]["template_path"] = legacy_template
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")
    assert caught.value.code == "FRD_TEMPLATE_PATH"


def test_frd_template_resolution_preserves_lowercase_docs_root_on_case_sensitive_hosts(
    tmp_path: Path,
) -> None:
    lowercase = tmp_path / "docs/.templates/App/FRD/APP-FRD-001-TEMPLATE.md"
    write(lowercase, "# canonical\n")
    assert runner._template_for_type(tmp_path, "FRD") == str(lowercase.resolve())


def test_repository_canonical_frd_template_matches_v8_section_contract() -> None:
    relative = "docs/.templates/App/FRD/APP-FRD-001-TEMPLATE.md"
    assert runner.contract_v8._validate_canonical_frd_template(ROOT, relative) == relative


def test_frd_create_rejects_canonical_template_missing_twenty_headings(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    accept_authority(process)
    write(repo / FRD_TEMPLATE, "# canonical name, legacy shape\n\n## 1. 기능 요약\n")
    dispatch = runner.next_action(process)
    proposal = active_frd_proposal(dispatch, process)
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")
    assert caught.value.code == "FRD_TEMPLATE_SHAPE"


def test_optional_render_block_requires_approved_lexical_anchor(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    dispatch = runner.next_action(process)
    proposal = active_frd_proposal(dispatch, process, with_render=True)
    proposal["actions"][0]["render_blocks"][0]["required_literals"] = []
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, proposal), "test-opus")
    assert caught.value.code == "PROPOSAL_RENDER"


def test_change_critic_also_requires_complete_evidence_certificate(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    accept_frd_thinker(process)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "change_critic"
    artifact = change_critique(process, dispatch)
    artifact["checks"] = artifact["checks"][:-1]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_CHECK_COVERAGE"


def test_change_critic_cannot_substitute_proposal_evidence_for_preview_receipts(
    tmp_path: Path,
) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    accept_frd_thinker(process)
    dispatch = runner.next_action(process)
    artifact = change_critique(process, dispatch)
    proposal_evidence = artifact["checks"][0]["evidence_ids"]
    artifact["checks"][2]["evidence_ids"] = proposal_evidence
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_SOURCE"


def test_change_critic_must_cite_every_operation_receipt(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    accept_frd_thinker(process)
    dispatch = runner.next_action(process)
    artifact = change_critique(process, dispatch)
    preview_check = artifact["checks"][2]
    preview_check["evidence_ids"] = [
        evidence_id for evidence_id in preview_check["evidence_ids"]
        if "MUT-001" not in str(evidence_row(dispatch, evidence_id)["quote"])
    ]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_COVERAGE"


def test_thinker_blocked_answer_requires_fresh_authority_certificate(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    first_authority_dispatch = accept_authority(process)
    old_state = runner.status(process)
    old_certificate_path = old_state["authority_certificate_path"]
    old_certificate_sha256 = old_state["authority_certificate_sha256"]

    thinker_dispatch = runner.next_action(process)
    runner.accept_artifact(
        process,
        write_artifact(thinker_dispatch, blocked_thinker_proposal(thinker_dispatch, process)),
        "test-opus",
    )
    blocked = runner.next_action(process)
    assert blocked["action"] == "ask_user"
    runner.resolve_block(
        process,
        str(blocked["question_id"]),
        answer="현재 Accepted ADR 체인을 지배 권위로 사용한다.",
    )

    reset = runner.status(process)
    assert reset["authority_certificate_path"] is None
    assert reset["authority_certificate_sha256"] is None
    assert reset["proposal_path"] is None
    assert reset["compiled_contract_path"] is None
    fresh_dispatch = runner.next_action(process)
    assert fresh_dispatch["role"] == "authority_critic"
    assert fresh_dispatch["dispatch_id"] != first_authority_dispatch["dispatch_id"]
    assert fresh_dispatch["input_digest"] != first_authority_dispatch["input_digest"]
    decision_path = (process / "decision.json").resolve()
    fresh_inputs = {
        Path(str(path)).resolve(): digest
        for path, digest in fresh_dispatch["input_hashes"].items()
    }
    assert fresh_inputs[decision_path] == runner._sha256(decision_path)
    assert fresh_dispatch["decision_has_answers"] is True

    missing_decision = authority_certificate(fresh_dispatch)
    scope_check = next(
        row for row in missing_decision["checks"] if row["check_id"] == "AUTH-SCOPE"
    )
    scope_check["evidence_ids"] = [scope_check["evidence_ids"][0]]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(
            process, write_artifact(fresh_dispatch, missing_decision), "test-opus",
        )
    assert caught.value.code == "CERTIFICATE_EVIDENCE_SOURCE"

    fresh_dispatch = runner.next_action(process)
    assert fresh_dispatch["role"] == "authority_critic"
    unbound_decision = authority_certificate(fresh_dispatch)
    unbound_decision["authority_facts"][0]["evidence_ids"] = [
        unbound_decision["authority_facts"][0]["evidence_ids"][0]
    ]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(
            process, write_artifact(fresh_dispatch, unbound_decision), "test-opus",
        )
    assert caught.value.code == "CERTIFICATE_DECISION_BINDING"

    fresh_dispatch = runner.next_action(process)
    assert fresh_dispatch["role"] == "authority_critic"
    runner.accept_artifact(
        process,
        write_artifact(fresh_dispatch, authority_certificate(fresh_dispatch)),
        "test-opus",
    )
    recertified = runner.status(process)
    assert recertified["authority_certificate_path"] != old_certificate_path
    assert recertified["authority_certificate_sha256"] != old_certificate_sha256
    assert runner.next_action(process)["role"] == "thinker"


def test_change_critic_blocked_answer_invalidates_proposal_and_recertifies(
    tmp_path: Path,
) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    old_certificate_sha256 = runner.status(process)["authority_certificate_sha256"]
    accept_frd_thinker(process)
    before_block = runner.status(process)
    assert before_block["proposal_path"] is not None
    assert before_block["compiled_contract_path"] is not None

    dispatch = runner.next_action(process)
    critique = change_critique(process, dispatch)
    critique["verdict"] = "BLOCKED"
    critique["checks"][0]["verdict"] = "BLOCKED"
    critique["question"] = {
        "question_id": "CHANGE-DECISION-001",
        "question": "논쟁 중인 문서 간 해석을 적용해야 합니까?",
        "evidence_ids": critique["checks"][0]["evidence_ids"],
    }
    runner.accept_artifact(process, write_artifact(dispatch, critique), "test-opus")
    blocked = runner.next_action(process)
    assert blocked["action"] == "ask_user"
    runner.resolve_block(
        process,
        str(blocked["question_id"]),
        answer="Accepted 권위 체인에 기록된 해석을 적용한다.",
    )

    reset = runner.status(process)
    for key in (
        "authority_certificate_path",
        "authority_certificate_sha256",
        "proposal_path",
        "proposal_sha256",
        "critique_path",
        "critique_sha256",
        "compiled_contract_path",
        "compiled_contract_sha256",
        "approved_contract_sha256",
    ):
        assert reset[key] is None
    fresh_dispatch = runner.next_action(process)
    assert fresh_dispatch["role"] == "authority_critic"
    runner.accept_artifact(
        process,
        write_artifact(fresh_dispatch, authority_certificate(fresh_dispatch)),
        "test-opus",
    )
    assert runner.status(process)["authority_certificate_sha256"] != old_certificate_sha256
    assert runner.next_action(process)["role"] == "thinker"


def test_claimspec_frd_compile_is_deterministic_and_runner_owned() -> None:
    action = frd_create_action()
    claims = [
        claim(),
        {
            **claim(),
            "claim_id": "CLM-002",
            "kind": "ACCEPTANCE",
            "statement": "수집된 관측값이 승인된 출력에 표시된다.",
        },
        {
            **claim(),
            "claim_id": "CLM-003",
            "kind": "TEST",
            "statement": "수집 동작을 자동화 테스트로 검증한다.",
        },
    ]
    action["claim_ids"] = ["CLM-001", "CLM-002", "CLM-003"]
    action["creation_spec"]["sections"][0]["claim_ids"] = ["CLM-001", "CLM-002", "CLM-003"]
    first = runner._render_frd_from_claims(action, claims)
    second = runner._render_frd_from_claims(action, list(reversed(claims)))
    assert first == second
    assert "Sample-FRD-002" in first
    assert "F002" in first
    assert "시스템은 날씨 관측값을 수집한다." in first
    assert "## 17." in first and "## 18." in first
    assert "CREATE_EXACT" not in first
    assert "Sample-TASK-001" not in first


def test_optional_sonnet_renderer_receives_only_bounded_prose_packet(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process, with_render=True)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "renderer"
    assert dispatch["model"] == "sonnet"
    assert dispatch["authorized_paths"] == []
    assert dispatch["staged_path"] is None
    for forbidden_key in ("task", "source", "authority", "document_index", "approved_contract", "patch", "checks"):
        assert forbidden_key not in dispatch
    input_paths = {Path(str(path)).resolve() for path in dispatch["input_hashes"]}
    assert (repo / TASK).resolve() not in input_paths
    assert len(input_paths) <= 8
    render_spec = read_json(Path(str(dispatch["render_spec"])))
    assert set(render_spec) == {"contract_version", "render_id", "action_id", "path", "blocks", "claims"}
    assert [row["statement"] for row in render_spec["claims"]] == ["시스템은 날씨 관측값을 수집한다."]
    assert all("statement" not in block for block in render_spec["blocks"])


def test_invalid_optional_renderer_falls_back_without_expanding_sonnet_authority(
    tmp_path: Path,
) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process, with_render=True)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "renderer"

    invalid = {
        "contract_version": 8,
        "render_spec_sha256": dispatch["render_spec_sha256"],
        "blocks": [{
            "render_id": "RB-001",
            "markdown": "승인된 필수 리터럴을 일부러 누락한다.",
            "claim_ids": ["CLM-001"],
        }],
    }
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, invalid), "test-sonnet")
    assert caught.value.code == "RENDER_REQUIRED_LITERAL"

    next_dispatch = runner.next_action(process)
    assert next_dispatch["role"] == "outcome_critic"
    state = runner.status(process)
    assert state["stage_results"]["render"] == {
        "owner": "runner", "status": "done", "result": "FALLBACK",
    }
    assert read_json(process / "render-receipt.json") == {
        "contract_version": 8,
        "contract_sha256": state["approved_contract_sha256"],
        "result": "FALLBACK",
        "entries": [{
            "action_id": "ACT-001",
            "path": FRD_PATH,
            "render_ids": ["RB-001"],
            "result": "FALLBACK",
        }],
    }
    assert next_dispatch["render_receipt"] == str(process / "render-receipt.json")
    assert next_dispatch["render_receipt_sha256"] == state["render_receipt_sha256"]
    staged = (process / "staging" / FRD_PATH).read_text(encoding="utf-8")
    assert "{{RENDER:RB-001}}" not in staged
    assert "This omits the required approved literal." not in staged
    assert "시스템은 날씨 관측값을 수집한다." in staged


def test_optional_renderer_rejects_invented_numeric_or_identifier_tokens(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process, with_render=True)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    artifact = {
        "contract_version": 8,
        "render_spec_sha256": dispatch["render_spec_sha256"],
        "blocks": [{
            "render_id": "RB-001",
            "markdown": "승인된 날씨 맥락에서 WeatherApiClient를 F999에 사용한다.",
            "claim_ids": ["CLM-001"],
        }],
    }
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-sonnet")
    assert caught.value.code == "RENDER_INVENTED_TOKEN"
    assert runner.next_action(process)["role"] == "outcome_critic"
    assert read_json(process / "render-receipt.json")["result"] == "FALLBACK"


def test_risk_approval_has_a_separate_non_overwriting_ledger_stage(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    state = runner.status(process)
    assert state["current_stage"] == "risk_approval"
    assert state["stage_results"]["change_review"] == {
        "owner": "change_critic", "status": "done", "result": "PASS",
    }
    risk = state["stage_results"]["risk_approval"]
    assert risk["owner"] == "user"
    assert risk["status"] == "blocked"
    assert risk["result"] == "PENDING_APPROVAL"

    approve_risk(process, blocked)
    state = runner.status(process)
    assert state["stage_results"]["change_review"]["result"] == "PASS"
    assert state["stage_results"]["risk_approval"] == {
        "owner": "user", "status": "done", "result": "APPROVED",
    }


@pytest.mark.parametrize("version", [5, 6, 7, 8])
def test_wrapper_resumes_each_existing_contract_without_migration(tmp_path: Path, version: int) -> None:
    process = tmp_path / f"process-v{version}"
    process.mkdir()
    write(process / "state.json", json.dumps({"contract_version": version}))
    implementation = wrapper._implementation(["next", "--process", str(process)])
    assert implementation.CONTRACT_VERSION == version


def test_wrapper_defaults_new_runs_to_contract_v8(tmp_path: Path) -> None:
    implementation = wrapper._implementation([
        "init", "--repo", str(tmp_path), "--task", TASK, "--app", APP,
    ])
    assert implementation.CONTRACT_VERSION == 8


def test_runner_implementation_change_requires_new_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, process = make_repo(tmp_path)
    monkeypatch.setattr(
        runner,
        "_implementation_fingerprint",
        lambda: {"contract_version": 8, "files": [], "sha256": "0" * 64},
    )
    with pytest.raises(runner.ContractError) as caught:
        runner.next_action(process)
    assert caught.value.code == "RUNNER_CHANGED_RESTART_REQUIRED"


def test_noop_still_requires_change_certificate_then_finishes_without_sonnet(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    accept_authority(process)
    accept_noop_thinker(process)
    accept_change_critic(process)
    done = runner.next_action(process)
    assert done["action"] == "done"
    assert done["terminal_result"] == "NOOP"
    state = runner.status(process)
    assert state["stage_results"]["change_review"]["result"] == "PASS"
    assert state["stage_results"]["risk_approval"]["result"] == "NOT_REQUIRED"
    assert state["final_next"] == "work-packet-write"


def test_outcome_critic_cannot_pass_with_an_incomplete_certificate(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "outcome_critic"
    artifact = outcome_certificate(process, dispatch)
    artifact["checks"] = artifact["checks"][:-1]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_CHECK_COVERAGE"


def test_outcome_critic_cannot_substitute_staged_text_for_mechanical_gate_evidence(
    tmp_path: Path,
) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    artifact = outcome_certificate(process, dispatch)
    artifact["checks"][-1]["evidence_ids"] = artifact["checks"][0]["evidence_ids"][1:]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_SOURCE"


def test_outcome_render_bounds_must_cite_runner_render_receipt(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    artifact = outcome_certificate(process, dispatch)
    render_check = next(
        check for check in artifact["checks"] if check["check_id"] == "OUTCOME-RENDER-BOUNDS"
    )
    render_check["evidence_ids"] = render_check["evidence_ids"][:-1]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_SOURCE"


def test_outcome_cross_doc_must_cite_every_staged_changed_path(tmp_path: Path) -> None:
    _, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    artifact = outcome_certificate(process, dispatch)
    cross_doc = artifact["checks"][2]
    omitted = (process / "staging" / FC_PATH).resolve()
    cross_doc["evidence_ids"] = [
        evidence_id for evidence_id in cross_doc["evidence_ids"]
        if (
            Path(str(runner.status(Path(str(dispatch["process"])))["repo_root"]))
            / str(evidence_row(dispatch, evidence_id)["path"])
        ).resolve() != omitted
    ]
    with pytest.raises(runner.ContractError) as caught:
        runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-opus")
    assert caught.value.code == "CERTIFICATE_EVIDENCE_COVERAGE"


def test_no_render_claimspec_commits_frd_and_fc_after_complete_outcome_certificate(
    tmp_path: Path,
) -> None:
    repo, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process)
    approve_risk(process, blocked)
    accept_outcome(process)

    state = runner.status(process)
    assert state["terminal_result"] == "DONE"
    assert state["final_audit"] == "PASS"
    assert state["stage_results"]["render"] == {
        "owner": "renderer", "status": "skipped", "result": "NOT_REQUIRED",
    }
    assert read_json(process / "render-receipt.json") == {
        "contract_version": 8,
        "contract_sha256": state["approved_contract_sha256"],
        "result": "NOT_REQUIRED",
        "entries": [],
    }
    approved_contract = read_json(process / "approved-contract.json")
    assert approved_contract["actions"][0]["creation_spec"]["template_path"] == FRD_TEMPLATE
    assert state["stage_results"]["outcome_review"] == {
        "owner": "outcome_critic", "status": "done", "result": "PASS",
    }
    assert (repo / FRD_PATH).is_file()
    frd = (repo / FRD_PATH).read_text(encoding="utf-8")
    assert "Sample-FRD-002" in frd
    assert "시스템은 날씨 관측값을 수집한다." in frd
    fc = (repo / FC_PATH).read_text(encoding="utf-8")
    assert "| F002 | Weather observation collection | Sample-FRD-002 §17 §18 |" in fc

    expected = (
        "갱신/생성: Docs/Sample/FRD/Sample-FRD-002.md, Docs/Sample/Sample-FC.md\n"
        "프로세스: .process/Sample-TASK-001/\n"
        "감사: PASS\n"
        "다음: work-packet-write"
    )
    assert runner.report(process) == expected
    assert (process / "final-report.txt").read_text(encoding="utf-8") == expected + "\n"


def test_valid_optional_renderer_replaces_placeholder_and_commits(tmp_path: Path) -> None:
    repo, process = make_repo(tmp_path)
    blocked = reach_risk_gate(process, with_render=True)
    approve_risk(process, blocked)
    dispatch = runner.next_action(process)
    assert dispatch["role"] == "renderer"
    staged = process / "staging" / FRD_PATH
    assert "{{RENDER:RB-001}}" in staged.read_text(encoding="utf-8")

    artifact = {
        "contract_version": 8,
        "render_spec_sha256": dispatch["render_spec_sha256"],
        "blocks": [{
            "render_id": "RB-001",
            "markdown": "승인된 날씨 관측값 수집 맥락을 설명한다.",
            "claim_ids": ["CLM-001"],
        }],
    }
    runner.accept_artifact(process, write_artifact(dispatch, artifact), "test-sonnet")
    staged_text = staged.read_text(encoding="utf-8")
    assert "{{RENDER:RB-001}}" not in staged_text
    assert "승인된 날씨 관측값 수집 맥락을 설명한다." in staged_text

    accept_outcome(process)
    state = runner.status(process)
    assert state["terminal_result"] == "DONE"
    assert state["stage_results"]["render"] == {
        "owner": "renderer", "status": "done", "result": "PASS",
    }
    assert read_json(process / "render-receipt.json") == {
        "contract_version": 8,
        "contract_sha256": state["approved_contract_sha256"],
        "result": "PASS",
        "entries": [{
            "action_id": "ACT-001",
            "path": FRD_PATH,
            "render_ids": ["RB-001"],
            "result": "PASS",
        }],
    }
    live = (repo / FRD_PATH).read_text(encoding="utf-8")
    assert "{{RENDER:RB-001}}" not in live
    assert "승인된 날씨 관측값 수집 맥락을 설명한다." in live
