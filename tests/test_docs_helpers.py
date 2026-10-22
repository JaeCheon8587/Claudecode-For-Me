import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import docs_helpers as dh


def assert_ok_with_hash(out: str) -> None:
    lines = out.strip().splitlines()
    assert len(lines) == 2, lines
    assert lines[0] == "OK"
    assert re.fullmatch(r"RETURN-SHA256: [0-9a-f]{64}  \S+", lines[1]), lines[1]


SAMPLE_INTENT_PATH = Path(
    r"C:/Users/cross/OneDrive/Desktop/qwer/docs/GugudanApi/INTENT/GugudanApi-INT-001.md"
)

INTENT_CANONICAL = """# {app}-INT-{nnn} — 샘플 기능 Intent

| 항목 | 값 |
|---|---|
| 문서 ID | {app}-INT-{nnn} |
| 기능 ID | F001 |
| 상태 | active |
| 작성 | tester · 2026-09-15 |
| 관련 Intent | none |

## Part 1 — 기능 정의

### Problem
문제 설명.

### Outcome
결과 설명.

- Out of scope: 항목A, 항목B

### Affected
영향 설명.

### Constraints
- C1. 제약 조건 — `{code, message}` 포맷 유지

### Decisions
- D1. 결정 — 근거: 근거 — 기각 대안: 대안

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-1. 요구 문장 (D1)

### Edge cases
- E-1. a → b (FR-1)

### Error cases
- X-1. a → b (FR-1)
"""


INTENT_RICH = """# {app}-INT-{nnn} — 리치 샘플 Intent

| 항목 | 값 |
|---|---|
| 문서 ID | {app}-INT-{nnn} |
| 기능 ID | F002 |
| 상태 | active |
| 작성 | tester · 2026-09-15 |
| 관련 Intent | none |

## Part 1 — 기능 정의

### Problem
문제 설명.

### Outcome
결과 설명.

- Out of scope: 항목A, DB(추상화만, 구현 제외), 항목C

### Affected
영향 설명.

### Constraints
- C1. 제약 조건 1
- C2. 제약 조건 2

### Decisions
- D1. 결정 1 — 근거: 근거 — 기각 대안: 대안
- D2. 결정 2 — 근거: 근거 — 기각 대안: 대안

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-1. 요구 문장 1 (D1)
- FR-2. 요구 문장 2 (D1, C2)
- FR-3. 요구 문장 3

### Edge cases
- E-1. 상황 1 → 기대 1 (FR-1)
- E-2. a | b → c (FR-2)

### Error cases
- X-1. 상황 → 기대 (FR-1)
- X-2. 제외 범위 요청 → 거부 (OS)
"""

# v1(3.74 이하) Intent — 작업 지시(유형 · 승인 · 검증 · Acceptance · Verification · Risks · Handoff)가 들어 있다.
INTENT_V1 = {
    "| 기능 ID | F001 |\n| 상태 | active |\n": "| 유형 | 기능개발 |\n| 상태 | draft |\n",
    "| 관련 Intent | none |\n": "| 승인 | pending |\n| 관련 Intent | none |\n| 검증 | pending |\n",
    "- X-1. a → b (FR-1)\n": "- X-1. a → b (FR-1)\n\n### Acceptance\n- [ ] A-1. 완료 조건 (FR-1)\n\n### Verification\n- 확인 방법\n",
}


def write_intent(
    tmp_path: Path,
    app: str = "Demo",
    nnn: str = "001",
    template: str = INTENT_CANONICAL,
    docs_dir: str = "docs",
    **overrides: str,
) -> Path:
    """정상 v2.0 Intent(기능 문서)를 작성한다. overrides 는 str.replace 쌍."""
    text = template
    for old, new in overrides.items():
        text = text.replace(old, new)
    text = text.replace("{app}", app).replace("{nnn}", nnn)
    path = tmp_path / docs_dir / app / "INTENT" / f"{app}-INT-{nnn}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_intent_rich(tmp_path: Path, app: str = "Demo", nnn: str = "001", **overrides: str) -> Path:
    """checklist 검증용 — 항목이 풍부한 Intent 문서를 작성한다."""
    return write_intent(tmp_path, app=app, nnn=nnn, template=INTENT_RICH, **overrides)


EXPECTED_CANONICAL_LINES = (
    "- EXP-1. 인터뷰에서 확정된 요구 — 출처: Q1/A1 — 종류: 요구",
    "- EXP-2. 인터뷰에서 확정된 완료조건 — 출처: Q2/A2 — 종류: 완료조건",
    "- EXP-3. 인터뷰에서 확정된 결정 — 출처: Q3/A3 — 종류: 결정",
    "- EXP-4. 인터뷰에서 확정된 제외 — 출처: Q4/A4 — 종류: 제외",
    "- EXP-5. 인터뷰에서 확정된 제약 — 출처: Q5/A5 — 종류: 제약",
    "- EXP-6. 인터뷰에서 확정된 프로세스 — 출처: Q6/A6 — 종류: 프로세스",
    "- EXP-7. 인터뷰에서 확정된 배경 — 출처: Q7/A7 — 종류: 배경",
)


def write_expected(tmp_path: Path, lines: list[str] | None = None) -> Path:
    """오라클 검증용 expected.md 를 작성한다. lines 주면 본문 줄을 교체한다."""
    body = EXPECTED_CANONICAL_LINES if lines is None else tuple(lines)
    text = "# Expected — Demo-INT-001\n" + "\n".join(body) + "\n"
    p = tmp_path / "expected.md"
    p.write_text(text, encoding="utf-8")
    return p


class TestCheckIntent:
    def _run(self, repo: Path, path: Path, extra: list[str] | None = None) -> int:
        argv = [
            "check-intent",
            "--repo",
            str(repo),
            "--file",
            path.relative_to(repo).as_posix(),
        ]
        if extra:
            argv += extra
        return dh.main(argv)

    def test_valid_intent_exit_0(self, tmp_path, capsys):
        path = write_intent(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "0 WARN, 0 FAIL" in out

    def test_json_output(self, tmp_path, capsys):
        path = write_intent(tmp_path)
        rc = self._run(tmp_path, path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["summary"]["fail"] == 0
        for item in payload["results"]:
            assert set(item) == {"level", "code", "path", "message"}
            assert item["level"] in {"PASS", "WARN", "FAIL"}
            assert item["path"].endswith("Demo-INT-001.md")

    @pytest.mark.parametrize(
        ("overrides", "code"),
        [
            (
                {"| 항목 | 값 |": "> ⚠ **TEMPLATE** — 복사한 뒤 이 경고 블록을 삭제한다.\n\n| 항목 | 값 |"},
                "INT_TEMPLATE_WARNING",
            ),
            ({"# {app}-INT-{nnn} — ": "# {app} INT-{nnn} — "}, "INT_TITLE"),
            ({"| 문서 ID | {app}-INT-{nnn} |": "| 문서 ID | {app}-INT-099 |"}, "INT_ID_FILENAME"),
            ({"| 기능 ID | F001 |\n": ""}, "INT_META_ROWS"),
            ({"| 기능 ID | F001 |": "| 기능 ID | 1 |"}, "INT_FEATURE_ID"),
            ({"| 상태 | active |": "| 상태 | draft |"}, "INT_STATUS"),
            ({"| 작성 | tester · 2026-09-15 |": "| 작성 | tester 2026-09-15 |"}, "INT_AUTHOR_FORMAT"),
            ({"| 관련 Intent | none |": "| 관련 Intent | {app}-INT-{nnn} |"}, "INT_RELATED"),
            ({"| 관련 Intent | none |": "| 관련 Intent | Demo-INT-002, Viewer-INT-001 |"}, "INT_RELATED"),
            ({"### Affected\n영향 설명.\n\n": ""}, "INT_PART1_HEADINGS"),
            ({"### Error cases\n- X-1. a → b (FR-1)\n": ""}, "INT_PART2_HEADINGS"),
            ({"### Error cases\n": "### Risks\n- 리스크\n\n### Error cases\n"}, "INT_LEGACY_SECTIONS"),
            ({"- Out of scope: 항목A, 항목B": "- Out of scope:"}, "INT_OUT_OF_SCOPE"),
            ({"### Open questions\nnone": "### Open questions\n"}, "INT_OPEN_QUESTIONS"),
            ({"결과 설명.": "{결과} 결과 설명."}, "INT_PLACEHOLDER"),
            ({"- D1. 결정 — 근거: 근거 — 기각 대안: 대안": "- D1. 결정 — 근거: 근거"}, "INT_DECISION_FORMAT"),
            (
                {"- C1. 제약 조건 — `{code, message}` 포맷 유지": "- 제약 조건 — `{code, message}` 포맷 유지"},
                "INT_CONSTRAINT_ID",
            ),
            (
                {"- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1)\n- FR-1. 요구 문장 2 (D1)"},
                "INT_ID_ORDER",
            ),
            (
                {"- FR-1. 요구 문장 (D1)": "- FR-2. 요구 문장 (D1)\n- FR-1. 요구 문장 (D1)"},
                "INT_ID_ORDER",
            ),
            ({"- FR-1. 요구 문장 (D1)": "none"}, "INT_ID_ORDER"),
            ({"- E-1. a → b (FR-1)": "- E-1. a → b (FR-9)"}, "INT_REF_DANGLING"),
            ({"- E-1. a → b (FR-1)": "- E-1. 응답에 `retryCount` 를 담는다 (FR-1)"}, "INT_NAME_KIND"),
            ({"- FR-1. 요구 문장 (D1)": "- FR-1. Upload() 로 저장한다 (D1)"}, "INT_NAME_CALL"),
            ({"- FR-1. 요구 문장 (D1)": "- FR-1. UploadController.cs 에서 저장한다 (D1)"}, "INT_NAME_FILE"),
        ],
    )
    def test_break_one_fails(self, tmp_path, capsys, overrides, code):
        path = write_intent(tmp_path, **overrides)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert f"FAIL {code}" in out

    def test_v1_intent_fails_with_migration_hint(self, tmp_path, capsys):
        """v1(3.74 이하) Intent 는 작업 지시가 들어 있다 — 옮기라는 안내와 함께 FAIL."""
        path = write_intent(tmp_path, **INTENT_V1)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        for code in ("INT_META_ROWS", "INT_STATUS", "INT_LEGACY_SECTIONS"):
            line = next(l for l in out.splitlines() if l.startswith(f"FAIL {code}"))
            assert "v1(3.74 이하) 형식이다" in line, line

    def test_backtick_braces_not_flagged(self, tmp_path, capsys):
        path = write_intent(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL INT_PLACEHOLDER" not in out

    def test_fr_number_gap_allowed(self, tmp_path, capsys):
        path = write_intent(tmp_path, **{"- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1)\n- FR-3. 요구 문장 2 (D1)"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out

    def test_edge_error_sections_none_pass(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{
                "### Edge cases\n- E-1. a → b (FR-1)": "### Edge cases\nnone",
                "### Error cases\n- X-1. a → b (FR-1)": "### Error cases\nnone",
            },
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "FAIL INT_ID_ORDER" not in out

    def test_retired_intent_may_have_no_fr(self, tmp_path, capsys):
        """기능을 없앤 Task 가 끝나면(done) 삭제 예정 줄이 다 지워진다 — retired Intent 는 FR 도 none 이다."""
        path = write_intent(
            tmp_path,
            **{
                "| 상태 | active |": "| 상태 | retired |",
                "- FR-1. 요구 문장 (D1)": "none",
                "- E-1. a → b (FR-1)": "none",
                "- X-1. a → b (FR-1)": "none",
            },
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "FAIL INT_ID_ORDER" not in out

    def test_retired_intent_empty_fr_without_none_fails(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{
                "| 상태 | active |": "| 상태 | retired |",
                "- FR-1. 요구 문장 (D1)": "",
                "- E-1. a → b (FR-1)": "none",
                "- X-1. a → b (FR-1)": "none",
            },
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        line = next(l for l in out.splitlines() if l.startswith("FAIL INT_ID_ORDER"))
        assert "retired 면 none 으로 둔다" in line, line

    def test_ref_kind_fr_referencing_fr_warns_only(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{"- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1)\n- FR-2. 요구 문장 (FR-1)"},
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "WARN INT_REF_KIND" in out

    def test_edge_refs_decision_and_out_of_scope_resolve(self, tmp_path, capsys):
        path = write_intent(tmp_path, **{"- E-1. a → b (FR-1)": "- E-1. a → b (D1, OS)"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL INT_REF_DANGLING" not in out

    def test_related_intent_without_file_warns_only(self, tmp_path, capsys):
        """계약을 주고받는 다른 App 의 Intent — 아직 그 파일이 없으면 WARN 이다."""
        write_intent(tmp_path, app="Viewer")
        path = write_intent(tmp_path, **{"| 관련 Intent | none |": "| 관련 Intent | Viewer-INT-001 · Viewer-INT-002 |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "WARN INT_RELATED" in out and "Viewer-INT-002" in out and "'Viewer-INT-001'" not in out

    def test_name_ident_warns_only(self, tmp_path, capsys):
        path = write_intent(tmp_path, **{"- FR-1. 요구 문장 (D1)": "- FR-1. retryCount 를 응답에 담는다 (D1)"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "WARN INT_NAME_IDENT" in out

    def test_part1_is_not_name_checked(self, tmp_path, capsys):
        """이름 규칙 검사는 Task 가 옮겨 가는 Part 2 문장만 본다 — Part 1 은 critic 의 G-3 이 본다."""
        path = write_intent(tmp_path, **{"결과 설명.": "결과 설명 — UploadService.Retry() 를 쓴다."})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS INT_NAME_CALL" in out

    @pytest.mark.parametrize(
        ("status", "level", "detail"),
        [
            ("approved", "PASS", "진행 표시 2개 — TSK-001"),
            ("done", "FAIL", "끝난 Task 의 진행 표시가 남아 있다"),
            ("dropped", "FAIL", "끝난 Task 의 진행 표시가 남아 있다"),
            (None, "WARN", "진행 표시의 Task 가 .task/ 에 없다"),
        ],
    )
    def test_marker_follows_task_status(self, tmp_path, capsys, status, level, detail):
        path = write_intent(tmp_path, **{
            "- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1) [TSK-001 진행 중]",
            "- E-1. a → b (FR-1)": "- E-1. a → b (FR-1) [TSK-001 삭제 예정]",
        })
        if status is not None:
            write_task(tmp_path, **{"| 상태 | approved |": f"| 상태 | {status} |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == (1 if level == "FAIL" else 0), out
        assert f"{level} INT_MARKER" in out and detail in out


class TestParseIntent:
    def test_canonical_document(self, tmp_path):
        doc = dh._parse_intent(write_intent(tmp_path).read_text(encoding="utf-8"))
        assert {kind: len(items) for kind, items in doc.items.items()} == {
            "D": 1,
            "C": 1,
            "OS": 2,
            "FR": 1,
            "E": 1,
            "X": 1,
        }
        assert doc.items["FR"][0].refs == ["D1"]
        assert doc.items["FR"][0].text == "요구 문장"
        assert doc.items["E"][0].text == "a → b"
        assert "(FR-1)" not in doc.items["E"][0].text
        assert doc.meta_order == dh.INTENT_META_EXPECTED

    def test_out_of_scope_parenthesis_split(self):
        doc = dh._parse_intent(
            "### Outcome\n- Out of scope: Docker·compose, DB(추상화만, 구현 제외), 배포\n"
        )
        assert [item.text for item in doc.items["OS"]] == [
            "Docker·compose",
            "DB(추상화만, 구현 제외)",
            "배포",
        ]

    def test_comments_hold_no_sections_or_items(self):
        """주석 안의 `### …` 은 섹션이 아니고 `- FR-n.` 은 항목이 아니다. `####` 소제목은 섹션을 끝내지 않는다."""
        doc = dh._parse_intent(
            "### Functional requirements\n"
            "#### 저장\n"
            "- FR-1. 가 (D1)\n"
            "<!--\n"
            "### Edge cases\n"
            "- FR-2. 예시 (D1)\n"
            "-->\n"
            "- FR-3. 다 (D1) <!-- 메모 -->\n"
        )
        assert [it.id for it in doc.items["FR"]] == ["FR-1", "FR-3"]
        assert doc.items["FR"][1].refs == ["D1"] and doc.items["FR"][1].body == "다 (D1)"
        assert "Edge cases" not in doc.sections

    @pytest.mark.skipif(not SAMPLE_INTENT_PATH.exists(), reason="real sample Intent not present")
    def test_real_sample_smoke(self):
        doc = dh._parse_intent(SAMPLE_INTENT_PATH.read_text(encoding="utf-8"))
        assert len(doc.items["FR"]) == 10
        assert doc.items["FR"][0].refs == ["D3", "D4"]
        assert len(doc.items["OS"]) == 7


class TestIntentChecklist:
    def _run(self, repo: Path, path: Path, extra: list[str] | None = None) -> int:
        argv = [
            "intent-checklist",
            "--repo",
            str(repo),
            "--file",
            path.relative_to(repo).as_posix(),
            "--round",
            "1",
        ]
        if extra:
            argv += extra
        return dh.main(argv)

    def _payload(self, tmp_path: Path, capsys) -> dict:
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--json"])
        out = capsys.readouterr().out
        assert rc == 0
        return json.loads(out)

    def _write_return(
        self,
        tmp_path: Path,
        payload: dict,
        *,
        drop_pass: tuple[str, ...] = (),
        extra_pass: tuple[str, ...] = (),
        fail_keys: tuple[str, ...] = (),
        na_entries: tuple[tuple[str, str], ...] = (),
        quotes: list[tuple[str, str]] | None = None,
    ) -> Path:
        ids = [r["id"] for r in payload["rows"] if r["id"] not in set(drop_pass)]
        lines = ["PASS: " + ", ".join(list(ids) + list(extra_pass))]
        if fail_keys:
            lines.append("FAIL: " + ", ".join(fail_keys))
        for key, reason in na_entries:
            lines.append(f"N/A: {key} — {reason}")
        if quotes is None:
            quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        for rid, text in quotes:
            lines.append(f'QUOTE: {rid} — "{text}"')
        p = tmp_path / "critic-round-1.txt"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def _check(self, tmp_path: Path, capsys, **kwargs) -> tuple[int, str]:
        payload = self._payload(tmp_path, capsys)
        ret = self._write_return(tmp_path, payload, **kwargs)
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--check-return", str(ret)])
        return rc, capsys.readouterr().out

    def test_row_generation(self, tmp_path):
        path = write_intent_rich(tmp_path)
        doc = dh._parse_intent(path.read_text(encoding="utf-8"))
        rows = dh._build_checklist(doc, "Demo-INT-001", 1)
        assert len(rows) == 19
        assert [r.kind for r in rows] == (
            ["OS"] * 3 + ["C"] * 2 + ["D"] * 2 + ["FR"] * 3 + ["E"] * 2 + ["X"] * 2 + ["G"] * 5
        )
        by_id = {r.id: r for r in rows}
        assert by_id["FR-2"].facts == "근거: D1, C2 · 참조하는 E/X: E-2"
        assert by_id["D1"].facts == "참조: FR-1, FR-2"
        assert by_id["D2"].facts == "참조: 없음"
        assert by_id["OS1"].facts == "참조: X-2"
        assert by_id["OS2"].facts == "참조: X-2"
        assert by_id["OS2"].target == "DB(추상화만, 구현 제외)"
        assert by_id["FR-3"].facts == "근거: 없음 · 참조하는 E/X: 없음"
        assert by_id["D1"].na_allowed is True
        assert by_id["FR-1"].na_allowed is False
        assert by_id["FR-1"].criteria[1].severity == "MAJOR"   # Task 의 완료 조건이 FR 문장에서 나온다
        assert by_id["G-3"].criteria[0].severity == "MAJOR"   # 이름 규칙(DOCUMENT_GUIDE §1.4)
        assert by_id["G-1"].target == "" and by_id["G-1"].facts == "" and by_id["G-1"].line is None
        assert by_id["D1"].line == doc.items["D"][0].line

    def test_quote_sample_deterministic(self, tmp_path):
        path = write_intent_rich(tmp_path)
        doc = dh._parse_intent(path.read_text(encoding="utf-8"))
        rows_a = dh._build_checklist(doc, "Demo-INT-001", 1)
        rows_b = dh._build_checklist(doc, "Demo-INT-001", 1)
        quotes_a = {r.id for r in rows_a if r.quote_required}
        quotes_b = {r.id for r in rows_b if r.quote_required}
        assert len(quotes_a) == 5
        assert quotes_a == quotes_b
        assert not any(r.kind == "G" and r.quote_required for r in rows_a)

    def test_markdown_output(self, tmp_path, capsys):
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "# Checklist — Demo-INT-001 — round 1" in out
        table_rows = [
            line
            for line in out.split("\n")
            if line.startswith("| ") and not line.startswith("| ID ")
        ]
        assert len(table_rows) == 19
        assert '"a \\| b → c"' in out
        assert out.count("[인용]") == 5
        assert any(line.startswith("rows: 19 · quote: ") for line in out.split("\n"))

    def test_json_output(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        assert payload["intent"] == "Demo-INT-001"
        assert payload["round"] == 1
        assert len(payload["rows"]) == 19
        assert set(payload["rows"][0]) == {
            "id", "kind", "target", "facts", "criteria", "na_allowed", "quote_required", "line",
        }
        assert set(payload["rows"][0]["criteria"][0]) == {"key", "text", "severity"}
        assert len(payload["quote_rows"]) == 5
        assert payload["traceability"] == {
            "fr": 3,
            "fr_with_ref": 2,
            "ex": 4,
            "ex_with_ref": 4,
            "d_unreferenced": 1,
            "c_unreferenced": 1,
        }

    def test_check_return_ok(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys)
        assert rc == 0
        assert_ok_with_hash(out)

    def test_check_return_missing(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("FR-3",))
        assert rc == 1
        assert "MISSING: FR-3" in out

    def test_check_return_extra(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, extra_pass=("ZZ-9",))
        assert rc == 1
        assert "EXTRA: ZZ-9" in out

    def test_check_return_overlap(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, fail_keys=("FR-1:a",))
        assert rc == 1
        assert "OVERLAP: FR-1" in out

    def test_check_return_bad_key(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("FR-1",), fail_keys=("FR-1:z",))
        assert rc == 1
        assert "BAD-KEY: FR-1:z" in out

    def test_check_return_na_not_allowed(self, tmp_path, capsys):
        rc, out = self._check(
            tmp_path, capsys, drop_pass=("FR-1",), na_entries=(("FR-1:a", "Decisions"),)
        )
        assert rc == 1
        assert "NA-NOT-ALLOWED: FR-1:a" in out

    def test_check_return_na_no_location(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("D1",), na_entries=(("D1:a", "그냥"),))
        assert rc == 1
        assert "NA-NO-LOCATION: D1:a" in out

    def test_check_return_na_old_sections_are_no_location(self, tmp_path, capsys):
        """Handoff · Risks 는 이제 Intent 섹션이 아니다 — N/A 의 반영 위치가 되지 못한다."""
        rc, out = self._check(tmp_path, capsys, drop_pass=("D1",), na_entries=(("D1:a", "Handoff 완료 보고 방식"),))
        assert rc == 1
        assert "NA-NO-LOCATION: D1:a" in out

    def test_check_return_na_with_location_accepted(self, tmp_path, capsys):
        rc, out = self._check(
            tmp_path, capsys, drop_pass=("D1",), na_entries=(("D1:a", "Decisions D1 — 동작을 요구하지 않는 결정"),)
        )
        assert rc == 0
        assert_ok_with_hash(out)

    def test_check_return_quote_missing(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]][:-1]
        rc, out = self._check(tmp_path, capsys, quotes=quotes)
        assert rc == 1
        assert "QUOTE-MISSING:" in out

    def test_check_return_quote_not_found(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        quotes[0] = (quotes[0][0], "이 문장은 문서 어디에도 없다")
        rc, out = self._check(tmp_path, capsys, quotes=quotes)
        assert rc == 1
        assert f"QUOTE-NOT-FOUND: {quotes[0][0]}" in out

    def test_check_return_pass_only_no_quotes(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, quotes=[])
        assert rc == 1
        assert "QUOTE-MISSING:" in out

    def test_check_return_fail_none_na_none_not_extra(self, tmp_path, capsys):
        """Regression: critic writing 'FAIL: none' / 'N/A: none' for a clean round must not become EXTRA: none."""
        payload = self._payload(tmp_path, capsys)
        ids = [r["id"] for r in payload["rows"]]
        quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        lines = ["PASS: " + ", ".join(ids), "FAIL: none", "N/A: none"]
        lines += [f'QUOTE: {rid} — "{text}"' for rid, text in quotes]
        ret = tmp_path / "critic-return-none.txt"
        ret.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--check-return", str(ret)])
        out = capsys.readouterr().out
        assert rc == 0
        assert_ok_with_hash(out)
        assert "EXTRA" not in out

    def test_check_return_fail_eobseum_na_eobseum_not_extra(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        ids = [r["id"] for r in payload["rows"]]
        quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        lines = ["PASS: " + ", ".join(ids), "FAIL: 없음", "N/A: 없음"]
        lines += [f'QUOTE: {rid} — "{text}"' for rid, text in quotes]
        ret = tmp_path / "critic-return-eobseum.txt"
        ret.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--check-return", str(ret)])
        out = capsys.readouterr().out
        assert rc == 0
        assert_ok_with_hash(out)
        assert "EXTRA" not in out

    def test_check_return_quote_none_still_missing(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        ids = [r["id"] for r in payload["rows"]]
        quote_rows = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        satisfied, missing_id = quote_rows[:-1], quote_rows[-1][0]
        lines = ["PASS: " + ", ".join(ids)]
        lines += [f'QUOTE: {rid} — "{text}"' for rid, text in satisfied]
        lines.append("QUOTE: none")
        ret = tmp_path / "critic-return-quote-none.txt"
        ret.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--check-return", str(ret)])
        out = capsys.readouterr().out
        assert rc == 1
        assert f"QUOTE-MISSING: {missing_id}" in out

    def test_check_return_fail_mixed_none_token_parsed(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        target = next(r for r in payload["rows"] if r["id"] == "FR-1")
        key = target["criteria"][0]["key"]
        ids = [r["id"] for r in payload["rows"] if r["id"] != "FR-1"]
        quotes = [(r["id"], r["target"]) for r in payload["rows"] if r["quote_required"]]
        lines = ["PASS: " + ", ".join(ids), f"FAIL: none, FR-1:{key}"]
        lines += [f'QUOTE: {rid} — "{text}"' for rid, text in quotes]
        ret = tmp_path / "critic-return-mixed.txt"
        ret.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path = write_intent_rich(tmp_path)
        rc = self._run(tmp_path, path, extra=["--check-return", str(ret)])
        out = capsys.readouterr().out
        assert rc == 0
        assert_ok_with_hash(out)
        assert "EXTRA" not in out

    def test_check_return_ok_prints_sha256(self, tmp_path, capsys):
        import hashlib as _hashlib
        rc, out = self._check(tmp_path, capsys)
        assert rc == 0
        lines = out.strip().splitlines()
        assert lines[0] == "OK"
        ret_path = tmp_path / "critic-round-1.txt"
        expected = _hashlib.sha256(ret_path.read_bytes()).hexdigest()
        assert len(expected) == 64
        assert lines[1] == f"RETURN-SHA256: {expected}  {ret_path.name}"

    def test_check_return_failing_has_no_sha256(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("FR-3",))
        assert rc == 1
        assert "RETURN-SHA256:" not in out

    def test_unparsable_doc_exit_2(self, tmp_path, capsys):
        path = tmp_path / "docs" / "Bad" / "INTENT" / "Bad-INT-001.md"
        path.parent.mkdir(parents=True)
        path.write_text("### Problem\n본문만 있고 제목·Part 2 없음\n", encoding="utf-8")
        rc = dh.main(
            [
                "intent-checklist",
                "--repo",
                str(tmp_path),
                "--file",
                "docs/Bad/INTENT/Bad-INT-001.md",
                "--round",
                "1",
            ]
        )
        assert rc == 2

    @pytest.mark.skipif(not SAMPLE_INTENT_PATH.exists(), reason="real sample Intent not present")
    def test_real_sample_smoke(self):
        doc = dh._parse_intent(SAMPLE_INTENT_PATH.read_text(encoding="utf-8"))
        rows = dh._build_checklist(doc, "GugudanApi-INT-001", 1)
        assert len([r for r in rows if r.kind == "G"]) == 5
        assert len([r for r in rows if r.kind == "OS"]) == 7
        assert len([r for r in rows if r.kind == "FR"]) == 10


class TestIntentChecklistOracle:
    def _run(self, repo: Path, path: Path, extra: list[str] | None = None) -> int:
        argv = [
            "intent-checklist",
            "--repo",
            str(repo),
            "--file",
            path.relative_to(repo).as_posix(),
            "--round",
            "1",
        ]
        if extra:
            argv += extra
        return dh.main(argv)

    def _payload(self, tmp_path: Path, capsys, *, oracle: bool = True) -> dict:
        path = write_intent_rich(tmp_path)
        extra = ["--json"]
        if oracle:
            extra += ["--oracle", write_expected(tmp_path).relative_to(tmp_path).as_posix()]
        rc = self._run(tmp_path, path, extra=extra)
        out = capsys.readouterr().out
        assert rc == 0
        return json.loads(out)

    def _write_return(
        self,
        tmp_path: Path,
        payload: dict,
        *,
        drop_pass: tuple[str, ...] = (),
        fail_keys: tuple[str, ...] = (),
        na_entries: tuple[tuple[str, str], ...] = (),
    ) -> Path:
        ids = [r["id"] for r in payload["rows"] if r["id"] not in set(drop_pass)]
        lines = ["PASS: " + ", ".join(ids)]
        if fail_keys:
            lines.append("FAIL: " + ", ".join(fail_keys))
        for key, reason in na_entries:
            lines.append(f"N/A: {key} — {reason}")
        for r in payload["rows"]:
            if r["quote_required"]:
                lines.append(f'QUOTE: {r["id"]} — "{r["target"]}"')
        p = tmp_path / "critic-round-1.txt"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def _check(self, tmp_path: Path, capsys, **kwargs) -> tuple[int, str]:
        payload = self._payload(tmp_path, capsys)
        ret = self._write_return(tmp_path, payload, **kwargs)
        path = write_intent_rich(tmp_path)
        rc = self._run(
            tmp_path,
            path,
            extra=["--check-return", str(ret), "--oracle", str(write_expected(tmp_path))],
        )
        return rc, capsys.readouterr().out

    def test_valid_oracle_prepends_exp_rows(self, tmp_path, capsys):
        plain = self._payload(tmp_path, capsys, oracle=False)
        payload = self._payload(tmp_path, capsys)
        assert len(payload["rows"]) == len(plain["rows"]) + 7
        assert [r["id"] for r in payload["rows"][:7]] == [f"EXP-{n}" for n in range(1, 8)]
        assert payload["rows"][7]["id"] == "OS1"
        assert payload["oracle"]["expected"] == 7
        assert payload["oracle"]["kinds"] == {kind: 1 for kind in dh.EXPECTED_KINDS}
        assert "oracle" not in plain

    def test_exp_criteria_and_na_by_kind(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        by_id = {r["id"]: r for r in payload["rows"]}
        assert by_id["EXP-1"]["facts"] == "출처: Q1/A1 · 종류: 요구"
        assert [(c["key"], c["severity"]) for c in by_id["EXP-1"]["criteria"]] == [
            ("a", "MAJOR"),
            ("b", "MAJOR"),
        ]
        for eid in ("EXP-4", "EXP-5"):   # 제외 · 제약
            assert [(c["key"], c["severity"]) for c in by_id[eid]["criteria"]] == [("a", "MAJOR")]
        for eid in ("EXP-6", "EXP-7"):   # 프로세스(Task 몫) · 배경
            assert [(c["key"], c["severity"]) for c in by_id[eid]["criteria"]] == [("a", "MINOR")]
        assert "Task 몫" in by_id["EXP-6"]["criteria"][0]["text"]
        exp_rows = [r for r in payload["rows"] if r["kind"] == "EXP"]
        assert len(exp_rows) == 7
        assert all(r["na_allowed"] is False for r in exp_rows)

    def test_quote_sample_excludes_exp_rows(self, tmp_path, capsys):
        plain = self._payload(tmp_path, capsys, oracle=False)
        payload = self._payload(tmp_path, capsys)
        assert payload["quote_rows"] == plain["quote_rows"]
        assert all(not r["id"].startswith("EXP-") for r in payload["rows"] if r["quote_required"])

    @pytest.mark.parametrize(
        "lines",
        [
            ["- EXP-1. 문장 — 출처: Q1/A1"],
            [
                EXPECTED_CANONICAL_LINES[0],
                EXPECTED_CANONICAL_LINES[1],
                EXPECTED_CANONICAL_LINES[1],
            ],
            [
                "- EXP-1. 문장 — 출처: Q1/A1 — 종류: 요구",
                "- EXP-3. 문장 — 출처: Q2/A2 — 종류: 결정",
                "- EXP-2. 문장 — 출처: Q3/A3 — 종류: 제외",
            ],
            ["- EXP-1. 문장 — 출처: Q1/A1 — 종류: 기타"],
            [],
        ],
    )
    def test_oracle_parse_errors_exit_2(self, tmp_path, capsys, lines):
        path = write_intent_rich(tmp_path)
        oracle = write_expected(tmp_path, lines=lines)
        rc = self._run(tmp_path, path, extra=["--oracle", oracle.relative_to(tmp_path).as_posix()])
        out = capsys.readouterr().out
        assert rc == 2
        assert "ORACLE:" in out
        assert "# Checklist" not in out

    def test_check_return_with_oracle_ok(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys)
        assert rc == 0
        assert_ok_with_hash(out)

    def test_check_return_missing_exp(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("EXP-4",))
        assert rc == 1
        assert "MISSING: EXP-4" in out

    def test_check_return_exp_na_not_allowed(self, tmp_path, capsys):
        rc, out = self._check(
            tmp_path, capsys, drop_pass=("EXP-1",), na_entries=(("EXP-1:a", "Decisions"),)
        )
        assert rc == 1
        assert "NA-NOT-ALLOWED: EXP-1:a" in out

    def test_check_return_exp_bad_key(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("EXP-5",), fail_keys=("EXP-5:b",))
        assert rc == 1
        assert "BAD-KEY: EXP-5:b" in out

    def test_without_oracle_row_ids_unchanged(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys, oracle=False)
        assert [r["id"] for r in payload["rows"]] == [
            "OS1", "OS2", "OS3", "C1", "C2", "D1", "D2",
            "FR-1", "FR-2", "FR-3", "E-1", "E-2", "X-1", "X-2",
            "G-1", "G-2", "G-3", "G-4", "G-5",
        ]

    def test_targets_keep_only_this_intents_rows(self, tmp_path, capsys):
        """한 인터뷰가 Intent 여러 개를 쓰면 항목마다 대상이 붙는다 — 대상 없는 항목은 모든 Intent 에 든다."""
        lines = [
            "- EXP-1. 데모 쪽 요구 — 출처: Q1/A1 — 종류: 요구 — 대상: Demo-INT-001",
            "- EXP-2. 뷰어 쪽 요구 — 출처: Q2/A2 — 종류: 요구 — 대상: Viewer-INT-001",
            "- EXP-3. 계약 결정 — 출처: Q3/A3 — 종류: 결정 — 대상: Demo-INT-001 · Viewer-INT-001",
            "- EXP-4. 공통 배경 — 출처: Q4/A4 — 종류: 배경",
        ]
        path = write_intent_rich(tmp_path)
        oracle = write_expected(tmp_path, lines=lines).relative_to(tmp_path).as_posix()
        rc = self._run(tmp_path, path, extra=["--json", "--oracle", oracle])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        exp = [r for r in payload["rows"] if r["kind"] == "EXP"]
        assert [r["id"] for r in exp] == ["EXP-1", "EXP-3", "EXP-4"]
        assert exp[1]["facts"] == "출처: Q3/A3 · 종류: 결정 · 대상: Demo-INT-001 · Viewer-INT-001"
        assert payload["oracle"]["expected"] == 3

    def test_targets_for_other_intents_only_exit_2(self, tmp_path, capsys):
        path = write_intent_rich(tmp_path)
        oracle = write_expected(tmp_path, lines=["- EXP-1. 뷰어 쪽 요구 — 출처: Q1/A1 — 종류: 요구 — 대상: Viewer-INT-001"])
        rc = self._run(tmp_path, path, extra=["--oracle", oracle.relative_to(tmp_path).as_posix()])
        out = capsys.readouterr().out
        assert rc == 2
        assert "ORACLE: Demo-INT-001 를 대상으로 한 EXP 항목이 없다" in out

    def test_bad_target_is_a_format_error(self, tmp_path, capsys):
        path = write_intent_rich(tmp_path)
        oracle = write_expected(tmp_path, lines=["- EXP-1. 요구 — 출처: Q1/A1 — 종류: 요구 — 대상: 뷰어"])
        rc = self._run(tmp_path, path, extra=["--oracle", oracle.relative_to(tmp_path).as_posix()])
        out = capsys.readouterr().out
        assert rc == 2
        assert "ORACLE: " in out and "형식 불일치" in out


# ---------------------------------------------------------------------------
# intent-catalog — 파생 인덱스 docs/<App>/<App>-INT-CATALOG.md
# ---------------------------------------------------------------------------


CATALOG_HEADER = "| Intent | 제목 | 기능 ID | 상태 | 진행 중 Task | 요약 | 규모 |"
CATALOG_SEPARATOR = "|---|---|---|---|---|---|---|"


def make_app_docs(tmp_path: Path, app: str = "Demo") -> Path:
    """docs/<App>/INTENT/ 골격만 만든다 — Intent 문서는 넣지 않는다."""
    (tmp_path / "docs" / app / "INTENT").mkdir(parents=True, exist_ok=True)
    return tmp_path / "docs" / app


def catalog_path(tmp_path: Path, app: str = "Demo") -> Path:
    return tmp_path / "docs" / app / f"{app}-INT-CATALOG.md"


def catalog_rows(text: str) -> list[str]:
    """카탈로그 표의 Intent 행(링크로 시작하는 줄)만 돌려준다."""
    return [line.strip() for line in text.split("\n") if line.startswith("| [")]


def catalog_cells(text: str, intent_id: str = "Demo-INT-001") -> list[str]:
    r"""해당 Intent 행을 셀 목록으로 쪼갠다. 이스케이프된 `\|` 는 셀 경계가 아니다."""
    for line in catalog_rows(text):
        if line.startswith(f"| [{intent_id}]("):
            cells = re.split(r"(?<!\\)\|", line)
            return [c.strip() for c in cells[1:-1]]
    raise AssertionError(f"row not found: {intent_id}\n{text}")


class TestIntentCatalog:
    def _run(self, repo: Path, app: str = "Demo", extra: list[str] | None = None) -> int:
        argv = ["intent-catalog", "--repo", str(repo), "--app", app]
        if extra:
            argv += extra
        return dh.main(argv)

    def _write(self, tmp_path: Path, capsys, app: str = "Demo") -> str:
        """--write 로 카탈로그를 만들고 그 본문을 돌려준다(출력은 버린다)."""
        rc = self._run(tmp_path, app, extra=["--write"])
        capsys.readouterr()
        assert rc == 0
        return catalog_path(tmp_path, app).read_text(encoding="utf-8")

    # --- V1 · 빈 INTENT ------------------------------------------------------

    def test_empty_intent_dir_renders_zero(self, tmp_path, capsys):
        make_app_docs(tmp_path)
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert out.strip().splitlines()[-1] == "intents: 0"
        assert catalog_rows(out) == []

    def test_missing_intent_dir_renders_zero(self, tmp_path, capsys):
        (tmp_path / "docs" / "Demo").mkdir(parents=True)
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert out.strip().splitlines()[-1] == "intents: 0"

    def test_unknown_app_exit_2(self, tmp_path, capsys):
        rc = self._run(tmp_path, app="NoSuch")
        capsys.readouterr()
        assert rc == 2

    def test_write_and_check_are_exclusive(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--write", "--check"])
        capsys.readouterr()
        assert rc == 2
        assert not catalog_path(tmp_path).exists()

    # --- V2 · --write 직후 --check 는 OK --------------------------------------

    def test_write_then_check_ok(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--write"])
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("WROTE ")
        assert "intents: 1" in out
        assert catalog_path(tmp_path).is_file()

        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 0
        assert out.splitlines() == ["OK", "intents: 1"]

    def test_check_without_catalog_is_stale(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert out.startswith("STALE missing:")
        assert "Demo-INT-CATALOG.md" in out

    # --- V3 · 손으로 고친 카탈로그는 stale ------------------------------------

    def test_check_detects_hand_edited_status_cell(self, tmp_path, capsys):
        write_intent(tmp_path)
        text = self._write(tmp_path, capsys)
        assert "| active |" in text
        catalog_path(tmp_path).write_text(
            text.replace("| active |", "| retired |"), encoding="utf-8"
        )
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "CHANGED Demo-INT-001" in out
        assert "STALE" in out

    def test_check_detects_deleted_row(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        write_intent(tmp_path, nnn="002")
        text = self._write(tmp_path, capsys)
        kept = "\n".join(
            line for line in text.split("\n") if not line.startswith("| [Demo-INT-002](")
        )
        catalog_path(tmp_path).write_text(kept, encoding="utf-8")
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "MISSING Demo-INT-002" in out
        assert "CHANGED Demo-INT-002" not in out

    def test_check_detects_extra_row(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        text = self._write(tmp_path, capsys)
        ghost = (
            "| [Demo-INT-009](INTENT/Demo-INT-009.md) | 유령 | F009 | active | "
            "none | ? | FR 0 · E 0 · X 0 |"
        )
        catalog_path(tmp_path).write_text(
            text.replace("\nintents: 1", f"{ghost}\n\nintents: 1"), encoding="utf-8"
        )
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "EXTRA Demo-INT-009" in out

    def test_check_detects_tail_line_tamper(self, tmp_path, capsys):
        write_intent(tmp_path)
        text = self._write(tmp_path, capsys)
        catalog_path(tmp_path).write_text(
            text.replace("intents: 1", "intents: 7"), encoding="utf-8"
        )
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "CHANGED (헤더 또는 intents 줄)" in out

    # --- --json 은 출력 포맷 플래그일 뿐 동작·exit code 를 바꾸지 않는다 -------

    def test_check_json_keeps_exit_1_when_stale(self, tmp_path, capsys):
        write_intent(tmp_path)
        text = self._write(tmp_path, capsys)
        catalog_path(tmp_path).write_text(
            text.replace("| active |", "| retired |"), encoding="utf-8"
        )
        rc = self._run(tmp_path, extra=["--check", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert payload["check"]["exists"] is True
        assert payload["check"]["stale"] is True
        assert "CHANGED Demo-INT-001" in payload["check"]["diff"]

    def test_check_json_exit_0_when_fresh(self, tmp_path, capsys):
        write_intent(tmp_path)
        self._write(tmp_path, capsys)
        rc = self._run(tmp_path, extra=["--check", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["check"] == {"exists": True, "stale": False, "diff": []}

    def test_check_json_missing_catalog_exit_1(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--check", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert payload["check"]["exists"] is False
        assert payload["check"]["stale"] is True

    def test_write_json_actually_writes_file(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--write", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["write"]["written"] is True
        assert catalog_path(tmp_path).is_file()
        assert catalog_rows(catalog_path(tmp_path).read_text(encoding="utf-8"))
        rc = self._run(tmp_path, extra=["--check"])
        capsys.readouterr()
        assert rc == 0

    def test_plain_json_payload_shape(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert set(payload) == {"app", "catalog", "count", "intents", "skipped"}
        assert payload["app"] == "Demo"
        assert payload["catalog"] == "docs/Demo/Demo-INT-CATALOG.md"
        assert payload["count"] == 1
        assert set(payload["intents"][0]) == {
            "id", "file", "title", "feature", "status", "tasks", "summary", "fr", "e", "x",
        }
        assert payload["intents"][0]["id"] == "Demo-INT-001"
        assert payload["intents"][0]["file"] == "INTENT/Demo-INT-001.md"
        assert (payload["intents"][0]["feature"], payload["intents"][0]["status"]) == ("F001", "active")
        assert payload["intents"][0]["tasks"] == []
        assert [payload["intents"][0][k] for k in ("fr", "e", "x")] == [1, 1, 1]
        assert not catalog_path(tmp_path).exists()

    # --- 렌더링 계약 (다른 도구가 이 출력에 의존한다) -------------------------

    def test_header_is_seven_columns(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        lines = out.split("\n")
        assert CATALOG_HEADER in lines
        assert lines[lines.index(CATALOG_HEADER) + 1] == CATALOG_SEPARATOR
        assert len(catalog_cells(out)) == 7

    def test_last_line_is_intent_count(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        write_intent(tmp_path, nnn="002")
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert out.strip().splitlines()[-1] == "intents: 2"
        assert len(catalog_rows(out)) == 2

    def test_scale_cell_format(self, tmp_path, capsys):
        write_intent_rich(tmp_path)
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert catalog_cells(out)[6] == "FR 3 · E 2 · X 2"

    def test_render_has_no_timestamp_and_is_byte_stable(self, tmp_path, capsys):
        write_intent(tmp_path)
        first = self._write(tmp_path, capsys).encode("utf-8")
        second = self._write(tmp_path, capsys).encode("utf-8")
        assert first == second, "같은 입력에 두 번 렌더하면 바이트가 같아야 한다"
        text = first.decode("utf-8")
        assert re.search(r"\d{4}-\d{2}-\d{2}", text) is None, "날짜가 들어가면 stale 비교가 항상 틀어진다"
        assert re.search(r"\d{2}:\d{2}", text) is None

    def test_pipe_in_title_and_summary_is_escaped(self, tmp_path, capsys):
        write_intent(
            tmp_path,
            **{"샘플 기능 Intent": "제목 | 파이프", "결과 설명.": "요약 | 파이프"},
        )
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        cells = catalog_cells(out)
        assert len(cells) == 7
        assert cells[1] == r"제목 \| 파이프"
        assert cells[5] == r"요약 \| 파이프"

    def test_feature_and_marker_task_cells(self, tmp_path, capsys):
        """진행 중 Task 는 진행 표시에서 뽑아 번호 순으로 Task 문서에 잇는다 — 카탈로그(docs/<App>/)에서 .task/ 는 두 단계 위."""
        write_intent(tmp_path, nnn="001", **{
            "- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1) [TSK-012 진행 중]",
            "- E-1. a → b (FR-1)": "- E-1. a → b (FR-1) [TSK-003 삭제 예정]",
        })
        write_intent(tmp_path, nnn="002")
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        cells = catalog_cells(out)
        assert cells[2] == "F001"
        assert cells[4] == "[TSK-003](../../.task/TSK-003.md) · [TSK-012](../../.task/TSK-012.md)"
        assert catalog_cells(out, "Demo-INT-002")[4] == "none"

    def test_summary_longer_than_50_is_truncated(self, tmp_path, capsys):
        write_intent(tmp_path, **{"결과 설명.": "가" * 60})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        summary = catalog_cells(out)[5]
        assert summary == "가" * (dh.INTENT_CATALOG_SUMMARY_MAX - 1) + "…"
        assert len(summary) == dh.INTENT_CATALOG_SUMMARY_MAX

    def test_summary_exactly_50_is_kept(self, tmp_path, capsys):
        write_intent(tmp_path, **{"결과 설명.": "나" * 50})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert catalog_cells(out)[5] == "나" * 50

    def test_non_matching_filename_is_skipped(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        intent_dir = tmp_path / "docs" / "Demo" / "INTENT"
        (intent_dir / "Demo-INT-TEMPLATE.md").write_text("# Demo-INT-TEMPLATE — 템플릿\n", encoding="utf-8")
        (intent_dir / "README.md").write_text("# 안내\n", encoding="utf-8")
        rc = self._run(tmp_path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["count"] == 1
        assert [r["id"] for r in payload["intents"]] == ["Demo-INT-001"]
        assert sorted(payload["skipped"]) == ["Demo-INT-TEMPLATE.md", "README.md"]

    # --- V5 · 깨진 Intent 파일 -----------------------------------------------

    def test_broken_intent_without_meta_table_fills_question_marks(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        broken = tmp_path / "docs" / "Demo" / "INTENT" / "Demo-INT-002.md"
        broken.write_text("메타 표도 제목도 없는 본문뿐인 파일.\n", encoding="utf-8")
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        cells = catalog_cells(out, "Demo-INT-002")
        assert cells[0] == "[Demo-INT-002](INTENT/Demo-INT-002.md)"
        assert cells[1:4] == ["?"] * 3
        assert cells[4:] == ["none", "?", "FR 0 · E 0 · X 0"]
        assert out.strip().splitlines()[-1] == "intents: 2"

    def test_broken_intent_with_title_only(self, tmp_path, capsys):
        broken = tmp_path / "docs" / "Demo" / "INTENT" / "Demo-INT-003.md"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text("# Demo-INT-003 — 제목만 있다\n\n본문.\n", encoding="utf-8")
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        cells = catalog_cells(out, "Demo-INT-003")
        assert cells[1] == "제목만 있다"
        assert cells[2:4] == ["?"] * 2
        assert cells[4:] == ["none", "?", "FR 0 · E 0 · X 0"]


class TestCheckAppIntentCatalog:
    """check --app 의 INT_CATALOG 규칙 — 카탈로그와 INTENT/ 의 불일치를 FAIL 로 잡는다."""

    def _lines(self, tmp_path: Path, capsys, app: str = "Demo") -> tuple[int, list[str]]:
        rc = dh.main(["check", "--repo", str(tmp_path), "--app", app])
        out = capsys.readouterr().out
        return rc, [line for line in out.split("\n") if " INT_CATALOG " in line]

    def _write_catalog(self, tmp_path: Path, capsys, app: str = "Demo") -> Path:
        rc = dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", app, "--write"])
        capsys.readouterr()
        assert rc == 0
        return catalog_path(tmp_path, app)

    def test_missing_catalog_fails(self, tmp_path, capsys):
        write_intent(tmp_path)
        rc, lines = self._lines(tmp_path, capsys)
        assert rc == 1
        assert len(lines) == 1
        assert lines[0].startswith("FAIL INT_CATALOG docs/Demo/Demo-INT-CATALOG.md")
        assert "missing" in lines[0]

    def test_stale_catalog_fails(self, tmp_path, capsys):
        write_intent(tmp_path)
        path = self._write_catalog(tmp_path, capsys)
        path.write_text(
            path.read_text(encoding="utf-8").replace("| active |", "| retired |"),
            encoding="utf-8",
        )
        rc, lines = self._lines(tmp_path, capsys)
        assert rc == 1
        assert len(lines) == 1
        assert lines[0].startswith("FAIL INT_CATALOG")
        assert "stale" in lines[0]

    def test_fresh_catalog_passes(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        write_intent(tmp_path, nnn="002")
        self._write_catalog(tmp_path, capsys)
        rc, lines = self._lines(tmp_path, capsys)
        assert rc == 0
        assert len(lines) == 1
        assert lines[0].startswith("PASS INT_CATALOG")
        assert "2 intents 최신" in lines[0]

    def test_new_intent_without_regeneration_goes_stale(self, tmp_path, capsys):
        write_intent(tmp_path, nnn="001")
        self._write_catalog(tmp_path, capsys)
        write_intent(tmp_path, nnn="002")
        _, lines = self._lines(tmp_path, capsys)
        assert len(lines) == 1
        assert lines[0].startswith("FAIL INT_CATALOG")
        assert "stale" in lines[0]

    def test_app_without_intent_docs_has_no_int_catalog_result(self, tmp_path, capsys):
        make_app_docs(tmp_path)
        _, lines = self._lines(tmp_path, capsys)
        assert lines == []

    def test_app_without_intent_dir_has_no_int_catalog_result(self, tmp_path, capsys):
        (tmp_path / "docs" / "Demo").mkdir(parents=True)
        _, lines = self._lines(tmp_path, capsys)
        assert lines == []

    def test_only_template_file_has_no_int_catalog_result(self, tmp_path, capsys):
        make_app_docs(tmp_path)
        (tmp_path / "docs" / "Demo" / "INTENT" / "Demo-INT-TEMPLATE.md").write_text(
            "# Demo-INT-TEMPLATE — 템플릿\n", encoding="utf-8"
        )
        _, lines = self._lines(tmp_path, capsys)
        assert lines == []


class TestCheckIntentOnly:
    """check 는 Intent 체계만 검사한다 — v3.58 에서 걷어낸 PRD·FC·FRD·ADR·TASK 를 요구하지 않는다."""

    def _run(self, tmp_path: Path, capsys, app: str = "Demo") -> tuple[int, str]:
        rc = dh.main(["check", "--repo", str(tmp_path), "--app", app])
        return rc, capsys.readouterr().out

    def test_intent_only_repo_passes(self, tmp_path, capsys):
        write_intent(tmp_path)
        assert dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", "Demo", "--write"]) == 0
        capsys.readouterr()
        rc, out = self._run(tmp_path, capsys)
        assert rc == 0, out
        assert not [line for line in out.splitlines() if line.startswith("FAIL ")]
        assert out.strip().splitlines()[-1] == "Summary: 2 PASS, 0 WARN, 0 FAIL"

    def test_app_without_legacy_docs_passes(self, tmp_path, capsys):
        make_app_docs(tmp_path)
        rc, out = self._run(tmp_path, capsys)
        assert rc == 0, out
        for code in ("APP_FILE", "APP_SUBDIR", "FRD_", "TASK_", "ADR_"):
            assert code not in out

    @pytest.mark.parametrize("cmd", ["list-apps", "next-id", "parse-fc", "parse-frd", "git-user"])
    def test_legacy_subcommands_removed(self, tmp_path, capsys, cmd):
        assert dh.main([cmd, "--repo", str(tmp_path)]) == 2
        assert "invalid choice" in capsys.readouterr().err


class TestDocsFolderCase:
    """문서 폴더는 레포마다 docs 또는 Docs 다 — 대소문자만 다른 표기는 같은 폴더로 본다.

    "docs" 를 하드코딩하면 대소문자 구분 FS(Linux)의 Docs 레포에서 App 을 못 찾아 check 가
    FAIL APPS 로, intent-catalog 가 --app not a directory 로 멈춘다.
    """

    def test_docs_root_follows_disk_spelling(self, tmp_path):
        (tmp_path / "Docs").mkdir()
        assert dh._docs_root(tmp_path).name == "Docs"

    def test_docs_root_defaults_to_lowercase(self, tmp_path):
        assert dh._docs_root(tmp_path) == tmp_path / "docs"

    def test_capital_docs_repo_catalog_and_check(self, tmp_path, capsys):
        write_intent(tmp_path, app="XLAB", docs_dir="Docs")   # --app 없는 스캔은 대문자 App 코드만 잡는다

        assert dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", "XLAB", "--write"]) == 0
        assert capsys.readouterr().out.strip() == "WROTE Docs/XLAB/XLAB-INT-CATALOG.md · intents: 1"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["Docs"]   # docs 를 따로 만들지 않는다

        assert dh.main(["check", "--repo", str(tmp_path)]) == 0         # --app 없이 스캔
        out = capsys.readouterr().out
        assert "PASS APP_DIR Docs/XLAB exists" in out
        assert out.strip().splitlines()[-1] == "Summary: 2 PASS, 0 WARN, 0 FAIL"

    @pytest.mark.parametrize("cmd", [["check-intent"], ["intent-checklist", "--round", "1"]])
    def test_file_arg_accepts_other_docs_spelling(self, tmp_path, capsys, cmd):
        """requirement-spec 은 --file 에 docs/… 를 넘긴다 — Docs 레포에서도 같은 파일을 읽어야 한다."""
        write_intent(tmp_path, docs_dir="Docs")
        rc = dh.main([*cmd, "--repo", str(tmp_path), "--file", "docs/Demo/INTENT/Demo-INT-001.md"])
        assert rc == 0, capsys.readouterr()


# ---------------------------------------------------------------------------
# Task — .task/TSK-<NNN>.md (check-task · task-catalog · check 의 TSK_CATALOG)
#
# Intent 는 기능 문서(상시)이고, Task 는 그 Intent 의 어느 항목을 바꾸는지(Scope 사본)와
# 완료 조건(Acceptance)을 정하는 작업 계약이다. 바뀌는 Intent 항목에는 진행 표시가 붙는다.
# ---------------------------------------------------------------------------


FEATURE_INTENT_CANONICAL = """# {app}-INT-{nnn} — 업로드

| 항목 | 값 |
|---|---|
| 문서 ID | {app}-INT-{nnn} |
| 기능 ID | F001 |
| 상태 | active |
| 작성 | tester · 2026-10-01 |
| 관련 Intent | none |

## Part 1 — 기능 정의

### Problem
문제 설명.

### Outcome
결과 설명.

- Out of scope: 여러 파일 동시 업로드

### Affected
업로드 기능 영역.

### Constraints
- C1. 제약 조건

### Decisions
- D1. 결정 — 근거: 근거 — 기각 대안: 대안

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)
- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1) [TSK-001 진행 중]
- FR-3. 업로드 응답에 처리 시간을 밀리초로 담는다. (D1) [TSK-001 진행 중]

### Edge cases
- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-001 삭제 예정]

### Error cases
- X-1. 빈 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)
"""

TASK_CANONICAL = """# TSK-{tnn} — 업로드 응답 보강

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-{tnn} |
| 유형 | 기능개발 |
| 상태 | approved |
| 대상 Intent | Demo-INT-001 |
| 선행 Task | none |
| 작성 | tester · 2026-10-22 |
| 승인 | tester · 2026-10-22 |
| 검증 | SKIPPED — 수동 작성 |

## Goal
- 계기: 재시도가 있었는지 응답에서 알 수 없다.
- 완료 상태: 응답에서 재시도 횟수와 처리 시간을 본다.

## Scope
<!-- 형식: `- {변경} · {App}-INT-{NNN} {항목 ID}. {Intent 문장}` -->
- 신규 · Demo-INT-001 FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)
- 변경 · Demo-INT-001 FR-3. 업로드 응답에 처리 시간을 밀리초로 담는다. (D1)
  - 이전: 업로드 응답에 처리 시간을 초로 담는다. (D1)
- 삭제 · Demo-INT-001 E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1)

- Out of scope: 화면 표시

## Acceptance
- [ ] A-1. 업로드 응답에 응답 필드 `retryCount` 가 있다. (Demo-INT-001 FR-2)
- [ ] A-2. 처리 시간이 밀리초로 온다. (Demo-INT-001 FR-3)
- [ ] A-3. 같은 파일을 두 번 올리면 두 번 저장된다. (Demo-INT-001 E-1, R-1)

## Verification
- 업로드 자동 테스트로 A-1 ~ A-3 을 확인한다.

## Risks
- R-1. 이미 저장된 중복 파일은 그대로 남는다 → 배포 안내에 적는다.

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | demo · Demo |
| 손대지 말 영역 | docs/Demo |
| 완료 보고 방식 | 채팅 요약 |
"""

TASK_REFACTOR = """# TSK-{tnn} — 업로드 저장 단계 분리

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-{tnn} |
| 유형 | 리팩토링 |
| 상태 | approved |
| 대상 Intent | Demo-INT-001 |
| 선행 Task | none |
| 작성 | tester · 2026-10-22 |
| 승인 | tester · 2026-10-22 |
| 검증 | SKIPPED — 수동 작성 |

## Goal
- 계기: 저장과 응답 조립이 한 단계에 섞여 있다.
- 완료 상태: 저장 단계가 분리되고 업로드 동작은 그대로다.

## Scope
- 보존 · Demo-INT-001 FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)

- Out of scope: 성능 개선

## Acceptance
- A-1. 업로드는 여전히 파일 하나를 받아 저장한다. (Demo-INT-001 FR-1)

## Verification
- 기존 업로드 자동 테스트가 그대로 통과한다.

## Risks
none

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | demo · Demo |
| 손대지 말 영역 | docs/Demo |
| 완료 보고 방식 | 채팅 요약 |
"""

# TSK-001 이 새로 만드는 FR-2 에 기대는 E — TSK_DEPENDS_ORDER 용. 대상 Intent 에 INTENT_WITH_E2 를 덧씌운다.
TASK_EDGE = """# TSK-{tnn} — 재시도 없는 업로드 응답

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-{tnn} |
| 유형 | 기능개발 |
| 상태 | approved |
| 대상 Intent | Demo-INT-001 |
| 선행 Task | TSK-001 |
| 작성 | tester · 2026-10-22 |
| 승인 | tester · 2026-10-22 |
| 검증 | SKIPPED — 수동 작성 |

## Goal
- 계기: 재시도 없이 끝난 업로드의 응답이 정해져 있지 않다.
- 완료 상태: 재시도 없이 끝난 업로드도 재시도 횟수를 0으로 받는다.

## Scope
- 신규 · Demo-INT-001 E-2. 재시도 없이 성공한 업로드는 응답 필드 `retryCount` 가 0이다. (FR-2)

- Out of scope: 화면 표시

## Acceptance
- [ ] A-1. 재시도 없이 성공한 업로드 응답의 응답 필드 `retryCount` 가 0이다. (Demo-INT-001 E-2)

## Verification
- 업로드 자동 테스트로 A-1 을 확인한다.

## Risks
none

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | demo · Demo |
| 손대지 말 영역 | docs/Demo |
| 완료 보고 방식 | 채팅 요약 |
"""

INTENT_WITH_E2 = {
    "(FR-1) [TSK-001 삭제 예정]\n": "(FR-1) [TSK-001 삭제 예정]\n"
    "- E-2. 재시도 없이 성공한 업로드는 응답 필드 `retryCount` 가 0이다. (FR-2) [TSK-002 진행 중]\n",
}


def write_feature_intent(
    tmp_path: Path, app: str = "Demo", nnn: str = "001", docs_dir: str = "docs", **overrides: str
) -> Path:
    """새 형식(기능 문서) Intent. overrides 는 str.replace 쌍."""
    return write_intent(tmp_path, app=app, nnn=nnn, template=FEATURE_INTENT_CANONICAL, docs_dir=docs_dir, **overrides)


def write_task(tmp_path: Path, name: str = "TSK-001", template: str = TASK_CANONICAL, **overrides: str) -> Path:
    """.task/<name>.md 를 쓴다. overrides 는 str.replace 쌍 — 없는 문자열을 바꾸려 하면 테스트가 헛돈다."""
    text = template.replace("{tnn}", name[len("TSK-"):])
    for old, new in overrides.items():
        assert old in text, f"override target not found: {old!r}"
        text = text.replace(old, new)
    path = tmp_path / ".task" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_task_pair(tmp_path: Path, task: dict | None = None, intent: dict | None = None) -> Path:
    """깨끗한 Task(TSK-001) + 대상 Intent(Demo-INT-001) 한 쌍. dict 는 문서별 str.replace 쌍."""
    intent = intent or {}
    for old in intent:
        assert old in FEATURE_INTENT_CANONICAL.replace("{app}", "Demo").replace("{nnn}", "001"), old
    write_feature_intent(tmp_path, **intent)
    return write_task(tmp_path, **(task or {}))


# done 전이(/worktree-delete 가 머지를 확인한 뒤) 뒤 Intent — 이 Task 의 진행 표시가 지워지고 삭제 예정 줄이 빠졌다.
INTENT_AFTER_DONE = {
    " (D1) [TSK-001 진행 중]": " (D1)",
    "- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-001 삭제 예정]": "none",
}


class TestParseIntentMarker:
    def test_marker_is_stripped_before_refs(self, tmp_path):
        doc = dh._parse_intent(write_feature_intent(tmp_path).read_text(encoding="utf-8"))
        fr2 = doc.items["FR"][1]
        assert fr2.marker == ("TSK-001", "진행 중")
        assert fr2.refs == ["D1"]
        assert fr2.text == "업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다."
        assert fr2.body == "업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)"
        assert doc.items["E"][0].marker == ("TSK-001", "삭제 예정")
        assert doc.items["E"][0].refs == ["FR-1"]
        assert doc.items["FR"][0].marker is None

    def test_legacy_intent_parse_unchanged(self, tmp_path):
        doc = dh._parse_intent(write_intent(tmp_path).read_text(encoding="utf-8"))
        fr = doc.items["FR"][0]
        assert (fr.text, fr.refs, fr.marker, fr.body) == ("요구 문장", ["D1"], None, "요구 문장 (D1)")

    def test_marker_in_the_middle_is_not_a_marker(self):
        doc = dh._parse_intent("### Functional requirements\n- FR-1. 문장 [TSK-001 진행 중] (D1)\n")
        fr = doc.items["FR"][0]
        assert fr.marker is None
        assert fr.body == "문장 [TSK-001 진행 중] (D1)"


class TestParseTask:
    def test_canonical_task(self, tmp_path):
        doc = dh._parse_task(write_task(tmp_path).read_text(encoding="utf-8"))
        assert doc.meta_order == dh.TASK_META_EXPECTED
        assert doc.targets == ["Demo-INT-001"]
        assert [(it.kind, it.key) for it in doc.scope] == [
            ("신규", "Demo-INT-001 FR-2"),
            ("변경", "Demo-INT-001 FR-3"),
            ("삭제", "Demo-INT-001 E-1"),
        ]
        assert doc.scope[0].text == "업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)"
        assert doc.scope[0].prev is None
        assert doc.scope[1].prev == "업로드 응답에 처리 시간을 초로 담는다. (D1)"
        assert doc.scope_bad_lines == []
        assert doc.out_of_scope == "화면 표시"
        assert [a.id for a in doc.acceptance] == ["A-1", "A-2", "A-3"]
        assert doc.acceptance[0].text == "업로드 응답에 응답 필드 `retryCount` 가 있다."
        assert doc.acceptance[2].refs == ["Demo-INT-001 E-1", "R-1"]
        assert all(a.checked for a in doc.acceptance)
        assert [r[0] for r in doc.risks] == ["R-1"]
        assert doc.handoff_order == dh.TASK_HANDOFF_EXPECTED
        assert doc.handoff["완료 보고 방식"] == "채팅 요약"
        assert doc.depends == []

    def test_targets_keep_order_and_drop_duplicates(self):
        doc = dh._parse_task(
            "| 항목 | 값 |\n|---|---|\n| 대상 Intent | LOADER-INT-003 · VIEWER-INT-001 · LOADER-INT-003 |\n"
        )
        assert doc.targets == ["LOADER-INT-003", "VIEWER-INT-001"]

    def test_depends_keep_order_and_drop_duplicates(self):
        doc = dh._parse_task("| 항목 | 값 |\n|---|---|\n| 선행 Task | TSK-003 · TSK-001 · TSK-003 · 1 |\n")
        assert doc.depends == ["TSK-003", "TSK-001"]

    def test_none_scope_body(self):
        doc = dh._parse_task("## Scope\n<!-- 주석 -->\nnone\n\n- Out of scope: 없음\n")
        assert doc.scope == [] and doc.scope_none is True and doc.scope_bad_lines == []
        assert doc.out_of_scope == "없음"

    def test_intent_path_follows_disk_spelling(self, tmp_path):
        write_feature_intent(tmp_path, docs_dir="Docs")
        assert dh._intent_path(tmp_path, "Demo-INT-001") == tmp_path / "Docs" / "Demo" / "INTENT" / "Demo-INT-001.md"
        assert dh._intent_path(tmp_path, "TSK-001") is None


class TestCheckTask:
    def _run(self, repo: Path, path: Path, extra: list[str] | None = None) -> int:
        argv = ["check-task", "--repo", str(repo), "--file", path.relative_to(repo).as_posix()]
        if extra:
            argv += extra
        return dh.main(argv)

    def test_valid_task_exit_0(self, tmp_path, capsys):
        path = write_task_pair(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "0 WARN, 0 FAIL" in out
        assert "PASS TSK_APPROVED_GATE" in out

    def test_json_output(self, tmp_path, capsys):
        path = write_task_pair(tmp_path)
        rc = self._run(tmp_path, path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["summary"]["fail"] == 0
        for item in payload["results"]:
            assert set(item) == {"level", "code", "path", "message"}
            assert item["path"] == ".task/TSK-001.md"

    @pytest.mark.parametrize(
        ("task", "intent", "code"),
        [
            ({"# TSK-001 — 업로드 응답 보강\n": "# TSK-001 — 업로드 응답 보강\n\n> ⚠ **TEMPLATE** — 지운다.\n"}, {},
             "TSK_TEMPLATE_WARNING"),
            ({"# TSK-001 — ": "# TSK-001 "}, {}, "TSK_TITLE"),
            ({"| 문서 ID | TSK-001 |": "| 문서 ID | TSK-002 |"}, {}, "TSK_ID_FILENAME"),
            ({"| 검증 | SKIPPED — 수동 작성 |\n": ""}, {}, "TSK_META_ROWS"),
            ({"| 유형 | 기능개발 |": "| 유형 | 기능개발 \\| 버그수정 |"}, {}, "TSK_TYPE_SINGLE"),
            ({"| 상태 | approved |": "| 상태 | 승인 |"}, {}, "TSK_STATUS"),
            ({"| 작성 | tester · 2026-10-22 |": "| 작성 | tester 2026-10-22 |"}, {}, "TSK_AUTHOR_FORMAT"),
            ({"| 승인 | tester · 2026-10-22 |": "| 승인 | 대기 |"}, {}, "TSK_APPROVAL_FORMAT"),
            ({"| 검증 | SKIPPED — 수동 작성 |": "| 검증 | 통과 |"}, {}, "TSK_GATE_ROW_FORMAT"),
            ({"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | Demo-INT-001, Demo-INT-002 |"}, {}, "TSK_TARGETS"),
            ({"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | none |"}, {}, "TSK_TARGETS"),
            ({"## Verification\n": "## 확인\n"}, {}, "TSK_SECTIONS"),
            ({"- 계기: 재시도가": "- 계기: {계기} 재시도가"}, {}, "TSK_PLACEHOLDER"),
            ({"| 손대지 말 영역 | docs/Demo |\n": ""}, {}, "TSK_HANDOFF_ROWS"),
            ({"| 손대지 말 영역 |": "| 브랜치명 | task/TSK-001 |\n| 손대지 말 영역 |"}, {}, "TSK_HANDOFF_ROWS"),
            ({"| 선행 Task | none |\n": ""}, {}, "TSK_META_ROWS"),
            ({"| 선행 Task | none |": "| 선행 Task | TSK-001 |"}, {}, "TSK_DEPENDS"),
            ({"| 선행 Task | none |": "| 선행 Task | TSK-009 |"}, {}, "TSK_DEPENDS"),
            ({"| 선행 Task | none |": "| 선행 Task | TSK-1 |"}, {}, "TSK_DEPENDS"),
            ({"| 선행 Task | none |": "| 선행 Task | TSK-002, TSK-003 |"}, {}, "TSK_DEPENDS"),
            ({"- Out of scope: 화면 표시": "- 기타 변경\n\n- Out of scope: 화면 표시"}, {}, "TSK_SCOPE_FORMAT"),
            ({"- 삭제 · Demo-INT-001 E-1.": "- 보존 · Demo-INT-001 E-1."}, {}, "TSK_SCOPE_KIND"),
            ({"- 신규 · Demo-INT-001 FR-2.": "- 신규 · Demo-INT-002 FR-2."}, {}, "TSK_SCOPE_TARGET"),
            ({"  - 이전: 업로드 응답에 처리 시간을 초로 담는다. (D1)\n": ""}, {}, "TSK_SCOPE_PREV"),
            ({"(FR-1)\n\n- Out of scope": "(FR-1)\n  - 이전: 옛 문장\n\n- Out of scope"}, {}, "TSK_SCOPE_PREV"),
            ({"- 변경 · Demo-INT-001 FR-3.": "- 신규 · Demo-INT-001 FR-2. 업로드 응답에 응답 필드 `retryCount` 로 "
              "재시도 횟수를 담는다. (D1)\n- 변경 · Demo-INT-001 FR-3."}, {}, "TSK_SCOPE_DUP"),
            ({"- Out of scope: 화면 표시": "- Out of scope:"}, {}, "TSK_OUT_OF_SCOPE"),
            ({"- [ ] A-2.": "- [ ] A-1."}, {}, "TSK_ID_ORDER"),
            ({"- R-1. 이미 저장된 중복 파일은 그대로 남는다 → 배포 안내에 적는다.": "없음"}, {}, "TSK_ID_ORDER"),
            ({"- [ ] A-2.": "- A-2."}, {}, "TSK_ACCEPTANCE_TYPE"),
            ({"(Demo-INT-001 FR-3)": "(FR-3)"}, {}, "TSK_REF_FORMAT"),
            ({"밀리초로 온다. (Demo-INT-001 FR-3)": "밀리초로 온다."}, {}, "TSK_REF_FORMAT"),
            ({"(Demo-INT-001 E-1, R-1)": "(Demo-INT-001 E-1, R-9)"}, {}, "TSK_REF_DANGLING"),
            ({"(Demo-INT-001 FR-2)": "(Demo-INT-001 FR-2, Goal)"}, {}, "TSK_REF_DANGLING"),
            ({"(Demo-INT-001 FR-3)": "(Demo-INT-001 FR-2)"}, {}, "TSK_SCOPE_COVERAGE"),
            ({"업로드 응답에 응답 필드 `retryCount` 가 있다.": "업로드 응답에 `retryCount` 가 있다."}, {}, "TSK_NAME_KIND"),
            ({"- 계기: 재시도가": "- 계기: UploadService.Retry() 가 없어 재시도가"}, {}, "TSK_NAME_CALL"),
            ({"- 계기: 재시도가": "- 계기: UploadController.cs 에서 재시도가"}, {}, "TSK_NAME_FILE"),
            ({"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | Demo-INT-001 · Demo-INT-009 |"}, {}, "TSK_INTENT_EXISTS"),
            ({}, {"처리 시간을 밀리초로 담는다. (D1) [TSK-001": "처리 시간을 마이크로초로 담는다. (D1) [TSK-001"},
             "TSK_SCOPE_MATCH"),
            ({}, {"(FR-1) [TSK-001 삭제 예정]": "(FR-1)"}, "TSK_MARKER"),
            ({}, {"(FR-1) [TSK-001 삭제 예정]": "(FR-1) [TSK-001 진행 중]"}, "TSK_MARKER"),
            ({}, {"저장한다. (D1)\n": "저장한다. (D1) [TSK-001 진행 중]\n"}, "TSK_MARKER"),
            ({}, {"### Open questions\nnone": "### Open questions\n- 남은 질문"}, "TSK_APPROVED_GATE"),
            ({"| 완료 보고 방식 | 채팅 요약 |": "| 완료 보고 방식 | pending |"}, {}, "TSK_APPROVED_GATE"),
            ({"| 검증 | SKIPPED — 수동 작성 |": "| 검증 | pending |"}, {}, "TSK_APPROVED_GATE"),
        ],
    )
    def test_break_one_fails(self, tmp_path, capsys, task, intent, code):
        path = write_task_pair(tmp_path, task=task, intent=intent)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert f"FAIL {code}" in out

    def test_task_outside_task_dir_fails_location(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        stray = tmp_path / "docs" / "TSK-001.md"
        stray.write_text((tmp_path / ".task" / "TSK-001.md").read_text(encoding="utf-8"), encoding="utf-8")
        rc = self._run(tmp_path, stray)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_LOCATION" in out

    @pytest.mark.parametrize(
        ("task", "code"),
        [
            ({"- 업로드 자동 테스트로 A-1 ~ A-3 을 확인한다.": "- `dotnet test` 로 A-1 ~ A-3 을 확인한다."},
             "TSK_VERIFY_COMMAND"),
            ({"- 계기: 재시도가": "- 계기: retryCount 가 없어 재시도가"}, "TSK_NAME_IDENT"),
        ],
    )
    def test_warn_only(self, tmp_path, capsys, task, code):
        path = write_task_pair(tmp_path, task=task)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert f"WARN {code}" in out
        assert "0 FAIL" in out

    @pytest.mark.parametrize(
        "goal",
        [
            "- 계기: 상태 코드 `400` · `503` 이 섞여 온다.",            # 같은 종류를 잇는 목록
            "- 계기: 상태 코드 `503` 과 오류 코드 `UPLOAD_EMPTY_FILE` 가 온다.",
            "- 계기: API `POST /uploads` 응답에 재시도 횟수가 없다.",
            "- 계기: 외부 API(결제) 호출이 느리다.",                      # 전부 대문자 + 한글 괄호는 호출이 아니다
            "- 계기: 재시도(retry) 정책이 없다.",
        ],
    )
    def test_external_names_with_kind_words_pass(self, tmp_path, capsys, goal):
        path = write_task_pair(tmp_path, task={"- 계기: 재시도가 있었는지 응답에서 알 수 없다.": goal})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "0 WARN, 0 FAIL" in out

    def test_handoff_paths_are_not_name_checked(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 손대지 말 영역 | docs/Demo |": "| 손대지 말 영역 | `src/Loader.Billing/` |"})
        rc = self._run(tmp_path, path)
        assert rc == 0, capsys.readouterr().out

    def test_in_review_keeps_markers_and_passes(self, tmp_path, capsys):
        """마감(in-review)은 머지 전이다 — 리뷰에서 돌려보낼 수 있으므로 표시와 삭제 예정 줄이 남는다."""
        path = write_task_pair(tmp_path, task={"| 상태 | approved |": "| 상태 | in-review |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_MARKER" in out and "PASS TSK_SCOPE_MATCH" in out
        assert "TSK_APPROVED_GATE" not in out

    def test_in_review_with_markers_cleared_fails(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 상태 | approved |": "| 상태 | in-review |"}, intent=INTENT_AFTER_DONE)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_MARKER" in out
        assert "FAIL TSK_SCOPE_MATCH" in out   # 삭제 항목이 done 전에 Intent 에서 빠졌다

    def test_done_with_markers_left_fails(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 상태 | approved |": "| 상태 | done |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_MARKER" in out

    def test_done_skips_scope_match_but_not_markers(self, tmp_path, capsys):
        later = {**INTENT_AFTER_DONE, "처리 시간을 밀리초로": "처리 시간을 마이크로초로"}   # 뒤의 Task 가 다시 바꿨다
        path = write_task_pair(tmp_path, task={"| 상태 | approved |": "| 상태 | done |"}, intent=later)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_SCOPE_MATCH" in out and "건너뜀" in out

    def test_dropped_with_markers_left_fails(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 상태 | approved |": "| 상태 | dropped |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_MARKER" in out

    def test_conflict_with_other_open_task(self, tmp_path, capsys):
        path = write_task_pair(tmp_path)
        write_task(tmp_path, name="TSK-002", **{"| 상태 | approved |": "| 상태 | draft |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_CONFLICT" in out
        assert "TSK-002" in out

    def test_done_task_does_not_conflict(self, tmp_path, capsys):
        path = write_task_pair(tmp_path)
        write_task(tmp_path, name="TSK-002", **{"| 상태 | approved |": "| 상태 | done |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert "PASS TSK_CONFLICT" in out
        assert "FAIL TSK_CONFLICT" not in out
        # TSK-002 는 이름만 다른 사본이라 다른 규칙도 TSK-001 쪽은 통과한다.
        assert rc == 0, out

    def test_two_preserve_tasks_do_not_conflict(self, tmp_path, capsys):
        write_feature_intent(tmp_path)
        path = write_task(tmp_path, name="TSK-003", template=TASK_REFACTOR)
        write_task(tmp_path, name="TSK-004", template=TASK_REFACTOR)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert "PASS TSK_CONFLICT" in out
        assert "PASS TSK_ACCEPTANCE_TYPE" in out   # 리팩토링 A 는 평문 목록
        assert rc == 0, out

    def test_refactor_without_intent_uses_goal(self, tmp_path, capsys):
        path = write_task(
            tmp_path, name="TSK-005", template=TASK_REFACTOR,
            **{
                "| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | none |",
                "- 보존 · Demo-INT-001 FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)": "none",
                "(Demo-INT-001 FR-1)": "(Goal)",
            },
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "TSK_INTENT_EXISTS" not in out

    def test_depends_on_existing_task_passes(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 선행 Task | none |": "| 선행 Task | TSK-002 |"})
        write_task(tmp_path, name="TSK-002", template=TASK_REFACTOR)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_DEPENDS" in out and "선행 Task: TSK-002" in out

    def test_depends_cycle_fails(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 선행 Task | none |": "| 선행 Task | TSK-002 |"})
        write_task(tmp_path, name="TSK-002", template=TASK_REFACTOR, **{"| 선행 Task | none |": "| 선행 Task | TSK-003 |"})
        write_task(tmp_path, name="TSK-003", template=TASK_REFACTOR, **{"| 선행 Task | none |": "| 선행 Task | TSK-001 |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_DEPENDS" in out and "순환: TSK-001 → TSK-002 → TSK-003 → TSK-001" in out

    def test_dropped_predecessor_warns(self, tmp_path, capsys):
        path = write_task_pair(tmp_path, task={"| 선행 Task | none |": "| 선행 Task | TSK-002 |"})
        write_task(tmp_path, name="TSK-002", template=TASK_REFACTOR, **{"| 상태 | approved |": "| 상태 | dropped |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "WARN TSK_DEPENDS" in out and "TSK-002" in out

    def test_edge_after_its_fr_passes(self, tmp_path, capsys):
        write_task_pair(tmp_path, intent=INTENT_WITH_E2)
        path = write_task(tmp_path, name="TSK-002", template=TASK_EDGE)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_DEPENDS_ORDER" in out and "0 WARN, 0 FAIL" in out

    def test_edge_before_its_fr_fails(self, tmp_path, capsys):
        write_task_pair(tmp_path, intent=INTENT_WITH_E2)
        path = write_task(tmp_path, name="TSK-002", template=TASK_EDGE, **{"| 선행 Task | TSK-001 |": "| 선행 Task | none |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL TSK_DEPENDS_ORDER" in out and "Demo-INT-001 E-2 가 기대는 FR-2 를 TSK-001" in out

    def test_edge_reaches_its_fr_through_another_task(self, tmp_path, capsys):
        write_task_pair(tmp_path, intent=INTENT_WITH_E2)
        write_task(tmp_path, name="TSK-003", template=TASK_REFACTOR, **{"| 선행 Task | none |": "| 선행 Task | TSK-001 |"})
        path = write_task(tmp_path, name="TSK-002", template=TASK_EDGE, **{"| 선행 Task | TSK-001 |": "| 선행 Task | TSK-003 |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_DEPENDS_ORDER" in out

    def test_edge_after_done_fr_needs_no_predecessor(self, tmp_path, capsys):
        """FR 을 바꾼 Task 가 끝났으면(done) 기댈 동작이 이미 있다 — 선행이 없어도 된다."""
        e1 = "- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-001 삭제 예정]"
        e2 = INTENT_WITH_E2["(FR-1) [TSK-001 삭제 예정]\n"].split("\n")[1]
        write_task_pair(
            tmp_path, task={"| 상태 | approved |": "| 상태 | done |"},
            intent={**INTENT_AFTER_DONE, e1: e2},   # TSK-001 이 끝나 E-1 은 빠졌고 표시도 없다
        )
        path = write_task(tmp_path, name="TSK-002", template=TASK_EDGE, **{"| 선행 Task | TSK-001 |": "| 선행 Task | none |"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "PASS TSK_DEPENDS_ORDER" in out

    def test_two_app_example_and_bugfix_pass(self, tmp_path, capsys):
        """초안 EXAMPLE.md 의 두 App 계약 변경(TSK-012)과 버그수정(TSK-011) — 같은 Intent 의 다른 항목이라 충돌하지 않는다."""
        for rel, text in EXAMPLE_FILES.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        for name in ("TSK-012", "TSK-011"):
            rc = self._run(tmp_path, tmp_path / ".task" / f"{name}.md")
            out = capsys.readouterr().out
            assert rc == 0, out
            assert "0 WARN, 0 FAIL" in out, out


EXAMPLE_FILES = {
    "docs/LOADER/INTENT/LOADER-INT-003.md": """# LOADER-INT-003 — 업로드

| 항목 | 값 |
|---|---|
| 문서 ID | LOADER-INT-003 |
| 기능 ID | F003 |
| 상태 | active |
| 작성 | 홍길동 · 2026-10-01 |
| 관련 Intent | VIEWER-INT-001 |

## Part 1 — 기능 정의

### Problem
사용자가 파일을 올려 보관할 방법이 없다.

### Outcome
사용자가 파일 하나를 올려 저장하고 결과를 바로 확인한다.

- Out of scope: 여러 파일 동시 업로드

### Affected
LOADER 업로드 기능 영역.

### Constraints
- C1. 업로드 응답은 2초 안에 돌아온다.

### Decisions
- D1. 업로드는 동기 응답으로 저장 결과를 돌려준다 — 근거: 화면이 결과를 바로 보여 준다 — 기각 대안: 비동기 작업 번호
- D2. 일시 오류는 서버가 다시 시도한다 — 근거: 사용자가 다시 올리는 문의가 반복된다 — 기각 대안: 화면에서 다시 시도

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-1. 업로드는 파일 하나를 받아 저장하고 저장 결과를 응답한다. (D1)
- FR-2. 업로드 결과 응답에 처리 시간과, 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1, D2) [TSK-012 진행 중]
- FR-4. 업로드가 일시 오류로 실패하면 설정 키 `upload.retry.max` 횟수만큼 다시 시도한다. (D2) [TSK-012 진행 중]

### Edge cases
- E-4. 재시도 끝에 성공해도 파일은 한 번만 저장된다. (FR-4) [TSK-012 진행 중]

### Error cases
- X-2. 0바이트 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)
- X-3. 재시도가 모두 실패하면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 를 반환한다. (FR-4) [TSK-012 진행 중]
""",
    "docs/VIEWER/INTENT/VIEWER-INT-001.md": """# VIEWER-INT-001 — 업로드 목록

| 항목 | 값 |
|---|---|
| 문서 ID | VIEWER-INT-001 |
| 기능 ID | F001 |
| 상태 | active |
| 작성 | 홍길동 · 2026-10-01 |
| 관련 Intent | LOADER-INT-003 |

## Part 1 — 기능 정의

### Problem
사용자가 올린 파일의 처리 결과를 한곳에서 볼 수 없다.

### Outcome
업로드 목록에서 파일마다 처리 결과를 본다.

- Out of scope: 목록 내보내기

### Affected
VIEWER 업로드 목록 화면.

### Constraints
none

### Decisions
- D3. 재시도가 있었는지는 문구로 보여 준다 — 근거: 아이콘은 의미를 따로 배워야 한다 — 기각 대안: 아이콘

### Open questions
none

---

## Part 2 — 동작

### Functional requirements
- FR-5. 업로드 목록은 응답 필드 `retryCount` 가 1 이상인 항목에 문구 "재시도 후 완료" 를 표시한다. (D3) [TSK-012 진행 중]

### Edge cases
none

### Error cases
none
""",
    ".task/TSK-012.md": """# TSK-012 — 업로드 일시 오류 자동 재시도

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-012 |
| 유형 | 기능개발 |
| 상태 | approved |
| 대상 Intent | LOADER-INT-003 · VIEWER-INT-001 |
| 선행 Task | none |
| 작성 | 홍길동 · 2026-10-22 |
| 승인 | 홍길동 · 2026-10-22 |
| 검증 | PASS — code PASS · llm PASS · 1/3 |

## Goal
- 계기: 네트워크 일시 오류로 업로드가 실패해 사용자가 다시 올리는 문의가 반복된다.
- 완료 상태: 일시 오류는 사용자가 다시 올리지 않아도 재시도로 복구되고, 업로드 목록에서 재시도가 있었는지 보인다. 끝내 실패하면 원인을 알 수 있는 오류 코드가 돌아온다.

## Scope
- 변경 · LOADER-INT-003 FR-2. 업로드 결과 응답에 처리 시간과, 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1, D2)
  - 이전: 업로드 결과 응답에 처리 시간을 담는다. (D1)
- 신규 · LOADER-INT-003 FR-4. 업로드가 일시 오류로 실패하면 설정 키 `upload.retry.max` 횟수만큼 다시 시도한다. (D2)
- 신규 · LOADER-INT-003 E-4. 재시도 끝에 성공해도 파일은 한 번만 저장된다. (FR-4)
- 신규 · LOADER-INT-003 X-3. 재시도가 모두 실패하면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 를 반환한다. (FR-4)
- 신규 · VIEWER-INT-001 FR-5. 업로드 목록은 응답 필드 `retryCount` 가 1 이상인 항목에 문구 "재시도 후 완료" 를 표시한다. (D3)

- Out of scope: 업로드 화면의 재시도 진행 표시 (후속 Task)

## Acceptance
- [ ] A-1. 일시 오류가 두 번 난 뒤 성공하는 업로드는 성공 응답을 받고, 응답 필드 `retryCount` 가 2다. (LOADER-INT-003 FR-4, LOADER-INT-003 FR-2)
- [ ] A-2. 설정 키 `upload.retry.max` 가 1이면 재시도는 한 번만 일어난다. (LOADER-INT-003 FR-4)
- [ ] A-3. 일시 오류가 계속되면 상태 코드 `503` 과 오류 코드 `UPLOAD_RETRY_EXHAUSTED` 가 돌아온다. (LOADER-INT-003 X-3)
- [ ] A-4. 권한 없음처럼 일시 오류가 아닌 실패는 다시 시도하지 않는다. (LOADER-INT-003 FR-4)
- [ ] A-5. 일시 오류 한 번 뒤 성공한 업로드는 파일이 한 번만 저장된다. (LOADER-INT-003 E-4)
- [ ] A-6. LOADER 가 응답 필드 `retryCount` 2 를 돌려준 업로드는 VIEWER 업로드 목록에 문구 "재시도 후 완료" 로 보인다. (LOADER-INT-003 FR-2, VIEWER-INT-001 FR-5)
- [ ] A-7. 응답 필드 `retryCount` 가 없는 응답을 받으면 VIEWER 는 문구를 표시하지 않고 목록을 정상으로 보여 준다. (R-2)

## Verification
- 일시 오류를 흉내 내는 자동 테스트로 A-1 ~ A-5 를 확인한다.
- 두 App 을 함께 띄운 통합 확인으로 A-6 을, 필드가 빠진 응답을 흉내 내는 테스트로 A-7 을 확인한다.

## Risks
- R-1. 배포 전에 이미 실패한 업로드는 자동으로 다시 시도되지 않는다 → 배포 안내에 적는다.
- R-2. VIEWER 가 LOADER 보다 먼저 배포되면 응답 필드 `retryCount` 가 없는 응답을 받는다 → 필드가 없어도 목록이 깨지지 않는지 A-7 로 확인한다.

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | upload-suite · LOADER, VIEWER |
| 손대지 말 영역 | `src/Loader.Billing/` |
| 완료 보고 방식 | 마감 보고 파일 + 채팅 요약 |
""",
    ".task/TSK-011.md": """# TSK-011 — 업로드 0바이트 파일 거부

| 항목 | 값 |
|---|---|
| 문서 ID | TSK-011 |
| 유형 | 버그수정 |
| 상태 | approved |
| 대상 Intent | LOADER-INT-003 |
| 선행 Task | none |
| 작성 | 홍길동 · 2026-10-20 |
| 승인 | 홍길동 · 2026-10-20 |
| 검증 | SKIPPED — 수동 작성 |

## Goal
- 계기: 크기가 0인 파일로 API `POST /uploads` 를 호출하면 상태 코드 `201` 이 돌아오고 빈 파일이 저장된다.
- 완료 상태: 0바이트 파일 업로드는 거부되고 아무것도 저장되지 않는다.

## Scope
- 위반 · LOADER-INT-003 X-2. 0바이트 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)

- Out of scope: 최대 크기 초과 파일 처리

## Acceptance
- [ ] A-1. 크기가 0인 파일로 API `POST /uploads` 를 호출하면 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 가 돌아오고 아무것도 저장되지 않는다. (LOADER-INT-003 X-2)

## Verification
- 0바이트 파일을 올리는 자동 테스트로 A-1 을 확인한다.

## Risks
none

## Handoff
| 항목 | 값 |
|---|---|
| repo · app | upload-suite · LOADER |
| 손대지 말 영역 | `src/Loader.Billing/` |
| 완료 보고 방식 | 채팅 요약 |
""",
}


def task_catalog_path(tmp_path: Path) -> Path:
    return tmp_path / ".task" / "task-catalog.md"


def task_catalog_cells(text: str, task_id: str = "TSK-001") -> list[str]:
    for line in text.split("\n"):
        if line.startswith(f"| [{task_id}]("):
            return [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
    raise AssertionError(f"row not found: {task_id}\n{text}")


class TestTaskCatalog:
    def _run(self, repo: Path, extra: list[str] | None = None) -> int:
        return dh.main(["task-catalog", "--repo", str(repo), *(extra or [])])

    def _write(self, tmp_path: Path, capsys) -> str:
        rc = self._run(tmp_path, extra=["--write"])
        capsys.readouterr()
        assert rc == 0
        return task_catalog_path(tmp_path).read_text(encoding="utf-8")

    def test_no_task_dir_exit_2(self, tmp_path, capsys):
        rc = self._run(tmp_path)
        assert rc == 2
        assert ".task/" in capsys.readouterr().err

    def test_write_and_check_are_exclusive(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        rc = self._run(tmp_path, extra=["--write", "--check"])
        capsys.readouterr()
        assert rc == 2
        assert not task_catalog_path(tmp_path).exists()

    def test_write_then_check_ok(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        rc = self._run(tmp_path, extra=["--write"])
        out = capsys.readouterr().out
        assert rc == 0
        assert out.strip() == "WROTE .task/task-catalog.md · tasks: 1"
        rc = self._run(tmp_path, extra=["--check"])
        assert rc == 0
        assert capsys.readouterr().out.splitlines() == ["OK", "tasks: 1"]

    def test_render_matches_draft_template_shape(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        text = self._write(tmp_path, capsys)
        lines = text.split("\n")
        assert lines[0] == "# TASK-CATALOG — Task Catalog"
        assert "| 문서 ID | TASK-CATALOG |" in lines
        assert "| Task | 설명 | 유형 | 상태 | 선행 | 대상 Intent |" in lines
        assert task_catalog_cells(text) == [
            "[TSK-001](TSK-001.md)", "업로드 응답 보강", "기능개발", "approved", "none",
            "[Demo-INT-001](../docs/Demo/INTENT/Demo-INT-001.md)",
        ]
        assert text.strip().splitlines()[-1] == "tasks: 1"
        assert re.search(r"\d{4}-\d{2}-\d{2}", text) is None, "날짜가 들어가면 stale 비교가 항상 틀어진다"

    def test_check_without_catalog_is_stale(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        rc = self._run(tmp_path, extra=["--check"])
        assert rc == 1
        assert capsys.readouterr().out.startswith("STALE missing: .task/task-catalog.md")

    def test_check_detects_hand_edited_status_cell(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        text = self._write(tmp_path, capsys)
        task_catalog_path(tmp_path).write_text(text.replace("| approved |", "| in-review |"), encoding="utf-8")
        rc = self._run(tmp_path, extra=["--check"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "CHANGED TSK-001" in out and "STALE" in out

    def test_check_detects_missing_row_and_tail(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        write_task(tmp_path, name="TSK-002", **{"| 상태 | approved |": "| 상태 | done |"})
        text = self._write(tmp_path, capsys)
        kept = "\n".join(line for line in text.split("\n") if not line.startswith("| [TSK-002]("))
        task_catalog_path(tmp_path).write_text(kept, encoding="utf-8")
        assert self._run(tmp_path, extra=["--check"]) == 1
        assert "MISSING TSK-002" in capsys.readouterr().out
        task_catalog_path(tmp_path).write_text(text.replace("tasks: 2", "tasks: 9"), encoding="utf-8")
        assert self._run(tmp_path, extra=["--check"]) == 1
        assert "CHANGED (헤더 또는 tasks 줄)" in capsys.readouterr().out

    def test_json_payload_shape(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        (tmp_path / ".task" / "notes.md").write_text("# 메모\n", encoding="utf-8")
        rc = self._run(tmp_path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert set(payload) == {"catalog", "count", "tasks", "skipped"}
        assert payload["catalog"] == ".task/task-catalog.md"
        assert payload["skipped"] == ["notes.md"]
        assert set(payload["tasks"][0]) == {"id", "file", "title", "type", "status", "depends", "intents"}
        assert payload["tasks"][0]["depends"] == []
        assert payload["tasks"][0]["intents"] == [
            {"id": "Demo-INT-001", "link": "../docs/Demo/INTENT/Demo-INT-001.md"}
        ]
        assert not task_catalog_path(tmp_path).exists()

    def test_catalog_file_is_not_a_task(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        self._write(tmp_path, capsys)
        rc = self._run(tmp_path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["count"] == 1 and payload["skipped"] == []

    def test_links_follow_docs_spelling_and_flag_missing(self, tmp_path, capsys):
        write_feature_intent(tmp_path, docs_dir="Docs")
        write_task(tmp_path, **{"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | Demo-INT-001 · Demo-INT-009 |"})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert task_catalog_cells(out)[5] == "[Demo-INT-001](../Docs/Demo/INTENT/Demo-INT-001.md) · ?Demo-INT-009"

    def test_depends_cell_links_tasks_and_flags_missing(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        write_task(tmp_path, name="TSK-002", template=TASK_REFACTOR, **{"| 선행 Task | none |": "| 선행 Task | TSK-001 · TSK-009 |"})
        rc = self._run(tmp_path, extra=["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["tasks"][1]["depends"] == [{"id": "TSK-001", "link": "TSK-001.md"}, {"id": "TSK-009", "link": None}]
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert task_catalog_cells(out, "TSK-002")[4] == "[TSK-001](TSK-001.md) · ?TSK-009"

    def test_none_targets_cell(self, tmp_path, capsys):
        write_task(tmp_path, name="TSK-005", template=TASK_REFACTOR, **{"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | none |"})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert task_catalog_cells(out, "TSK-005")[5] == "none"


class TestCheckTaskCatalog:
    """check 의 TSK_CATALOG — Task 는 레포 단위라 --app 을 줘도 본다. Task 가 없으면 아무 줄도 내지 않는다."""

    def _run(self, tmp_path: Path, capsys) -> tuple[int, str]:
        rc = dh.main(["check", "--repo", str(tmp_path), "--app", "Demo"])
        return rc, capsys.readouterr().out

    def _catalogs(self, tmp_path: Path, capsys) -> None:
        assert dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", "Demo", "--write"]) == 0
        assert dh.main(["task-catalog", "--repo", str(tmp_path), "--write"]) == 0
        capsys.readouterr()

    def test_no_task_dir_prints_nothing(self, tmp_path, capsys):
        write_intent(tmp_path)
        assert dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", "Demo", "--write"]) == 0
        capsys.readouterr()
        rc, out = self._run(tmp_path, capsys)
        assert rc == 0
        assert "TSK_" not in out
        assert out.strip().splitlines()[-1] == "Summary: 2 PASS, 0 WARN, 0 FAIL"

    def test_missing_task_catalog_fails(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        assert dh.main(["intent-catalog", "--repo", str(tmp_path), "--app", "Demo", "--write"]) == 0
        capsys.readouterr()
        rc, out = self._run(tmp_path, capsys)
        assert rc == 1
        assert "FAIL TSK_CATALOG .task/task-catalog.md missing" in out

    def test_fresh_task_catalog_passes(self, tmp_path, capsys):
        write_task_pair(tmp_path)
        self._catalogs(tmp_path, capsys)
        rc, out = self._run(tmp_path, capsys)
        assert rc == 0, out
        assert "PASS TSK_CATALOG .task/task-catalog.md 1 tasks 최신" in out

    def test_status_change_without_regeneration_goes_stale(self, tmp_path, capsys):
        path = write_task_pair(tmp_path)
        self._catalogs(tmp_path, capsys)
        path.write_text(path.read_text(encoding="utf-8").replace("| 상태 | approved |", "| 상태 | in-review |"), encoding="utf-8")
        rc, out = self._run(tmp_path, capsys)
        assert rc == 1
        assert "FAIL TSK_CATALOG .task/task-catalog.md stale" in out


# ---------------------------------------------------------------------------
# /task-split — 기준선(intent-base) · 변경 목록(intent-diff) · 진행 표시(mark-intent) · 자르기 검사(split-check)
#
# 흐름: requirement-spec 수정 모드가 고치기 전 사본을 남긴다 → Intent 를 고친다(INTENT_EDITED) →
# /task-split 이 변경 목록으로 Task 를 쓰고 표시를 붙인다(= FEATURE_INTENT_CANONICAL) → 승인하면 사본을 지운다.
# ---------------------------------------------------------------------------


# 고친 뒤 · 자르기 전 — 진행 표시가 없고, 지운 E-1 자리는 none 이다.
INTENT_EDITED = INTENT_AFTER_DONE
# 고치기 전(기준선) — FR-2 가 없고, FR-3 은 초 단위이고, E-1 이 있다.
INTENT_BEFORE_EDIT = {
    "- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1) [TSK-001 진행 중]\n": "",
    "처리 시간을 밀리초로 담는다. (D1) [TSK-001 진행 중]": "처리 시간을 초로 담는다. (D1)",
    " (FR-1) [TSK-001 삭제 예정]": " (FR-1)",
}
TASK_DRAFT = {"| 상태 | approved |": "| 상태 | draft |"}
INTENT_REL = "docs/Demo/INTENT/Demo-INT-001.md"
BASE_REL = ".process/intent-base/Demo-INT-001.md"


def feature_intent_text(**overrides: str) -> str:
    text = FEATURE_INTENT_CANONICAL
    for old, new in overrides.items():
        assert old in text, f"override target not found: {old!r}"
        text = text.replace(old, new)
    return text.replace("{app}", "Demo").replace("{nnn}", "001")


def write_intent_base(tmp_path: Path, **overrides: str) -> Path:
    """requirement-spec 수정 모드가 남기는 기준선 사본. 기본값은 고치기 전 Intent."""
    path = tmp_path / BASE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(feature_intent_text(**(overrides or INTENT_BEFORE_EDIT)), encoding="utf-8")
    return path


def scope_block(task_text: str) -> str:
    """Task Scope 의 항목 줄(이전 줄 포함)만 — 주석 · Out of scope 는 뺀다."""
    body = task_text.split("## Scope\n", 1)[1].split("\n\n", 1)[0]
    return "\n".join(line for line in body.split("\n") if line.startswith(("- ", "  - ")))


def run_dh(capsys, *argv: str) -> tuple[int, str, str]:
    rc = dh.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


class TestIntentBase:
    def test_save_copies_bytes_and_keeps_older_base(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path, **INTENT_BEFORE_EDIT)
        write_task(tmp_path, **{"| 상태 | approved |": "| 상태 | done |"})   # 한 번 잘라 개발한 Intent
        rc, out, _ = run_dh(capsys, "intent-base", "--repo", str(tmp_path), "--intent", "Demo-INT-001", "--save")
        assert (rc, out.strip()) == (0, f"SAVED {BASE_REL}")
        before = intent.read_bytes()
        assert (tmp_path / BASE_REL).read_bytes() == before
        # 자르기 전에 한 번 더 고쳐도 더 오래된 기준선을 지킨다 — 두 번의 고침이 모두 변경 목록에 나와야 한다.
        intent.write_text(feature_intent_text(**INTENT_EDITED), encoding="utf-8")
        rc, out, _ = run_dh(capsys, "intent-base", "--repo", str(tmp_path), "--intent", "Demo-INT-001", "--save")
        assert rc == 0 and out.startswith(f"KEPT {BASE_REL}")
        assert (tmp_path / BASE_REL).read_bytes() == before

    def test_never_cut_intent_gets_no_base(self, tmp_path, capsys):
        """한 번도 자르지 않은 Intent 는 항목 전부가 아직 코드에 없다 — 기준선을 남기면 고친 차이만 잘린다."""
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)   # 초안만 가리킨다 — 아직 자르지 않았다
        argv = ["intent-base", "--repo", str(tmp_path), "--intent", "Demo-INT-001", "--save"]
        rc, out, _ = run_dh(capsys, *argv)
        assert rc == 0 and out.startswith(f"NEW {BASE_REL}")
        assert not (tmp_path / BASE_REL).exists()
        rc, out, _ = run_dh(capsys, *argv, "--implemented")   # 옛 방식으로 이미 구현한 Intent
        assert (rc, out.strip()) == (0, f"SAVED {BASE_REL}")

    def test_drop_then_none(self, tmp_path, capsys):
        write_feature_intent(tmp_path)
        write_intent_base(tmp_path)
        argv = ["intent-base", "--repo", str(tmp_path), "--intent", "Demo-INT-001", "--drop"]
        assert run_dh(capsys, *argv)[:2] == (0, f"DROPPED {BASE_REL}\n")
        assert not (tmp_path / BASE_REL).exists()
        assert run_dh(capsys, *argv)[:2] == (0, f"NONE {BASE_REL}\n")

    def test_save_without_intent_exits_2(self, tmp_path, capsys):
        rc, _, err = run_dh(capsys, "intent-base", "--repo", str(tmp_path), "--intent", "Demo-INT-009", "--save")
        assert rc == 2 and "Intent 파일이 없다" in err
        assert not (tmp_path / ".process").exists()

    @pytest.mark.parametrize("cmd", [["intent-base", "--drop"], ["intent-base", "--save"], ["intent-diff"]])
    def test_path_like_intent_is_refused(self, tmp_path, capsys, cmd):
        """--intent 에 경로 조각이 오면 기준선 경로가 .process/intent-base/ 밖(여기서는 레포 루트의 victim.md)을 가리킨다."""
        victim = tmp_path / "victim.md"
        victim.write_text("지우면 안 된다\n", encoding="utf-8")
        rc, _, err = run_dh(capsys, cmd[0], "--repo", str(tmp_path), "--intent", "../../victim", *cmd[1:])
        assert rc == 2 and "'<App>-INT-<NNN>'" in err
        assert victim.read_text(encoding="utf-8") == "지우면 안 된다\n"


class TestIntentDiff:
    def _diff(self, tmp_path, capsys, *extra: str) -> tuple[int, str]:
        rc, out, _ = run_dh(capsys, "intent-diff", "--repo", str(tmp_path), "--intent", "Demo-INT-001", *extra)
        return rc, out

    def test_base_mode_lists_scope_lines_verbatim(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_intent_base(tmp_path)
        rc, out = self._diff(tmp_path, capsys)
        lines = out.strip().split("\n")
        assert rc == 0
        assert lines[0] == f"Demo-INT-001 · mode base · base {BASE_REL}"
        assert lines[-1] == "changes: 3"
        # 변경 목록의 줄이 곧 Task Scope 줄이다 — TASK_CANONICAL 의 Scope 와 글자 그대로 같다.
        assert "\n".join(lines[1:-1]) == scope_block(TASK_CANONICAL)

    def test_json_payload(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_intent_base(tmp_path)
        rc, out = self._diff(tmp_path, capsys, "--json")
        payload = json.loads(out)
        assert rc == 0
        assert set(payload) == {"intent", "path", "base", "mode", "open_questions", "changes", "next_ids"}
        assert payload["next_ids"] == {"D": 2, "C": 2, "FR": 4, "E": 2, "X": 2}
        assert (payload["path"], payload["base"], payload["mode"], payload["open_questions"]) == (
            INTENT_REL, BASE_REL, "base", True,
        )
        assert [(c["kind"], c["id"]) for c in payload["changes"]] == [("신규", "FR-2"), ("변경", "FR-3"), ("삭제", "E-1")]
        fr3 = payload["changes"][1]
        assert set(fr3) == {"kind", "id", "text", "prev", "scope_line", "prev_line", "locked_by"}
        assert fr3["prev"] == "업로드 응답에 처리 시간을 초로 담는다. (D1)"
        assert fr3["prev_line"] == "  - 이전: 업로드 응답에 처리 시간을 초로 담는다. (D1)"
        assert payload["changes"][2]["text"] == "같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1)"
        assert all(c["locked_by"] is None for c in payload["changes"])

    def test_marked_intent_keeps_the_same_changes(self, tmp_path, capsys):
        """mark-intent 뒤에도 변경 목록은 같다 — 다시 넣은 삭제 항목은 `삭제 예정` 표시로 삭제로 본다."""
        write_feature_intent(tmp_path)
        write_intent_base(tmp_path)
        rc, out = self._diff(tmp_path, capsys, "--json")
        changes = json.loads(out)["changes"]
        assert [(c["kind"], c["id"], c["locked_by"]) for c in changes] == [
            ("신규", "FR-2", "TSK-001"), ("변경", "FR-3", "TSK-001"), ("삭제", "E-1", "TSK-001"),
        ]
        rc, out = self._diff(tmp_path, capsys)
        assert "- 신규 · Demo-INT-001 FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)  (표시: TSK-001)" in out

    def test_other_task_marker_is_locked_by(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **{**INTENT_EDITED, "밀리초로 담는다. (D1)\n": "밀리초로 담는다. (D1) [TSK-007 진행 중]\n"})
        write_intent_base(tmp_path)
        rc, out = self._diff(tmp_path, capsys, "--json")
        locked = {c["id"]: c["locked_by"] for c in json.loads(out)["changes"]}
        assert locked == {"FR-2": None, "FR-3": "TSK-007", "E-1": None}

    def test_next_ids_count_deleted_numbers(self, tmp_path, capsys):
        """지운 번호도 다시 쓰지 않는다 — 기준선과 Task Scope 에만 남은 번호까지 센다."""
        write_feature_intent(tmp_path, **INTENT_EDITED)   # E-1 을 지웠다 — 지금 Intent 에는 E 가 없다
        write_intent_base(tmp_path)
        write_task(tmp_path, name="TSK-002", template=TASK_EDGE, **{
            "| 상태 | approved |": "| 상태 | done |", "Demo-INT-001 E-2": "Demo-INT-001 E-7",
        })
        rc, out = self._diff(tmp_path, capsys, "--json")
        assert json.loads(out)["next_ids"]["E"] == 8

    def test_other_task_pending_delete_is_not_a_change(self, tmp_path, capsys):
        """다른 Task 가 지우는 중인 항목(기준선에도 같은 표시)은 이번 고침의 변경이 아니다."""
        pending = {
            "- FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1) [TSK-001 진행 중]\n": "",
            "(FR-1) [TSK-001 삭제 예정]": "(FR-1) [TSK-009 삭제 예정]",
        }
        write_intent_base(tmp_path, **pending, **{"처리 시간을 밀리초로 담는다. (D1) [TSK-001 진행 중]": "처리 시간을 초로 담는다. (D1)"})
        write_feature_intent(tmp_path, **pending, **{"처리 시간을 밀리초로 담는다. (D1) [TSK-001 진행 중]": "처리 시간을 분으로 담는다. (D1)"})
        write_task(tmp_path, name="TSK-009")   # 아직 끝나지 않았다(approved)
        rc, out = self._diff(tmp_path, capsys, "--json")
        changes = json.loads(out)["changes"]
        assert [(c["kind"], c["id"], c["locked_by"]) for c in changes] == [("변경", "FR-3", None)]

    @pytest.mark.parametrize(
        ("status", "base", "current", "expected"),
        [
            # done 이 지운 `삭제 예정` 줄 — 이미 끝난 삭제다
            ("done", {" (D1) [TSK-001 진행 중]": " (D1)", "(FR-1) [TSK-001 삭제 예정]": "(FR-1) [TSK-009 삭제 예정]"},
             INTENT_EDITED, []),
            # dropped 가 되돌린 신규(FR-2 줄이 빠졌다) · 변경(FR-3 이 `이전` 문장으로)
            ("dropped", {" (D1) [TSK-001 진행 중]": " (D1) [TSK-009 진행 중]", " (FR-1) [TSK-001 삭제 예정]": " (FR-1)"},
             INTENT_BEFORE_EDIT, []),
            # done 뒤에 사용자가 고친 것은 변경이다 — 끝난 Task 는 잠그지 않는다
            ("done", {" (D1) [TSK-001 진행 중]": " (D1) [TSK-009 진행 중]", " (FR-1) [TSK-001 삭제 예정]": " (FR-1)"},
             {" (D1) [TSK-001 진행 중]": " (D1)", "밀리초로": "마이크로초로", " (FR-1) [TSK-001 삭제 예정]": " (FR-1)"},
             [("변경", "FR-3", None)]),
        ],
    )
    def test_finished_task_lifecycle_is_not_a_change(self, tmp_path, capsys, status, base, current, expected):
        write_intent_base(tmp_path, **base)
        write_feature_intent(tmp_path, **current)
        write_task(tmp_path, name="TSK-009", **{"| 상태 | approved |": f"| 상태 | {status} |"})
        rc, out = self._diff(tmp_path, capsys, "--json")
        changes = json.loads(out)["changes"]
        assert [(c["kind"], c["id"], c["locked_by"]) for c in changes] == expected

    def test_subheading_and_comments_follow_one_section_rule(self, tmp_path, capsys):
        """`####` 소제목은 섹션을 끝내지 않고, 주석 안의 항목은 항목이 아니다 — 변경 목록과 진행 표시가 같은 항목을 본다."""
        subheading = {"- FR-1.": "#### 저장\n- FR-1."}
        x1 = "- X-1. 빈 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)\n"
        write_intent_base(tmp_path, **INTENT_BEFORE_EDIT, **subheading)
        write_feature_intent(tmp_path, **INTENT_EDITED, **subheading, **{x1: "<!--\n" + x1 + "-->\nnone\n"})
        rc, out = self._diff(tmp_path, capsys, "--json")
        changes = [(c["kind"], c["id"]) for c in json.loads(out)["changes"]]
        assert changes == [("신규", "FR-2"), ("변경", "FR-3"), ("삭제", "E-1"), ("삭제", "X-1")]   # 주석으로 감싼 X-1 은 지운 것이다
        write_task(tmp_path, **TASK_DRAFT)
        rc, out, _ = run_dh(capsys, "mark-intent", "--repo", str(tmp_path), "--task", ".task/TSK-001.md")
        assert rc == 0, out   # 소제목 아래의 FR-2 · FR-3 도 같은 섹션이다
        assert "표시 3" in out

    def test_new_mode_lists_every_item_as_new(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **INTENT_EDITED)
        rc, out = self._diff(tmp_path, capsys, "--json")
        payload = json.loads(out)
        assert (payload["mode"], payload["base"]) == ("new", None)
        assert [(c["kind"], c["id"]) for c in payload["changes"]] == [
            ("신규", "FR-1"), ("신규", "FR-2"), ("신규", "FR-3"), ("신규", "X-1"),
        ]

    def test_draft_task_does_not_end_new_mode(self, tmp_path, capsys):
        """초안은 지금 자르는 중인 Task 다 — 초안을 쓴 뒤 다시 비교해도 새 Intent 는 여전히 전부 신규다."""
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._diff(tmp_path, capsys, "--json")
        assert json.loads(out)["mode"] == "new"

    @pytest.mark.parametrize("status", ["approved", "done", "dropped"])
    def test_cut_intent_without_base_has_no_changes(self, tmp_path, capsys, status):
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **{"| 상태 | approved |": f"| 상태 | {status} |"})
        rc, out = self._diff(tmp_path, capsys)
        assert rc == 0
        assert out.split("\n")[0] == "Demo-INT-001 · mode none"
        assert out.strip().split("\n")[-1] == "changes: 0"

    def test_open_questions_warn(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **{**INTENT_EDITED, "### Open questions\nnone": "### Open questions\n- 남은 질문"})
        write_intent_base(tmp_path)
        rc, out = self._diff(tmp_path, capsys)
        assert rc == 0
        assert "WARN OPEN_QUESTIONS" in out

    def test_missing_intent_exits_2(self, tmp_path, capsys):
        rc, _, err = run_dh(capsys, "intent-diff", "--repo", str(tmp_path), "--intent", "Demo-INT-009")
        assert rc == 2 and "Intent 파일이 없다: Demo-INT-009" in err


class TestWriteAll:
    def test_failed_temp_write_changes_nothing(self, tmp_path):
        """임시 파일을 쓰다 실패하면 원본은 하나도 바뀌지 않고 임시 파일도 남지 않는다."""
        a, b = tmp_path / "a.md", tmp_path / "gone" / "b.md"   # b 의 폴더가 없다 — 둘째 임시 파일을 못 만든다
        a.write_bytes(b"old a\r\n")
        with pytest.raises(OSError):
            dh._write_all([(a, "new a\r\n"), (b, "new b\n")])
        assert a.read_bytes() == b"old a\r\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md"]

    def test_failed_replace_keeps_rest_and_leaves_no_temp(self, tmp_path, monkeypatch):
        """바꿔 끼우다 멈추면(Windows 에서 다른 프로세스가 파일을 잡고 있을 때) 앞서 바꾼 파일만 새 본문이고
        나머지는 원본 그대로다. 남은 임시 파일은 지운다."""
        a, b = tmp_path / "a.md", tmp_path / "b.md"
        a.write_bytes(b"old a\n")
        b.write_bytes(b"old b\n")
        real, calls = dh.os.replace, []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise PermissionError(13, "다른 프로세스가 잡고 있다", str(dst))
            real(src, dst)

        monkeypatch.setattr(dh.os, "replace", flaky)
        with pytest.raises(PermissionError):
            dh._write_all([(a, "new a\n"), (b, "new b\n")])
        assert (a.read_bytes(), b.read_bytes()) == (b"new a\n", b"old b\n")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md", "b.md"]


class TestMarkIntent:
    def _mark(self, tmp_path, capsys, *extra: str, task: str = ".task/TSK-001.md") -> tuple[int, str]:
        rc, out, _ = run_dh(capsys, "mark-intent", "--repo", str(tmp_path), "--task", task, *extra)
        return rc, out

    def test_marks_and_reinserts_deleted_item(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._mark(tmp_path, capsys)
        assert (rc, out.strip()) == (0, f"MARKED {INTENT_REL} · 표시 3 · 다시 넣은 삭제 항목 1")
        # 고친 Intent 에 표시를 붙이면 자르기 뒤 모습(FEATURE_INTENT_CANONICAL)이 된다 — 지운 E-1 은 none 자리에 돌아온다.
        assert intent.read_text(encoding="utf-8") == feature_intent_text()

    def test_second_run_changes_nothing(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path)
        write_task(tmp_path, **TASK_DRAFT)
        before = intent.read_bytes()
        rc, out = self._mark(tmp_path, capsys)
        assert (rc, out.strip()) == (0, f"MARKED {INTENT_REL} · 표시 0 · 다시 넣은 삭제 항목 0")
        assert intent.read_bytes() == before

    def test_remove_restores_edited_intent(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path)
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._mark(tmp_path, capsys, "--remove")
        assert (rc, out.strip()) == (0, f"CLEARED {INTENT_REL} · 표시 2 · 삭제 줄 1")
        assert intent.read_text(encoding="utf-8") == feature_intent_text(**INTENT_EDITED)

    def test_json_payload(self, tmp_path, capsys):
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._mark(tmp_path, capsys, "--json")
        assert rc == 0
        assert json.loads(out) == {
            "task": "TSK-001", "remove": False,
            "intents": [{"intent": "Demo-INT-001", "path": INTENT_REL, "marked": ["FR-2", "FR-3", "E-1"], "inserted": ["E-1"],
                         "unmarked": []}],
            "missing": [],
        }

    def test_scope_change_unmarks_left_items_and_frees_them(self, tmp_path, capsys):
        """자르기를 고쳐 E-1 이 TSK-002 로 옮겨 가면 — TSK-001 을 다시 맞추면 표시와 다시 넣은 줄이 빠지고, TSK-002 가 가져간다."""
        intent = write_feature_intent(tmp_path)   # TSK-001 이 셋 다 표시한 상태
        write_task(tmp_path, **{**TASK_DRAFT, SCOPE_E1 + "\n": ""})
        rc, out = self._mark(tmp_path, capsys)
        assert (rc, out.strip()) == (0, f"MARKED {INTENT_REL} · 표시 0 · 다시 넣은 삭제 항목 0 · 걷어 낸 표시 1")
        assert "- E-1." not in intent.read_text(encoding="utf-8")
        write_task(tmp_path, name="TSK-002", **{**TASK_DRAFT, SCOPE_FR23 + "\n": ""})
        rc, out = self._mark(tmp_path, capsys, task=".task/TSK-002.md")
        assert (rc, out.strip()) == (0, f"MARKED {INTENT_REL} · 표시 1 · 다시 넣은 삭제 항목 1")
        assert "- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-002 삭제 예정]" in intent.read_text(encoding="utf-8")

    def test_non_utf8_intent_is_not_rewritten(self, tmp_path, capsys):
        """UTF-8 이 아닌 Intent(cp949 저장 등)는 고치지 않는다 — 바꿔 읽고 되쓰면 git 에 없는 유일한 사본이 깨진다."""
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        intent.write_bytes(intent.read_text(encoding="utf-8").encode("cp949", errors="replace"))
        write_task(tmp_path, **TASK_DRAFT)
        before = intent.read_bytes()
        for extra in ((), ("--remove",)):
            rc, out = self._mark(tmp_path, capsys, *extra)
            assert rc == 1, out
            assert "UTF-8 로 읽을 수 없다" in out
            assert intent.read_bytes() == before

    def test_write_failure_is_reported_and_rerun_finishes(self, tmp_path, capsys, monkeypatch):
        """바꿔 끼우다 멈추면 traceback 이 아니라 FAIL 로 끝난다. 다시 실행하면 깨끗이 실행한 것과 같아진다."""
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)
        before = intent.read_bytes()
        real = dh.os.replace

        def locked(src, dst):
            raise PermissionError(13, "다른 프로세스가 잡고 있다", str(dst))

        monkeypatch.setattr(dh.os, "replace", locked)
        rc, _, err = run_dh(capsys, "mark-intent", "--repo", str(tmp_path), "--task", ".task/TSK-001.md")
        assert rc == 2 and "쓰다가 멈췄다" in err and "다시 실행" in err, err
        assert intent.read_bytes() == before
        assert sorted(p.name for p in intent.parent.iterdir()) == [intent.name]

        monkeypatch.setattr(dh.os, "replace", real)
        rc, out = self._mark(tmp_path, capsys)
        assert rc == 0, out
        assert intent.read_text(encoding="utf-8") == feature_intent_text()

    def test_writes_leave_no_temp_files(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._mark(tmp_path, capsys)
        assert rc == 0, out
        assert sorted(p.name for p in intent.parent.iterdir()) == [intent.name]

    def test_remove_skips_missing_intent(self, tmp_path, capsys):
        """취소 정리는 Intent 가 없어도 막히지 않는다 — 걷어 낼 표시가 없을 뿐이다."""
        write_feature_intent(tmp_path)
        write_task(tmp_path, **{**TASK_DRAFT, "| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | Demo-INT-001 · Demo-INT-009 |"})
        rc, out = self._mark(tmp_path, capsys, "--remove")
        assert rc == 0, out
        assert f"CLEARED {INTENT_REL} · 표시 2 · 삭제 줄 1" in out and "SKIP Demo-INT-009" in out

    def test_crlf_without_trailing_newline(self, tmp_path, capsys):
        """CRLF 문서가 줄바꿈 없이 끝나고 마지막 줄이 그 섹션의 마지막 항목이면 — 넣은 줄도 CRLF, 파일 끝은 그대로."""
        intent = write_feature_intent(tmp_path)
        text = feature_intent_text(**INTENT_EDITED).replace("### Edge cases\nnone\n\n", "")
        text = text.rstrip("\n") + "\n\n### Edge cases\n- E-0. 영 (FR-1)"
        intent.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        write_task(tmp_path, **TASK_DRAFT)
        rc, _ = self._mark(tmp_path, capsys)
        raw = intent.read_bytes().decode("utf-8")
        assert rc == 0
        assert raw.endswith("- E-0. 영 (FR-1)\r\n- E-1. 같은 파일을 두 번 올리면 한 번만 저장된다. (FR-1) [TSK-001 삭제 예정]")
        rest = raw.replace("\r\n", "")
        assert "\n" not in rest and "\r" not in rest   # 홀로 남은 \n · \r 이 없다

    def test_crlf_is_kept(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path)
        intent.write_bytes(feature_intent_text(**INTENT_EDITED).replace("\n", "\r\n").encode("utf-8"))
        write_task(tmp_path, **TASK_DRAFT)
        rc, _ = self._mark(tmp_path, capsys)
        raw = intent.read_bytes().decode("utf-8")
        assert rc == 0
        assert raw == feature_intent_text().replace("\n", "\r\n")

    @pytest.mark.parametrize(
        ("intent", "problem"),
        [
            ({**INTENT_EDITED, "재시도 횟수를 담는다. (D1)\n": "재시도 횟수를 담는다. (D1) [TSK-002 진행 중]\n"},
             "Demo-INT-001 FR-2 에 다른 Task 의 표시 [TSK-002 진행 중] 가 있다"),
            (INTENT_BEFORE_EDIT, "Demo-INT-001 FR-2 가 Intent 에 없다"),
        ],
    )
    def test_problem_writes_nothing(self, tmp_path, capsys, intent, problem):
        path = write_feature_intent(tmp_path, **intent)
        write_task(tmp_path, **TASK_DRAFT)
        before = path.read_bytes()
        rc, out = self._mark(tmp_path, capsys)
        assert rc == 1
        assert f"FAIL MARK {problem}" in out
        assert path.read_bytes() == before   # 막힌 항목 말고 FR-3 · E-1 도 표시하지 않았다

    def test_missing_intent_fails(self, tmp_path, capsys):
        write_task(tmp_path, **TASK_DRAFT)
        rc, out = self._mark(tmp_path, capsys)
        assert rc == 1 and "FAIL MARK Demo-INT-001: Intent 파일이 없다" in out

    def test_preserve_items_get_no_marker(self, tmp_path, capsys):
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, name="TSK-003", template=TASK_REFACTOR)
        before = intent.read_bytes()
        rc, out = self._mark(tmp_path, capsys, task=".task/TSK-003.md")
        assert (rc, out.strip()) == (0, f"MARKED {INTENT_REL} · 표시 0 · 다시 넣은 삭제 항목 0")
        assert intent.read_bytes() == before

    @pytest.mark.parametrize(
        ("section", "expected"),
        [
            ("- E-3. 다 (FR-1)\n", "- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n- E-3. 다 (FR-1)\n"),            # 뒤 번호 앞
            ("- E-1. 가 (FR-1)\n- E-3. 다 (FR-1)\n",
             "- E-1. 가 (FR-1)\n- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n- E-3. 다 (FR-1)\n"),                 # 사이
            ("- E-1. 가 (FR-1)\n\n", "- E-1. 가 (FR-1)\n- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n\n"),        # 마지막 항목 뒤
            ("none\n", "- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n"),                                             # none 자리
            ("\n", "- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n\n"),                                               # 빈 섹션 — 헤딩 바로 뒤
            ("- E-2. 나 (FR-1)\n", "- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n"),                               # 아직 있으면 표시만
        ],
    )
    def test_deleted_item_position(self, section, expected):
        items = dh._parse_task("## Scope\n- 삭제 · Demo-INT-001 E-2. 나 (FR-1)\n").scope
        text = f"### Edge cases\n{section}### Error cases\nnone\n"
        new, marked, inserted, problems = dh.apply_task_marks(text, "TSK-001", items)
        assert (marked, problems) == (["E-2"], [])
        assert inserted == ([] if section.startswith("- E-2.") else ["E-2"])
        assert new == f"### Edge cases\n{expected}### Error cases\nnone\n"

    @pytest.mark.parametrize(("section", "item", "needle"), [
        # 다른 Task 의 표시 뒤에 주석 — 줄 끝 기준으로만 보면 잠금을 지나쳐 표시가 둘이 된다
        ("- E-2. 나 (FR-1) [TSK-002 진행 중] <!-- 메모 -->\n", "- 신규 · Demo-INT-001 E-2. 나 (FR-1)", "HTML 주석"),
        # 주석 안의 표시 모양 — 주석 안을 고치고 붙였다고 보고하면 안 된다
        ("- E-2. 나 (FR-1) <!-- 옛 [TSK-001 삭제 예정] -->\n", "- 신규 · Demo-INT-001 E-2. 나 (FR-1)", "HTML 주석"),
        # 같은 ID 가 둘 — 첫 줄에만 붙이면 둘째 줄이 표시 없이 남는다
        ("- E-2. 나 (FR-1)\n- E-2. 나 (FR-1)\n", "- 신규 · Demo-INT-001 E-2. 나 (FR-1)", "2번 있다"),
        # 마지막 항목 줄이 여는 주석 — 그 뒤에 넣으면 보이지 않는 줄이 된다
        ("- E-1. 가 (FR-1) <!-- 여러 줄\n주석 -->\n", "- 삭제 · Demo-INT-001 E-2. 나 (FR-1)", "주석 안"),
        # 주석이 붙은 none — 바꿔 끼우면 주석이 사라진다
        ("none <!-- 메모 -->\n", "- 삭제 · Demo-INT-001 E-2. 나 (FR-1)", "`none` 줄"),
    ])
    def test_unsafe_lines_are_problems_and_untouched(self, section, item, needle):
        items = dh._parse_task(f"## Scope\n{item}\n").scope
        text = f"### Edge cases\n{section}### Error cases\nnone\n"
        new, marked, inserted, problems = dh.apply_task_marks(text, "TSK-001", items)
        assert new == text
        assert (marked, inserted) == ([], [])
        assert len(problems) == 1 and needle in problems[0], problems

    def test_reinsert_keeps_continuation_lines_together(self):
        """마지막 항목에 딸린 들여 쓴 줄을 가르지 않는다 — 다시 넣은 줄은 그 뒤에 온다."""
        items = dh._parse_task("## Scope\n- 삭제 · Demo-INT-001 E-2. 나 (FR-1)\n").scope
        text = "### Edge cases\n- E-1. 가 (FR-1)\n  이어지는 설명\n\n### Error cases\nnone\n"
        new, _, inserted, problems = dh.apply_task_marks(text, "TSK-001", items)
        assert (inserted, problems) == (["E-2"], [])
        assert new == ("### Edge cases\n- E-1. 가 (FR-1)\n  이어지는 설명\n- E-2. 나 (FR-1) [TSK-001 삭제 예정]\n\n"
                       "### Error cases\nnone\n")


class TestClearTaskMarks:
    def test_keeps_other_tasks_and_crlf(self):
        text = (
            "### Functional requirements\r\n"
            "- FR-1. 가 (D1) [TSK-001 진행 중]\r\n"
            "- FR-2. 나 (D1) [TSK-002 진행 중]\r\n"
            "- FR-3. 다 (D1) [TSK-001 삭제 예정]\r\n"
            "\r\n"
            "### Edge cases\r\n"
            "- E-1. 라 (FR-1) [TSK-001 삭제 예정]\r\n"
            "\r\n"
            "### Error cases\r\n"
            "- X-1. 마 (FR-1) [TSK-002 삭제 예정]\r\n"
        )

        new, cleared, deleted, problems = dh.clear_task_marks(text, "TSK-001")

        assert (cleared, deleted, problems) == (["FR-1"], ["FR-3", "E-1"], [])
        assert new == (
            "### Functional requirements\r\n"
            "- FR-1. 가 (D1)\r\n"
            "- FR-2. 나 (D1) [TSK-002 진행 중]\r\n"
            "\r\n"
            "### Edge cases\r\n"
            "none\r\n"
            "\r\n"
            "### Error cases\r\n"
            "- X-1. 마 (FR-1) [TSK-002 삭제 예정]\r\n"
        )

    def test_ignores_headings_inside_comments(self):
        """주석 안의 `###` 은 헤딩이 아니다 — 섹션 경계로 보면 남은 항목이 있는데도 none 을 끼워 넣는다."""
        text = (
            "### Edge cases\n"
            "- E-1. 가 (FR-1) [TSK-001 삭제 예정]\n"
            "<!--\n"
            "### 예시\n"
            "-->\n"
            "- E-2. 나 (FR-1)\n"
        )

        new, cleared, deleted, problems = dh.clear_task_marks(text, "TSK-001")

        assert (cleared, deleted, problems) == ([], ["E-1"], [])
        assert new == "### Edge cases\n<!--\n### 예시\n-->\n- E-2. 나 (FR-1)\n"

    @pytest.mark.parametrize("line", [
        "- X-1. 가 (FR-1) [TSK-001 삭제 예정] <!-- 메모 -->",
        "- X-1. 가 (FR-1) [TSK-001 진행 중] <!-- 여러 줄\n이어지는 주석 -->",
        "<!-- 앞 주석\n-->- X-1. 가 (FR-1) [TSK-001 삭제 예정]",
    ])
    def test_marked_line_with_comment_is_left_alone(self, line):
        """표시 줄에 주석이 섞여 있으면 고치지 않는다 — 줄째 지우면 주석 여닫이가 깨져 뒤 본문이 숨거나 드러난다."""
        text = f"### Error cases\n{line}\n- X-2. 나 (FR-1)\n"

        new, cleared, deleted, problems = dh.clear_task_marks(text, "TSK-001")

        assert new == text
        assert (cleared, deleted) == ([], [])
        assert len(problems) == 1 and "HTML 주석" in problems[0] and problems[0].startswith("X-1")

    def test_roundtrip_crlf_without_final_newline(self):
        """줄바꿈 없이 끝난 CRLF 파일 — 끝에 다시 넣은 삭제 줄을 지우면 원래 바이트로 돌아온다(끝에 \\r 이 남지 않는다)."""
        text = "### Error cases\r\n- X-1. 가 (FR-1)"
        items = dh._parse_task("## Scope\n- 삭제 · Demo-INT-001 X-2. 나 (FR-1)\n").scope

        marked_text, _, inserted, problems = dh.apply_task_marks(text, "TSK-001", items)
        assert (inserted, problems) == (["X-2"], [])
        assert marked_text == "### Error cases\r\n- X-1. 가 (FR-1)\r\n- X-2. 나 (FR-1) [TSK-001 삭제 예정]"

        new, _, deleted, problems = dh.clear_task_marks(marked_text, "TSK-001")
        assert (deleted, problems) == (["X-2"], [])
        assert new == text


# 새 Intent(한 번도 자르지 않음)를 Task 하나에 전부 신규로 담는다.
TASK_ALL_NEW = {
    **TASK_DRAFT,
    scope_block(TASK_CANONICAL): "\n".join([
        "- 신규 · Demo-INT-001 FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)",
        "- 신규 · Demo-INT-001 FR-2. 업로드 응답에 응답 필드 `retryCount` 로 재시도 횟수를 담는다. (D1)",
        "- 신규 · Demo-INT-001 FR-3. 업로드 응답에 처리 시간을 밀리초로 담는다. (D1)",
        "- 신규 · Demo-INT-001 X-1. 빈 파일은 상태 코드 `400` 과 오류 코드 `UPLOAD_EMPTY_FILE` 로 거부한다. (FR-1)",
    ]),
}
SCOPE_FR23 = "\n".join(scope_block(TASK_CANONICAL).split("\n")[:3])
SCOPE_E1 = scope_block(TASK_CANONICAL).split("\n")[3]


class TestSplitCheck:
    def _split(self, tmp_path, capsys, *names: str) -> tuple[int, str]:
        argv = ["split-check", "--repo", str(tmp_path)]
        for name in names:
            argv += ["--task", f".task/{name}.md"]
        rc, out, _ = run_dh(capsys, *argv)
        return rc, out

    def _cut(self, tmp_path, intent: dict | None = None, **task: str) -> None:
        """기준선 + 자른 뒤 Intent + 초안 TSK-001."""
        write_intent_base(tmp_path)
        write_feature_intent(tmp_path, **(intent or {}))
        write_task(tmp_path, **{**TASK_DRAFT, **task})

    def test_one_task_covers_every_change(self, tmp_path, capsys):
        self._cut(tmp_path)
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 0, out
        assert "PASS SPLIT_COVERAGE 바뀐 항목 3개를 Task 1개가 한 번씩 나눴다" in out

    def test_two_tasks_share_the_changes(self, tmp_path, capsys):
        self._cut(tmp_path, **{SCOPE_E1 + "\n": ""})
        write_task(tmp_path, name="TSK-002", **{**TASK_DRAFT, SCOPE_FR23 + "\n": ""})
        rc, out = self._split(tmp_path, capsys, "TSK-001", "TSK-002")
        assert rc == 0, out
        assert "바뀐 항목 3개를 Task 2개가" in out

    @pytest.mark.parametrize(
        ("task", "code", "detail"),
        [
            ({SCOPE_E1 + "\n": ""}, "SPLIT_UNASSIGNED", "Demo-INT-001 E-1 (삭제) 가 어느 Task 에도 없다"),
            ({"- 신규 · Demo-INT-001 FR-2.": "- 변경 · Demo-INT-001 FR-2."}, "SPLIT_KIND", "변경 목록은 신규, TSK-001 는 변경"),
            ({"재시도 횟수를 담는다. (D1)\n- 변경": "재시도 횟수를 넣는다. (D1)\n- 변경"}, "SPLIT_TEXT", "Demo-INT-001 FR-2"),
            ({"  - 이전: 업로드 응답에 처리 시간을 초로": "  - 이전: 업로드 응답에 처리 시간을 분으로"}, "SPLIT_PREV", "Demo-INT-001 FR-3"),
            ({SCOPE_E1: SCOPE_E1 + "\n- 변경 · Demo-INT-001 FR-1. 업로드는 파일 하나를 받아 저장한다. (D1)"},
             "SPLIT_EXTRA", "Demo-INT-001 FR-1: TSK-001 Scope 의 변경 항목이지만 바뀐 항목이 아니다"),
            ({"| 대상 Intent | Demo-INT-001 |": "| 대상 Intent | Demo-INT-001 · Demo-INT-009 |"}, "SPLIT_INTENT",
             "Demo-INT-009: Intent 파일이 없다"),
        ],
    )
    def test_break_one_fails(self, tmp_path, capsys, task, code, detail):
        self._cut(tmp_path, **task)
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 1
        assert f"FAIL {code}" in out and detail in out
        assert "SPLIT_COVERAGE" not in out

    def test_same_item_in_two_tasks_fails(self, tmp_path, capsys):
        self._cut(tmp_path)
        write_task(tmp_path, name="TSK-002", **{**TASK_DRAFT, SCOPE_FR23 + "\n": ""})
        rc, out = self._split(tmp_path, capsys, "TSK-001", "TSK-002")
        assert rc == 1
        assert "FAIL SPLIT_DUP Demo-INT-001 E-1 가 여러 Task 에 있다: TSK-001 · TSK-002" in out

    def test_item_locked_by_another_task_fails(self, tmp_path, capsys):
        self._cut(tmp_path, intent={"밀리초로 담는다. (D1) [TSK-001 진행 중]": "밀리초로 담는다. (D1) [TSK-007 진행 중]"})
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 1
        assert "FAIL SPLIT_LOCKED Demo-INT-001 FR-3: TSK-007 가 이미 바꾸는 중" in out

    def test_size_warn_does_not_fail(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(dh, "SPLIT_MAX_FR", 1)
        self._cut(tmp_path)
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 0, out
        assert "WARN SPLIT_SIZE" in out and "TSK-001: Scope 3 · FR 2" in out

    def test_new_intent_cut_into_draft_passes(self, tmp_path, capsys):
        """새 Intent 를 초안으로 자른 직후 — 초안이 Intent 를 가리켜도 변경 목록은 여전히 전부 신규다."""
        write_feature_intent(tmp_path, **INTENT_EDITED)
        write_task(tmp_path, **TASK_ALL_NEW)
        assert run_dh(capsys, "mark-intent", "--repo", str(tmp_path), "--task", ".task/TSK-001.md")[0] == 0
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 0, out
        assert "바뀐 항목 4개를 Task 1개가" in out

    def test_task_split_flow_end_to_end(self, tmp_path, capsys):
        """기준선 → 변경 목록 → Task(초안) → 진행 표시 → check-task · split-check → 승인 → 기준선 소비."""
        intent = write_feature_intent(tmp_path, **INTENT_EDITED)
        write_intent_base(tmp_path)
        repo = str(tmp_path)
        rc, out, _ = run_dh(capsys, "intent-diff", "--repo", repo, "--intent", "Demo-INT-001", "--json")
        lines = []
        for ch in json.loads(out)["changes"]:
            lines += [ch["scope_line"]] + ([ch["prev_line"]] if ch["prev_line"] else [])
        assert "\n".join(lines) == scope_block(TASK_CANONICAL)   # Scope 는 변경 목록을 그대로 옮긴다
        task = write_task(tmp_path, **TASK_DRAFT)
        assert run_dh(capsys, "mark-intent", "--repo", repo, "--task", ".task/TSK-001.md")[0] == 0
        assert intent.read_text(encoding="utf-8") == feature_intent_text()
        rc, out, _ = run_dh(capsys, "check-task", "--repo", repo, "--file", ".task/TSK-001.md")
        assert rc == 0, out
        rc, out = self._split(tmp_path, capsys, "TSK-001")
        assert rc == 0, out
        task.write_text(task.read_text(encoding="utf-8").replace("| 상태 | draft |", "| 상태 | approved |"), encoding="utf-8")
        rc, out, _ = run_dh(capsys, "check-task", "--repo", repo, "--file", ".task/TSK-001.md")
        assert rc == 0 and "PASS TSK_APPROVED_GATE" in out, out
        assert run_dh(capsys, "intent-base", "--repo", repo, "--intent", "Demo-INT-001", "--drop")[:2] == (0, f"DROPPED {BASE_REL}\n")
        rc, out, _ = run_dh(capsys, "intent-diff", "--repo", repo, "--intent", "Demo-INT-001", "--json")
        assert (json.loads(out)["mode"], json.loads(out)["changes"]) == ("none", [])
