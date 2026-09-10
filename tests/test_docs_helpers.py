import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import docs_helpers as dh


INSTRUCTION_INCLUDE_KEYS = ("goal", "content", "type_required", "fixed_must", "guardrail")


def write_instruction(
    repo: Path,
    slug: str = "sample",
    header: str = "유형: 기능 개발 / 추가한 가정 0개",
    include=INSTRUCTION_INCLUDE_KEYS,
) -> Path:
    """requirement-spec가 저장하는 지시서(기능 개발 유형) 포맷을 재현한다."""
    req_dir = repo / ".requirements"
    req_dir.mkdir(parents=True, exist_ok=True)
    parts = [
        f"# 요구사항 개발 지시서: {slug}",
        "",
        f"> 출처(GROUND TRUTH): .requirements/grill-me-{slug}.md + .requirements/{slug}-acceptance.md",
        "",
        "---",
        "",
        header,
        "",
    ]
    if "goal" in include:
        parts += ["[작업 목표]", "샘플 기능 추가.", ""]
    if "content" in include:
        parts += ["[작업 내용]", "- 엔드포인트 추가", ""]
    if "type_required" in include:
        parts += ["[완료 조건]", "- 동작함", ""]
    parts += ["[검증 방법]", "- 단위 테스트", ""]
    if "fixed_must" in include:
        parts += ["[필수 사항]", "protected·public 함수는 기능 흐름만 관장. 함수 및 클래스 OCP, SRP 준수.", ""]
    if "guardrail" in include:
        parts += [
            "[에이전트 행동 규칙]",
            "- 파일을 수정하기 전에 변경 계획을 먼저 제시한다.",
            "- 의존성 추가, 마이그레이션, 파일 삭제는 사전 승인을 받는다.",
            "- 막히면 [불확실성 처리] 정책을 따른다.",
        ]
    path = req_dir / f"requirement-{slug}.md"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


class TestCheckInstruction:
    def _run(self, repo: Path, path: Path) -> int:
        return dh.main([
            "check-instruction",
            "--repo",
            str(repo),
            "--file",
            path.relative_to(repo).as_posix(),
        ])

    def test_valid_feature_instruction_exit_0(self, tmp_path, capsys):
        path = write_instruction(tmp_path)
        rc = self._run(tmp_path, path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "0 FAIL" in out

    def test_missing_meta_header_fails(self, tmp_path):
        # "유형:" 접두어가 없는 헤더 → 메타 헤더 검출 실패
        path = write_instruction(tmp_path, header="추가한 가정 0개")
        assert self._run(tmp_path, path) == 1

    @pytest.mark.parametrize("drop", ["goal", "content", "type_required", "guardrail"])
    def test_missing_required_item_fails(self, tmp_path, drop):
        include = tuple(k for k in INSTRUCTION_INCLUDE_KEYS if k != drop)
        path = write_instruction(tmp_path, include=include)
        assert self._run(tmp_path, path) == 1

    def test_feature_missing_fixed_must_fails(self, tmp_path):
        include = tuple(k for k in INSTRUCTION_INCLUDE_KEYS if k != "fixed_must")
        path = write_instruction(tmp_path, include=include)
        assert self._run(tmp_path, path) == 1

    def test_doc_type_without_fixed_must_passes(self, tmp_path, capsys):
        req_dir = tmp_path / ".requirements"
        req_dir.mkdir(parents=True)
        path = req_dir / "requirement-guide.md"
        path.write_text(
            "유형: 문서화 / 추가한 가정 0개\n\n"
            "[작업 목표]\n온보딩 가이드.\n\n"
            "[작업 내용]\n- 개요 작성\n\n"
            "[대상 독자]\n신규 입사자\n\n"
            "[에이전트 행동 규칙]\n"
            "- 파일을 수정하기 전에 변경 계획을 먼저 제시한다.\n"
            "- 의존성 추가, 마이그레이션, 파일 삭제는 사전 승인을 받는다.\n"
            "- 막히면 [불확실성 처리] 정책을 따른다.\n",
            encoding="utf-8",
        )
        rc = self._run(tmp_path, path)
        assert rc == 0
        assert "0 FAIL" in capsys.readouterr().out
