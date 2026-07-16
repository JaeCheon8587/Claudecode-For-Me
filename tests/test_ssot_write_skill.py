from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/ssot-write/SKILL.md"
COMMAND = ROOT / "commands/ssot-write.md"
BUILD = ROOT / "skills/ssot-write/templates/build.md"
PROGRESS = ROOT / "skills/ssot-write/templates/progress.md"
OPENAI = ROOT / "skills/ssot-write/agents/openai.yaml"
AGENTS = {
    "planner": ROOT / "agents/ssot-planner.md",
    "writer": ROOT / "agents/ssot-writer.md",
    "critic": ROOT / "agents/ssot-critic.md",
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_models_and_independent_roles_are_fixed() -> None:
    skill = text(SKILL)
    command = text(COMMAND)
    assert "model: opus" in command.split("---", 2)[1]
    expected = {"planner": "opus", "writer": "sonnet", "critic": "opus"}
    for role, model in expected.items():
        value = text(AGENTS[role])
        assert f"name: ssot-{role}" in value
        assert f"model: {model}" in value
        assert f"당신은 **오직 {role.title()}" in value
    assert "general-purpose" in skill
    assert "실제 독립 에이전트" in skill


def test_gate_controller_and_state_are_removed() -> None:
    combined = text(SKILL) + text(COMMAND) + "\n".join(text(path) for path in AGENTS.values())
    assert not (ROOT / "skills/ssot-write/scripts/ssot_gate.py").exists()
    assert not (ROOT / "skills/ssot-write/references/contracts.md").exists()
    for forbidden in ("STATE_PATH", "BASELINE_DIR", "DIFF_PATH", "before_lines", "after_lines"):
        assert forbidden not in combined
    assert "Gate Controller, state, baseline, diff replay, audit, resume" in text(COMMAND)


def test_main_uses_build_and_progress_before_every_dispatch() -> None:
    skill = text(SKILL)
    assert BUILD.is_file()
    assert PROGRESS.is_file()
    assert "모든 Agent 호출 직전에 `build.md`와 `progress.md`를 반드시 다시 읽는다" in skill
    assert "고정 실행 설계" in skill
    assert "현재 cycle" in skill
    assert "Maximum Critic cycles: 3" in text(BUILD)
    assert "## Cycle History" in text(PROGRESS)


def test_path_only_agent_communication_is_explicit() -> None:
    skill = text(SKILL)
    command = text(COMMAND)
    assert "무조건 파일 경로만" in skill
    assert "KEY=절대경로" in skill
    assert "Critic finding 요약" in skill
    assert "${CLAUDE_PLUGIN_ROOT}/skills/ssot-write/SKILL.md" in command
    assert "<REPO_ROOT>/.process/<TASK-stem>/" in skill
    for key in ("TASK_PATH", "PLAN_PATH", "CHANGES_PATH", "REVIEW_PATH"):
        assert key in skill


def test_critic_result_and_replanning_loop_are_fixed() -> None:
    skill = text(SKILL)
    critic = text(AGENTS["critic"])
    for envelope in (
        "SUCCESS REVIEW_PATH=<path>",
        "FAIL REVIEW_PATH=<path>",
        "SUCCESS REVIEW_PATH=<absolute-path>",
        "FAIL REVIEW_PATH=<absolute-path>",
    ):
        assert envelope in skill + critic
    assert "반드시 Planner부터" in skill
    assert "PLAN_PATH + REVIEW_PATH" in skill
    assert "세 번째 `FAIL`" in skill
    assert "MANUAL_REQUIRED" in skill


def test_critic_compares_task_semantics_to_actual_ssot_and_ignores_plan() -> None:
    skill = text(SKILL)
    critic = text(AGENTS["critic"])
    command = text(COMMAND)
    combined = skill + critic + command
    assert "Critic에게 `PLAN_PATH`를 전달하면 **절대로 안 된다.**" in combined
    assert "`PLAN_PATH`를 전달받거나 읽으면 **절대로 안 된다.**" in critic
    assert "TASK_PATH" in critic
    assert "CHANGES_PATH" in critic
    assert "result_paths" in critic
    assert "checks는 **무조건 정확히 네 개**" in critic
    for check_id in (
        "SEMANTIC-CONTRADICTION",
        "CORE-OMISSION",
        "PROHIBITED-SCOPE",
        "UNSUPPORTED-ADDITION",
    ):
        assert check_id in critic
    assert "코드 경로·파일명·클래스/메서드명·테스트명·빌드 명령" in critic
    assert "check가 하나라도 FAIL이면 전체 결과는 **무조건 FAIL**" in critic
    assert '"checks"' in critic
    assert '"task_evidence"' in critic
    assert '"result_evidence"' in critic
    assert "plan acceptance criteria" not in critic
    assert "TASK의 모든 명시적 요구사항과 금지사항" not in critic
    critic_dispatch = skill.split("### Critic", 1)[1].split("## Critic FAIL 재계획", 1)[0]
    assert "\nPLAN_PATH\n" not in critic_dispatch
    assert "\nTASK_PATH\n" in critic_dispatch
    assert "\nCHANGES_PATH\n" in critic_dispatch


def test_failed_review_becomes_bounded_repair_plan() -> None:
    skill = text(SKILL)
    planner = text(AGENTS["planner"])
    command = text(COMMAND)
    combined = skill + planner + command
    assert '"mode": "FULL | REPAIR"' in planner
    assert "reference_finding_ids" in planner
    assert "FAIL finding을 해결하는 파일만" in skill
    assert "전체 계획을 반복하면 **절대로 안 된다.**" in command
    assert "새 전체 계획" not in combined


def test_writer_preserves_cumulative_results_across_repairs() -> None:
    skill = text(SKILL)
    writer = text(AGENTS["writer"])
    for field in ('"cycle_paths"', '"result_paths"', '"repair_actions"'):
        assert field in writer
    assert "이전 cycle의 파일·수정 기록을 보존" in writer
    assert "cycle_paths" in skill
    assert "result_paths" in skill
    assert "누적 `changes.files`" in skill


def test_noop_still_requires_critic() -> None:
    combined = text(SKILL) + text(AGENTS["planner"]) + text(AGENTS["critic"])
    assert "Planner의 `NOOP`도 Critic 검토 없이 완료하면 **절대로 안 된다.**" in combined
    assert "NOOP이면 Writer를 호출하면 절대로 안 된다" in combined
    assert "noop_evidence" in combined


def test_output_ownership_and_six_file_limit() -> None:
    skill = text(SKILL)
    for name in ("build.md", "progress.md", "plan.json", "changes.json", "review.json", "handoff.json"):
        assert name in skill
    assert "최대 6개" in skill
    assert "Planner는 `plan.json`" in skill
    assert "Writer는 계획된 SSOT와 `changes.json`" in skill
    assert "Critic은 `review.json`" in skill
    assert "Main은 `build.md`, `progress.md`, 성공 시 `handoff.json`" in skill


def test_writer_uses_section_level_change_summary() -> None:
    writer = text(AGENTS["writer"])
    for field in ('"section"', '"anchor"', '"summary"', '"criteria"'):
        assert field in writer
    assert "line 좌표" not in writer


def test_handoff_and_downstream_contract_are_success_based() -> None:
    skill = text(SKILL)
    pipeline = text(ROOT / "skills/pipeline-runner/SKILL.md")
    work_packet = text(ROOT / "skills/work-packet-write/SKILL.md")
    assert '"status": "SUCCESS"' in skill
    assert "progress.md" in pipeline and "handoff.json.status" in pipeline
    assert "progress.md" in work_packet and "status: SUCCESS" in work_packet
    assert "state.status=DONE" not in pipeline
    assert "<process-dir>/state.json" not in work_packet


def test_openai_metadata_matches_review_loop() -> None:
    value = text(OPENAI)
    assert 'display_name: "SSOTWrite"' in value
    assert "Planner·Writer·Critic 순환" in value
    assert "Gate Controller" not in value


def test_emphasis_remains_consistent() -> None:
    combined = "\n".join([text(SKILL), *(text(path) for path in AGENTS.values())])
    assert combined.count("**절대로") >= 25
    assert combined.count("**반드시") >= 10
    assert combined.count("**무조건") >= 5
