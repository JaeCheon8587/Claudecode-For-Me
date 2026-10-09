"""`/codenav-install` — 문서 폴더 docs·Docs 동일 취급 + 레포 로컬 미러 동기.

레포마다 문서 폴더가 docs 또는 Docs 다. 소문자 docs/ 만 찾으면 대소문자 구분 FS 의
Docs 레포에 docs/ 가 따로 생기고, 대소문자 무시 FS 에서도 CLAUDE.md 링크가 실제 표기와
어긋난다(GitHub 웹 · Linux 에서는 깨진 링크). v2.0.0 에서 없앤 Docs 폴더 인식을 되살린다.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = "commands/codenav-install.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_docs_folder_step_reuses_existing_spelling():
    step = section(read(COMMAND), "#### 8.1", "#### 8.2")
    assert "`Docs/`" in step
    assert "대소문자" in step
    assert "따로 만들지 않는다" in step
    assert "`Test-Path docs` 만으로 정하지 않는다" in step   # Windows·macOS 는 Docs 에도 True
    assert "하나도 없으면 `cwd/docs/` 를 새로 만든다" in step


def test_both_folders_use_lowercase_and_skip_link_fix():
    """대소문자 구분 FS 에서 예전 버전이 Docs 레포에 docs/ 를 따로 만들어 둔 상태 —
    Docs 를 고르면 가이드가 하나 더 생기고 링크를 옮겨 기존 가이드가 고아가 된다."""
    text = read(COMMAND)
    step = section(text, "#### 8.1", "#### 8.2")
    assert "둘 이상 찍히면" in step
    assert "`docs/` 를 쓴다" in step
    assert "공존" in step
    merge = section(text, "#### 8.3", "### 9.")
    assert "공존이면 고치지 않는다" in merge


def test_guide_path_follows_actual_docs_folder():
    text = read(COMMAND)
    assert "](docs/codenav-guide.md)" not in text, "CLAUDE.md 링크가 소문자 docs 로 고정돼 있다"
    assert "[<문서 폴더>/codenav-guide.md](<문서 폴더>/codenav-guide.md)" in text
    assert "Test-Path <문서 폴더>/codenav-guide.md" in text


def test_existing_link_with_other_spelling_is_corrected():
    """예전 실행은 Docs 레포에도 소문자 docs/ 링크를 달았다 — '이미 있음' 으로 넘기면 그대로 남는다."""
    merge = section(read(COMMAND), "#### 8.3", "### 9.")
    assert "대소문자만 다르면" in merge
    assert "표시 텍스트와 대상 경로" in merge
    assert "실제 표기로 고친다" in merge


def test_verification_checks_link_spelling_exactly():
    """`codenav-guide` 단어만 찾으면 표기가 틀린 링크도 통과한다."""
    verify = section(read(COMMAND), "### 9.", "### 10.")
    assert 'Select-String -CaseSensitive -SimpleMatch "(<문서 폴더>/codenav-guide.md)" CLAUDE.md' in verify


@pytest.mark.parametrize("mirror", sorted(p.name for p in (ROOT / ".claude" / "commands").glob("*.md")))
def test_repo_local_command_mirror_matches_plugin_command(mirror: str):
    """.claude/commands/ 는 이 레포에서 쓰는 사본이다 — 한쪽만 고치면 수정이 조용히 되돌아간다."""
    assert (ROOT / "commands" / mirror).is_file(), f"{mirror}: 플러그인 커맨드에 없다 — 레포 전용이면 이 테스트에서 뺀다"
    assert read(f".claude/commands/{mirror}") == read(f"commands/{mirror}")
