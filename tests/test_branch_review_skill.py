"""branch-review SKILL — spec · standards 수집 glob 이 문서 폴더 docs · Docs 를 둘 다 본다.

Glob 도구는 Windows 에서도 경로를 대소문자 구분으로 맞춘다 — `docs/**/*.md` 는 `Docs/a.md` 를
찾지 못한다(실측). 그러면 Docs 레포에서 spec 문서가 빠져 spec finder 의 신뢰도 등급이 떨어진다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_spec_and_standards_globs_cover_capital_docs():
    text = read("skills/branch-review/SKILL.md")
    spec = section(text, "#### 3-1.", "#### 3-2.")
    standards = section(text, "#### 3-2.", "**언어/스택 자동 감지**")
    assert "`Docs/**/*.md`" in spec
    assert "대소문자를 구분" in spec
    assert "`Docs/architecture/**/*.md`" in standards
