from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "work-packet-write"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_frontmatter_name():
    text = read("skills/work-packet-write/SKILL.md")
    assert text.startswith("---\n")
    assert "name: work-packet-write" in text.split("---", 2)[1]
    assert "description:" in text.split("---", 2)[1]
    assert "[TODO" not in text


def test_command_invokes_skill_file():
    text = read("commands/work-packet-write.md")
    assert "skills/work-packet-write/SKILL.md" in text
    assert "<TASK-path>" in text
    assert "--process" in text
    assert "Next: forge-scope" in text


def test_skill_only_creates_work_packet_and_hands_off_to_forge_scope():
    docs = read("skills/work-packet-write/SKILL.md") + "\n" + read("commands/work-packet-write.md")
    for expected in (
        "Work Packet 파일만 생성",
        "TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일은 수정하지 않는다",
        "Next: forge-scope",
        "docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md",
    ):
        assert expected in docs


def test_skill_uses_task_and_confirmed_matrix_context():
    text = read("skills/work-packet-write/SKILL.md")
    for expected in (
        "Confirmed SSOT Action Matrix",
        ".process/<TASK-stem>/ssot-write-build.md",
        "CREATE` 또는 `UPDATE` 대상인 SSOT 파일",
        "Required SSOT",
        "읽을 범위",
    ):
        assert expected in text


def test_auditor_templates_are_read_only_and_check_router_shape():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((SKILL_DIR / "templates").glob("phase5-auditor-*.md"))
    )
    for expected in (
        "read-only",
        "no edit",
        "no write",
        "context router",
        "Required SSOT links exist",
        "not long TASK or SSOT body copies",
        "Only the Work Packet file was created or modified",
        "PASS | FAIL | AUDIT_BLOCKED",
    ):
        assert expected in combined


def test_work_packet_template_exists_and_uses_expected_id_shape():
    text = read("docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md")
    for expected in (
        "{App}-WP-{NNN}",
        "Context Router",
        "Scope Authority",
        "Truth Authority",
        "Required SSOT",
        "Readiness Checklist",
    ):
        assert expected in text
