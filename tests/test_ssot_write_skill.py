from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/ssot-write/SKILL.md"
COMMAND = ROOT / "commands/ssot-write.md"
RUNNER = ROOT / "scripts/ssot_runner_v8.py"
CONTRACT = ROOT / "scripts/ssot_contract_v8.py"
WRAPPER = ROOT / "scripts/ssot_runner.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_declares_contract_v8_transactional_pipeline():
    value = text(SKILL)
    assert "Contract v8" in value
    assert "ClaimSpec" in value
    assert "Authority Critic" in value
    assert "Change Critic" in value
    assert "Outcome Critic" in value
    assert "evidence" in value
    assert "runner만" in value
    assert "rollback" in value


def test_cognitive_roles_and_models_are_separated():
    value = text(RUNNER)
    assert '"authority_critic": "opus"' in value
    assert '"thinker": "opus"' in value
    assert '"change_critic": "opus"' in value
    assert '"renderer": "sonnet"' in value
    assert '"outcome_critic": "opus"' in value
    skill = text(SKILL)
    assert "새 컨텍스트" in skill
    assert "이전 역할 대화" in skill


def test_v8_role_templates_are_present_and_renderer_is_artifact_only():
    names = (
        "v8-authority-critic-input.md", "v8-claim-thinker-input.md",
        "v8-change-critic-input.md", "v8-prose-renderer-input.md",
        "v8-outcome-critic-input.md",
    )
    for name in names:
        value = text(ROOT / "skills/ssot-write/templates" / name)
        assert "Contract v8" in value
    renderer = text(ROOT / "skills/ssot-write/templates/v8-prose-renderer-input.md")
    assert "JSON artifact" in renderer
    assert "Do not modify permanent documents, staging" in renderer
    thinker = text(ROOT / "skills/ssot-write/templates/v8-claim-thinker-input.md")
    assert "evidence_catalog" in thinker
    assert "evidence_ids" in thinker
    assert "한국어 강제 계약" in thinker
    assert "document_template" in thinker
    outcome = text(ROOT / "skills/ssot-write/templates/v8-outcome-critic-input.md")
    assert "render-receipt.json" in outcome


def test_runner_has_compiled_preview_governance_and_journaled_commit():
    value = text(RUNNER) + text(CONTRACT)
    for expected in (
        "FC_FRD_TRACE", "ADR_DISPOSITION", "approved-contract.json",
        "compiled-preview.patch", "governance.json", "REPLACE_EXACT",
        "RUNNER_CREATE_FROM_CLAIMS", "CERTIFICATE_CHECK_COVERAGE",
        "validation-root", "commit-journal.json", "commit-backup",
        "RESULT_PATH_MISMATCH", "STALE_DISPATCH", "COMMIT_FAILED_ROLLED_BACK",
        "template_sha256", "input_digest", "actual_model",
        "_advisory_file_lock", "_recover_interrupted_commit", '"PREPARING"',
    ):
        assert expected in value


def test_command_uses_runner_prompt_path_and_verbatim_report():
    value = text(COMMAND)
    assert "Contract v8" in value
    assert "prompt_path" in value
    assert "accept-artifact" in value
    assert "allow_additional_text" in value
    assert "final-report.txt" in value


def test_wrapper_routes_old_processes_without_migration():
    value = text(WRAPPER)
    assert "New runs use Contract v8" in value
    assert "version == 5" in value
    assert "version == 6" in value
    assert "version == 7" in value
    assert "version == 8" in value
    assert "ssot_runner_v5" in value
    assert "ssot_runner_v6" in value
    assert "ssot_runner_v7" in value


def test_skill_has_distinct_terminal_semantics_and_risk_gate():
    value = text(SKILL)
    for result in (
        "NOOP", "OBSOLETE", "REWRITE_REQUIRED", "USER_REJECTED",
        "MANUAL_REQUIRED", "PLAN_REJECTED", "VERIFY_FAILED", "RECOVERY_REQUIRED",
    ):
        assert result in value
    assert "compiled contract SHA" in value
    assert "사용자 승인" in value
