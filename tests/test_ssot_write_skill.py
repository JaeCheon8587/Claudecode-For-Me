from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "ssot-write"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_frontmatter_and_multi_agent_trigger():
    text = read("skills/ssot-write/SKILL.md")
    frontmatter = text.split("---", 2)[1]
    assert text.startswith("---\n")
    assert "name: ssot-write" in frontmatter
    assert "멀티 에이전트" in frontmatter
    assert "컨텍스트" in frontmatter
    assert "[TODO" not in text


def test_command_invokes_skill_and_preserves_main_context():
    text = read("commands/ssot-write.md")
    for expected in (
        "skills/ssot-write/SKILL.md",
        "<TASK-path>",
        "--resume",
        ".process/<slug>/ssot-write-progress.md",
        "메인은 오케스트레이션만 수행",
        "메인이 fallback하지 않고",
    ):
        assert expected in text


def test_role_model_mapping_is_explicit():
    text = read("skills/ssot-write/SKILL.md")
    for expected in (
        "Main orchestrator",
        "Planning thinker",
        "SSOT actor",
        "Consistency auditor",
        'model: "opus"',
        'model: "sonnet"',
        'subagent_type: "general-purpose"',
    ):
        assert expected in text
    assert "Opus planner/auditor" in text
    assert "Sonnet actor" in text


def test_main_is_orchestrator_only_and_uses_status_envelopes():
    docs = read("skills/ssot-write/SKILL.md") + read("commands/ssot-write.md")
    for expected in (
        "메인은 TASK 본문, SSOT 본문, 전체 diff",
        "메인은 서브에이전트에 파일 내용을 복사하지 않고",
        "STATUS: READY | PASS | FAIL | BLOCKED",
        "SUMMARY",
        "QUESTION",
        "CHANGED",
        "required subagent unavailable",
    ):
        assert expected in docs


def test_process_templates_define_role_owned_stages_and_handoffs():
    combined = (
        read("skills/ssot-write/templates/ssot-write-build.md")
        + "\n"
        + read("skills/ssot-write/templates/ssot-write-progress.md")
    )
    for expected in (
        "pending / doing / done / blocked",
        "TASK 검증",
        "영향 SSOT 분석",
        "SSOT 수정 계획 확정",
        "SSOT 파일 수정",
        "수정 후 일관성 감사",
        "결과 정리/보고",
        "Opus planner",
        "Sonnet actor",
        "Opus auditor",
        "ssot-write-impact.md",
        "ssot-write-action.md",
        "ssot-write-audit.md",
    ):
        assert expected in combined


def test_opus_planner_owns_decisions_but_not_permanent_ssot_writes():
    text = read("skills/ssot-write/templates/impact-planner-input.md")
    for expected in (
        'model: "opus"',
        "Think and decide",
        "Do not edit TASK or permanent SSOT files",
        "Confirmed SSOT Action Matrix",
        "CREATE / UPDATE / SKIP / BLOCKED",
        "ssot-write-impact.md",
        "Return only this envelope",
    ):
        assert expected in text


def test_impact_output_requires_actor_ready_all_ssot_matrix():
    text = read("skills/ssot-write/templates/impact-planner-output.md")
    for expected in (
        "Required SSOT Coverage Matrix",
        "PRD",
        "FC",
        "FRD",
        "ADR",
        "ADR-CATALOG",
        "ARCHITECTURE",
        "CREATE/UPDATE/SKIP/BLOCKED",
        "Actor-Ready Decision",
        "Prohibited scope expansion",
    ):
        assert expected in text


def test_sonnet_actor_is_only_permanent_ssot_writer_and_has_modes():
    skill = read("skills/ssot-write/SKILL.md")
    actor = read("skills/ssot-write/templates/ssot-actor-input.md")
    combined = skill + "\n" + actor
    for expected in (
        'model: "sonnet"',
        "Mode: `<bootstrap|apply|repair|finalize>`",
        "Mode: bootstrap",
        "Mode: apply",
        "Mode: repair",
        "Mode: finalize",
        "Execute only `CREATE` and `UPDATE` rows",
        "Never modify TASK",
        "SSOT actor만 영구 SSOT를 수정",
    ):
        assert expected in combined


def test_opus_auditor_produces_mechanical_repair_contract():
    auditor_input = read("skills/ssot-write/templates/consistency-auditor-input.md")
    auditor_output = read("skills/ssot-write/templates/consistency-auditor-output.md")
    combined = auditor_input + "\n" + auditor_output
    for expected in (
        'model: "opus"',
        "Do not modify TASK or permanent SSOT files",
        "Confirmed SSOT Action Matrix",
        "Repair Contract",
        "file-specific",
        "Sonnet actor",
        "TASK markdown link or TASK ID citation",
    ):
        assert expected in combined


def test_progress_template_separates_snapshot_from_append_only_log():
    text = read("skills/ssot-write/templates/ssot-write-progress.md")
    for expected in (
        "Latest resume snapshot",
        "updates these rows in place",
        "Append-only log",
        "Impact audit digest",
        "Changed paths",
        "Consistency audit digest",
    ):
        assert expected in text


def test_ssot_write_hands_off_to_work_packet_write_only():
    docs = read("skills/ssot-write/SKILL.md") + "\n" + read("commands/ssot-write.md")
    assert "Next: work-packet-write" in docs
    for phrase in (
        "Work Packet 파일",
        "WORK_PACKET",
        "work-packet-write/SKILL.md",
        "CREATE work-packet",
        "CREATE Work Packet",
    ):
        assert phrase not in docs
