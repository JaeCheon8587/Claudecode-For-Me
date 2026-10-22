"""`/worktree-delete` — 워크트리 정리 커맨드(스킬 없음, 커맨드 단독).

고정할 계약:
1. 지우기 전에 안전 게이트(커밋 안 된 변경 · 머지 여부)를 본다 — 멈추면 묻고, 플래그를 임의로 붙이지 않는다.
2. 머지가 확인되면 마감한 Task 를 done 으로 바꾸고 진행 표시를 지운다(커밋 없음).
3. 서브모듈 메인 원본은 지우지 않는다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "worktree-delete.md"


def read() -> str:
    return COMMAND.read_text(encoding="utf-8")


def test_command_exists_without_skill_dir():
    assert COMMAND.is_file()
    assert not (ROOT / "skills" / "worktree-delete").exists()


def test_frontmatter_declares_flags():
    hint = next(line for line in read().splitlines() if line.startswith("argument-hint:"))
    for flag in ("<slug>", "--merged", "--force"):
        assert flag in hint, flag


def test_safety_gate_stops_and_asks():
    text = read()
    assert "§F 삭제를 멈춘다" in text
    assert "머지되지 않았다" in text and "커밋 안 된 변경이 있다" in text
    assert "플래그를 임의로 붙여 다시 실행하지 않는다" in text
    assert "대신 머지하지 않는다" in text
    assert "squash · rebase" in text
    assert "되돌릴 수 없게" in text and "명시" in text


def test_done_transition_after_merge():
    text = read()
    assert "in-review → done" in text
    assert "삭제 예정" in text
    assert "커밋 없음" in text
    assert "origin/<X>" in text, "원격 base 의 같은 이름 로컬 브랜치도 본다"


def test_branch_is_not_guessed():
    text = read()
    assert ".process/worktree/<slug>.json" in text
    assert "work/<slug>" in text
    assert "추측하지 않는다" in text


def test_submodule_main_copy_is_preserved():
    text = read()
    assert "서브모듈 안전" in text
    assert "링크만 해제" in text


def test_does_not_rewrite_documents_without_asking():
    text = read()
    assert "dropped" in text
    assert "묻지 않고 고치지 않는다" in text
