import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/slack-brief/SKILL.md"
COMMAND = ROOT / "commands/slack-brief.md"
TEMPLATE = ROOT / "skills/slack-brief/templates/message.md"
CHANNELS = ROOT / "skills/slack-brief/channels.example.json"
PLUGIN = ROOT / ".claude-plugin/plugin.json"
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"

MENTION_RE = re.compile(r"^<@[UWB][A-Z0-9]+>$")
BACKSLASH = chr(92)
USER_PATH_PREFIX = "C:" + BACKSLASH + "Users" + BACKSLASH + "cross"

TYPE_SECTIONS = {
    "[개발]": ("목표", "접근", "전환점", "결과"),
    "[기술]": ("개요", "동작 원리", "함정·한계", "적용"),
    "[결정]": ("쟁점", "선택지", "판단 근거", "결정"),
    "[장애]": ("증상", "조사", "원인", "조치"),
    "[제안]": ("현상", "아이디어", "리스크", "제안"),
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> str:
    return text(path).split("---", 2)[1]


def test_files_exist() -> None:
    for path in (SKILL, COMMAND, TEMPLATE, CHANNELS):
        assert path.exists(), path


def test_command_frontmatter_is_fixed() -> None:
    front = frontmatter(COMMAND)
    assert "model: opus" in front
    assert "effort: high" in front
    for flag in ("--channels", "--dry-run", "--max"):
        assert flag in front
    body = text(COMMAND)
    assert "${CLAUDE_PLUGIN_ROOT}/skills/slack-brief/SKILL.md" in body


def test_skill_description_carries_trigger_vocabulary() -> None:
    front = frontmatter(SKILL)
    assert "name: slack-brief" in front
    for trigger in ("슬랙", "공유", "봇", "채널", "slack brief"):
        assert trigger in front


def test_all_type_sections_and_fixed_background_are_declared() -> None:
    for source in (SKILL, TEMPLATE):
        body = text(source)
        assert "**배경**" in body
        for type_label, sections in TYPE_SECTIONS.items():
            assert type_label in body
            for section in sections:
                assert section in body, (source.name, type_label, section)


def test_background_two_sentence_contract_is_explicit() -> None:
    body = text(TEMPLATE)
    assert "정확히 2문장" in body
    assert "환경·제약·전제" in body


def test_instruction_sentences_are_forbidden() -> None:
    for source in (SKILL, TEMPLATE, COMMAND):
        body = text(source)
        assert "작업 지시문" in body, source.name
    skill = text(SKILL)
    assert "지시문 부재" in skill
    # 봇 요청 절은 완전히 제거되었다 — 각 봇이 담당 업무를 이미 알고 있다
    for source in (SKILL, TEMPLATE, COMMAND):
        assert "봇 요청" not in text(source), source.name
    assert "capabilities" not in text(SKILL)


def test_mention_and_channel_id_rules_exist() -> None:
    body = text(SKILL)
    assert "^<@[UWB][A-Z0-9]+>$" in body
    assert "channel_id" in body
    assert "thread_ts" in body
    assert "채널명 문자열" in body


def test_self_check_has_eight_items_and_limits() -> None:
    body = text(SKILL)
    assert "아래 8개가 **전부 통과해야**" in body
    assert "3000" in body
    assert "1200" in body


def test_standard_markdown_is_mandated_over_slack_mrkdwn() -> None:
    skill = text(SKILL)
    template = text(TEMPLATE)
    assert "표준 마크다운" in skill
    assert "표준 마크다운" in template
    # 단일 별표 굵게는 변환기를 거치면 별표가 노출되므로 금지되어야 한다
    assert "단일 별표" in skill
    assert "단일 별표" in template
    for source in (skill, template):
        assert "<@U…>" in source
    # 절 라벨은 전부 표준 마크다운 굵게로 표기되어야 한다
    for name in ("배경", "전환점", "판단 근거", "동작 원리"):
        assert "**" + name + "**" in skill, name
        assert not re.search(r"(?<!\*)\*" + re.escape(name) + r"\*(?!\*)", skill), name
        assert not re.search(r"(?<!\*)\*" + re.escape(name) + r"\*(?!\*)", template), name


def test_single_channel_and_single_topic_modal_exceptions_exist() -> None:
    body = text(SKILL)
    assert "후보가 1개면" in body
    assert "채널이 **1개뿐이면**" in body


def test_approval_gate_has_three_choices_and_volume_guard() -> None:
    body = text(SKILL)
    assert "3지를 묻는다" in body
    for choice in ("`전송`", "`타입 수정`", "`취소`"):
        assert choice in body, choice
    assert "12건" in body
    assert "--dry-run" in body


def test_single_agent_design_is_enforced() -> None:
    combined = text(SKILL) + text(COMMAND)
    assert "서브에이전트" in combined
    assert "단일 에이전트" in combined
    assert "Agent(" not in combined
    assert "subagent_type" not in combined


def test_one_topic_per_message_and_split_rules() -> None:
    body = text(SKILL)
    assert "토픽 1개 = 메시지 1개" in body
    assert "4개 단위로 묶어 최대 4개 질문" in body


def test_artifacts_and_sent_log_paths_are_fixed() -> None:
    body = text(SKILL)
    assert ".process/slack-brief/" in body
    assert "sent-log.jsonl" in body
    assert "receipt.json" in body
    assert "topics.json" in body


def test_channels_example_is_placeholder_only_and_schema_valid() -> None:
    data = json.loads(text(CHANNELS))
    assert data["channels"], "example must ship at least one channel"
    seen_in_channel = set()
    for channel in data["channels"]:
        for key in ("key", "name", "channel_id", "bot", "purpose", "tone"):
            assert key in channel, key
        bot = channel["bot"]
        assert MENTION_RE.match(bot["mention"]), bot["mention"]
        assert "in_channel" in bot
        seen_in_channel.add(bool(bot["in_channel"]))
        assert channel["channel_id"].startswith("C0000000"), channel["channel_id"]
        assert bot["mention"].startswith("<@U0000000"), bot["mention"]
    assert seen_in_channel == {True, False}, "example must cover in_channel true and false"


def test_no_email_or_absolute_user_path_leaks_in_shipped_files() -> None:
    for path in (SKILL, COMMAND, TEMPLATE, CHANNELS):
        body = text(path)
        assert "@mirero.co.kr" not in body
        assert USER_PATH_PREFIX not in body


def test_plugin_version_is_synced() -> None:
    plugin = json.loads(text(PLUGIN))
    marketplace = json.loads(text(MARKETPLACE))
    assert plugin["version"] == marketplace["plugins"][0]["version"]
