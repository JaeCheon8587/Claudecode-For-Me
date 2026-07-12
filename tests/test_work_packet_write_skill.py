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
    assert "Expected Required SSOT Execution Matrix" in text
    assert "Execution Gate" in text
    assert "Implementation Output Contract" in text
    assert "Work Packet matrix와 동일 컬럼" in text
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
        "Expected Required SSOT Execution Matrix",
        ".process/<TASK-stem>/ssot-write-build.md",
        "CREATE` 또는 `UPDATE` 대상인 SSOT 파일",
        "Required SSOT Execution Matrix",
        "Source matrix row",
        "Blocking / Open Questions",
        "읽을 범위",
        "CREATE/UPDATE target path",
        "Input Precedence and Downstream Constraints",
        "approved authority relation",
        "Downstream constraint <Relation ID>",
    ):
        assert expected in text


def test_skill_limits_creation_status_to_draft_or_ready():
    docs = read("skills/work-packet-write/SKILL.md") + "\n" + read("docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md")
    assert "상태는 `Draft` 또는 `Ready`만 사용" in docs
    assert "In Progress` / `Done` / `Dropped`는 후속 운영" in docs


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
        "Confirmed SSOT Action Matrix",
        "Expected Required SSOT Execution Matrix",
        "Expected",
        "Observed",
        "Required fix",
        "File/Section Audit",
        "Required SSOT Execution Matrix links exist",
        "CURRENT_SSOT_WINS",
        "downstream Work Packet instruction",
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
        "Execution Gate",
        "Required SSOT Execution Matrix",
        "Source matrix row",
        "Blocking / Open Questions",
        "Readiness Checklist",
        "Implementation Output Contract",
    ):
        assert expected in text


def test_work_packet_template_uses_matrix_columns_and_blocking_contract():
    text = read("docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md")
    for expected in (
        "SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority",
        "`CREATE` / `UPDATE` 대상은 기본 `Required`",
        "실행에 직접 필요 없는 `SKIP` 대상은 넣지 않는다",
        "`CREATE/UPDATE target path`가 비어 있거나 파일이 없으면 임의 링크를 만들지 않는다",
        "상태는 `Draft`이며",
        "| Issue | Source | Impact | Required decision |",
        "`Ready`일 때는 `none`으로 명시",
        "일반 SKIP 대상 SSOT는 Required로 들어가지 않았고",
        "CURRENT_SSOT_WINS",
        "Downstream constraint PREC-001",
        "모든 downstream Work Packet instruction",
    ):
        assert expected in text


def test_work_packet_template_defines_execution_gate_and_output_contract():
    text = read("docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md")
    for expected in (
        "Draft = do not implement",
        "Ready | forge-scope 진행 가능",
        "Draft | 구현 금지",
        "CREATE/UPDATE target path 누락 또는 파일 미존재가 있으면 상태가 `Draft`",
        "Changed files",
        "Scope match",
        "Tests run",
        "Not run",
        "Deviations",
    ):
        assert expected in text


def test_skill_requires_draft_for_missing_create_update_target():
    docs = read("skills/work-packet-write/SKILL.md") + "\n" + read("commands/work-packet-write.md")
    for expected in (
        "`CREATE/UPDATE target path`가 비어 있거나 파일이 없으면 임의 링크를 만들지 않는다",
        "Work Packet 상태를 `Draft`",
        "Blocking / Open Questions`에 기록",
        "Ready 로 쓰지 않는다",
    ):
        assert expected in docs


def test_auditor_input_expected_matrix_uses_same_columns():
    text = read("skills/work-packet-write/templates/phase5-auditor-input.md")
    for expected in (
        "Use the same columns as the Work Packet matrix",
        "| SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority |",
        "same-column table comparison",
        "CREATE/UPDATE target path` missing or nonexistent means `Draft` + `Blocking / Open Questions`",
    ):
        assert expected in text


def test_auditor_output_requires_expected_observed_fix_structure():
    text = read("skills/work-packet-write/templates/phase5-auditor-output.md")
    for expected in (
        "| Target | Expected | Observed | Result | Required fix |",
        "Use `Result: PASS` only when every File/Section Audit row and every checklist item is PASS.",
        "Work Packet section: fix summary",
        "Required SSOT Execution Matrix matches expected CREATE/UPDATE coverage",
        "Execution Gate",
        "Implementation Output Contract",
        "Gate consistency",
        "Expected Required SSOT Execution Matrix uses the same columns as the Work Packet matrix",
        "Missing `CREATE/UPDATE target path` handling is Draft + Blocking",
        "Ordinary SKIP rows are not Required",
        "Ambiguous precedence is Draft + Blocking",
    ):
        assert expected in text
