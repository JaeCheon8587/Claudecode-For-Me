"""Intent 는 루트 intent/ — 폴더 · 파일명 · 문서 ID 전부 소문자 (v3.76).

v3.76 에서 Intent 를 `docs/<App>/INTENT/<App>-INT-NNN.md` 에서 `intent/<app>/<app>-int-NNN.md` 로,
Task 를 `.task/TSK-NNN.md` 에서 `.task/tsk-NNN.md` 로 옮겼다. 카탈로그는 App 마다
`intent/<app>/intent-catalog.md`, 진입점은 `intent/intent-app-catalog.md` 다. 도구는 옛 표기를 읽지 않는다.
옛 표기가 스킬 · 커맨드 · 에이전트 · 스크립트 · 템플릿 · README 현행 절에 다시 들어오면 실패한다 —
가이드 한 줄이 남으면 AI 가 그 줄대로 옛 위치에 Intent 를 만들고, 도구는 그 Intent 를 찾지 못한다.

면제는 옛 표기를 "읽지 않는다" 고 알리는 문구뿐이다 (ALLOWED). 면제되는 것은 그 문구 자체다 —
같은 줄의 다른 옛 표기는 잡는다. README 의 변경 이력(## 4. 이전)은 과거 기록이라 보지 않는다.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 옛 Intent ID · 카탈로그 · 폴더, 옛 Task ID, 옛 템플릿 이름. 항목 ID(FR-1 · A-1)와 검사 코드(TSK_CONFLICT)는 대문자 그대로다.
OLD = re.compile(
    r"-INT-(?:\d|<|\{)"                 # LOADER-INT-001 · <App>-INT-<NNN> · {App}-INT-{NNN} · APP-INT-001-TEMPLATE
    r"|INT-CATALOG|TASK-CATALOG"
    r"|INTENT/"                          # docs/<App>/INTENT/
    r"|\bTSK-(?:\d|<|\{|\*)"             # TSK-012 · TSK-<NNN> · TSK-{NNN} · .task/TSK-*.md
    r"|task-catalog-TEMPLATE",
    re.ASCII,
)

SCAN = (
    ("skills", "**/*.md"),
    ("commands", "**/*.md"),
    ("agents", "*.md"),
    ("scripts", "*.py"),
    ("docs/.templates", "**/*.md"),
    (".claude/agents", "*.md"),
    (".claude/commands", "*.md"),
)
README_LIVE_FROM = "\n## 4. "

# 파일 → 옛 표기를 써도 되는 문구들(옛 표기는 읽지 않는다는 안내).
ALLOWED: dict[str, tuple[str, ...]] = {
    "scripts/docs_helpers.py": ("옛 표기(docs/<App>/INTENT/, TSK-001.md)", "`Loader-INT-003.md` 가 있으면"),
    "scripts/worktree_setup.py": ("`TSK-001` 로 줘도 받아 준다",),
    "docs/.templates/DOCUMENT_GUIDE.md": ("대문자가 섞인 파일(`Loader-INT-001.md` · `TSK-001.md`)", "옛 위치(`docs/{App}/INTENT/`)"),
    "skills/requirement-spec/SKILL.md": ("옛 위치(`docs/<App>/INTENT/`)",),
}


def _files() -> list[Path]:
    out: list[Path] = []
    for base, pattern in SCAN:
        out += sorted((ROOT / base).glob(pattern))
    return out


def _line_hits(rel: str, lines: list[str], first_line: int = 1) -> list[str]:
    phrases = ALLOWED.get(rel, ())
    out: list[str] = []
    for n, line in enumerate(lines, first_line):
        for phrase in phrases:
            line = line.replace(phrase, "")
        if OLD.search(line):
            out.append(f"{rel}:{n}: {line.strip()[:120]}")
    return out


def _readme_live() -> tuple[list[str], int]:
    text = (ROOT / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    cut = text.index(README_LIVE_FROM)
    return text[cut:].splitlines(), text[:cut].count("\n") + 1


def test_scan_covers_guides():
    rels = {p.relative_to(ROOT).as_posix() for p in _files()}
    for must in ("skills/requirement-spec/SKILL.md", "skills/task-split/SKILL.md", "skills/branch-review/SKILL.md",
                 "commands/worktree-init.md", "commands/worktree-delete.md", "scripts/docs_helpers.py",
                 "docs/.templates/DOCUMENT_GUIDE.md", "docs/.templates/CLAUDE-TEMPLATE.md",
                 "docs/.templates/intent/app/app-int-001-template.md", "docs/.templates/.task/tsk-001-template.md"):
        assert must in rels, must


def test_no_old_intent_or_task_notation():
    hits: list[str] = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        hits += _line_hits(rel, path.read_text(encoding="utf-8").splitlines())
    lines, start = _readme_live()
    hits += _line_hits("README.md", lines, start)
    assert not hits, "옛 Intent · Task 표기:\n" + "\n".join(hits)


def test_allowlist_is_still_needed():
    for rel, phrases in ALLOWED.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in text, f"{rel}: 면제 문구가 없다 — ALLOWED 에서 지울 것: {phrase}"


def test_templates_are_lowercase_and_in_place():
    templates = ROOT / "docs" / ".templates"
    for rel in ("intent/intent-app-catalog-template.md", "intent/app/intent-catalog-template.md",
                "intent/app/app-int-001-template.md", ".task/tsk-001-template.md", ".task/task-catalog-template.md"):
        assert (templates / rel).is_file(), rel
    for folder in ("intent", ".task"):
        for p in (templates / folder).rglob("*"):
            name = p.relative_to(templates).as_posix()
            assert name == name.lower(), f"대문자가 섞인 Intent · Task 템플릿: {name}"
    assert not (templates / "App" / "INTENT").exists()


def test_claude_template_links_app_catalog_as_entry():
    """세션은 검색이 아니라 링크로 Intent 를 찾는다 — 문서가 exclude 라 ripgrep 기반 Grep · Glob 이 건너뛴다."""
    text = (ROOT / "docs" / ".templates" / "CLAUDE-TEMPLATE.md").read_text(encoding="utf-8")
    assert "[`intent/intent-app-catalog.md`](intent/intent-app-catalog.md)" in text
    guide = (ROOT / "docs" / ".templates" / "DOCUMENT_GUIDE.md").read_text(encoding="utf-8")
    assert "`/CLAUDE.md` 문서 인덱스 → `intent/intent-app-catalog.md` → `intent/{app}/intent-catalog.md`" in guide


# --- 가드 자체의 구멍 -------------------------------------------------------
def test_old_forms_are_caught_and_new_forms_pass():
    for line in ("docs/LOADER/INTENT/LOADER-INT-003.md", "`<App>-INT-<NNN>`", "{App}-INT-CATALOG",
                 "finish TSK-012", "`.task/TSK-*.md`", "TASK-CATALOG", "APP-INT-001-TEMPLATE.md",
                 "task-catalog-TEMPLATE.md"):
        assert OLD.search(line), line
    for line in ("intent/loader/loader-int-003.md", "finish tsk-012", "`.task/tsk-*.md`", "TSK_CONFLICT",
                 "loader-int-003 FR-4", "[tsk-012 진행 중]", "INT_APP_CATALOG", "PRD-TEMPLATE.md"):
        assert not OLD.search(line), line


def test_allowed_phrase_exempts_only_itself(monkeypatch):
    rel, phrase = "commands/x.md", "옛 위치(`docs/<App>/INTENT/`)"
    monkeypatch.setitem(ALLOWED, rel, (phrase,))
    assert _line_hits(rel, [f"{phrase}는 읽지 않는다"]) == []
    assert _line_hits(rel, [f"{phrase}는 읽지 않는다 — `finish TSK-001`"]), "같은 줄의 다른 옛 표기까지 면제된다"
