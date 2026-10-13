"""`/session-brief` — 세션이 자기 작업을 드릴다운으로 요약 보고하는 커맨드.

세션을 4~6개 오가면 돌아왔을 때 그 세션이 무엇을 하던 중이었는지 헷갈린다. 세션이 자기
맥락으로 현재 주제의 기능 · 맥락 · 마지막 수행 내용 · 남은 일을 한 화면에 보고한다.

`!` 주입은 명령이 실패하면 커맨드 전체가 실행되지 않는다(실측 — git 레포가 아닌 폴더에서
`Shell command failed for pattern ...`, 턴 0). 그래서 주입마다 `2>&1 || echo "(…)"` 로 끝나야 한다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "commands/session-brief.md"
INJECTION = re.compile(r"!`([^`]+)`")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def frontmatter(text: str) -> str:
    return text.split("---\n", 2)[1]


def body(text: str) -> str:
    return text.split("---\n", 2)[2]


def test_frontmatter_parses_as_yaml():
    # description 안의 ": " · " #" 하나로 프런트매터가 깨지면 커맨드 설명 · 허용 도구가 통째로 사라진다.
    yaml = pytest.importorskip("yaml")
    meta = yaml.safe_load(frontmatter(read(COMMAND)))
    assert set(meta) == {"allowed-tools", "description"}
    assert "뭐 하고 있었" in meta["description"] and "쓰지 않는다" in meta["description"]


def test_tools_are_read_only_git():
    meta = frontmatter(read(COMMAND))
    tools = re.search(r"^allowed-tools:(.*)$", meta, re.M).group(1)
    assert "Bash(git status:*)" in tools and "Bash(git log:*)" in tools
    for banned in ("git add", "git commit", "git push", "git reset", "git checkout", "git switch",
                   "Edit", "Write"):
        assert banned not in tools, banned


def test_description_triggers_on_session_recall_only():
    meta = frontmatter(read(COMMAND))
    desc = re.search(r"^description:(.*)$", meta, re.M).group(1)
    assert "뭐 하고 있었" in desc
    assert "세션" in desc
    assert "문서" in desc and "쓰지 않는다" in desc   # 문서 · 파일 요약 요청에는 발동하지 않는다


def test_every_injection_survives_failure():
    cmds = INJECTION.findall(body(read(COMMAND)))
    assert any(c.startswith("git status --short --branch") for c in cmds)
    assert any(c.startswith("git log --oneline") for c in cmds)
    for c in cmds:
        assert "2>&1" in c and re.search(r'\|\| echo "\(.+\)"$', c), c


def test_report_sections_in_order():
    text = body(read(COMMAND))
    heads = ["### 기능", "### 맥락", "### 마지막 수행 내용", "### 남은 일 · 대기 중"]
    pos = [text.index(h) for h in heads]
    assert pos == sorted(pos)
    assert "네 섹션 헤더는 항상 쓴다" in text   # 세션끼리 같은 자리에서 찾게 — 실측에서 맥락 섹션이 빠졌다
    assert "예외는 진행한 작업이 없는 세션 하나뿐" in text   # 작업 없는 세션의 한 줄 보고와 모순되지 않게
    for tag in ("[결정 대기]", "[미완료]", "[작업 상태]", "[이전:"):
        assert tag in text, tag


def test_scope_and_size_rules():
    text = body(read(COMMAND))
    assert "마지막 대화" in text          # 주제는 마지막 대화 기준
    assert "3단계" in text and "30줄" in text
    assert "파일 경로" in text            # 기본 제외, 남은 일에서만 허용
    assert "기능 섹션부터 줄인다" in text and "남은 일은 줄이지 않는다" in text   # 넘칠 때 줄이는 순서


def test_accuracy_rules():
    text = body(read(COMMAND))
    assert "검증 미확인" in text           # 증거 없는 완료 금지
    assert "압축 이전 — 세부 불명" in text  # 압축으로 잃은 세부를 지어내지 않는다
    assert "호출과 그 출력은 보고 전체에서 제외한다" in text   # 두 번째 호출부터 "마지막 수행: 요약 보고" 가 찍히지 않게
    assert "git 레포가 아니면" in text      # 작업 상태 항목 생략
    assert "파일을 고치지 않는다" in text   # 보고만 한다


def test_readme_lists_the_command():
    # 커맨드 수는 실제 파일 수에서 계산한다 — 다른 커맨드를 추가 · 제거할 때마다 이 테스트를 고치지 않게.
    readme = read("README.md")
    n = len(list((ROOT / "commands").glob("*.md")))
    assert f"슬래시 커맨드 {n}종" in readme
    assert f"Command {n} ·" in readme and f"### Command {n}종" in readme
    assert "| `session-brief` |" in readme
    assert re.search(r"│   [├└]── session-brief\.md", readme)


def test_changelog_records_introduction():
    # 현재 버전 단정은 test_forge_scope_skill.py 가 맡는다. 여기서는 도입 기록만.
    assert "### v3.68.0 — `/session-brief` 신설" in read("README.md")
