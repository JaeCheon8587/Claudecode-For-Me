"""`/task-split` — Intent 의 바뀐 항목을 Task n 개로 자르는 스킬.

핵심 계약을 고정한다:
1. 결정적인 일(변경 목록 · 진행 표시 · 검사 · 카탈로그 · 기준선)은 docs_helpers 서브커맨드가 한다 — 스킬이 부르는 서브커맨드 · 코드는 실제로 있다.
2. 자르기 기준(세로 조각 · 패턴 · 안티패턴 · App 을 넘는 계약 변경)과 크기 상한이 스크립트 상수와 같다.
3. 일괄 승인 1회 뒤 개발 프롬프트를 내고 멈춘다 — 워크트리 · 커밋 · 후속 커맨드를 실행하지 않는다. 문서는 커밋하지 않는다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "task-split" / "SKILL.md"
COMMAND = ROOT / "commands" / "task-split.md"
DH_SOURCE = ROOT / "scripts" / "docs_helpers.py"

sys.path.insert(0, str(ROOT / "scripts"))
import docs_helpers as dh  # noqa: E402


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "frontmatter 가 없다"
    block = text.split("---\n", 2)[1]
    return {k.strip(): v.strip() for k, v in (line.split(":", 1) for line in block.splitlines() if ":" in line)}


def test_command_and_skill_share_frontmatter():
    skill, command = frontmatter(read(SKILL)), frontmatter(read(COMMAND))
    assert skill["name"] == "task-split"
    assert skill["description"] == command["description"]
    assert skill["argument-hint"] == command["argument-hint"]
    for token in ("<Intent ID 또는 경로>", "--type 기능개발|버그수정|리팩토링"):
        assert token in skill["argument-hint"]


def test_command_defers_to_skill_and_stops_at_prompt():
    text = read(COMMAND)
    assert "skills/task-split/SKILL.md" in text
    assert "문서를 커밋하지 않는다" in text
    assert "자동으로 실행하지 않는다" in text


def test_helper_subcommands_exist():
    """스킬이 부르는 `python "$DH" <sub>` 는 docs_helpers CLI 에 있어야 한다 — 이름이 어긋나면 세션이 손으로 대신한다."""
    used = set(re.findall(r'python "\$DH" ([a-z][a-z-]*)', read(SKILL)))
    defined = set(re.findall(r'sub\.add_parser\("([a-z-]+)"\)', read(DH_SOURCE)))
    expected = {"ensure-exclude", "intent-diff", "mark-intent", "check-task", "split-check",
                "task-catalog", "intent-catalog", "intent-base"}
    assert expected <= used, f"스킬이 부르지 않는 단계: {sorted(expected - used)}"
    assert used <= defined, f"없는 서브커맨드: {sorted(used - defined)}"


def test_result_codes_exist():
    codes = set(re.findall(r"\b((?:SPLIT|TSK)_[A-Z_]+)\b", read(SKILL)))
    source = read(DH_SOURCE)
    missing = sorted(c for c in codes if f'"{c}"' not in source)
    assert not missing, f"스킬이 말하는 코드가 docs_helpers 에 없다: {missing}"
    for code in ("SPLIT_UNASSIGNED", "SPLIT_DUP", "SPLIT_EXTRA", "TSK_DEPENDS_ORDER"):
        assert code in codes


def test_flow_order():
    text = read(SKILL)
    text = text[text.index("## Phase 1"):]   # 머리말의 흐름 한 줄(`finish tsk-<NNN>` 포함)은 빼고 본문 순서만
    steps =["intent-diff --repo . --intent", "mark-intent --repo . --task", "check-task --repo . --file",
             "split-check --repo . --task", "task-catalog --repo . --write", "--drop", "finish tsk-<NNN>"]
    positions = [text.find(s) for s in steps]
    assert -1 not in positions, [s for s, p in zip(steps, positions) if p == -1]
    assert positions == sorted(positions), "변경 목록 → 표시 → 검사 → 승인 → 기준선 소비 → 개발 프롬프트 순서가 아니다"


def test_slicing_criteria():
    text = read(SKILL)
    patterns = ["1. 뼈대 먼저", "2. 흐름 단계", "3. 경로", "4. 규칙 변형", "5. 데이터 변형", "6. 연산",
                "7. 인터페이스(App)", "8. 비기능 미루기"]
    missing = [p for p in patterns if f"| {p} |" not in text]
    assert not missing, f"자르기 패턴 누락: {missing}"
    for anti in ("계층 자르기", "준비 전용 Task", "너무 잘게", "같은 항목을 두 Task 에", "E · X 를 그 FR 보다 앞 Task 에"):
        assert anti in text, f"안티패턴 누락: {anti}"
    assert "세로 조각" in text and "혼자 머지해도" in text
    assert "하위 호환이 되면" in text and "하위 호환이 안 되면" in text
    # 크기 상한은 split-check 의 SPLIT_SIZE 와 같은 값이다.
    assert f"Scope {dh.SPLIT_MAX_SCOPE}항목 · FR {dh.SPLIT_MAX_FR}개" in text


def test_task_types_and_statuses():
    text = read(SKILL)
    for kind in ("| 기능개발 |", "| 버그수정 |", "| 리팩토링 |"):
        assert kind in text
    assert "`상태` = `draft`" in text and "`상태` = `approved`" in text
    assert "in-dev" not in text, "in-dev 상태는 없어졌다 — approved → in-review(finish)"


def test_no_commit_and_no_follow_up_execution():
    text = read(SKILL)
    assert "문서는 커밋하지 않는다" in text and ".git/info/exclude" in text
    commands = "\n".join(re.findall(r"```bash\n(.*?)```", text, flags=re.S))
    for gone in ("git ", "$WT_SETUP\" init", "/worktree-init"):
        assert gone not in commands, f"스킬이 실행하면 안 되는 것: {gone}"
    assert "**실행하지 않는다.**" in text
    assert "진행 표시를 손으로 붙이지 않는다" in text


def test_template_paths_resolve():
    text = read(SKILL)
    assert "docs/.templates/.task/tsk-001-template.md" in text
    assert (ROOT / "docs" / ".templates" / ".task" / "tsk-001-template.md").is_file()
