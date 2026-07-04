from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pipeline_runner_check.py"


VALID_BUILD = """# Pipeline Build — smoke

## Input
- Requirement Spec: .requirements/requirement-smoke.md
- Source Request: smoke
- App: Smoke
- Slug: smoke
- Process Dir: `.process/pipeline-smoke/`

## Scale Assessment
| Axis | Score | Evidence |
|---|---:|---|
| 변경 범위 | 0 | single |

## Routing Decision
- Total Score: 1
- Size: XS/S
- Forced Conditions: none
- Selected Pipeline: `task-write -> forge-scope -> branch-review`

## Step Parameters
| Order | Skill | Input | Required Params | Expected Output | Gate | Next Input |
|---:|---|---|---|---|---|---|
| 1 | task-write | req | --from req | docs/Smoke/TASK/Smoke-TASK-001.md | task exists | TASK path |

## Approval
- Status: approved
- Approved Pipeline: `task-write -> forge-scope -> branch-review`
- Approved By: user
- Approved At: 2026-07-04

## Risk Notes
- none
"""


VALID_PROGRESS = """# Pipeline Progress — smoke

## Current State
- Status: done
- Current Step: final
- Last Updated: 2026-07-04

## Step Status
| Order | Skill | Status | Input | Output | Notes |
|---:|---|---|---|---|---|
| 1 | task-write | done | req | docs/Smoke/TASK/Smoke-TASK-001.md | Audit: PASS |
| 2 | forge-scope | skipped | TASK path | none | bounded test |

## Output Registry
- TASK: docs/Smoke/TASK/Smoke-TASK-001.md
- SSOT: none
- SSOT Process: none
- Work Packet: none
- Forge Slug: skipped
- Forge Branch: skipped
- DDR Result: skipped
- Branch Review: skipped

## Decisions / Deviations
- none

## Append-only Log
- initialized: pipeline build/progress created.
- step: task-write — result — created TASK.

## Final Output
- TASK: docs/Smoke/TASK/Smoke-TASK-001.md
- SSOT: none
- Work Packet: none
- Forge Branch: skipped
- DDR Result: skipped
- Branch Review: skipped
"""


def write_process(tmp_path: Path, build: str = VALID_BUILD, progress: str = VALID_PROGRESS) -> Path:
    process = tmp_path / ".process" / "pipeline-smoke"
    process.mkdir(parents=True)
    (process / "pipeline-build.md").write_text(build, encoding="utf-8")
    (process / "pipeline-progress.md").write_text(progress, encoding="utf-8")
    task = tmp_path / "docs" / "Smoke" / "TASK" / "Smoke-TASK-001.md"
    task.parent.mkdir(parents=True)
    task.write_text("# Smoke TASK\n", encoding="utf-8")
    return process


def run_check(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_template_passes_valid_contract(tmp_path: Path):
    process = write_process(tmp_path)
    result = run_check(tmp_path, "template", "--process", str(process))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Summary:" in result.stdout
    assert "\nFAIL " not in result.stdout


def test_template_fails_missing_heading(tmp_path: Path):
    process = write_process(tmp_path, build=VALID_BUILD.replace("## Step Parameters", "## Steps"))
    result = run_check(tmp_path, "template", "--process", str(process))
    assert result.returncode == 1
    assert "FAIL BUILD_HEADING ## Step Parameters" in result.stdout


def test_approval_fails_when_pending(tmp_path: Path):
    process = write_process(tmp_path, build=VALID_BUILD.replace("- Status: approved", "- Status: pending"))
    result = run_check(tmp_path, "approval", "--process", str(process))
    assert result.returncode == 1
    assert "FAIL APPROVAL_APPROVED" in result.stdout


def test_approval_output_survives_legacy_console_encoding(tmp_path: Path):
    build = VALID_BUILD.replace("- Approved By: user", "- Approved By: user — explicit approval")
    process = write_process(tmp_path, build=build)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp949"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "approval", "--process", str(process)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Summary:" in result.stdout


def test_progress_fails_when_doing_remains(tmp_path: Path):
    process = write_process(tmp_path, progress=VALID_PROGRESS.replace("| 1 | task-write | done |", "| 1 | task-write | doing |"))
    result = run_check(tmp_path, "progress", "--process", str(process))
    assert result.returncode == 1
    assert "FAIL STEP_STATUS_DOING" in result.stdout


def test_outputs_fails_when_done_output_missing(tmp_path: Path):
    process = write_process(
        tmp_path,
        progress=VALID_PROGRESS.replace("docs/Smoke/TASK/Smoke-TASK-001.md", "docs/Smoke/TASK/Missing.md"),
    )
    result = run_check(tmp_path, "outputs", "--process", str(process), "--repo", str(tmp_path))
    assert result.returncode == 1
    assert "FAIL STEP_OUTPUT_EXISTS" in result.stdout


def test_outputs_preserves_dot_prefixed_paths(tmp_path: Path):
    progress = VALID_PROGRESS.replace(
        "| 2 | forge-scope | skipped | TASK path | none | bounded test |",
        "| 2 | forge-scope | done | TASK path | .worktree/smoke | build/test pass |",
    ).replace(
        "- Branch Review: skipped",
        "- Branch Review: .worktree/smoke/.review/branch-review.md",
    )
    process = write_process(tmp_path, progress=progress)
    worktree = tmp_path / ".worktree" / "smoke"
    review = worktree / ".review" / "branch-review.md"
    review.parent.mkdir(parents=True)
    review.write_text("# review\n", encoding="utf-8")

    result = run_check(tmp_path, "outputs", "--process", str(process), "--repo", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "forge-scope output exists: .worktree/smoke" in result.stdout
    assert "registry output exists: .worktree/smoke/.review/branch-review.md" in result.stdout
