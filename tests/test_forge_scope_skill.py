from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_forge_scope_skill_is_work_packet_first():
    text = read("skills/forge-scope/SKILL.md")
    for expected in (
        "<WORK_PACKET-or-TASK-doc-path>",
        "권장 경로는 `/forge-scope <WORK_PACKET>`",
        "Work Packet 입력 판별",
        "Draft = do not implement",
        "Required SSOT Execution Matrix",
        "Implementation Output Contract",
    ):
        assert expected in text


def test_forge_scope_skill_documents_ready_gate_and_legacy_task_path():
    text = read("skills/forge-scope/SKILL.md")
    for expected in (
        "상태는 정확히 `Ready`",
        "`Blocking / Open Questions`는 `none`",
        "연결 TASK 링크",
        "`Priority = Required` 행",
        "TASK legacy 입력 게이트",
        "Work Packet 기반 Required SSOT gate",
    ):
        assert expected in text


def test_forge_scope_completion_report_uses_output_contract_fields():
    text = read("skills/forge-scope/SKILL.md")
    for expected in (
        "Changed files",
        "Scope match",
        "Tests run",
        "Not run",
        "Deviations",
    ):
        assert expected in text


def test_command_and_readme_prefer_work_packet_usage():
    docs = read("commands/forge-scope.md") + "\n" + read("README.md")
    for expected in (
        "<WORK_PACKET-or-TASK-doc-path>",
        "Work Packet을 우선 입력",
        "Draft = do not implement",
        "Required SSOT Execution Matrix",
        "Implementation Output Contract",
        "TASK 직접 입력은 legacy",
        "/claudecode-for-me:forge-scope docs/App/WORK_PACKET/APP-WP-003.md",
    ):
        assert expected in docs


def test_forge_scope_build_template_separates_work_packet_task_and_ssot_inputs():
    text = read("scripts/forge_templates/forge-scope-build.md")
    for expected in (
        "Work Packet: `{workPacketPath}`",
        "TASK 문서: `{taskDocPath}`",
        "Required SSOT",
        "Work Packet §5 실행 규칙",
        "Work Packet §8 검증 입력",
        "Draft Work Packet 구현",
        "완료 보고 contract 누락",
    ):
        assert expected in text
