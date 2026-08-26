import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import docs_helpers as dh


def test_next_id_supports_work_packet_kind_aliases(tmp_path, capsys):
    wp_dir = tmp_path / "docs" / "XLAB" / "WORK_PACKET"
    wp_dir.mkdir(parents=True)
    (wp_dir / "XLAB-WP-001.md").write_text("# one\n", encoding="utf-8")
    (wp_dir / "XLAB-WP-002.md").write_text("# two\n", encoding="utf-8")

    rc = dh.main([
        "next-id",
        "--repo",
        str(tmp_path),
        "--app",
        "XLAB",
        "--kind",
        "work-packet",
    ])

    assert rc == 0
    assert capsys.readouterr().out.strip() == "003"


def write_task(repo: Path, app: str = "XLAB", nnn: str = "001", body_extra: str = "") -> Path:
    task_dir = repo / "docs" / app / "TASK"
    task_dir.mkdir(parents=True)
    task = task_dir / f"{app}-TASK-{nnn}.md"
    task.write_text(
        f"""# {app}-TASK-{nnn} - Sample

| 항목 | 값 |
|---|---|
| 문서 ID | {app}-TASK-{nnn} |
| 버전 | 0.1 (Draft) |
| 상태 | Draft |
| 작업 유형 | feature |
| 작성 가정 | 요구사항 입력 기준의 작업 범위 초안 |

## 1. 작업 요약
- Sample

## 6. 입력 근거

| 입력 | 내용 |
|---|---|
| 요구사항 원문 | 대화 입력 |
| 수용 기준 입력 | 없음 |
| 제약/금지 입력 | 없음 |
| 미반영 입력 | 없음 |

## 9. 완료 기준

| ID | Given (전제) | When (행위) | Then (기대 결과, literal 우선) | 확인 방법 | 검증 대상 (§8 단계 / §3 목표) |
|---|---|---|---|---|---|
| AC-T{nnn}-001 | 전제 | 행위 | 결과 | 단위 | §8-1 / §3 |

### 9.1 단위 테스트 명세

없음 - 테스트 대상 없음

### 9.2 엣지 케이스

없음 - 경계 조건 없음

### 9.3 오류 처리

없음 - 오류 입력 없음
{body_extra}
""",
        encoding="utf-8",
    )
    return task


class TestCheckTask:
    def test_valid_task_exit_0_without_ssot_files(self, tmp_path, capsys):
        task = write_task(tmp_path)

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            task.relative_to(tmp_path).as_posix(),
        ])

        out = capsys.readouterr().out
        assert rc == 0
        assert "Summary:" in out
        assert "0 FAIL" in out

    def test_doc_id_mismatch_fails(self, tmp_path):
        task = write_task(tmp_path, nnn="001")
        task.rename(task.with_name("XLAB-TASK-002.md"))

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            "docs/XLAB/TASK/XLAB-TASK-002.md",
        ])

        assert rc == 1

    @pytest.mark.parametrize(
        "bad_text",
        [
            "> TEMPLATE warning\n",
            "- {미치환 placeholder}\n",
        ],
    )
    def test_template_or_placeholder_fails(self, tmp_path, bad_text):
        task = write_task(tmp_path, body_extra=bad_text)

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            str(task),
        ])

        assert rc == 1

    @pytest.mark.parametrize(
        "remove_heading",
        [
            "### 9.2 엣지 케이스",
            "### 9.3 오류 처리",
        ],
    )
    def test_missing_required_9_subsections_fail(self, tmp_path, remove_heading):
        task = write_task(tmp_path)
        text = task.read_text(encoding="utf-8").replace(remove_heading, "")
        task.write_text(text, encoding="utf-8")

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            str(task),
        ])

        assert rc == 1

    def test_ssot_markdown_link_fails(self, tmp_path):
        task = write_task(tmp_path, body_extra="\n- [FRD](../FRD/XLAB-FRD-001.md)\n")

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            str(task),
        ])

        assert rc == 1

    def test_optional_section_placeholder_row_fails(self, tmp_path):
        task = write_task(
            tmp_path,
            body_extra="""

## 11. 미확인 사항

| ID | 항목 | 영향 | 결정 필요자 | 결정 기한 | 상태 |
|---|---|---|---|---|---|
| Q-T001-001 | 확인 필요 항목 | 영향 | 담당자 / PO / 개발 리드 | YYYY-MM-DD | Open / Resolved |
""",
        )

        rc = dh.main([
            "check-task",
            "--repo",
            str(tmp_path),
            "--app",
            "XLAB",
            "--task",
            str(task),
        ])

        assert rc == 1


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
