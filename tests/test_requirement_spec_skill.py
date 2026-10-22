"""`requirement-spec` — Intent(기능 문서)를 새로 쓰거나 고치는 스킬 (Intent v2.0).

핵심 계약을 고정한다:
1. 결정적인 일(exclude · 기준선 · 변경 목록 · 검사 · 체크리스트 · 카탈로그)은 docs_helpers 서브커맨드가 한다 —
   스킬이 부르는 서브커맨드 · 결과 코드는 실제로 있다.
2. 서브에이전트 템플릿(expector · critic)의 치환 자리와 스킬이 치환하는 자리가 같다 — 어긋나면 `{{…}}` 가 그대로 넘어간다.
3. Intent v2 형식(메타 5행 · Part 2 3섹션)을 스킬이 그대로 쓴다. 완료 조건 · 확인 방법 · 위험 · 착수 정보는 Task 몫이다.
4. 고치기 전에 기준선을 남기고, 확정 1회 뒤 `/task-split` 을 안내만 한다. 문서는 커밋하지 않는다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "requirement-spec" / "SKILL.md"
COMMAND = ROOT / "commands" / "requirement-spec.md"
EXPECTOR = ROOT / "skills" / "requirement-spec" / "templates" / "intent-expector.md"
CRITIC = ROOT / "skills" / "requirement-spec" / "templates" / "intent-critic.md"
DH_SOURCE = ROOT / "scripts" / "docs_helpers.py"

sys.path.insert(0, str(ROOT / "scripts"))
import docs_helpers as dh  # noqa: E402


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "frontmatter 가 없다"
    block = text.split("---\n", 2)[1]
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in block.splitlines() if ":" in line)}


def section(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end)]


def test_command_and_skill_share_frontmatter():
    skill, command = frontmatter(read(SKILL)), frontmatter(read(COMMAND))
    assert skill["name"] == "requirement-spec"
    assert skill["description"] == command["description"]
    assert skill["argument-hint"] == command["argument-hint"]
    for token in ("<Intent ID 또는 경로>", "--app <App>", "--no-gate"):
        assert token in skill["argument-hint"]
    assert "--type" not in skill["argument-hint"], "유형은 Task 몫이다 — Intent 에는 유형이 없다"


def test_command_defers_to_skill_and_stops_at_confirmation():
    text = read(COMMAND)
    assert "skills/requirement-spec/SKILL.md" in text
    assert "커밋하지 않는다" in text and ".git/info/exclude" in text
    assert "`/task-split` 을 자동으로 실행하지 않는다" in text


def test_helper_subcommands_exist():
    """스킬이 부르는 `python "$DH" <sub>` 는 docs_helpers CLI 에 있어야 한다."""
    used = set(re.findall(r'python "\$DH" ([a-z][a-z-]*)', read(SKILL)))
    defined = set(re.findall(r'sub\.add_parser\("([a-z-]+)"\)', read(DH_SOURCE)))
    expected = {"ensure-exclude", "intent-base", "intent-diff", "check-intent", "intent-checklist", "intent-catalog"}
    assert expected <= used, f"스킬이 부르지 않는 단계: {sorted(expected - used)}"
    assert used <= defined, f"없는 서브커맨드: {sorted(used - defined)}"


def test_result_codes_exist():
    # `INT_NAME_*` 처럼 접두로 쓴 것은 그 접두로 시작하는 코드가 있으면 된다.
    codes = set(re.findall(r"\b((?:INT|TSK)_[A-Z]+(?:_[A-Z]+)*)", read(SKILL)))
    source = read(DH_SOURCE)
    missing = sorted(c for c in codes if f'"{c}' not in source)
    assert not missing, f"스킬이 말하는 코드가 docs_helpers 에 없다: {missing}"


def test_baseline_results_match_helper():
    """기준선 결과 3가지(SAVED · KEPT · NEW)와 --implemented 를 스킬이 다룬다 — intent-base 가 찍는 낱말과 같다."""
    text = read(SKILL)
    source = read(DH_SOURCE)
    for word in ("SAVED", "KEPT", "NEW"):
        assert f"`{word}`" in text, word
        assert f'print(f"{word} ' in source, f"intent-base 가 {word} 를 찍지 않는다"
    assert "--implemented" in text and "--drop" in text
    assert "next_ids" in text and '"next_ids"' in source


def test_subagent_placeholders_match():
    """스킬이 치환한다고 적은 자리 == 템플릿에 있는 자리. 남은 `{{…}}` 는 서브에이전트에 그대로 넘어간다."""
    text = read(SKILL)
    for template, start, end in ((EXPECTOR, "### 2a", "### 2b"), (CRITIC, "### 3d", "### 3e")):
        in_template = set(re.findall(r"\{\{([A-Z_]+)\}\}", read(template)))
        in_skill = set(re.findall(r"\{\{([A-Z_]+)\}\}", section(text, start, end)))
        assert in_template == in_skill, f"{template.name}: 템플릿 {sorted(in_template)} · 스킬 {sorted(in_skill)}"


def test_multiline_placeholder_is_on_its_own_line():
    """`{{INTENTS}}` · `{{CARRY}}` 는 여러 줄 값이다 — 표 칸 · 문장 안에 두면 치환 뒤 표 · 문장이 깨진다."""
    for template, name in ((EXPECTOR, "INTENTS"), (CRITIC, "CARRY")):
        lines = [line for line in read(template).splitlines() if f"{{{{{name}}}}}" in line]
        assert lines, f"{template.name}: {{{{{name}}}}} 가 없다"
        for line in lines:
            assert line.strip() == f"{{{{{name}}}}}", f"{template.name}: {line}"


def test_intent_v2_format_in_skill():
    text = read(SKILL)
    assert " · ".join(dh.INTENT_META_EXPECTED) in text, "v1 옮기기의 메타 5행이 템플릿 · 검사와 다르다"
    derive = section(text, "### 2b", "## Phase 3")
    assert " / ".join(dh.INTENT_PART2_SECTIONS) in derive, "Part 2 는 FR · Edge · Error 3섹션이다"
    for legacy in dh.INTENT_LEGACY_SECTIONS:
        assert f"`{legacy}`" not in derive, f"Part 2 파생에 작업 지시 섹션이 남았다: {legacy}"
    # v1 은 확정 때 메타 `승인` · `검증` 행을 썼다 — v2 Intent 에는 그 행이 없다(옮길 때 지우는 것만 남는다).
    for gone in ("`승인` = `", "메타 표의 `검증` 행", "`유형` 행에는", "AskUserQuestion` 1회로 확정", ".gitignore"):
        assert gone not in text, f"v1 잔재: {gone}"


def test_flow_order():
    text = read(SKILL)
    text = text[text.index("## Phase 0"):]
    steps = ["ensure-exclude --repo .", "intent-base --repo . --intent <Intent ID> --save",
             "intent-diff --repo . --intent <Intent ID> --json", "check-intent --repo . --file",
             "intent-checklist --repo . --file", "intent-catalog --repo . --app <App> --write", "`/task-split <Intent ID> …`"]
    # check-intent 는 v1 옮기기(기준선 앞)에도 나온다 — 앞 단계 뒤에서 처음 나오는 자리로 순서를 본다.
    pos = 0
    for step in steps:
        found = text.find(step, pos)
        assert found != -1, f"순서대로 나오지 않는다(exclude → 기준선 → 변경 목록 → 검사 → 체크리스트 → 카탈로그 → 안내): {step}"
        pos = found + len(step)


def test_edit_mode_keeps_unchanged_items_and_markers():
    text = read(SKILL)
    assert "바꾸지 않는 항목은 글자 하나도 고치지 않는다" in text
    assert "진행 표시가 붙은 항목은 고치지 않는다" in text
    assert "이번 변경 밖" in text, "변경 밖 항목의 finding 은 기각한다 — 고치면 /task-split 이 변경으로 자른다"
    assert "<W>/before/<Intent ID>.md" in text, "중단 때 되돌릴 고치기 전 사본"


def test_boundary_no_task_no_commit():
    text = read(SKILL)
    boundary = section(text, "## 산출물 경계", "## 실패 처리")
    assert "Task(`.task/`) · 진행 표시 — `/task-split` 몫" in boundary
    assert "커밋하지 않는다" in boundary
    assert "git commit" not in text and "git add -" not in text
    assert "mark-intent" not in text, "진행 표시는 /task-split 이 붙인다"
