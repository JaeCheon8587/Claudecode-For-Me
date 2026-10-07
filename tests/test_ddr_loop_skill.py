from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RETIRED = ("Work Packet", "Required SSOT", "forge-scope-build", "TASK", "feat-<slug>")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ddr_loop_skill_documents_manifest_intent_docs():
    text = read("skills/ddr-loop/SKILL.md")
    for expected in (
        "--docs 생략 시 forge-init 매니페스트의 Intent",
        "intent_worktree",
        "명시 docs override",
        "python \"$DDR\" init --slug <slug> [--docs <doc...>]",
        "--worktree <manifest.branch>",
    ):
        assert expected in text
    for retired in RETIRED:
        assert retired not in text, retired


def test_ddr_loop_command_and_readme_document_manifest_intent():
    command = read("commands/ddr-loop.md")
    readme = read("README.md")
    for expected in ("[--docs <doc", "--docs 생략 시 forge-init 매니페스트의 Intent"):
        assert expected in command
    for retired in RETIRED:
        assert retired not in command, retired
    section = readme[readme.index("### 6.11 ddr-loop"):readme.index("## 7. 외부 연동 도구")]
    for expected in ("/claudecode-for-me:ddr-loop LOADER-INT-007", "forge-init 매니페스트"):
        assert expected in section
    for retired in RETIRED:
        assert retired not in section, retired


def test_ddr_loop_build_template_exposes_intent_source():
    text = read("scripts/ddr_templates/ddr-loop-build.md")
    for expected in (
        "비교 문서 source: `{docsSource}`",
        "Intent: `{intentPath}`",
        "base ref(vs): `{base}`",
    ):
        assert expected in text
    for retired in RETIRED:
        assert retired not in text, retired
