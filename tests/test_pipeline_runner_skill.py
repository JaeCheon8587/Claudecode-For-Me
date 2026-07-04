from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "pipeline-runner"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_frontmatter_name():
    text = read("skills/pipeline-runner/SKILL.md")
    assert text.startswith("---\n")
    assert "name: pipeline-runner" in text.split("---", 2)[1]
    assert "description:" in text.split("---", 2)[1]
    assert "[TODO" not in text


def test_command_invokes_skill_file_and_documents_gate():
    text = read("commands/pipeline-runner.md")
    assert "skills/pipeline-runner/SKILL.md" in text
    assert "<requirement-path>" in text
    assert "--resume" in text
    assert "Approval: pending" in text
    assert "사용자 승인 전" in text


def test_skill_links_references_and_templates():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "references/routing-rules.md",
        "references/skill-catalog.md",
        "templates/pipeline-build.md",
        "templates/pipeline-progress.md",
        "scripts/pipeline_runner_init.py",
        "scripts/pipeline_runner_check.py",
    ):
        assert expected in text


def test_skill_requires_build_progress_and_resume_from_progress():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        ".process/pipeline-<slug>/pipeline-build.md",
        "pipeline-progress.md",
        "승인 게이트",
        "`--resume`",
        "`done`이 아닌 첫 단계",
        "build/progress",
    ):
        assert expected in text


def test_skill_requires_post_step_reconciliation_and_bounded_stop():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "Post-step reconciliation",
        "하위 스킬 실행이 끝나면 즉시 pipeline-runner 상태로 돌아와",
        "특정 단계까지만 실행",
        "나머지 단계는 `skipped`",
        "progress가 `doing`인 상태로 최종 응답하지 않는다",
    ):
        assert expected in text


def test_skill_defines_template_contract_gate():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "Template Contract Gate",
        "heading과 table header를 보존",
        "섹션 이름 변경",
        "필수 섹션 생략",
        "자유 서술형 대체를 금지",
        "`{{...}}` placeholder가 남아 있으면",
        "후속 스킬 실행 금지",
        "Current Step: template-contract-gate",
    ):
        assert expected in text


def test_skill_lists_required_template_sections_and_headers():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "`## Input`",
        "`## Scale Assessment`",
        "`## Routing Decision`",
        "`## Step Parameters`",
        "`## Approval`",
        "`## Risk Notes`",
        "`## Current State`",
        "`## Step Status`",
        "`## Output Registry`",
        "`## Decisions / Deviations`",
        "`## Append-only Log`",
        "`## Final Output`",
        "| Axis | Score | Evidence |",
        "| Order | Skill | Input | Required Params | Expected Output | Gate | Next Input |",
        "| Order | Skill | Status | Input | Output | Notes |",
    ):
        assert expected in text


def test_skill_strengthens_approval_and_step_output_gates():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "정확히 `approved`가 아니면 Phase 4 진입 금지",
        "`Approved By`, `Approved At`",
        "Step output gates",
        "TASK 파일 존재",
        "worktree 존재",
        "branch 존재",
        "forge-scope build/progress 존재",
        "review report 존재",
        "Recommendation 기록",
        "Step output gate 실패 시 다음 단계로 진행하지 않는다",
    ):
        assert expected in text


def test_skill_requires_pipeline_validator_commands():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "Validator Helper",
        "python <PIPELINE_CHECK> template --process .process/pipeline-<slug>",
        "python <PIPELINE_CHECK> approval --process .process/pipeline-<slug>",
        "python <PIPELINE_CHECK> progress --process .process/pipeline-<slug>",
        "python <PIPELINE_CHECK> outputs --process .process/pipeline-<slug> --repo .",
        "`1`: contract fail. 후속 스킬 실행 금지.",
        "실패하면 다음 step으로 진행하지 않는다",
    ):
        assert expected in text


def test_skill_requires_pipeline_init_helper_and_forbids_direct_write():
    text = read("skills/pipeline-runner/SKILL.md")
    for expected in (
        "Init Helper",
        "build/progress 생성은 helper가 담당",
        "직접 Write로 새로 작성하지 않는다",
        "python <PIPELINE_INIT> init",
        "--scores-json <json-or-path>",
        "--steps-json <json-or-path>",
        "placeholder만 치환",
        "heading, table header, section order를 보존",
        "helper 없이 build/progress를 자유 형식으로 새로 작성하지 않는다",
    ):
        assert expected in text


def test_routing_rules_define_scale_axes_and_size_bands():
    text = read("skills/pipeline-runner/references/routing-rules.md")
    for expected in (
        "변경 범위",
        "SSOT 영향도",
        "데이터/API/계약 영향도",
        "테스트/검증 난이도",
        "실패 리스크",
        "의존성/불확실성",
        "작업 분할 필요성",
        "0~4",
        "5~8",
        "9~13",
        "14+",
    ):
        assert expected in text


def test_routing_rules_define_selected_pipelines_and_forced_conditions():
    text = read("skills/pipeline-runner/references/routing-rules.md")
    for expected in (
        "task-write -> forge-scope -> branch-review",
        "task-write -> ssot-write -> work-packet-write -> forge-scope -> branch-review",
        "task-write -> ssot-write -> work-packet-write -> forge-scope -> ddr-loop -> branch-review",
        "`ssot-write`가 포함되면 `work-packet-write`도 반드시 포함",
        "`work-packet-write`는 `ssot-write` 없이 기본 삽입하지 않는다",
        "SSOT not enforced in forge-scope input",
    ):
        assert expected in text


def test_skill_catalog_documents_io_gates_and_status_values():
    text = read("skills/pipeline-runner/references/skill-catalog.md")
    for expected in (
        "task-write",
        "ssot-write",
        "work-packet-write",
        "forge-scope",
        "ddr-loop",
        "branch-review",
        "Work Packet `Ready`",
        "pending / doing / done / blocked / skipped",
    ):
        assert expected in text


def test_templates_define_required_sections():
    combined = (
        read("skills/pipeline-runner/templates/pipeline-build.md")
        + "\n"
        + read("skills/pipeline-runner/templates/pipeline-progress.md")
    )
    for expected in (
        "Scale Assessment",
        "Routing Decision",
        "Forced Conditions",
        "Selected Pipeline",
        "Step Parameters",
        "Approval",
        "Risk Notes",
        "Current State",
        "Step Status",
        "Output Registry",
        "Append-only Log",
        "Final Output",
    ):
        assert expected in combined


def test_templates_start_approval_pending_and_status_pending():
    text = read("skills/pipeline-runner/templates/pipeline-build.md") + "\n" + read(
        "skills/pipeline-runner/templates/pipeline-progress.md"
    )
    for expected in (
        "Status: pending",
        "Approved Pipeline",
        "Current Step: approval",
        "waiting for approval",
    ):
        assert expected in text


def test_templates_document_contract_and_allowed_statuses():
    text = read("skills/pipeline-runner/templates/pipeline-build.md") + "\n" + read(
        "skills/pipeline-runner/templates/pipeline-progress.md"
    )
    for expected in (
        "Template Contract",
        "Do not rename, omit, collapse",
        "Remove all double-brace placeholders",
        "Status allowed values: pending | approved | rejected",
        "Status allowed values: pending | in-progress | done | blocked",
        "Step Status allowed values: pending | doing | done | blocked | skipped",
        "Event format:",
        "no step remains doing",
    ):
        assert expected in text


def test_agents_metadata_exists():
    text = read("skills/pipeline-runner/agents/openai.yaml")
    for expected in (
        "display_name: \"PipelineRunner\"",
        "short_description:",
        "default_prompt:",
    ):
        assert expected in text
