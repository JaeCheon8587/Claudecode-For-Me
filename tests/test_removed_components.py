"""제거하거나 이름을 바꾼 스킬 · 커맨드가 다시 들어오지 않게 — 파일, 플러그인 소스 속 참조, README 현행 설명.

README 의 `## 3. 업데이트`(변경로그)는 이력이라 검사하지 않는다. 사용자 레벨 설정(예:
`~/.claude/slack-channels.json`)은 레포 밖이라 대상이 아니다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 이름 → 스킬 · 커맨드 밖에 함께 지운 경로. forge-init · forge-cancel 은 v3.74.0 에서
# worktree-init · worktree-delete 로 이름을 바꿨고, forge-scope 는 v3.73.0, 나머지는 v3.69.0 에서 제거.
REMOVED = {
    "slack-brief": ["tests/test_slack_brief_skill.py"],
    "acceptance-design": [],
    "doc-driven-review": ["scripts/doc_driven_review.py", "tests/test_doc_driven_review.py"],
    "ddr-loop": ["scripts/ddr_loop.py", "scripts/ddr_templates", "tests/test_ddr_loop.py",
                 "tests/test_ddr_loop_skill.py"],
    "forge-scope": ["tests/test_forge_scope_skill.py", "scripts/forge_templates"],
    "forge-init": ["tests/test_forge_init_command.py"],
    "forge-cancel": [],
}

# forge 라는 이름은 커맨드 이름 밖에도 퍼져 있었다 — 매니페스트 폴더(.process/forge) · 로그
# 접두사([forge]) · helper 변수(FORGE=). v3.74.0 에서 모두 걷어냈다. forget · forgery 는 다른 낱말이다.
FORGE_WORD = re.compile(r"forge(?![a-z])", re.IGNORECASE)


def _spellings(name: str) -> tuple[str, str]:
    # 스크립트 · 모듈은 밑줄 표기(doc_driven_review)로 불린다.
    return name, name.replace("-", "_")

SOURCES = (
    ("skills", "**/*.md"),
    ("skills", "**/*.json"),
    ("commands", "**/*.md"),
    ("agents", "*.md"),
    ("scripts", "**/*.py"),
    ("scripts", "**/*.md"),
    ("docs/.templates", "**/*.md"),
    (".claude/agents", "*.md"),
    (".claude/commands", "*.md"),
    (".claude-plugin", "*.json"),
    ("tests", "*.py"),
)
SELF = Path(__file__).resolve()


def _sources() -> list[Path]:
    out: list[Path] = []
    for base, pattern in SOURCES:
        out += [p for p in sorted((ROOT / base).glob(pattern)) if p.resolve() != SELF]
    return out


def _readme_current() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    head, rest = text.split("## 3. 업데이트", 1)
    return head + rest.split("## 4. 제거", 1)[1]


@pytest.mark.parametrize("name", sorted(REMOVED))
def test_removed_files_absent(name):
    assert not (ROOT / "skills" / name).exists(), f"skills/{name}/"
    assert not (ROOT / "commands" / f"{name}.md").exists(), f"commands/{name}.md"
    for rel in REMOVED[name]:
        assert not (ROOT / rel).exists(), rel


@pytest.mark.parametrize("name", sorted(REMOVED))
def test_no_reference_in_plugin_sources(name):
    hits = [p.relative_to(ROOT).as_posix() for p in _sources()
            if any(s in p.read_text(encoding="utf-8", errors="replace") for s in _spellings(name))]
    assert not hits, f"{name} 참조가 남아 있다: {hits}"


@pytest.mark.parametrize("name", sorted(REMOVED))
def test_readme_current_sections_do_not_list(name):
    current = _readme_current()
    assert not any(s in current for s in _spellings(name)), f"README 현행 설명에 {name} 가 남아 있다"


def test_gitignore_has_no_entries_for_removed():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for name in REMOVED:
        assert not any(s in text for s in _spellings(name)), name


def test_no_forge_vocabulary_left():
    hits = [f"{p.relative_to(ROOT).as_posix()}:{n}: {line.strip()[:80]}"
            for p in _sources()
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
            if FORGE_WORD.search(line)]
    assert not hits, "forge 어휘가 남아 있다:\n" + "\n".join(hits)
    assert not FORGE_WORD.search(_readme_current()), "README 현행 설명에 forge 어휘가 남아 있다"


def test_forge_word_pattern():
    for s in ("/forge-init", ".process/forge/", "[forge]", 'FORGE="', "Forge 도구"):
        assert FORGE_WORD.search(s), s
    for s in ("forget", "Forgery"):
        assert not FORGE_WORD.search(s), s


def test_scan_reaches_sources():
    rels = {p.relative_to(ROOT).as_posix() for p in _sources()}
    for must in ("commands/session-brief.md", "skills/requirement-spec/SKILL.md", "scripts/docs_helpers.py",
                 ".claude/commands/codenav-install.md", "tests/test_intent_only.py"):
        assert must in rels, must
