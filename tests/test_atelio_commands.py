"""atelio 커맨드 3종 — 액션 아이템 생성 · 진행 기록 · 상태 조회.

전역 지침으로 상시 로드하던 atelio MCP 사용 규칙을 사용자가 직접 호출하는 커맨드로 옮겼다.
쓰기(생성 · 기록)는 모두 승인 후에만, 진행 기록은 템플릿 2종 + 코드 식별자 금지.
monday 게시는 팀 보드에 공개되는 작업이라 커맨드로 두지 않는다 — atelio UI 에서만 한다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "atelio-item": "mcp__atelio__create_action_item",
    "atelio-log": "mcp__atelio__add_progress_log",
    "atelio-status": None,   # 읽기 전용
}
WRITE_TOOLS = [t for t in COMMANDS.values() if t] + ["mcp__atelio__create_module", "mcp__atelio__create_project",
                                                     "mcp__atelio__request_monday_publish"]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def frontmatter(text: str) -> str:
    return text.split("---\n", 2)[1]


def body(text: str) -> str:
    return text.split("---\n", 2)[2]


def allowed_tools(name: str) -> list[str]:
    meta = frontmatter(read(f"commands/{name}.md"))
    return [t.strip() for t in re.search(r"^allowed-tools:(.*)$", meta, re.M).group(1).split(",")]


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_frontmatter_parses_as_yaml(name):
    yaml = pytest.importorskip("yaml")
    meta = yaml.safe_load(frontmatter(read(f"commands/{name}.md")))
    assert {"allowed-tools", "description", "argument-hint"} <= set(meta)
    assert "atelio" in meta["description"]


@pytest.mark.parametrize("name,write_tool", sorted(COMMANDS.items()))
def test_each_command_allows_only_its_own_write_tool(name, write_tool):
    tools = allowed_tools(name)
    assert "ToolSearch" in tools   # atelio 도구는 deferred — 로드 없이 부르면 실패한다
    for t in WRITE_TOOLS:
        assert (t in tools) == (t == write_tool), t
    for banned in ("Edit", "Write"):
        assert banned not in tools, banned


@pytest.mark.parametrize("name,write_tool", sorted((n, t) for n, t in COMMANDS.items() if t))
def test_writes_require_approval(name, write_tool):
    text = body(read(f"commands/{name}.md"))
    short = write_tool.removeprefix("mcp__atelio__")
    assert "AskUserQuestion" in text
    assert re.search(rf"(승인|확인) 없이 `{short}` (을|를) 호출하지 않는다", text), short
    assert "추측하지 않는다" in text   # id 는 조회로 확정


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_tools_loaded_via_toolsearch(name):
    assert 'ToolSearch("select:mcp__atelio__' in body(read(f"commands/{name}.md"))


def test_async_results_not_reported_as_done():
    assert "wiki_status" in body(read("commands/atelio-item.md"))
    assert "기록 요청됨" in body(read("commands/atelio-log.md"))


def test_no_monday_publish_command():
    # monday 게시는 atelio UI 에서만 — 커맨드 파일도, 커맨드 본문의 게시 도구 언급도 없어야 한다.
    assert not (ROOT / "commands" / "atelio-publish.md").exists()
    for path in (ROOT / "commands").glob("atelio-*.md"):
        assert "request_monday_publish" not in read(f"commands/{path.name}"), path.name


def test_log_has_both_templates():
    text = body(read("commands/atelio-log.md"))
    assert "### 기능 개발 템플릿" in text and "### 기능 개선 템플릿" in text
    heads = ["- 개선 전", "- 개선 필요 이유", "- 개선 후"]
    pos = [text.index(h) for h in heads]
    assert pos == sorted(pos)
    assert "YYYY-MM-DD" in text and "4칸" in text and "3단계" in text


def test_log_bans_code_identifiers_but_keeps_domain_terms():
    text = body(read("commands/atelio-log.md"))
    rules = text[text.index("## 작성 규칙"):]
    for kind in ("클래스", "함수", "변수", "파일 경로"):
        assert kind in rules, kind
    assert "도메인 용어는 쓴다" in rules and "P_KEY" in rules


def test_log_template_examples_have_no_code_identifiers():
    # 예시가 식별자를 담으면 모델이 그대로 따라 쓴다 — 템플릿 코드 블록 안에는 식별자가 없어야 한다.
    text = body(read("commands/atelio-log.md"))
    templates = text[text.index("## 템플릿"):text.index("## 작성 규칙")]
    blocks = re.findall(r"```\n(.*?)```", templates, re.S)
    assert len(blocks) == 2
    for block in blocks:
        assert not re.search(r"\w+\(\)", block), "함수 호출 형태"
        assert not re.search(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", block), "PascalCase 타입명"
        assert not re.search(r"\b[a-z]+[A-Z]\w*\b", block), "camelCase 식별자"


def test_status_is_read_only():
    text = body(read("commands/atelio-status.md"))
    assert "읽기 전용" in text and "지어내지 않는다" in text


def test_readme_does_not_mention_atelio():
    # 사용자 결정 — atelio 커맨드는 README 에 기록하지 않는다(서버 URL 노출 방지 포함).
    assert "atelio" not in read("README.md").lower()


REGISTER = "claude mcp add --transport http --scope user atelio https://atelio.site/mcp/mcp"


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_command_guides_registration_when_tools_missing(name):
    # 플러그인은 .mcp.json 을 싣지 않는다 — 서버 미등록이면 커맨드가 등록 명령을 안내해야 한다.
    assert REGISTER in body(read(f"commands/{name}.md"))


def test_plugin_ships_no_mcp_config():
    assert not (ROOT / ".mcp.json").exists()
