"""오케스트레이터 2종(opus / fable)의 불변 계약.

v3.65.0 에서 외부 위임(ext-scout / ext-coder)을 폐지하고 모든 미션을
Claude Code 서브에이전트로 보내도록 바꿨다. 이 파일은 그 전환이
문서 한쪽에만 적용돼 두 오케스트레이터가 갈라지는 것을 막는다.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPUS = ROOT / "agents" / "opus-orchestrator.md"
FABLE = ROOT / "agents" / "fable-orchestrator.md"
FRONTMATTER_LINES = 9  # `---` ~ `---` (name/description/model/effort/tools/disallowedTools/initialPrompt)

# ext 위임의 흔적. "context"·"next"·"text" 같은 부분일치를 피해 토큰으로만 본다.
EXT_TOKENS = (
    "ext-scout", "ext-coder", "ext-scribe", "ext-explorer",
    "ext_dispatch", "ext_preambles", "EXT-FIRST",
)
EXT_WORD = re.compile(r"\bext\b", re.IGNORECASE)

SATELLITES = (
    "scout", "explorer", "analyst", "coder", "scribe", "reviewer", "reviewer-lite",
)


def body(p: Path) -> str:
    return "".join(p.read_text(encoding="utf-8").splitlines(keepends=True)[FRONTMATTER_LINES:])


def test_bodies_are_identical():
    """두 오케스트레이터는 frontmatter 만 다르다 — 본문이 갈라지면 한쪽만 고친 것이다."""
    a, b = body(OPUS), body(FABLE)
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest(), (
        "본문이 다르다 — opus 에서 고친 뒤 fable 에 동기화하지 않았다"
    )


def test_frontmatter_differs_only_in_name_and_model():
    head = lambda p: p.read_text(encoding="utf-8").splitlines()[:FRONTMATTER_LINES]
    diff = [(x, y) for x, y in zip(head(OPUS), head(FABLE)) if x != y]
    keys = {d[0].split(":", 1)[0] for d in diff}
    assert keys == {"name", "description", "model", "effort"}, keys


def test_no_external_delegation():
    """ext 는 폐지됐다 — 라우팅이 다시 ext 로 새면 네이티브 에이전트가 폴백으로 강등된다."""
    for p in (OPUS, FABLE):
        text = p.read_text(encoding="utf-8")
        hits = [tok for tok in EXT_TOKENS if tok in text]
        assert not hits, f"{p.name} still references external delegation: {hits}"
        words = EXT_WORD.findall(text)
        assert not words, f"{p.name} still uses the bare token 'ext' {len(words)}x"


def test_routing_table_sends_scout_and_coder_native():
    text = OPUS.read_text(encoding="utf-8")
    assert "| Locate files / symbols / call sites / tests | claudecode-for-me:scout" in text
    assert "| Implement — ANY source change | claudecode-for-me:coder" in text
    assert "no external transport" in text


def test_coder_spec_quality_survived_the_removal():
    """①②③④ 는 ext 라우팅 장치가 아니라 스펙 품질 요건이라 남아야 한다."""
    text = OPUS.read_text(encoding="utf-8")
    assert "10. Coder spec quality" in text
    for marker in ("① TARGET FILES absolute", "② the TARGET STATE", "③ the algorithm",
                   "④ VERIFY a single command"):
        assert marker in text, marker


def test_hard_limit_allowlist_matches_tools_frontmatter():
    """HARD LIMIT 6 의 허용목록과 frontmatter 의 Agent() 목록이 어긋나면 안 된다."""
    text = OPUS.read_text(encoding="utf-8")
    declared = set(re.findall(r"claudecode-for-me:([a-z-]+)", text.split("---")[1]))
    assert declared == set(SATELLITES), declared
    for name in SATELLITES:
        assert f":{name}" in text, name
