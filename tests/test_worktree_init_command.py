"""`/worktree-init` — 개발 환경 구성 커맨드(스킬 없음, 커맨드 단독).

핵심 계약을 고정한다:
1. 이름 하나로 워크트리만 만든다 — **Task 를 읽지 않는다**(승인 커밋 게이트 · 상태 전이 없음).
2. 문서(문서 폴더 · .task/)는 **커밋하지 않는다** — exclude 에 올리고 복사한다.
3. **후속 스킬을 실행하지 않는다** — 보고하고 끝낸다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "worktree-init.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_command_exists_without_skill_dir():
    """worktree-delete·codenav-*·commit-analysis 와 같은 커맨드 단독 구성."""
    assert COMMAND.is_file()
    assert not (ROOT / "skills" / "worktree-init").exists()


def test_frontmatter_declares_name_argument():
    text = read("commands/worktree-init.md")
    assert text.startswith("---")
    hint = next(line for line in text.splitlines() if line.startswith("argument-hint:"))
    assert "<name>" in hint
    for flag in ("--base <ref>", "--branch <branch>", "--force"):
        assert flag in hint, f"missing flag in argument-hint: {flag}"
    for gone in ("<Task-doc-path>", "<Intent-doc-path>", "--name <slug>"):
        assert gone not in hint, f"Task 를 읽지 않는다 — 옛 인자: {gone}"


def test_covers_the_setup_steps():
    text = read("commands/worktree-init.md")
    required = (
        "branches --name <이름>",
        "init <이름> --quiet --base <선택한 ref>",
        ".process/worktree/handoff.json",
        ".process/worktree/<slug>.json",
        "AskUserQuestion",
        "임의 선택 금지",
        "work/<이름>",
    )
    missing = [s for s in required if s not in text]
    assert not missing, f"commands/worktree-init.md is missing: {missing}"


def test_does_not_read_tasks_or_commit_documents():
    """Task 게이트 · 승인 커밋 · 상태 전이는 없어졌다. 문서는 커밋하지 않는다(팀 정책)."""
    text = read("commands/worktree-init.md")
    assert "Task 를 읽지 않는다" in text
    assert "문서는 커밋하지 않는다" in text
    assert ".git/info/exclude" in text
    assert "복사" in text
    for gone in ("승인 커밋 게이트", "Task 승인", "check-task", "--doc", "in-dev", "git add --"):
        assert gone not in text, f"옛 절차가 남아 있다: {gone}"


def test_reports_exit_codes_and_stops():
    text = read("commands/worktree-init.md")
    for s in ("exit 1", "exit 2", "exit 0"):
        assert s in text
    assert "임의로 `--force` 를 붙이지 않는다" in text
    assert "커밋이 하나도 없다" in text
    assert "tracked_docs" in text and "대신 하지 않는다" in text


def test_does_not_chain_into_another_skill():
    """파이프라인 금지 — 페인을 띄우거나 다음 스킬을 대신 호출하지 않는다.

    다음 단계는 '안내 문장'으로만 등장해야 하고, 실행 지시로 등장하면 안 된다.
    """
    text = read("commands/worktree-init.md")
    banned = (
        "herdr agent start", "herdr agent prompt", "herdr pane split",
        "herdr worktree open", "herdr worktree create",
    )
    hits = [s for s in banned if s in text]
    assert not hits, f"commands/worktree-init.md must not drive another session: {hits}"

    assert "후속 단계를 실행하지 않는다" in text
    assert "보고하고 끝낸다" in text

    # 다음 단계는 개발 프롬프트 · Task 마다 finish · 머지 뒤 /worktree-delete 안내뿐이다.
    assert "/task-split" in text
    assert '`python "<WT_SETUP 절대경로>" finish TSK-<NNN>`' in text
    assert "/worktree-delete <이름>" in text

    # /dispatch-session 도 마찬가지로 예시일 뿐임이 본문에 박혀 있어야 한다.
    assert "/dispatch-session" in text
    assert "예시 문장일 뿐 여기서 실행하지 않는다" in text
