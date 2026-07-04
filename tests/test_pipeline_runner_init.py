from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "scripts" / "pipeline_runner_init.py"
CHECK = ROOT / "scripts" / "pipeline_runner_check.py"


def run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_init_generates_template_conformant_files(tmp_path: Path):
    req = tmp_path / ".requirements" / "requirement-smoke.md"
    req.parent.mkdir()
    req.write_text("# smoke\n", encoding="utf-8")
    scores = {
        "변경 범위": {"score": 0, "evidence": "single"},
        "SSOT 영향도": {"score": 1, "evidence": "task only"},
    }
    result = run(
        tmp_path,
        str(INIT),
        "init",
        "--requirement",
        str(req.relative_to(tmp_path)),
        "--app",
        "Smoke",
        "--name",
        "smoke",
        "--pipeline",
        "task-write -> forge-scope -> branch-review",
        "--total-score",
        "2",
        "--size",
        "XS/S",
        "--scores-json",
        json.dumps(scores, ensure_ascii=False),
        "--date",
        "2026-07-04",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    process = tmp_path / ".process" / "pipeline-smoke"
    build = (process / "pipeline-build.md").read_text(encoding="utf-8")
    progress = (process / "pipeline-progress.md").read_text(encoding="utf-8")
    assert "## Input" in build
    assert "## Scale Assessment" in build
    assert "| Axis | Score | Evidence |" in build
    assert "## Current State" in progress
    assert "| Order | Skill | Status | Input | Output | Notes |" in progress
    assert "{{" not in build
    assert "{{" not in progress


def test_init_output_passes_checker(tmp_path: Path):
    req = tmp_path / ".requirements" / "requirement-smoke.md"
    req.parent.mkdir()
    req.write_text("# smoke\n", encoding="utf-8")
    init = run(
        tmp_path,
        str(INIT),
        "init",
        "--requirement",
        str(req.relative_to(tmp_path)),
        "--app",
        "Smoke",
        "--name",
        "smoke",
        "--pipeline",
        "task-write -> forge-scope -> branch-review",
        "--force",
    )
    assert init.returncode == 0, init.stdout + init.stderr
    check = run(tmp_path, str(CHECK), "template", "--process", ".process/pipeline-smoke")
    assert check.returncode == 0, check.stdout + check.stderr


def test_init_refuses_existing_process_without_force(tmp_path: Path):
    req = tmp_path / ".requirements" / "requirement-smoke.md"
    req.parent.mkdir()
    req.write_text("# smoke\n", encoding="utf-8")
    args = [
        str(INIT),
        "init",
        "--requirement",
        str(req.relative_to(tmp_path)),
        "--name",
        "smoke",
        "--pipeline",
        "task-write -> forge-scope -> branch-review",
    ]
    first = run(tmp_path, *args)
    second = run(tmp_path, *args)
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 2
    assert "already exists" in second.stderr
