"""`/dispatch-session` — herdr 페인에 Claude 세션을 띄우는 범용 런처.

고정할 계약:
1. **범용** — forge 매니페스트를 읽지 않는다.
2. **만들지 않는다** — 워크트리 생성은 `/forge-init` 몫이다.
3. **위치는 사용자가 고른다** — 임의 선택 금지.
4. **보고하고 끝낸다** — 폴링·대리 응답 금지.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "dispatch-session.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_command_exists_without_skill_dir():
    """forge-cancel·forge-init 과 같은 커맨드 단독 구성."""
    assert COMMAND.is_file()
    assert not (ROOT / "skills" / "dispatch-session").exists()


def test_frontmatter_declares_the_arguments():
    text = read("commands/dispatch-session.md")
    assert text.startswith("---")
    hint_line = next(l for l in text.splitlines() if l.startswith("argument-hint:"))
    for flag in ("--agent", "--prompt", "--kind", "--name", "--direction"):
        assert flag in hint_line, f"argument-hint is missing {flag}"


def test_requires_a_herdr_session():
    """herdr 밖에서는 페인을 만들 방법이 없다 — 조용히 실패하면 안 된다."""
    text = read("commands/dispatch-session.md")
    assert "HERDR_ENV" in text
    assert "중단한다" in text
    assert "claude --agent <agent-name>" in text, "수동 폴백 명령이 없다"


def test_placement_is_always_asked():
    text = read("commands/dispatch-session.md")
    assert "AskUserQuestion" in text
    assert "임의 선택 금지" in text


def test_does_not_create_worktrees():
    """생성자가 둘이 되면 매니페스트 없는 워크트리가 생기고 /forge-cancel 이 브랜치를 못 찾는다."""
    text = read("commands/dispatch-session.md")
    assert "herdr worktree open" in text
    assert "herdr worktree create` 를 쓰지 않는다" in text
    assert "워크트리를 생성하지 않고" in text


def test_is_generic_and_does_not_read_forge_state():
    """forge 전용 지식이 들어오면 herdr 의존이 forge 체인으로 번진다."""
    text = read("commands/dispatch-session.md")
    assert "forge 를 모른다" in text
    for forge_internal in ("worktree_setup.py", "INT-CATALOG", "in-dev", "handoff 를 파싱"):
        assert forge_internal not in text, f"forge 내부를 참조한다: {forge_internal}"


def test_name_normalisation_is_delegated_to_the_script():
    """산문 규칙은 오적용된다 — slug 는 대문자·점을 보존하는데 herdr 는 안 받는다."""
    text = read("commands/dispatch-session.md")
    assert "scripts/herdr_name.py" in text
    assert "--strict" in text, "--name 으로 받은 값 검증 경로가 없다"
    assert "조용히 고치지 말고" in text


def test_waits_for_idle_before_prompting():
    """initialPrompt 가 돌고 있는 중에 프롬프트를 보내면 턴이 겹친다."""
    text = read("commands/dispatch-session.md")
    assert "herdr agent wait" in text
    assert "initialPrompt" in text


def test_handles_the_three_failure_codes():
    text = read("commands/dispatch-session.md")
    for code in ("agent_not_ready", "agent_blocked", "agent_prompt_stalled"):
        assert code in text, f"미처리 실패 코드: {code}"
    assert "재전송하지 말고" in text
    assert "대신 답하지 않는다" in text


def test_slash_prompt_submission_is_verified_not_assumed():
    """Claude Code 가 `/` 에서 자동완성 메뉴를 띄우면 Enter 가 제출이 아니라
    메뉴 선택으로 먹힌다. 버전에 따라 달라지므로 매번 확인하고 폴백한다."""
    text = read("commands/dispatch-session.md")
    assert "herdr agent read" in text
    assert "send-keys" in text
    assert "실제로 제출됐는지" in text
    # 자연어 우회는 $ARGUMENTS 계약을 깨므로 금지다.
    assert "자연어로 풀어 보내지 않는다" in text


def test_blocks_duplicate_agents_in_one_cwd():
    """오케스트레이터 둘이 한 워크트리에 붙으면 ledger 와 커밋이 경합한다."""
    text = read("commands/dispatch-session.md")
    assert "중복 기동 방지" in text
    assert "herdr agent list" in text
    assert "확인 불가" in text, "cwd 를 모를 때 조용히 넘어가면 안 된다"


def test_reports_and_stops():
    text = read("commands/dispatch-session.md")
    assert "보고하고 끝낸다" in text
    assert "폴링하지 않" in text
    assert "포커스를 옮기지 않는다" in text
    # 정리 순서 — 워크트리를 먼저 지우면 세션의 cwd 가 사라진다.
    assert "/forge-cancel" in text
    # 알림 구독이 없다는 사실을 사용자에게 넘긴다.
    assert "구독 기능이 없다" in text


def test_pane_id_comes_from_the_response():
    """사이드바 순서나 예시에서 유추하면 엉뚱한 페인에 에이전트를 띄운다."""
    text = read("commands/dispatch-session.md")
    assert "pane_id" in text
    assert "유추하지 않는다" in text
    assert "지어내지 않는다" in text


def test_forge_cancel_guards_live_sessions():
    """세션이 도는 중에 워크트리를 지우면 그 세션의 cwd 가 사라진다."""
    text = read("commands/forge-cancel.md")
    assert "herdr agent list" in text
    assert "살아있는 세션" in text
    assert "대신 종료해주지 않는다" in text
    # herdr 가 없는 환경에서도 /forge-cancel 은 그대로 동작해야 한다.
    assert "건너뛴다" in text
