from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "ssot-write"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_frontmatter_name():
    text = read("skills/ssot-write/SKILL.md")
    assert text.startswith("---\n")
    assert "name: ssot-write" in text.split("---", 2)[1]
    assert "description:" in text.split("---", 2)[1]
    assert "[TODO" not in text


def test_command_invokes_skill_file():
    text = read("commands/ssot-write.md")
    assert "skills/ssot-write/SKILL.md" in text
    assert "<TASK-path>" in text
    assert "--resume" in text
    assert ".process/<slug>/ssot-write-progress.md" in text


def test_build_and_progress_templates_define_required_stages():
    combined = (
        read("skills/ssot-write/templates/ssot-write-build.md")
        + "\n"
        + read("skills/ssot-write/templates/ssot-write-progress.md")
    )
    for expected in (
        ".process",
        "pending / doing / done / blocked",
        "TASK 검증",
        "영향 SSOT 분석",
        "SSOT 수정 계획 확정",
        "SSOT 파일 수정",
        "수정 후 일관성 감사",
        "결과 보고",
    ):
        assert expected in combined


def test_auditor_templates_are_read_only_and_guard_task_citations():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((SKILL_DIR / "templates").glob("*auditor-*.md"))
    )
    for expected in (
        "read-only",
        "no edit",
        "no write",
        "no TASK citation",
        "TASK markdown link",
        "PASS | FAIL | AUDIT_BLOCKED",
    ):
        assert expected in combined


def test_impact_output_requires_all_ssot_types_and_matrix_fields():
    text = read("skills/ssot-write/templates/impact-auditor-output.md")
    for expected in (
        "Required SSOT Coverage Matrix",
        "PRD",
        "FC",
        "FRD",
        "ADR",
        "ADR-CATALOG",
        "ARCHITECTURE",
        "CREATE/UPDATE/SKIP/BLOCKED",
        "Evidence from TASK",
        "Evidence from SSOT",
        "Confidence",
        "Blocking question",
    ):
        assert expected in text


def test_consistency_input_includes_confirmed_matrix_and_impact_summary():
    text = read("skills/ssot-write/templates/consistency-auditor-input.md")
    for expected in (
        "Confirmed SSOT Action Matrix",
        "Impact audit result summary",
        "Audit against the Confirmed SSOT Action Matrix",
        "missing from Changed SSOT paths",
    ):
        assert expected in text


def test_consistency_output_has_file_level_expected_observed_fix_structure():
    text = read("skills/ssot-write/templates/consistency-auditor-output.md")
    for expected in (
        "File Audit",
        "Expected change",
        "Observed change",
        "Required fix",
        "FC and FRD identifiers",
        "ADR and ADR-CATALOG identifiers/statuses",
        "TASK ID citation",
        "content-based summaries",
    ):
        assert expected in text


def test_progress_template_separates_snapshot_from_append_only_log():
    text = read("skills/ssot-write/templates/ssot-write-progress.md")
    for expected in (
        "Latest resume snapshot",
        "Update these rows in place",
        "Append-only log",
        "Impact audit digest",
        "Confirmed plan digest",
        "Consistency audit digest",
    ):
        assert expected in text


def test_build_template_records_confirmed_ssot_action_matrix():
    text = read("skills/ssot-write/templates/ssot-write-build.md")
    for expected in (
        "Confirmed SSOT Action Matrix",
        "Phase 3 writes the final main-agent decision",
        "Source impact row",
        "ARCHITECTURE",
    ):
        assert expected in text


def test_ssot_write_hands_off_to_work_packet_write_only():
    docs = read("skills/ssot-write/SKILL.md") + "\n" + read("commands/ssot-write.md")
    assert "Next: work-packet-write" in docs
    forbidden = (
        "Work Packet 파일",
        "WORK_PACKET",
        "work-packet-write/SKILL.md",
        "CREATE work-packet",
        "CREATE Work Packet",
    )
    for phrase in forbidden:
        assert phrase not in docs
