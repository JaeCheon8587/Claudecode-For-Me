from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ddr_loop_skill_documents_work_packet_auto_docs():
    text = read("skills/ddr-loop/SKILL.md")
    for expected in (
        "--docs 생략 시 forge-scope-build.md의 Work Packet",
        "Work Packet + 연결 TASK + Required SSOT",
        "Required SSOT Execution Matrix",
        "명시 docs override",
        "python \"$DDR\" init --slug <slug> [--docs <doc...>]",
    ):
        assert expected in text


def test_ddr_loop_command_and_readme_prefer_auto_docs():
    text = read("commands/ddr-loop.md") + "\n" + read("README.md")
    for expected in (
        "[--docs <doc",
        "--docs 생략 시 forge-scope Work Packet에서 자동 구성",
        "ddr-loop Work Packet docs 자동 구성",
        "Work Packet + 연결 TASK + `Required SSOT Execution Matrix`",
        "/claudecode-for-me:ddr-loop LOADER-WP-007",
    ):
        assert expected in text


def test_ddr_loop_build_template_exposes_auto_doc_source():
    text = read("scripts/ddr_templates/ddr-loop-build.md")
    for expected in (
        "비교 문서 source: `{docsSource}`",
        "Work Packet: `{workPacketPath}`",
        "TASK 문서: `{taskDocPath}`",
        "Required SSOT: {requiredSsotDocs}",
        "Work Packet의 Required SSOT Execution Matrix를 DDR 비교에서 누락",
    ):
        assert expected in text
