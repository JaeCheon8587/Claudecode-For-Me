import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import docs_helpers as dh


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
