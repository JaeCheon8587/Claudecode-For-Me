import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_is_intent_only_orchestrator_procedure():
    text = read("skills/forge-scope/SKILL.md")
    required = (
        "승인된 Intent",
        'worktree_setup.py" init --doc <Intent>',
        "## F0 —",
        "## F1 —",
        "## F2 —",
        "## F3 —",
        "## F4 —",
        "## F5 —",
        "오케스트레이터",
        "Work Packet·TASK 입력은 v3.58 에서 폐지",
    )
    missing = [expected for expected in required if expected not in text]
    assert not missing, f"SKILL.md is missing required strings: {missing}"


def test_skill_wave_loop_is_red_green_review_commit():
    text = read("skills/forge-scope/SKILL.md")
    required = (
        "**RED**",
        "**GREEN**",
        "`error CS` 0개",
        "reviewer-lite",
        "UNCOVERED",
        "feat(<ID>): W<k>",
        "--repo <worktree>",
    )
    missing = [expected for expected in required if expected not in text]
    assert not missing, f"SKILL.md is missing required strings: {missing}"


def test_skill_keeps_guardrails():
    text = read("skills/forge-scope/SKILL.md")
    required = (
        "*.sln",
        "requirement-spec 으로 되돌린다",
        "in-dev → in-review",
        "미충족 + 사유",
        "/forge-cancel",
    )
    missing = [expected for expected in required if expected not in text]
    assert not missing, f"SKILL.md is missing required strings: {missing}"


def test_skill_drops_inline_and_legacy_text():
    text = read("skills/forge-scope/SKILL.md")
    legacy = (
        "인라인으로 수행",
        "run_in_background",
        "forge-scope-build.md",
        "forge-scope-progress.md",
        "Work Packet을 우선",
        "Ready gate",
    )
    leftovers = [expected for expected in legacy if expected in text]
    assert not leftovers, f"SKILL.md still contains legacy strings: {leftovers}"


def test_command_takes_intent_path():
    text = read("commands/forge-scope.md")
    assert "<Intent-doc-path>" in text
    assert "skills/forge-scope/SKILL.md" in text
    assert "WORK_PACKET" not in text


def test_forge_templates_removed():
    assert not (ROOT / "scripts" / "forge_templates").exists()


def test_plugin_version_is_3_61_1():
    plugin = json.loads(read(".claude-plugin/plugin.json"))
    assert plugin["version"] == "3.61.1"

    marketplace = json.loads(read(".claude-plugin/marketplace.json"))
    matched = 0
    for entry in marketplace["plugins"]:
        if entry.get("name") == "claudecode-for-me":
            assert entry["version"] == "3.61.1"
            matched += 1
    assert matched >= 1
