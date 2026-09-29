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
| 유형 | 기능개발 |
| 상태 | draft |
| 작성 | tester · 2026-09-15 |
| 승인 | pending |
| 관련 Intent | none |
| 검증 | pending |

## Part 1 — 기능 명세

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

## Part 2 — 작업 지시

### Functional requirements
- FR-1. 요구 문장 (D1)

### Edge cases
- E-1. a → b (FR-1)

### Error cases
- X-1. a → b (FR-1)

### Acceptance
- [ ] A-1. 완료 조건 (FR-1)

### Verification
- 확인 방법

### Risks
- 리스크

### Handoff
| 항목 | 값 |
|---|---|
| repo · app | pending |
| base branch | main |
| 브랜치명 | intent/{app}-INT-{nnn} |
| 손대지 말 영역 | pending |
| 완료 보고 방식 | pending |
"""


APPROVED_CLEAN = {
    "| 상태 | draft |": "| 상태 | approved |",
    "| 검증 | pending |": "| 검증 | PASS — code PASS · llm PASS · 1/3 |",
    "| repo · app | pending |": "| repo · app | qwer · GugudanApi |",
    "| 손대지 말 영역 | pending |": "| 손대지 말 영역 | docs/GugudanApi |",
    "| 완료 보고 방식 | pending |": "| 완료 보고 방식 | 보고 |",
}


INTENT_RICH = """# {app}-INT-{nnn} — 리치 샘플 Intent

| 항목 | 값 |
|---|---|
| 문서 ID | {app}-INT-{nnn} |
| 유형 | 기능개발 |
| 상태 | draft |
| 작성 | tester · 2026-09-15 |
| 승인 | pending |
| 관련 Intent | none |
| 검증 | pending |

## Part 1 — 기능 명세

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

## Part 2 — 작업 지시

### Functional requirements
- FR-1. 요구 문장 1 (D1)
- FR-2. 요구 문장 2 (D1, C2)
- FR-3. 요구 문장 3

### Edge cases
- E-1. 상황 1 → 기대 1 (FR-1)
- E-2. a | b → c (FR-2)

### Error cases
- X-1. 상황 → 기대 (FR-1)

### Acceptance
- [ ] A-1. 완료 조건 1 (FR-1)
- [ ] A-2. 완료 조건 2 (FR-2)
- [ ] A-3. 제외 확인 (OS)

### Verification
- 확인 방법 1
- 확인 방법 2

### Risks
- 리스크

### Handoff
| 항목 | 값 |
|---|---|
| repo · app | pending |
| base branch | main |
| 브랜치명 | intent/{app}-INT-{nnn} |
| 손대지 말 영역 | pending |
| 완료 보고 방식 | pending |
"""


def write_intent(
    tmp_path: Path,
    app: str = "Demo",
    nnn: str = "001",
    template: str = INTENT_CANONICAL,
    **overrides: str,
) -> Path:
    """정상 3.60 포맷 Intent 문서를 작성한다. overrides 는 str.replace 쌍."""
    text = template
    for old, new in overrides.items():
        text = text.replace(old, new)
    text = text.replace("{app}", app).replace("{nnn}", nnn)
    path = tmp_path / "docs" / app / "INTENT" / f"{app}-INT-{nnn}.md"
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
        assert rc == 0
        assert "0 FAIL" in out

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
            ({"| 유형 | 기능개발 |\n": ""}, "INT_META_ROWS"),
            ({"| 유형 | 기능개발 |": "| 유형 | 기능개발 \\| 리팩토링 |"}, "INT_TYPE_SINGLE"),
            ({"| 상태 | draft |": "| 상태 | 초안 |"}, "INT_STATUS"),
            ({"| 작성 | tester · 2026-09-15 |": "| 작성 | tester 2026-09-15 |"}, "INT_AUTHOR_FORMAT"),
            ({"| 승인 | pending |": "| 승인 | 대기 |"}, "INT_APPROVAL_FORMAT"),
            ({"### Affected\n영향 설명.\n\n": ""}, "INT_PART1_HEADINGS"),
            ({"### Risks\n- 리스크\n\n": ""}, "INT_PART2_HEADINGS"),
            ({"- Out of scope: 항목A, 항목B": "- Out of scope:"}, "INT_OUT_OF_SCOPE"),
            ({"### Open questions\nnone": "### Open questions\n"}, "INT_OPEN_QUESTIONS"),
            ({"| base branch | main |\n": ""}, "INT_HANDOFF_ROWS"),
            ({"intent/{app}-INT-{nnn}": "intent/{App}-INT-{NNN}"}, "INT_BRANCH_PLACEHOLDER"),
            ({"결과 설명.": "{결과} 결과 설명."}, "INT_PLACEHOLDER"),
            ({"| 검증 | pending |": "| 검증 | code PASS |"}, "INT_GATE_ROW_FORMAT"),
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
            ({"### Acceptance\n- [ ] A-1. 완료 조건 (FR-1)": "### Acceptance\nnone"}, "INT_ID_ORDER"),
            ({"| 유형 | 기능개발 |": "| 유형 | 리팩토링 |"}, "INT_ACCEPTANCE_TYPE"),
            ({"- [ ] A-1. 완료 조건 (FR-1)": "- [ ] A-1. 완료 조건 (FR-9)"}, "INT_REF_DANGLING"),
            (
                {**APPROVED_CLEAN, "### Open questions\nnone": "### Open questions\n미해결 질문"},
                "INT_APPROVED_GATE",
            ),
            (
                {**APPROVED_CLEAN, "| 손대지 말 영역 | pending |": "| 손대지 말 영역 | pending |"},
                "INT_APPROVED_GATE",
            ),
            ({**APPROVED_CLEAN, "| 검증 | pending |": "| 검증 | pending |"}, "INT_APPROVED_GATE"),
            (
                {**APPROVED_CLEAN, "| 검증 | pending |": "| 검증 | FAIL — code FAIL · llm PASS · 1/3 |"},
                "INT_APPROVED_GATE",
            ),
        ],
    )
    def test_break_one_fails(self, tmp_path, capsys, overrides, code):
        path = write_intent(tmp_path, **overrides)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert f"FAIL {code}" in out

    def test_legacy_six_meta_rows_warns(self, tmp_path, capsys):
        path = write_intent(tmp_path, **{"| 검증 | pending |\n": ""})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "INT_META_LEGACY" in out
        assert "0 FAIL" in out

    def test_backtick_braces_not_flagged(self, tmp_path, capsys):
        path = write_intent(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL INT_PLACEHOLDER" not in out


    def test_fr_number_gap_allowed(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{
                "- FR-1. 요구 문장 (D1)": "- FR-1. 요구 문장 (D1)\n- FR-3. 요구 문장 2 (D1)",
                "- [ ] A-1. 완료 조건 (FR-1)": "- [ ] A-1. 완료 조건 (FR-1, FR-3)",
            },
        )
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

    def test_approved_gate_conditions_met(self, tmp_path, capsys):
        path = write_intent(tmp_path, **APPROVED_CLEAN)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "PASS INT_APPROVED_GATE" in out

    def test_approved_gate_skipped_pre_360(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{**APPROVED_CLEAN, "| 검증 | pending |": "| 검증 | SKIPPED — pre-3.60 |"},
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "PASS INT_GATE_ROW_FORMAT" in out
        assert "PASS INT_APPROVED_GATE" in out

    def test_legacy_approved_with_pending_handoff_skips_gate(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{"| 검증 | pending |\n": "", "| 상태 | draft |": "| 상태 | approved |"},
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "INT_META_LEGACY" in out
        assert "INT_APPROVED_GATE" not in out

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

    def test_verify_command_span_warns_only(self, tmp_path, capsys):
        path = write_intent(tmp_path, **{"- 확인 방법": "- 확인 방법: `pytest -q`"})
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out
        assert "WARN INT_VERIFY_COMMAND" in out

    def test_acceptance_refs_decision_and_out_of_scope_resolve(self, tmp_path, capsys):
        path = write_intent(
            tmp_path,
            **{"- [ ] A-1. 완료 조건 (FR-1)": "- [ ] A-1. 완료 조건 (D1, OS)"},
        )
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "FAIL INT_REF_DANGLING" not in out

    @pytest.mark.parametrize(
        ("overrides", "condition"),
        [
            (
                {**APPROVED_CLEAN, "### Open questions\nnone": "### Open questions\n미해결 질문"},
                "Open questions != none",
            ),
            (
                {**APPROVED_CLEAN, "| 손대지 말 영역 | pending |": "| 손대지 말 영역 | pending |"},
                "Handoff pending",
            ),
            (
                {**APPROVED_CLEAN, "| 유형 | 기능개발 |": "| 유형 | 기능개발 \\| 리팩토링 |"},
                "유형 not single",
            ),
            (
                {**APPROVED_CLEAN, "| 검증 | pending |": "| 검증 | pending |"},
                "검증 not PASS/OVERRIDE/SKIPPED",
            ),
        ],
    )
    def test_approved_gate_condition_messages(self, tmp_path, capsys, overrides, condition):
        path = write_intent(tmp_path, **overrides)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL INT_APPROVED_GATE" in out
        assert condition in out


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
            "A": 1,
        }
        assert doc.items["FR"][0].refs == ["D1"]
        assert doc.items["FR"][0].text == "요구 문장"
        assert doc.items["A"][0].checked is True
        assert doc.items["E"][0].text == "a → b"
        assert "(FR-1)" not in doc.items["E"][0].text

    def test_out_of_scope_parenthesis_split(self):
        doc = dh._parse_intent(
            "### Outcome\n- Out of scope: Docker·compose, DB(추상화만, 구현 제외), 배포\n"
        )
        assert [item.text for item in doc.items["OS"]] == [
            "Docker·compose",
            "DB(추상화만, 구현 제외)",
            "배포",
        ]

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
        assert len(rows) == 21
        assert [r.kind for r in rows] == (
            ["OS"] * 3 + ["C"] * 2 + ["D"] * 2 + ["FR"] * 3 + ["E"] * 2 + ["X"] + ["A"] * 3 + ["G"] * 5
        )
        by_id = {r.id: r for r in rows}
        assert by_id["FR-2"].facts == "근거: D1, C2 · 참조하는 E/X/A: E-2, A-2"
        assert by_id["D1"].facts == "참조: FR-1, FR-2"
        assert by_id["D2"].facts == "참조: 없음"
        assert by_id["OS1"].facts == "참조 A: A-3"
        assert by_id["OS2"].facts == "참조 A: A-3"
        assert by_id["OS2"].target == "DB(추상화만, 구현 제외)"
        assert by_id["FR-3"].facts == "근거: 없음 · 참조하는 E/X/A: 없음"
        assert by_id["D1"].na_allowed is True
        assert by_id["FR-1"].na_allowed is False
        assert by_id["FR-1"].criteria[1].severity == "MINOR"
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
        assert len(table_rows) == 21
        assert '"a \\| b → c"' in out
        assert out.count("[인용]") == 5
        assert any(line.startswith("rows: 21 · quote: ") for line in out.split("\n"))

    def test_json_output(self, tmp_path, capsys):
        payload = self._payload(tmp_path, capsys)
        assert payload["intent"] == "Demo-INT-001"
        assert payload["round"] == 1
        assert len(payload["rows"]) == 21
        assert set(payload["rows"][0]) == {
            "id", "kind", "target", "facts", "criteria", "na_allowed", "quote_required", "line",
        }
        assert set(payload["rows"][0]["criteria"][0]) == {"key", "text", "severity"}
        assert len(payload["quote_rows"]) == 5
        assert payload["traceability"] == {
            "fr": 3,
            "fr_with_ref": 2,
            "a": 3,
            "a_with_ref": 3,
            "ex": 3,
            "ex_with_ref": 3,
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
            tmp_path, capsys, drop_pass=("FR-1",), na_entries=(("FR-1:a", "Handoff"),)
        )
        assert rc == 1
        assert "NA-NOT-ALLOWED: FR-1:a" in out

    def test_check_return_na_no_location(self, tmp_path, capsys):
        rc, out = self._check(tmp_path, capsys, drop_pass=("D1",), na_entries=(("D1:a", "그냥"),))
        assert rc == 1
        assert "NA-NO-LOCATION: D1:a" in out

    def test_check_return_na_with_location_accepted(self, tmp_path, capsys):
        rc, out = self._check(
            tmp_path, capsys, drop_pass=("D1",), na_entries=(("D1:a", "Handoff 완료 보고 방식"),)
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
        for eid in ("EXP-4", "EXP-5", "EXP-6"):
            assert [(c["key"], c["severity"]) for c in by_id[eid]["criteria"]] == [("a", "MAJOR")]
        assert [(c["key"], c["severity"]) for c in by_id["EXP-7"]["criteria"]] == [("a", "MINOR")]
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
            tmp_path, capsys, drop_pass=("EXP-1",), na_entries=(("EXP-1:a", "Handoff"),)
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
            "FR-1", "FR-2", "FR-3", "E-1", "E-2", "X-1",
            "A-1", "A-2", "A-3", "G-1", "G-2", "G-3", "G-4", "G-5",
        ]


# ---------------------------------------------------------------------------
# intent-catalog — 파생 인덱스 docs/<App>/<App>-INT-CATALOG.md
# ---------------------------------------------------------------------------


CATALOG_HEADER = "| Intent | 제목 | 유형 | 상태 | 검증 | 요약 | 규모 |"
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
        assert "| draft |" in text
        catalog_path(tmp_path).write_text(
            text.replace("| draft |", "| approved |"), encoding="utf-8"
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
            "| [Demo-INT-009](INTENT/Demo-INT-009.md) | 유령 | 기능개발 | draft | "
            "pending | ? | FR 0 · A 0 |"
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
            text.replace("| draft |", "| approved |"), encoding="utf-8"
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
            "id", "file", "title", "type", "status", "gate", "summary", "fr", "a",
        }
        assert payload["intents"][0]["id"] == "Demo-INT-001"
        assert payload["intents"][0]["file"] == "INTENT/Demo-INT-001.md"
        assert payload["intents"][0]["fr"] == 1
        assert payload["intents"][0]["a"] == 1
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
        assert catalog_cells(out)[6] == "FR 3 · A 3"

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

    @pytest.mark.parametrize(
        ("gate_value", "expected"),
        [
            ("PASS — code PASS · llm PASS · 2/3", "PASS 2/3"),
            ("FAIL — code FAIL · llm PASS · 1/3", "FAIL 1/3"),
            ("OVERRIDE — code FAIL · 사람 승인 · 3/3", "OVERRIDE 3/3"),
            ("SKIPPED — --no-gate", "SKIPPED — --no-gate"),
            ("SKIPPED — pre-3.60", "SKIPPED — pre-3.60"),
            ("pending", "pending"),
        ],
    )
    def test_gate_cell_abbreviation(self, tmp_path, capsys, gate_value, expected):
        write_intent(tmp_path, **{"| 검증 | pending |": f"| 검증 | {gate_value} |"})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert catalog_cells(out)[4] == expected

    def test_gate_skipped_keeps_leading_double_dash(self, tmp_path, capsys):
        """회귀: `SKIPPED — --no-gate` 의 앞 `--` 가 깎여 `-no-gate` 가 되면 안 된다."""
        write_intent(tmp_path, **{"| 검증 | pending |": "| 검증 | SKIPPED — --no-gate |"})
        rc = self._run(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        cell = catalog_cells(out)[4]
        assert cell.endswith("--no-gate")
        assert "— -no-gate" not in cell

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
        assert cells[1:6] == ["?"] * 5
        assert cells[6] == "FR 0 · A 0"
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
        assert cells[2:6] == ["?"] * 4
        assert cells[6] == "FR 0 · A 0"


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
            path.read_text(encoding="utf-8").replace("| draft |", "| approved |"),
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
        _, lines = self._lines(tmp_path, capsys)
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
