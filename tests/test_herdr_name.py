"""`scripts/herdr_name.py` — herdr 에이전트 이름 정규화.

산문 규칙으로 두면 오적용된다. `worktree_setup.py` 의 `_slugify` 는
`[^A-Za-z0-9._-]` 만 치환하므로 slug 에 대문자와 점이 남는데, herdr 는
`^[a-z][a-z0-9_-]{0,31}$` 만 받는다. 그 변환을 실행 가능한 계약으로 고정한다.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from herdr_name import MAX_LEN, VALID, is_valid, normalize  # noqa: E402

SCRIPT = ROOT / "scripts" / "herdr_name.py"


def test_slug_with_uppercase_becomes_valid():
    """실제 _slugify 출력. 그대로 agent start 에 넘기면 거부된다."""
    assert normalize("MyApp-INT-007") == "myapp-int-007"


def test_every_output_matches_the_herdr_pattern():
    samples = [
        "MyApp-INT-007", "foo.bar baz", "  spaced  ", "한글-문서", "007-foo",
        "UPPER_CASE", "a" * 40, "---", "9", "x", "feat/intent-api.v2",
    ]
    for raw in samples:
        name = normalize(raw)
        assert VALID.match(name), f"{raw!r} -> {name!r} violates herdr name rule"
        assert is_valid(name)


def test_dots_spaces_and_slashes_collapse_to_hyphen():
    assert normalize("foo.bar baz") == "foo-bar-baz"
    assert normalize("intent/MyApp-INT-007") == "intent-myapp-int-007"


def test_leading_non_alpha_is_stripped():
    """herdr 는 선두 문자가 알파벳일 것을 요구한다."""
    assert normalize("007-foo") == "foo"
    assert normalize("_foo") == "foo"


def test_empty_result_falls_back():
    for raw in ("한글", "---", "9", "", "...."):
        assert normalize(raw) == "agent", raw


def test_truncated_to_32():
    name = normalize("a" * 40)
    assert name == "a" * MAX_LEN
    assert len(name) == 32


def test_truncation_does_not_leave_trailing_separator():
    """32번째가 하이픈이면 잘린 자리에 구분자만 남는다 — 보기 싫고 충돌 접미와 겹친다."""
    raw = "a" * 31 + "-" + "b" * 10
    assert normalize(raw) == "a" * 31


def test_collision_appends_suffix():
    assert normalize("foo", taken=["foo"]) == "foo-2"
    assert normalize("foo", taken=["foo", "foo-2"]) == "foo-3"


def test_collision_suffix_respects_the_length_cap():
    """접미를 붙이느라 32자를 넘기면 herdr 가 거부한다."""
    base = "a" * 32
    name = normalize(base, taken=[base])
    assert len(name) <= MAX_LEN
    assert name.endswith("-2")
    assert VALID.match(name)


def test_exhausted_suffixes_raise():
    taken = ["foo"] + [f"foo-{n}" for n in range(2, 100)]
    try:
        normalize("foo", taken=taken)
    except ValueError as e:
        assert "충돌" in str(e)
    else:
        raise AssertionError("100개가 모두 차면 조용히 중복 이름을 내면 안 된다")


def test_is_valid_rejects_what_herdr_rejects():
    for bad in ("MyApp", "007foo", "-foo", "fo o", "a" * 33, "", "foo.bar"):
        assert not is_valid(bad), bad
    for good in ("f", "foo", "foo-2", "a_b-c9", "a" * 32):
        assert is_valid(good), good


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_cli_prints_one_line():
    r = _run("MyApp-INT-007")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "myapp-int-007"


def test_cli_honours_taken():
    r = _run("foo", "--taken", "foo,bar")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "foo-2"


def test_cli_strict_rejects_user_supplied_invalid_name():
    """--name 으로 받은 값은 조용히 고치지 않고 사용자에게 알린다."""
    r = _run("MyApp", "--strict")
    assert r.returncode == 2
    assert "herdr 이름 규칙 위반" in r.stderr
    assert not r.stdout.strip()

    ok = _run("myapp", "--strict")
    assert ok.returncode == 0
    assert ok.stdout.strip() == "myapp"


def test_cli_strict_rejects_taken_name():
    r = _run("myapp", "--strict", "--taken", "myapp")
    assert r.returncode == 2
    assert "이미 쓰이는 이름" in r.stderr
