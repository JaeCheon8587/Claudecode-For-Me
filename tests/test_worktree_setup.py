import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "worktree_setup.py"


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "forge-test@example.invalid")
    run_git(tmp_path, "config", "user.name", "Forge Test")
    run_git(tmp_path, "config", "commit.gpgsign", "false")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# Test repo\n", encoding="utf-8")
    run_git(tmp_path, "add", "README.md")
    run_git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def commit_all(repo: Path, message: str = "docs") -> None:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-q", "-m", message)


def write_task(repo: Path, nnn: str = "001") -> Path:
    task = repo / "docs" / "XLAB" / "TASK" / f"XLAB-TASK-{nnn}.md"
    task.parent.mkdir(parents=True, exist_ok=True)
    task.write_text(
        f"""# XLAB-TASK-{nnn} - Sample

| 항목 | 값 |
|---|---|
| 문서 ID | XLAB-TASK-{nnn} |
| 버전 | 1.0 |
| 상태 | Accepted |

## 8. 작업 단계
| 단계 | 작업 | 산출물 / 관찰 가능 결과 | 선행 조건 | 상태 |
|---|---|---|---|---|
| 1 | 샘플 구현 | 테스트 통과 | 없음 | Todo |

## 9. 완료 기준
| ID | Given (전제) | When (행위) | Then (기대 결과, literal 우선) | 확인 방법 | 검증 대상 (§8 단계 / §3 목표) |
|---|---|---|---|---|---|
| AC-T{nnn}-001 | 입력 | 실행 | 성공 | 단위 | §8-1 |

### 9.1 단위 테스트 명세
| ID | 테스트명 | 프로젝트 | 클래스 | 함수명 | 선행 조건/픽스처 | 검증 대상 | 도입 근거 | 검증 AC |
|---|---|---|---|---|---|---|---|---|
| TS-T{nnn}-001 | sample | tests/Sample.Tests.csproj | SampleTests | passes | 없음 | 성공 | 회귀 방지 | AC-T{nnn}-001 |

### 9.2 엣지 케이스
없음 - 경계 조건 없음

### 9.3 오류 처리
없음 - 오류 입력 없음

## 12. 구현 참고 정보
없음
""",
        encoding="utf-8",
    )
    return task


def write_ssot(repo: Path, nnn: str = "001") -> Path:
    ssot = repo / "docs" / "XLAB" / "FRD" / f"XLAB-FRD-{nnn}.md"
    ssot.parent.mkdir(parents=True, exist_ok=True)
    ssot.write_text(f"# XLAB-FRD-{nnn}\n\n## 1. 기준\n- 구현 기준\n", encoding="utf-8")
    return ssot


def write_work_packet(repo: Path, nnn: str = "001", *, status: str = "Ready", ssot_nnn: str = "001") -> Path:
    wp = repo / "docs" / "XLAB" / "WORK_PACKET" / f"XLAB-WP-{nnn}.md"
    wp.parent.mkdir(parents=True, exist_ok=True)
    wp.write_text(
        f"""# XLAB-WP-{nnn} - Sample

| 항목 | 값 |
|---|---|
| 문서 ID | XLAB-WP-{nnn} |
| 버전 | 1.0 |
| 상태 | {status} |
| 연결 TASK | [XLAB-TASK-{nnn}](../TASK/XLAB-TASK-{nnn}.md) |

## 3. Execution Gate

| 상태 | 실행 판단 | 기준 |
|---|---|---|
| Ready | forge-scope 진행 가능 | blocking 없음 |
| Draft | 구현 금지 | Blocking / Open Questions 해결 필요 |

| 현재 판정 | 근거 |
|---|---|
| {status} | 문서 준비 상태 |

## 4. Required SSOT Execution Matrix

| SSOT type | Action | Document | Read range | Why required | Source matrix row | Priority |
|---|---|---|---|---|---|---|
| FRD | UPDATE | [XLAB-FRD-{ssot_nnn}](../FRD/XLAB-FRD-{ssot_nnn}.md) | §1 | 기능 기준 | row 1 | Required |

## 5. 실행 규칙
- TASK 에 없는 작업은 구현하지 않는다.

## 6. 실행 경계
| 구분 | 내용 |
|---|---|
| 반드시 수행 | 샘플 구현 |
| 금지 | 범위 밖 구현 |
| 허용 | 테스트 보강 |
| 중단 조건 | 충돌 |

## 7. Blocking / Open Questions

| Issue | Source | Impact | Required decision |
|---|---|---|---|
| none | none | none | none |

## 8. 검증 입력
| 구분 | 기준 |
|---|---|
| 완료 기준 | TASK §9 |
| 단위 테스트 | TASK §9.1 |
| 빌드/테스트 명령 | 코드베이스 기준으로 탐색 |

## 10. Implementation Output Contract
| 항목 | 필수 내용 |
|---|---|
| Changed files | 변경한 파일 목록 |
| Scope match | 구현 범위 일치 여부 |
| Tests run | 실행한 빌드/테스트 |
| Not run | 미실행 검증 |
| Deviations | 이탈 |
""",
        encoding="utf-8",
    )
    return wp


def run_init(repo: Path, doc: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "init", "--doc", str(doc), "--quiet", *extra],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def manifest_from(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_ready_work_packet_init_passes_and_manifest_tracks_task(git_repo: Path):
    task = write_task(git_repo, "001")
    write_ssot(git_repo, "001")
    wp = write_work_packet(git_repo, "001")
    commit_all(git_repo)

    result = run_init(git_repo, wp)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["input_kind"] == "WORK_PACKET"
    assert manifest["work_packet"] == str(wp.resolve())
    assert manifest["task_doc"] == str(task.resolve())
    build_md = Path(manifest["build_md"]).read_text(encoding="utf-8")
    assert "Work Packet: `docs/XLAB/WORK_PACKET/XLAB-WP-001.md`" in build_md
    assert "TASK 문서: `docs/XLAB/TASK/XLAB-TASK-001.md`" in build_md


def test_draft_work_packet_blocks_before_worktree_creation(git_repo: Path):
    write_task(git_repo, "002")
    write_ssot(git_repo, "002")
    wp = write_work_packet(git_repo, "002", status="Draft")
    commit_all(git_repo)

    result = run_init(git_repo, wp)

    assert result.returncode == 2
    assert "Draft = do not implement" in result.stderr
    assert not (git_repo / ".worktree" / "XLAB-WP-002").exists()


def test_ready_work_packet_with_missing_required_ssot_blocks(git_repo: Path):
    write_task(git_repo, "003")
    wp = write_work_packet(git_repo, "003", ssot_nnn="999")
    commit_all(git_repo)

    result = run_init(git_repo, wp)

    assert result.returncode == 2
    assert "Required SSOT" in result.stderr
    assert "파일 없음" in result.stderr
    assert not (git_repo / ".worktree" / "XLAB-WP-003").exists()


def test_task_direct_input_keeps_legacy_gate_and_manifest(git_repo: Path):
    task = write_task(git_repo, "004")
    commit_all(git_repo)

    result = run_init(git_repo, task)

    assert result.returncode == 0, result.stderr
    manifest = manifest_from(result)
    assert manifest["input_kind"] == "TASK"
    assert manifest["work_packet"] is None
    assert manifest["task_doc"] == str(task.resolve())
