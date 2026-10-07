"""Intent 1문서 체계 — 폐지한 문서 체계의 잔재 토큰 부재.

v3.58 에서 작업 단위 문서를 Intent 하나로 통합했다(FRD · FC · ADR 파일과 카탈로그 ·
TASK · Work Packet 폐지). 그 토큰이 스킬 · 커맨드 · 에이전트 · 스크립트 · 템플릿에 다시
들어오면 실패한다. 템플릿은 AI 가 레포를 세팅할 때 참고하는 명세라서, 잔재 한 줄이 새
레포마다 옛 구조를 다시 심는다.

면제는 두 가지뿐이다.
- 폐지 안내 3줄 — 옛 입력을 받으면 막는 가드 (ALLOWED). 면제되는 것은 그 문구 자체다 —
  같은 줄의 다른 토큰은 잡는다.
- DOCUMENT_GUIDE 의 retired-doc-types 블록 — 폐지 문서 → Intent 대응표. 다른 파일에 같은
  마커를 옮겨 적어도 면제되지 않고, 닫히지 않은 블록은 그 자체로 실패다.
개념어 "ADR" 단독(Intent 템플릿의 "ADR 은 별도 파일 없이 …")은 토큰이 아니다.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# re.ASCII — 유니코드 \b 는 한글을 단어 문자로 봐서 "FC를" 처럼 조사가 붙은 토큰을 놓친다.
RETIRED = re.compile(
    r"FRD"
    r"|\bFC\b|-FC\b"
    r"|ADR-CATALOG|ADR/|-ADR-"
    r"|TASK/|-TASK-"
    r"|WORK_PACKET|Work Packet|work[-_]packet"
    r"|forge-scope-build",
    re.ASCII,
)

SCAN = (
    ("skills", "**/*.md"),
    ("commands", "**/*.md"),               # codenav-templates/ 포함
    ("agents", "*.md"),
    ("scripts", "*.py"),
    ("scripts/ddr_templates", "*.md"),
    ("scripts/ext_preambles", "*.md"),
    ("docs/.templates", "**/*.md"),
)

# 파일 → 그 파일에서 잔재 토큰을 써도 되는 문구. 면제는 이 문구에만 걸린다.
ALLOWED = {
    "skills/forge-scope/SKILL.md": "Work Packet·TASK 입력은 v3.58 에서 폐지",
    "commands/forge-init.md": "Work Packet·TASK 입력은 … 폐지",
    "scripts/worktree_setup.py": "Work Packet·TASK 입력은 v3.58 에서 폐지",
}
BLOCK_FILE = "docs/.templates/DOCUMENT_GUIDE.md"
BLOCK_BEGIN = "<!-- retired-doc-types:begin -->"
BLOCK_END = "<!-- retired-doc-types:end -->"


def _files() -> list[Path]:
    out: list[Path] = []
    for base, pattern in SCAN:
        out += sorted((ROOT / base).glob(pattern))
    return out


def _file_hits(rel: str, lines: list[str]) -> list[str]:
    out: list[str] = []
    phrase = ALLOWED.get(rel)
    in_block = False
    for n, line in enumerate(lines, 1):
        if rel == BLOCK_FILE and BLOCK_BEGIN in line:
            in_block = True
        if in_block:
            if BLOCK_END in line:
                in_block = False
            continue
        if RETIRED.search(line.replace(phrase, "") if phrase else line):
            out.append(f"{rel}:{n}: {line.strip()[:120]}")
    if in_block:
        out.append(f"{rel}: {BLOCK_BEGIN} 뒤에 {BLOCK_END} 가 없다 — 파일 나머지가 통째로 면제된다")
    return out


def _hits() -> list[str]:
    out: list[str] = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        out += _file_hits(rel, path.read_text(encoding="utf-8").splitlines())
    return out


def test_scan_covers_plugin_sources():
    rels = {p.relative_to(ROOT).as_posix() for p in _files()}
    for must in ("skills/ddr-loop/SKILL.md", "agents/scribe.md", "scripts/ddr_loop.py",
                 "docs/.templates/CLAUDE-TEMPLATE.md", "docs/.templates/.rules/DDD_ARCHITECTURE_RULES.md",
                 "commands/codenav-templates/CODENAV-GUIDE-TEMPLATE.md", "scripts/ext_preambles/coder.md"):
        assert must in rels, must


def test_no_retired_doc_tokens():
    hits = _hits()
    assert not hits, "폐지한 문서 체계 토큰:\n" + "\n".join(hits)


def test_allowlist_is_still_needed():
    # 안내 문구를 지웠는데 면제만 남으면 면제가 썩는다.
    for rel, phrase in ALLOWED.items():
        assert phrase in (ROOT / rel).read_text(encoding="utf-8"), f"{rel}: 면제 문구가 없다 — ALLOWED 에서 지울 것"


def test_retired_block_is_closed():
    text = (ROOT / BLOCK_FILE).read_text(encoding="utf-8")
    assert text.count(BLOCK_BEGIN) == text.count(BLOCK_END) >= 1


# --- 가드 자체의 구멍 -------------------------------------------------------
def test_token_followed_by_korean_particle_is_caught():
    # 한글도 단어 문자라서 유니코드 \b 는 "FC를" 사이에 경계를 보지 못한다.
    for line in ("App PRD 가 FC를 흡수했다", "{App}-FC를 만든다"):
        assert RETIRED.search(line), line
    assert not RETIRED.search("FCM 토큰")   # 다른 낱말의 일부는 토큰이 아니다


def test_marker_block_exempts_only_document_guide():
    lines = [BLOCK_BEGIN, "FRD 폴더를 만든다", BLOCK_END]
    assert _file_hits(BLOCK_FILE, lines) == []
    assert _file_hits("skills/x/SKILL.md", lines), "다른 파일의 마커는 면제가 아니다"


def test_unclosed_marker_block_is_reported():
    assert _file_hits(BLOCK_FILE, [BLOCK_BEGIN, "FRD 폴더를 만든다"]), "닫히지 않은 블록이 파일 나머지를 면제한다"


def test_allowed_phrase_exempts_only_itself():
    rel = "commands/forge-init.md"
    assert _file_hits(rel, [f"- `{ALLOWED[rel]}` → Intent 를 작성한다"]) == []
    assert _file_hits(rel, [f"- `{ALLOWED[rel]}` → FRD 를 작성한다"]), "같은 줄의 다른 토큰까지 면제된다"
