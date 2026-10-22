"""docs/.templates/ 참조 무결성.

템플릿은 대상 레포를 세팅할 때 AI 가 참고하는 명세다. 템플릿·스킬·커맨드 본문이
가리키는 `.templates/<경로>.md` 가 실제로 없으면 AI 는 없는 양식을 찾아 헤매거나
옛 구조를 지어낸다 — v3.58 에서 TASK/WORK_PACKET 템플릿을 지운 뒤
CLAUDE-TEMPLATE 이 그것들을 계속 가리켰던 것처럼.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "docs" / ".templates"
TEMPLATE_REF = re.compile(r"\.templates/([A-Za-z0-9_./-]+\.md)")


def _sources() -> list[Path]:
    return (
        sorted(TEMPLATES.rglob("*.md"))
        + sorted((ROOT / "skills").rglob("*.md"))
        + sorted((ROOT / "commands").glob("*.md"))
    )


def _refs() -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for src in _sources():
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            for m in TEMPLATE_REF.finditer(line):
                out.append((src.relative_to(ROOT).as_posix(), n, m.group(1)))
    return out


def test_scan_finds_template_refs():
    # 정규식이 썩어 0건이 되면 아래 테스트가 공허하게 통과한다.
    assert len(_refs()) >= 10


def test_template_refs_resolve():
    missing = [
        f"{src}:{n} → .templates/{rel}"
        for src, n, rel in _refs()
        if not (TEMPLATES / rel).is_file()
    ]
    assert not missing, "없는 템플릿을 가리킨다:\n" + "\n".join(missing)


def test_root_templates_link_with_actual_docs_spelling():
    """CLAUDE · README 는 레포 루트에 놓여 링크가 `docs/…` 로 시작한다. 기존 레포의 문서 폴더가
    Docs 면 링크도 Docs 로 달아야 한다 — Linux · WSL 은 대소문자를 구분해 소문자 링크가 깨진다."""
    for name in ("CLAUDE-TEMPLATE.md", "README-TEMPLATE.md"):
        warning = next(line for line in (TEMPLATES / name).read_text(encoding="utf-8").splitlines()
                       if "**TEMPLATE**" in line)
        assert "`Docs/`" in warning and "링크" in warning, name
    guide = (TEMPLATES / "DOCUMENT_GUIDE.md").read_text(encoding="utf-8")
    folder_rule = next(line for line in guide.splitlines() if line.startswith("**문서 폴더 표기**"))
    assert "링크" in folder_rule
