from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/work-packet-write/SKILL.md"
COMMAND = ROOT / "commands/work-packet-write.md"
BUILD = ROOT / "skills/work-packet-write/templates/build.md"
PROGRESS = ROOT / "skills/work-packet-write/templates/progress.md"
WP_TEMPLATE = ROOT / "docs/.templates/App/WORK_PACKET/APP-WP-001-TEMPLATE.md"
AGENTS = {
    "builder": ROOT / "agents/wp-builder.md",
    "critic": ROOT / "agents/wp-critic.md",
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_frontmatter_name() -> None:
    skill = text(SKILL)
    assert skill.startswith("---\n")
    front = skill.split("---", 2)[1]
    assert "name: work-packet-write" in front
    assert "description:" in front
    assert "[TODO" not in skill


def test_two_agent_roles_are_opus_and_independent() -> None:
    skill = text(SKILL)
    for role in ("builder", "critic"):
        value = text(AGENTS[role])
        assert f"name: wp-{role}" in value
        assert "model: opus" in value
        assert f"오직 {role.title()}" in value
    assert "general-purpose" in skill
    assert "실제 독립 에이전트" in skill
    # 2-agent only: no Planner/Writer role split for this skill
    assert not (ROOT / "agents/wp-planner.md").exists()
    assert not (ROOT / "agents/wp-writer.md").exists()


def test_main_context_protection_contract() -> None:
    skill = text(SKILL)
    assert BUILD.is_file()
    assert PROGRESS.is_file()
    assert "본문을 절대로 읽지 않는다" in skill
    assert "오케스트레이션을 오직 `build.md`와 `progress.md`만 보고" in skill
    assert "모든 Agent 호출 직전에 `build.md`와 `progress.md`를 반드시 다시 읽는다" in skill
    assert "라우팅은 오직" in skill and "SUCCESS/FAIL 토큰" in skill
    assert "top-level 필드만" in skill
    assert "## Cycle History" in text(PROGRESS)


def test_path_two_way_convention() -> None:
    skill = text(SKILL)
    assert "무조건 `KEY=절대경로`만" in skill
    assert "경로 2원화" in skill
    assert "REPO_ROOT 기준 상대경로" in skill
    assert "KEY=절대경로" in text(BUILD)


def test_builder_returns_path_only_and_keeps_boundary() -> None:
    builder = text(AGENTS["builder"])
    assert "SUCCESS WP_PATH=<absolute-path>" in builder
    assert "FAIL WP_PATH=<absolute-path>" in builder
    assert "manifest.json" in builder
    assert "장문 복제" in builder
    assert "REPO_ROOT 기준 상대" in builder
    # builder must not touch TASK/SSOT/code
    assert "코드 파일을 생성·수정·삭제하면 **절대로 안 된다.**" in builder


def test_critic_is_linking_only_with_exactly_five_checks() -> None:
    critic = text(AGENTS["critic"])
    assert "무조건 정확히 5개" in critic
    for check_id in (
        "ROUTER-DISCIPLINE",
        "LINK-COVERAGE",
        "LINK-VALIDITY",
        "LINK-TRACEABILITY",
        "GATE-LINKAGE",
    ):
        assert check_id in critic
    # concern is linking, NOT content truth
    assert "내용의 참/거짓" in critic
    assert "링킹이 제대로 됐는가" in critic
    # independence: does not receive manifest
    assert "`manifest.json`을 입력으로 받지 않으며" in critic
    # return envelope
    assert "SUCCESS REVIEW_PATH=<absolute-path> WP_STATE=Ready|Draft" in critic
    assert "FAIL REVIEW_PATH=<absolute-path>" in critic
    # any FAIL -> overall FAIL
    assert "하나라도 FAIL이면 전체 `result`는 무조건 FAIL" in critic


def test_critic_never_receives_manifest_path() -> None:
    skill = text(SKILL)
    assert "Critic에게 `MANIFEST_PATH`를 전달하면 **절대로 안 된다.**" in skill
    assert "`MANIFEST_PATH`는 **절대로 전달하지 않는다.**" in skill
    # the Critic dispatch block must not list MANIFEST_PATH
    critic_dispatch = skill.split("### Critic", 1)[1].split("## Critic FAIL", 1)[0]
    assert "\nMANIFEST_PATH\n" not in critic_dispatch
    assert "\nHANDOFF_PATH\n" in critic_dispatch
    assert "\nWP_PATH\n" in critic_dispatch


def test_authority_row_dedup_is_codified() -> None:
    builder = text(AGENTS["builder"])
    critic = text(AGENTS["critic"])
    template = text(WP_TEMPLATE)
    assert "중복 AUTHORITY 행을 만들면 절대로 안 된다" in builder
    assert "어딘가에 Required로" in builder
    assert "어딘가에 Required로 커버" in critic
    assert "전용 AUTHORITY 행이 없어도 위반이 아니다" in critic
    assert "중복 `AUTHORITY` 행을 만들지 않는다" in template


def test_repair_loop_from_builder_and_manual_required() -> None:
    skill = text(SKILL)
    assert "**Builder부터** REPAIR cycle" in skill
    assert "세 번째 `FAIL`은 `MANUAL_REQUIRED`" in skill
    assert "handoff.json`을 작성하면 **절대로 안 된다.**" in skill
    assert "Maximum Critic cycles: 3" in text(BUILD)


def test_states_ready_draft_blocked_manual_are_distinguished() -> None:
    skill = text(SKILL)
    for state in ("Ready", "Draft", "BLOCKED", "MANUAL_REQUIRED"):
        assert state in skill
    assert "정당한 Draft" in text(AGENTS["critic"])
    assert "handoff 불량/부재" in skill


def test_skill_only_creates_work_packet_and_hands_off_to_forge_scope() -> None:
    skill = text(SKILL)
    command = text(COMMAND)
    assert "Work Packet 파일 1개만" in skill
    assert "Next: forge-scope" in skill
    assert "docs/<App>/WORK_PACKET/<App>-WP-<NNN>.md" in skill or "<App>-WP-<NNN>.md" in skill
    assert '"next": "forge-scope"' in skill
    # command boundary + hand-off
    assert "TASK, PRD, FC, FRD, ADR, ADR-CATALOG, ARCHITECTURE, 코드 파일을 수정하지 않는다" in command


def test_command_invokes_skill_file_with_new_contract() -> None:
    command = text(COMMAND)
    assert "skills/work-packet-write/SKILL.md" in command
    assert "<TASK-path>" in command
    assert "--process" in command
    assert "Next: forge-scope" in command
    assert "Builder" in command and "Critic" in command
    assert "링킹" in command
    for check_id in ("ROUTER-DISCIPLINE", "LINK-COVERAGE", "GATE-LINKAGE"):
        assert check_id in command


def test_no_phase5_auditor_remnants() -> None:
    # legacy single-agent phase 5 auditor is fully removed
    assert not (ROOT / "skills/work-packet-write/templates/phase5-auditor-input.md").exists()
    assert not (ROOT / "skills/work-packet-write/templates/phase5-auditor-output.md").exists()
    combined = text(SKILL) + text(COMMAND)
    assert "phase5-auditor" not in combined
    # templates dir is now uniform with task/ssot: only build + progress
    template_files = sorted(p.name for p in (ROOT / "skills/work-packet-write/templates").glob("*"))
    assert template_files == ["build.md", "progress.md"]


def test_work_packet_template_still_defines_router_shape() -> None:
    template = text(WP_TEMPLATE)
    for expected in (
        "{App}-WP-{NNN}",
        "Context Router",
        "Scope Authority",
        "Truth Authority",
        "Execution Gate",
        "SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority",
        "Blocking / Open Questions",
        "Implementation Output Contract",
        "Changed files",
        "Deviations",
    ):
        assert expected in template


def test_emphasis_remains_consistent() -> None:
    combined = "\n".join([text(SKILL), *(text(path) for path in AGENTS.values())])
    assert combined.count("**절대로") >= 20
    assert combined.count("**무조건") >= 5
