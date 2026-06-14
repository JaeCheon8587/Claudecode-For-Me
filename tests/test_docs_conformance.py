"""
docs_conformance.py 단위 테스트.

실행:
    pytest tests/test_docs_conformance.py -v
"""

import sys
from pathlib import Path

import pytest

# scripts/ 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import docs_conformance as ddc


# ─── TestBuildPrompt ──────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_reference_target_내용_포함(self, tmp_path):
        ref = tmp_path / "req.md"
        d1 = tmp_path / "FRD-007.md"
        prompt = ddc.build_prompt(
            (ref, "# Req\n운영자는 status 로 필터링한다"),
            [(d1, "# FRD\nstatus 필터 §8")],
        )
        assert "운영자는 status 로 필터링한다" in prompt
        assert "status 필터 §8" in prompt
        assert "## 대상:" in prompt
        assert "FRD-007.md" in prompt

    def test_출력_템플릿_키워드_강제(self, tmp_path):
        ref = tmp_path / "req.md"
        prompt = ddc.build_prompt((ref, "요구 본문"), [(tmp_path / "t.md", "대상 본문")])
        for kw in (
            "# 요구사항 정합 검증:",
            "## 요구 반영 표",
            "## 부족 항목",
            "CONFORMANCE RUBRIC",
            "Conformance: <integer 0-100>%",
            "requirements-conformance auditor",
        ):
            assert kw in prompt, f"키워드 누락: {kw!r}"

    def test_reference_stem_헤더(self, tmp_path):
        ref = tmp_path / "req-XLAB-TASK-003.md"
        prompt = ddc.build_prompt((ref, "x"), [(tmp_path / "t.md", "y")])
        assert "# 요구사항 정합 검증: req-XLAB-TASK-003" in prompt


# ─── TestExtractConformance ───────────────────────────────────────────────────

class TestExtractConformance:
    def test_정상_추출(self):
        assert ddc.extract_conformance("blah\nConformance: 87%\n") == 87

    def test_마지막_매치_사용(self):
        out = "Conformance: 40%\n중간\nConformance: 95%"
        assert ddc.extract_conformance(out) == 95

    def test_범위밖_None(self):
        assert ddc.extract_conformance("Conformance: 101%") is None

    def test_누락_None(self):
        assert ddc.extract_conformance("리포트에 점수 없음") is None


# ─── TestValidateOutput ───────────────────────────────────────────────────────

VALID = (
    "# 요구사항 정합 검증: req-x\n\n"
    "## 요약\n- 요구 항목 2개\n\n"
    "## Conformance\n"
    "Counts: ✓ 1, ⚠ 1, ✗ 0 (총 2)\n"
    "Conformance: 75%"
)


class TestValidateOutput:
    def test_정상(self):
        ok, errors, pct = ddc.validate_output(VALID)
        assert ok, errors
        assert pct == 75

    def test_헤더_누락(self):
        bad = VALID.replace("# 요구사항 정합 검증: req-x\n\n", "")
        ok, errors, _ = ddc.validate_output(bad)
        assert not ok
        assert any("헤더" in e for e in errors)

    def test_conformance_마지막라인_누락(self):
        bad = VALID + "\n\n뒤에 후문이 붙음"
        ok, errors, pct = ddc.validate_output(bad)
        assert not ok
        assert pct is None
        assert any("Conformance" in e for e in errors)

    def test_범위밖_101(self):
        bad = VALID.replace("Conformance: 75%", "Conformance: 101%")
        ok, errors, pct = ddc.validate_output(bad)
        assert not ok
        assert pct is None


# ─── TestDedupeTargets ────────────────────────────────────────────────────────

class TestDedupeTargets:
    def test_reference_와_동일경로_제거(self, tmp_path):
        ref = tmp_path / "req.md"
        ref.write_text("r", encoding="utf-8")
        t1 = tmp_path / "a.md"
        out = ddc.dedupe_targets(ref, [t1, ref])
        assert out == [t1]

    def test_중복_target_제거(self, tmp_path):
        ref = tmp_path / "req.md"
        t1 = tmp_path / "a.md"
        out = ddc.dedupe_targets(ref, [t1, t1])
        assert out == [t1]


# ─── TestMainCodexMissing ─────────────────────────────────────────────────────

class TestMainCodexMissing:
    def test_codex_미설치_exit_2(self, tmp_path, monkeypatch, capsys):
        # codex 미설치 시뮬레이션 (doc_driven_review._build_codex_cmd 가 shutil.which 사용)
        monkeypatch.setattr("shutil.which", lambda name: None)
        ref = tmp_path / "req.md"
        ref.write_text("# Req\n요구 1", encoding="utf-8")
        tgt = tmp_path / "FRD.md"
        tgt.write_text("# FRD\n본문", encoding="utf-8")
        rc = ddc.main([
            "--reference", str(ref),
            "--targets", str(tgt),
            "--repo-root", str(tmp_path),
        ])
        assert rc == ddc.EXIT_NO_CODEX

    def test_reference_와_동일_target만_지정_에러(self, tmp_path):
        ref = tmp_path / "req.md"
        ref.write_text("# Req", encoding="utf-8")
        rc = ddc.main([
            "--reference", str(ref),
            "--targets", str(ref),
            "--repo-root", str(tmp_path),
        ])
        assert rc == ddc.EXIT_ERR

    def test_dry_run_codex_없이_프롬프트_출력(self, tmp_path, capsys):
        ref = tmp_path / "req.md"
        ref.write_text("# Req\n요구 1", encoding="utf-8")
        tgt = tmp_path / "FRD.md"
        tgt.write_text("# FRD\n본문", encoding="utf-8")
        rc = ddc.main([
            "--reference", str(ref),
            "--targets", str(tgt),
            "--repo-root", str(tmp_path),
            "--dry-run",
        ])
        assert rc == ddc.EXIT_OK
        out = capsys.readouterr().out
        assert "# 요구사항 정합 검증:" in out
        assert "요구 1" in out
