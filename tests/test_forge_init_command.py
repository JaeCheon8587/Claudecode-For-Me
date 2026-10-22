"""`/forge-init` — 개발 환경 구성 커맨드(스킬 없음, 커맨드 단독).

핵심 계약 두 가지를 고정한다:
1. 환경 구성(승인 커밋 게이트 · base 선택 · init · 매니페스트)을 여기서 한다.
2. **후속 스킬을 실행하지 않는다** — 보고하고 끝낸다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "forge-init.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_command_exists_without_skill_dir():
    """forge-cancel·codenav-*·commit-analysis 와 같은 커맨드 단독 구성."""
    assert COMMAND.is_file()
    assert not (ROOT / "skills" / "forge-init").exists()


def test_frontmatter_declares_task_argument():
    text = read("commands/forge-init.md")
    assert text.startswith("---")
    assert "argument-hint:" in text
    assert "<Task-doc-path>" in text
    assert "<Intent-doc-path>" not in text, "Intent 는 기능 문서라 개발 입력이 아니다"
    for flag in ("--name <slug>", "--base <ref>", "--force"):
        assert flag in text, f"missing flag in argument-hint: {flag}"


def test_covers_the_four_setup_steps():
    text = read("commands/forge-init.md")
    required = (
        "승인 커밋 게이트",
        "docs(<ID>): Task 승인",
        "git status --porcelain",
        'branches --doc <Task>',
        'init --doc <Task> --quiet --base <선택한 ref>',
        ".process/forge/handoff.json",
        ".process/forge/<slug>.json",
        "AskUserQuestion",
        "임의 선택 금지",
    )
    missing = [s for s in required if s not in text]
    assert not missing, f"commands/forge-init.md is missing: {missing}"


def test_checks_task_and_regenerates_catalogs_before_approval_commit():
    """승인 커밋 뒤에 init 게이트에서 막히지 않도록 check-task 를 먼저 돌리고, 승인 커밋에는
    다시 만든 카탈로그(task-catalog · INT 카탈로그)를 함께 넣는다."""
    text = read("commands/forge-init.md")
    for s in ("check-task --repo . --file .task/TSK-<NNN>.md",
              "task-catalog --repo . --write",
              "intent-catalog --repo . --app <App> --write",
              "'.task/TSK-<NNN>.md' '.task/task-catalog.md'"):
        assert s in text, s
    assert text.index("check-task --repo .") < text.index("## 2 — base 브랜치 선택")


def test_reports_exit_codes_and_stops():
    text = read("commands/forge-init.md")
    for s in ("exit 1", "exit 2", "exit 0"):
        assert s in text
    assert "Task 를 고치지 않는다" in text
    assert "Intent 는 기능 문서라 개발 입력이 아니다" in text   # Intent 경로를 넣었을 때의 안내


def test_does_not_chain_into_another_skill():
    """파이프라인 금지 — 페인을 띄우거나 다음 스킬을 대신 호출하지 않는다.

    다음 단계는 '안내 문장'으로만 등장해야 하고, 실행 지시로 등장하면 안 된다.
    """
    text = read("commands/forge-init.md")
    # 금지하는 것은 **실행 지시**다. 터미널에서 직접 두드리는 형태만 막는다 —
    # `/dispatch-session` 을 예시로 **언급**하는 것은 허용한다(아래에서 따로 단정).
    banned = (
        "herdr agent start", "herdr agent prompt", "herdr pane split",
        "herdr worktree open", "herdr worktree create",
    )
    hits = [s for s in banned if s in text]
    assert not hits, f"commands/forge-init.md must not drive another session: {hits}"

    assert "후속 단계를 실행하지 않는다" in text
    assert "보고하고 끝낸다" in text

    # 다음 단계는 개발 세션 시작과 마감(finish) 안내뿐이다 — 개발 절차 스킬은 없다.
    assert ".process/forge/handoff.json" in text
    assert '`python "<FORGE 절대경로>" finish`' in text

    # /dispatch-session 도 마찬가지로 예시일 뿐임이 본문에 박혀 있어야 한다.
    assert "/dispatch-session" in text
    assert "예시 문장일 뿐 여기서 실행하지 않는다" in text


def test_approval_commit_comes_after_base_selection():
    """승인 커밋은 현재 브랜치(HEAD)에 올라가는데 init 은 Task · 대상 Intent 가 **고른 base 에**
    있어야 통과시킨다. 커밋을 base 선택보다 먼저 하면, 현재 브랜치가 아닌 base 를 고른
    순간 `Task 가 base '<ref>' 에 없다`(exit 2)로 반드시 막힌다 — 드라이런에서 재현됨.
    """
    text = read("commands/forge-init.md")
    base_step = text.index("## 2 — base 브랜치 선택")
    commit_step = text.index("## 3 — 승인 커밋 게이트")
    assert base_step < commit_step, "승인 커밋이 base 선택보다 앞서면 안 된다"

    # 고른 base 가 현재 브랜치가 아닐 때의 처리가 명시돼 있어야 한다.
    assert "고른 base ≠ 현재 브랜치" in text
    assert "대신 체크아웃해주지 않는다" in text


def test_status_check_is_path_scoped():
    """인자 없는 porcelain 은 untracked 디렉터리를 `?? docs/` · `?? .task/` 한 줄로 접는다 —
    어떤 파일이 미커밋인지 안 보인다(드라이런에서 재현됨)."""
    text = read("commands/forge-init.md")
    assert "--porcelain -uall --" in text
    assert "?? docs/" in text
    assert "?? .task/" in text
