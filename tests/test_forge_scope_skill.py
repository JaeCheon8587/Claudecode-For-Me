import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_skill_is_intent_only_orchestrator_procedure():
    text = read("skills/forge-scope/SKILL.md")
    required = (
        "승인된 Intent",
        ".process/forge/handoff.json",
        "/forge-init",
        "git rev-parse --git-common-dir",
        "## F0 —",
        "## F2 —",
        "## F3 —",
        "## F4 —",
        "## F5 —",
        "오케스트레이터",
        "Work Packet·TASK 입력은 v3.58 에서 폐지",
    )
    missing = [expected for expected in required if expected not in text]
    assert not missing, f"SKILL.md is missing required strings: {missing}"


def test_skill_does_not_create_the_worktree():
    """환경 구성은 /forge-init 몫. 이 스킬이 다시 워크트리를 만들면 중첩 워크트리가 생긴다."""
    text = read("skills/forge-scope/SKILL.md")
    leftovers = [
        s
        for s in (
            'worktree_setup.py" init --doc',
            'worktree_setup.py" branches --doc',
            "### F1-a — base 브랜치 선택",
            "## F1 —",
        )
        if s in text
    ]
    assert not leftovers, f"SKILL.md still performs environment setup: {leftovers}"
    assert "워크트리를 만들지 않는다" in text


def test_skill_slice_loop_is_red_green_review_commit():
    text = read("skills/forge-scope/SKILL.md")
    required = (
        "**RED**",
        "**GREEN**",
        "`error CS` 0개",
        "reviewer-lite",
        "UNCOVERED",
        "feat(<ID>): S<k>",
        "TARGET FILES = **워크트리 절대경로**",
    )
    missing = [expected for expected in required if expected not in text]
    assert not missing, f"SKILL.md is missing required strings: {missing}"


def test_skill_avoids_wave_term_collision():
    """오케스트레이터 프로토콜의 wave(한 메시지 동시 스폰)와 뜻이 충돌한다 —
    forge 의 순차 단위는 '슬라이스'로 부른다."""
    text = read("skills/forge-scope/SKILL.md")
    assert "웨이브" not in text
    assert "슬라이스" in text


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


def test_command_takes_manifest_path():
    text = read("commands/forge-scope.md")
    assert "handoff.json" in text
    assert "skills/forge-scope/SKILL.md" in text
    assert "WORK_PACKET" not in text
    # 환경 구성 플래그는 /forge-init 으로 옮겼다.
    for moved in ("--base <ref>", "--force", "--name <slug>"):
        assert moved not in text, f"commands/forge-scope.md still advertises {moved}"


def test_forge_templates_removed():
    assert not (ROOT / "scripts" / "forge_templates").exists()


def test_plugin_version_is_3_65_0():
    plugin = json.loads(read(".claude-plugin/plugin.json"))
    assert plugin["version"] == "3.65.0"

    marketplace = json.loads(read(".claude-plugin/marketplace.json"))
    matched = 0
    for entry in marketplace["plugins"]:
        if entry.get("name") == "claudecode-for-me":
            assert entry["version"] == "3.65.0"
            matched += 1
    assert matched >= 1
