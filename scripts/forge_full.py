#!/usr/bin/env python3
"""
Forge Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.

Usage:
    python3 scripts/forge_full.py <phase-dir> [--push] [--trust] [--force] [--verbose] [--strict]

Environment:
    FORGE_TRUST=1            --trust 대신 사용 가능 (--dangerously-skip-permissions 옵트인)
    FORGE_CLAUDE_TIMEOUT     Claude CLI 타임아웃(초). 미설정 시 1800.
"""

import argparse
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

log = logging.getLogger("forge")

PHASE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ALLOWED_STATUS = frozenset({"pending", "completed", "error", "blocked", "interrupted"})
PROMPT_ARGV_LIMIT = (
    8_000 if os.name == "nt" else 100_000
)  # 이 길이 초과 시 stdin 으로 전달 (argv ARG_MAX 회피 + ps 노출 방지). Windows ARG_MAX≈32KB 회피.
PLACEHOLDER_RE = re.compile(r"\{[^}\n]+\}")
VALID_PRESETS = frozenset({"auto", "contract-tdd"})
VALID_docs_MODES = frozenset({"root", "recursive", "explicit"})
DEFAULT_MAX_GUARDRAIL_BYTES = 120_000
# forge-full splitter·step 모두 Opus 4.8 + effort high 고정 (지능 최우선).
FULL_CLAUDE_MODEL = "claude-opus-4-8"
FULL_CLAUDE_EFFORT = "high"
REQUIRED_STEP_HEADINGS = (
    "## 읽어야 할 파일",
    "## 작업",
    "## Acceptance Criteria",
    "## 검증 절차",
    "## 금지사항",
)
_QUIET = False


def _qprint(*args, **kwargs) -> None:
    if not _QUIET:
        print(*args, **kwargs)


def _err(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug[:60].rstrip("-") or "step"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 40)].rstrip() + "\n\n[... truncated by forge-full ...]\n"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FullGuardrailPathValidator:
    """forge-full 전용 guardrail 문서 경로 검증기."""

    def __init__(self, root: Optional[Path] = None):
        self._root = root or ROOT
        self._docs_dir = (self._root / "docs").resolve()

    def validate_one(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"문서 경로가 비어 있습니다: {rel!r}")
        rel = rel.lstrip("/")
        if len(rel) > 256:
            raise ValueError(f"문서 경로가 너무 깁니다: {rel}")
        if "\\" in rel:
            raise ValueError(f"역슬래시 경로는 허용되지 않습니다: {rel}")
        if Path(rel).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", rel):
            raise ValueError(f"절대 경로는 허용되지 않습니다: {rel}")
        if not rel.startswith("docs/"):
            raise ValueError(f"docs/ 하위 문서만 허용됩니다: {rel}")
        if not rel.endswith(".md"):
            raise ValueError(f"Markdown 문서만 허용됩니다: {rel}")
        candidate = (self._root / rel).resolve()
        if self._docs_dir not in candidate.parents and candidate != self._docs_dir:
            raise ValueError(f"docs/ 밖을 가리킵니다: {rel}")
        if not candidate.is_file():
            raise FileNotFoundError(f"문서 파일 없음: {rel}")
        return candidate

    def validate_many(self, docs: list[str]) -> list[Path]:
        seen: set[str] = set()
        paths: list[Path] = []
        for doc in docs:
            path = self.validate_one(doc)
            rel = path.relative_to(self._root).as_posix()
            if rel not in seen:
                seen.add(rel)
                paths.append(path)
        return paths


class FullGuardrailLoader:
    """CLAUDE.md + full guardrail profile을 결합한다."""

    def __init__(
        self,
        root: Optional[Path] = None,
        *,
        strict: bool = False,
        compact_docs: bool = False,
        max_bytes: int = DEFAULT_MAX_GUARDRAIL_BYTES,
    ):
        self._root = root or ROOT
        self._strict = strict
        self._compact_docs = compact_docs
        self._max_bytes = max_bytes
        self._validator = FullGuardrailPathValidator(self._root)

    def load(self, guardrails: Optional[dict] = None) -> str:
        guardrails = guardrails or {"mode": "root", "docs": []}
        mode = guardrails.get("mode", "root")
        docs = list(guardrails.get("docs") or [])
        if mode not in VALID_docs_MODES:
            raise ValueError(f"알 수 없는 docs-mode: {mode}")

        sections: list[str] = []
        claude_md = self._root / "CLAUDE.md"
        if claude_md.exists():
            text = _read_text(claude_md)
            self._warn_placeholders(claude_md, text)
            sections.append(f"## 프로젝트 규칙 (CLAUDE.md)\n\n{text}")

        for doc in self._select_docs(mode, docs):
            text = _read_text(doc)
            self._warn_placeholders(doc, text)
            if self._compact_docs:
                text = self._compact_doc_text(text)
            rel = doc.relative_to(self._root).as_posix()
            sections.append(f"## {rel}\n\n{text}")

        result = "\n\n---\n\n".join(sections) if sections else ""
        if self._max_bytes > 0 and len(result.encode("utf-8")) > self._max_bytes:
            raise ValueError(
                f"guardrail 크기가 제한을 초과했습니다 "
                f"({len(result.encode('utf-8'))} > {self._max_bytes} bytes). "
                "--compact-docs 또는 --docs-mode explicit을 사용하세요."
            )
        return result

    def _select_docs(self, mode: str, docs: list[str]) -> list[Path]:
        docs_dir = self._root / "docs"
        if mode == "explicit":
            return self._validator.validate_many(docs)
        if not docs_dir.is_dir():
            return []
        if mode == "recursive":
            return [p for p in sorted(docs_dir.rglob("*.md")) if ".templates" not in p.relative_to(docs_dir).parts]
        return sorted(docs_dir.glob("*.md"))

    def _warn_placeholders(self, path: Path, text: str) -> None:
        matches = PLACEHOLDER_RE.findall(text)
        if not matches:
            return
        sample = matches[0]
        log.warning(
            "%s: placeholder 감지 — %d건 (예: %s). 작성하거나 삭제하세요.",
            path,
            len(matches),
            sample,
        )
        if self._strict:
            _err(f"--strict 모드 — placeholder가 남아 있습니다: {path}")

    @staticmethod
    def _compact_doc_text(text: str) -> str:
        keep_patterns = (
            "개요",
            "목표",
            "범위",
            "요구",
            "Acceptance",
            "Criteria",
            "AC",
            "아키텍처",
            "구조",
            "정책",
            "도메인",
            "상태",
            "결정",
            "Open",
            "미결",
            "미확인",
            "비기능",
        )
        lines = text.splitlines()
        kept: list[str] = []
        keep = True
        for line in lines:
            if line.startswith("## "):
                keep = any(p.lower() in line.lower() for p in keep_patterns)
            if keep or line.startswith("# "):
                kept.append(line)
        compact = "\n".join(kept).strip() or text
        return _truncate(compact, 24_000)


class FullDocReadinessChecker:
    """splitter 실행 전 문서의 미결/애매함을 coarse하게 판정한다."""

    BLOCK_PATTERNS = (
        re.compile(r"결정.{0,4}필요"),
        re.compile(r"undecided", re.IGNORECASE),
        re.compile(r"TBD"),
        re.compile(r"다음\s*중\s*하나"),
    )

    def __init__(self, root: Optional[Path] = None):
        self._root = root or ROOT

    def check(self, docs: list[Path]) -> dict:
        issues: list[dict] = []
        for path in docs:
            text = _read_text(path)
            rel = path.relative_to(self._root).as_posix()
            for pat in self.BLOCK_PATTERNS:
                m = pat.search(text)
                if m:
                    issues.append(
                        {
                            "severity": "question",
                            "file": rel,
                            "kind": "open-decision",
                            "message": f"문서에 미결 마커가 있습니다: {m.group(0)}",
                        }
                    )
                    break
            placeholders = PLACEHOLDER_RE.findall(text)
            if placeholders:
                issues.append(
                    {
                        "severity": "warning",
                        "file": rel,
                        "kind": "placeholder",
                        "message": f"placeholder {len(placeholders)}건",
                    }
                )
        severity = "clear"
        if any(i["severity"] == "blocked" for i in issues):
            severity = "blocked"
        elif any(i["severity"] == "question" for i in issues):
            severity = "question"
        elif issues:
            severity = "warning"
        return {"severity": severity, "issues": issues}


class FullPlanValidator:
    """forge-full splitter/preset plan 검증."""

    @staticmethod
    def validate(plan: dict, *, phase_dir: str, root: Optional[Path] = None) -> None:
        root = root or ROOT
        if not isinstance(plan, dict):
            _err("plan은 JSON object여야 합니다.")
        for key in ("project", "phase", "guardrails", "steps"):
            if key not in plan:
                _err(f"plan에 '{key}' 키가 없습니다.")
        if plan["phase"] != phase_dir:
            _err(f"plan.phase가 phase_dir와 다릅니다: {plan['phase']} != {phase_dir}")
        if not isinstance(plan["project"], str) or not plan["project"].strip():
            _err("plan.project는 비어 있지 않은 문자열이어야 합니다.")
        guardrails = plan["guardrails"]
        if not isinstance(guardrails, dict):
            _err("plan.guardrails는 객체여야 합니다.")
        mode = guardrails.get("mode")
        docs = guardrails.get("docs", [])
        if mode not in VALID_docs_MODES:
            _err(f"plan.guardrails.mode가 올바르지 않습니다: {mode}")
        if not isinstance(docs, list) or not all(isinstance(d, str) for d in docs):
            _err("plan.guardrails.docs는 문자열 배열이어야 합니다.")
        FullGuardrailPathValidator(root).validate_many(docs)

        steps = plan["steps"]
        if not isinstance(steps, list) or not (1 <= len(steps) <= 30):
            _err("plan.steps는 1~30개 배열이어야 합니다.")
        seen_names: set[str] = set()
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                _err(f"steps[{i}]는 객체여야 합니다.")
            if step.get("step") != i:
                _err("step 번호는 0부터 연속이어야 합니다.")
            name = step.get("name")
            if not isinstance(name, str) or not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
                _err(f"step name은 kebab-case여야 합니다: {name!r}")
            if name in seen_names:
                _err(f"step name 중복: {name}")
            seen_names.add(name)
            if not isinstance(step.get("brief"), str) or not step["brief"].strip():
                _err(f"steps[{i}].brief가 비어 있습니다.")
            body = step.get("body")
            if not isinstance(body, str) or not body.strip():
                _err(f"steps[{i}].body가 비어 있습니다.")
            for heading in REQUIRED_STEP_HEADINGS:
                if heading not in body:
                    _err(f"steps[{i}].body에 필수 heading 없음: {heading}")
            if "```" not in body:
                _err(f"steps[{i}].body의 Acceptance Criteria에 실행 코드블록이 필요합니다.")


class FullPlanEmitter:
    """검증된 full plan을 phases/full/<phase>로 atomic emit."""

    def __init__(self, root: Optional[Path] = None):
        self._root = root or ROOT
        self._phases_dir = self._root / "phases" / "full"

    def emit(self, plan: dict) -> Path:
        phase = plan["phase"]
        dest = self._phases_dir / phase
        if dest.exists() and any(dest.iterdir()):
            _err(f"기존 phase를 덮어쓰지 않습니다: {dest}")
        self._phases_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._phases_dir / f".{phase}.tmp-{os.getpid()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        try:
            index = {
                "project": plan["project"],
                "phase": phase,
                "guardrails": plan["guardrails"],
                "steps": [{"step": s["step"], "name": s["name"], "status": "pending"} for s in plan["steps"]],
            }
            (tmp / "index.json").write_text(
                json.dumps(index, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            for step in plan["steps"]:
                (tmp / f"step{step['step']}.md").write_text(
                    step["body"],
                    encoding="utf-8",
                )
            if dest.exists():
                dest.rmdir()
            tmp.rename(dest)
            self._upsert_top_index(phase)
            return dest
        except Exception:
            if tmp.exists():
                shutil.rmtree(tmp)
            raise

    def _upsert_top_index(self, phase: str) -> None:
        top_path = self._phases_dir / "index.json"
        if top_path.exists():
            try:
                top = json.loads(top_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return
        else:
            top = {"phases": []}
        phases = top.setdefault("phases", [])
        if not any(p.get("dir") == phase for p in phases if isinstance(p, dict)):
            phases.append({"dir": phase, "status": "pending"})
            top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False), encoding="utf-8")


class FullContractTddPlanBuilder:
    """forge-full 전용 contract-tdd 고정 workflow plan 생성."""

    def __init__(self, root: Optional[Path] = None):
        self._root = root or ROOT

    def build(self, phase: str, docs: list[str], prompts: list[str], guardrails: dict) -> dict:
        if len(docs) != 1:
            _err("--preset=contract-tdd는 --doc 문서 1개가 필요합니다.")
        doc = docs[0].lstrip("/")
        prompt_text = "\n".join(f"- {p.strip()}" for p in prompts if p.strip()) or "- 문서 요구사항을 따른다."
        target = self._test_target()
        full_target = self._solution_target()
        steps = [
            (
                "contract-skeleton",
                "계약 표면과 skeleton을 만든다",
                self._body(
                    0,
                    "contract-skeleton",
                    doc,
                    prompt_text,
                    "git diff --stat HEAD",
                    "계약 surface/interface/DTO/route skeleton만 만든다. 실제 비즈니스 로직은 구현하지 않는다.",
                    "실제 비즈니스 로직 구현 금지. 이유: red-tests 이전에 green을 만들지 않기 위함이다.",
                ),
            ),
            (
                "red-tests",
                "구현 전 실패 테스트를 추가한다",
                self._body(
                    1,
                    "red-tests",
                    doc,
                    prompt_text,
                    f'dotnet test {target} --no-restore --filter "<feature-specific-filter>"',
                    "FRD 요구사항을 검증하는 테스트를 추가하고 의도한 이유로 실패하는지 확인한다.",
                    "제품 코드 구현 금지. 이유: red 단계의 실패 신호를 보존하기 위함이다.",
                    extra=(
                        "위 test 명령은 실패해야 하며, 컴파일/인프라 오류가 아니라 "
                        "미구현 또는 assertion mismatch여야 한다."
                    ),
                ),
            ),
            (
                "green-implementation",
                "red 테스트를 통과시키는 최소 구현",
                self._body(
                    2,
                    "green-implementation",
                    doc,
                    prompt_text,
                    f'dotnet test {target} --no-restore --filter "<feature-specific-filter>"',
                    "step1 테스트를 통과시키는 최소 제품 코드를 구현한다.",
                    "step1 테스트 삭제/완화/skip 금지. 이유: red 신호를 무력화하지 않기 위함이다.",
                ),
            ),
            (
                "regression-hardening",
                "정리와 전체 회귀 검증",
                self._body(
                    3,
                    "regression-hardening",
                    doc,
                    prompt_text,
                    f"dotnet test {full_target} --no-restore\ngit diff --check",
                    "구현을 정리하고 filter 없는 전체 회귀를 수행한다.",
                    "범위 밖 리팩터링 금지. 이유: full phase라도 contract-tdd 산출물 안정성을 우선한다.",
                ),
            ),
        ]
        return {
            "project": self._project_name(),
            "phase": phase,
            "guardrails": guardrails,
            "steps": [
                {"step": i, "name": name, "brief": brief, "body": body} for i, (name, brief, body) in enumerate(steps)
            ],
        }

    def _body(
        self, num: int, name: str, doc: str, prompt_text: str, ac: str, task: str, forbidden: str, extra: str = ""
    ) -> str:
        extra_text = f"\n\n{extra}\n" if extra else ""
        return (
            f"# Step {num}: {name}\n\n"
            "## 읽어야 할 파일\n\n"
            "- `CLAUDE.md`\n"
            f"- `{doc}`\n"
            "- 관련 PRD/ARCH/ADR guardrail 내용을 확인한다.\n\n"
            "## 작업\n\n"
            f"{task}\n\n"
            "요구사항:\n"
            f"{prompt_text}\n"
            f"{extra_text}\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            f"{ac}\n"
            "```\n\n"
            "## 검증 절차\n\n"
            "1. Acceptance Criteria 명령을 실행한다.\n"
            "2. 결과에 따라 `phases/full/<phase>/index.json`의 해당 step 상태를 갱신한다.\n"
            "3. summary에는 변경 파일과 검증 결과를 200자 이내로 기록한다.\n\n"
            "## 금지사항\n\n"
            f"- {forbidden}\n"
            "- 기존 테스트를 깨뜨리지 마라. 이유: full phase 회귀 안정성을 유지해야 한다.\n"
        )

    def _project_name(self) -> str:
        claude = self._root / "CLAUDE.md"
        if claude.exists():
            for line in claude.read_text(encoding="utf-8").splitlines():
                if line.startswith("# 프로젝트:"):
                    return line.removeprefix("# 프로젝트:").strip() or self._root.name
        return self._root.name

    def _solution_target(self) -> str:
        slns = sorted(self._root.glob("*.sln")) + sorted((self._root / "Src").glob("*.sln"))
        return slns[0].relative_to(self._root).as_posix() if slns else "."

    def _test_target(self) -> str:
        test_projects = sorted(self._root.glob("Src/Tests/**/*.csproj"))
        if len(test_projects) == 1:
            return test_projects[0].relative_to(self._root).as_posix()
        return self._solution_target()


class FullStepSplitter:
    """문서 기반 full phase splitter."""

    def __init__(self, root: Optional[Path] = None):
        self._root = root or ROOT

    def build(self, phase: str, prompts: list[str], docs: list[Path], guardrails: dict) -> dict:
        prompt = self._build_prompt(phase, prompts, docs, guardrails)
        stdout = self._call_claude(prompt)
        plan = self._parse_plan(stdout)
        return plan

    def _build_prompt(self, phase: str, prompts: list[str], docs: list[Path], guardrails: dict) -> str:
        prompt_text = "\n".join(f"- {p}" for p in prompts if p.strip()) or "- 문서 기반 full phase plan 생성"
        doc_sections = []
        for p in docs:
            rel = p.relative_to(self._root).as_posix()
            doc_sections.append(f"### {rel}\n\n{_truncate(_read_text(p), 32_000)}")
        docs_text = "\n\n".join(doc_sections)
        return (
            "forge-full 문서 기반 splitter로 동작하라. strict JSON object만 출력하라.\n\n"
            f"phase: {phase}\n"
            f"guardrails: {json.dumps(guardrails, ensure_ascii=False)}\n\n"
            "사용자 요구사항:\n"
            f"{prompt_text}\n\n"
            "문서:\n"
            f"{docs_text}\n\n"
            "출력 schema:\n"
            "{\n"
            '  "project": "<project>",\n'
            f'  "phase": "{phase}",\n'
            '  "guardrails": {"mode": "root|recursive|explicit", "docs": ["docs/...md"]},\n'
            '  "steps": [{"step": 0, "name": "kebab-case", "brief": "...", "body": "..."}]\n'
            "}\n\n"
            "각 body는 반드시 다음 H2를 포함한다: "
            + ", ".join(REQUIRED_STEP_HEADINGS)
            + "\nAcceptance Criteria에는 실행 가능한 bash 코드블록을 포함한다.\n"
        )

    def _call_claude(self, prompt: str) -> str:
        cmd = ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json",
               "--model", FULL_CLAUDE_MODEL, "--effort", FULL_CLAUDE_EFFORT]
        stdin_input = prompt if len(prompt) > PROMPT_ARGV_LIMIT else None
        if stdin_input is None:
            cmd.append(prompt)
        result = subprocess.run(
            cmd,
            cwd=self._root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=stdin_input,
            timeout=1800,
        )
        if result.returncode != 0:
            _err(f"splitter Claude 호출 실패: {result.stderr.strip()[:500]}")
        return result.stdout

    @staticmethod
    def _parse_plan(stdout: str) -> dict:
        text = stdout.strip()
        try:
            outer = json.loads(text)
            if isinstance(outer, dict) and isinstance(outer.get("result"), str):
                text = outer["result"].strip()
            elif isinstance(outer, dict) and "steps" in outer:
                return outer
        except json.JSONDecodeError:
            pass
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            _err(f"splitter JSON 파싱 실패 (line {e.lineno}, col {e.colno}): {e.msg}")


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다.

    stderr가 TTY가 아니면(파이프/CI 등) 스피너 애니메이션을 비활성화하여
    NO_COLOR/캡처 환경에서 ANSI 잔여물이 남지 않도록 한다.
    """
    stop = threading.Event()
    t0 = time.monotonic()
    is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())

    def _animate():
        frames = "◐◓◑◒"
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th: Optional[threading.Thread] = None
    if is_tty and not _QUIET:
        th = threading.Thread(target=_animate, daemon=True)
        th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        if th is not None:
            th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 Forge."""

    MAX_RETRIES = 3
    CLAUDE_TIMEOUT_SEC = 1800
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))
    PHASES_SUBDIR = "full"

    def __init__(
        self,
        phase_dir_name: str,
        *,
        auto_push: bool = False,
        force: bool = False,
        strict: bool = False,
        quiet: bool = False,
        compact_docs: bool = False,
        max_guardrail_bytes: int = DEFAULT_MAX_GUARDRAIL_BYTES,
    ):
        self._validate_phase_dir_name(phase_dir_name)

        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases" / self.PHASES_SUBDIR
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push
        self._force = force
        self._strict = strict
        self._quiet = quiet
        self._compact_docs = compact_docs
        self._max_guardrail_bytes = max_guardrail_bytes
        self._claude_timeout = self._resolve_timeout()

        # path traversal 최종 방어 — 정규식 통과 후에도 resolve 결과가 phases/ 하위인지 확인
        try:
            resolved = self._phase_dir.resolve()
            phases_resolved = self._phases_dir.resolve()
        except (OSError, RuntimeError) as e:
            print(f"ERROR: phase 경로 해석 실패: {e}", file=sys.stderr)
            sys.exit(1)
        if phases_resolved not in resolved.parents and resolved != phases_resolved:
            print(f"ERROR: phase 경로가 phases/ 디렉토리 밖을 가리킵니다: {resolved}", file=sys.stderr)
            sys.exit(1)

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found", file=sys.stderr)
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found", file=sys.stderr)
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._validate_index_schema(idx, self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])

    # --- 검증 헬퍼 ---

    @staticmethod
    def _validate_phase_dir_name(name: str) -> None:
        if not name:
            print("ERROR: phase 디렉토리 이름이 비어 있습니다.", file=sys.stderr)
            sys.exit(1)
        if Path(name).is_absolute():
            print(f"ERROR: 절대경로는 허용되지 않습니다: {name}", file=sys.stderr)
            sys.exit(1)
        bad = [c for c in ("/", "\\", ":", "..") if c in name]
        if bad:
            print(f"ERROR: phase 디렉토리 이름에 금지된 문자/시퀀스 포함: {bad} ({name!r})", file=sys.stderr)
            sys.exit(1)
        if not PHASE_NAME_RE.match(name):
            print(f"ERROR: phase 디렉토리 이름은 [A-Za-z0-9._-] 만 허용됩니다: {name!r}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _validate_index_schema(idx, file_path: Path) -> None:
        def _err(msg: str):
            print(f"ERROR: {file_path} 스키마 위반 — {msg}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(idx, dict):
            _err("최상위는 객체여야 합니다.")
        guardrails = idx.get("guardrails")
        if guardrails is not None:
            if not isinstance(guardrails, dict):
                _err("'guardrails'는 객체여야 합니다.")
            mode = guardrails.get("mode")
            docs = guardrails.get("docs", [])
            if mode not in VALID_docs_MODES:
                _err(f"guardrails.mode='{mode}' 허용되지 않음.")
            if not isinstance(docs, list) or not all(isinstance(d, str) for d in docs):
                _err("guardrails.docs는 문자열 배열이어야 합니다.")
        steps = idx.get("steps")
        if not isinstance(steps, list):
            _err("'steps'는 배열이어야 합니다.")
        seen = set()
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                _err(f"steps[{i}]는 객체여야 합니다.")
            for key, typ in (("step", int), ("name", str), ("status", str)):
                if key not in s:
                    _err(f"steps[{i}]에 '{key}' 키 없음.")
                if not isinstance(s[key], typ) or (typ is int and isinstance(s[key], bool)):
                    _err(f"steps[{i}].{key} 타입 불일치 (기대: {typ.__name__}).")
            if s["status"] not in ALLOWED_STATUS:
                _err(f"steps[{i}].status='{s['status']}' 허용되지 않음 (허용: {sorted(ALLOWED_STATUS)}).")
            if s["step"] in seen:
                _err(f"step 번호 중복: {s['step']}")
            seen.add(s["step"])

    @classmethod
    def _resolve_timeout(cls) -> int:
        raw = os.environ.get("FORGE_CLAUDE_TIMEOUT", "").strip()
        if not raw:
            return cls.CLAUDE_TIMEOUT_SEC
        try:
            v = int(raw)
            if v <= 0:
                raise ValueError
            return v
        except ValueError:
            log.warning("FORGE_CLAUDE_TIMEOUT=%r 무효 — 기본값 %d 사용", raw, cls.CLAUDE_TIMEOUT_SEC)
            return cls.CLAUDE_TIMEOUT_SEC

    def run(self):
        self._print_header()
        self._check_blockers()
        self._checkout_branch()
        guardrails = self._load_guardrails()
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._finalize()

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(
                f"ERROR: {p} JSON 파싱 실패 (line {e.lineno}, col {e.colno}): {e.msg}",
                file=sys.stderr,
            )
            sys.exit(1)

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- git ---

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=self._root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print("  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        verify = self._run_git("rev-parse", "--verify", branch)
        if verify.returncode == 0:
            # 기존 브랜치로 전환 — 미커밋 변경사항이 있으면 충돌 위험 → dirty tree 검사
            status = self._run_git("status", "--porcelain")
            if status.returncode == 0 and status.stdout.strip() and not self._force:
                print(
                    "  ERROR: 작업 트리에 변경사항이 있습니다.\n"
                    "  git stash 하거나 commit한 후 다시 시도하세요. 또는 --force로 우회할 수 있습니다.",
                    file=sys.stderr,
                )
                sys.exit(1)
            r = self._run_git("checkout", branch)
        else:
            # 새 브랜치 생성 — 미커밋 변경사항은 새 브랜치로 함께 이동되므로 안전
            r = self._run_git("checkout", "-b", branch)

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print("  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        _qprint(f"  Branch: {branch}")

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"phases/{self.PHASES_SUBDIR}/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{self.PHASES_SUBDIR}/{self._phase_dir_name}/index.json"

        self._run_git("add", "-A")
        self._run_git("reset", "HEAD", "--", output_rel)
        self._run_git("reset", "HEAD", "--", index_rel)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                _qprint(f"  Commit: {msg}")
            else:
                log.warning("코드 커밋 실패: %s", r.stderr.strip())

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                log.warning("housekeeping 커밋 실패: %s", r.stderr.strip())

    # --- top-level index ---

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                ts_key = {"completed": "completed_at", "error": "failed_at", "blocked": "blocked_at"}.get(status)
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    def _load_guardrails(self) -> str:
        if hasattr(self, "_index_file"):
            index = self._read_json(self._index_file)
            guardrails = index.get("guardrails") or {"mode": "root", "docs": []}
        else:
            guardrails = {"mode": "root", "docs": []}
        loader = FullGuardrailLoader(
            ROOT,
            strict=getattr(self, "_strict", False),
            compact_docs=getattr(self, "_compact_docs", False),
            max_bytes=getattr(self, "_max_guardrail_bytes", DEFAULT_MAX_GUARDRAIL_BYTES),
        )
        try:
            return loader.load(guardrails)
        except (ValueError, FileNotFoundError) as e:
            _err(f"guardrail 로딩 실패: {e}")

    def _warn_placeholders(self, path: Path, text: str) -> None:
        matches = PLACEHOLDER_RE.findall(text)
        if not matches:
            return
        sample = matches[0]
        log.warning(
            "%s: placeholder 감지 — %d건 (예: %s). 작성하거나 삭제하세요.",
            path,
            len(matches),
            sample,
        )
        if getattr(self, "_strict", False):
            print(
                f"ERROR: --strict 모드 — placeholder가 남아 있습니다: {path}",
                file=sys.stderr,
            )
            sys.exit(1)

    @staticmethod
    def _build_step_context(index: dict) -> str:
        sorted_steps = sorted(index["steps"], key=lambda s: s["step"])
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in sorted_steps
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def _build_preamble(self, guardrails: str, step_context: str, prev_error: Optional[str] = None) -> str:
        commit_example = self.FEAT_MSG.format(phase=self._phase_name, num="N", name="<step-name>")
        retry_section = ""
        if prev_error:
            retry_section = f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n{prev_error}\n\n---\n\n"
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{retry_section}"
            f"## 작업 규칙\n\n"
            f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            f"3. 기존 테스트를 깨뜨리지 마라.\n"
            f"4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
            f"5. /phases/{self.PHASES_SUBDIR}/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            f'   - AC 통과 → "completed" + "summary" 필드에 이 step의 산출물을 한 줄로 요약\n'
            f'   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → "error" + "error_message" 기록\n'
            f'   - 사용자 개입이 필요한 경우 (API 키, 인증, 수동 설정 등) → "blocked" + '
            f'"blocked_reason" 기록 후 즉시 중단\n'
            f"6. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    # --- Claude 호출 ---

    # M4: _invoke_claude는 흐름만 관장 — 명령 빌드/실행/정규화/저장은 헬퍼로 분리
    def _invoke_claude(self, step: dict, preamble: str) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            return self._handle_missing_step_file(step_num, step_name, step_file)

        prompt = preamble + step_file.read_text(encoding="utf-8")
        cmd, stdin_input = self._build_claude_invocation(prompt)
        returncode, stdout, stderr = self._run_claude(cmd, stdin_input)

        if returncode != 0:
            print(f"\n  WARN: Claude가 비정상 종료됨 (code {returncode})")
            if stderr:
                print(f"  stderr: {stderr[:500]}")

        output = {
            "step": step_num,
            "name": step_name,
            "exitCode": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        self._persist_step_output(step_num, output)
        return output

    def _handle_missing_step_file(self, step_num: int, step_name: str, step_file: Path) -> dict:
        # C9: step.md 미존재 → blocked + 사용자 안내
        reason = f"step{step_num}.md 파일이 없습니다 ({step_file}). 작성 후 status를 'pending'으로 reset하세요."
        self._mark_step_blocked(step_num, reason)
        output = {
            "step": step_num,
            "name": step_name,
            "exitCode": -2,
            "stdout": "",
            "stderr": reason,
        }
        self._persist_step_output(step_num, output)
        return output

    def _build_claude_invocation(self, prompt: str):
        """C7: 긴 prompt는 stdin, 짧은 prompt는 argv. (cmd, stdin_input) 튜플 반환."""
        base_cmd = ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json",
                    "--model", FULL_CLAUDE_MODEL, "--effort", FULL_CLAUDE_EFFORT]
        if len(prompt) > PROMPT_ARGV_LIMIT:
            return base_cmd, prompt
        return base_cmd + [prompt], None

    def _run_claude(self, cmd, stdin_input):
        """Claude subprocess 호출. 타임아웃은 비정상 종료로 정규화 → retry 루프 합류."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self._root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._claude_timeout,
                input=stdin_input,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as e:
            partial_stdout = e.stdout or ""
            partial_stderr = e.stderr or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            if isinstance(partial_stderr, bytes):
                partial_stderr = partial_stderr.decode("utf-8", errors="replace")
            print(
                f"\n  WARN: Claude CLI 타임아웃 ({self._claude_timeout}s) — retry 루프로 진입",
                file=sys.stderr,
            )
            return -1, partial_stdout, (f"Claude CLI timed out after {self._claude_timeout}s.\n" + partial_stderr)

    def _persist_step_output(self, step_num: int, output: dict) -> None:
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    def _mark_step_blocked(self, step_num: int, reason: str) -> None:
        index = self._read_json(self._index_file)
        ts = self._stamp()
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "blocked"
                s["blocked_reason"] = reason
                s["blocked_at"] = ts
                break
        self._write_json(self._index_file, index)

    # --- 헤더 & 검증 ---

    def _print_header(self):
        _qprint(f"\n{'=' * 60}")
        _qprint("  Forge Step Executor")
        _qprint(f"  Phase: {self._phase_name} | Steps: {self._total}")
        if self._auto_push:
            _qprint("  Auto-push: enabled")
        _qprint(f"{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        # C3: 정방향 정렬 순회 — 첫 error → exit 1, 첫 blocked → exit 2
        # 사용자가 steps 배열 순서를 잘못 작성해도 동작 보장
        for s in sorted(index["steps"], key=lambda x: x["step"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print("  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print("  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- 실행 루프 ---

    # M4 (Extract Method): _execute_single_step은 흐름만 관장 — status별 처리는 헬퍼로 분리
    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 sys.exit으로 종료."""
        step_num, step_name = step["step"], step["name"]
        done_count = self._completed_step_count()
        prev_error: Optional[str] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            elapsed = self._run_attempt(step, guardrails, prev_error, attempt, done_count)

            status = self._read_step_status(step_num)
            if status == "completed":
                self._record_step_completion(step_num, step_name, elapsed)
                return True
            if status == "blocked":
                self._record_step_blocked_exit(step_num, step_name, elapsed)
                # _record_step_blocked_exit는 sys.exit(2)로 종료
            err_msg = self._read_step_error(step_num)
            if attempt < self.MAX_RETRIES:
                prev_error = err_msg
                self._record_step_retry(step_num, attempt, err_msg)
            else:
                self._record_step_final_failure(step_num, step_name, err_msg, elapsed)
                # _record_step_final_failure는 sys.exit(1)로 종료

        return False  # unreachable — 위 분기에서 항상 sys.exit 또는 return True

    def _run_attempt(
        self, step: dict, guardrails: str, prev_error: Optional[str], attempt: int, done_count: int
    ) -> int:
        """단일 시도(progress + Claude 호출). KeyboardInterrupt는 interrupted 처리."""
        step_num, step_name = step["step"], step["name"]
        index = self._read_json(self._index_file)
        step_context = self._build_step_context(index)
        preamble = self._build_preamble(guardrails, step_context, prev_error)

        tag = f"Step {step_num}/{self._total - 1} ({done_count} done): {step_name}"
        if attempt > 1:
            tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

        try:
            with progress_indicator(tag) as pi:
                self._invoke_claude(step, preamble)
                return int(pi.elapsed)
        except KeyboardInterrupt:
            self._mark_step_interrupted(step_num)
            print(
                f"\n  ⚠ Interrupted. Step {step_num} ({step_name}) marked as 'interrupted'.",
                file=sys.stderr,
            )
            sys.exit(130)

    def _completed_step_count(self) -> int:
        return sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")

    def _read_step_status(self, step_num: int) -> str:
        index = self._read_json(self._index_file)
        return next(
            (s.get("status", "pending") for s in index["steps"] if s["step"] == step_num),
            "pending",
        )

    def _read_step_error(self, step_num: int) -> str:
        index = self._read_json(self._index_file)
        return next(
            (s.get("error_message", "Step did not update status") for s in index["steps"] if s["step"] == step_num),
            "Step did not update status",
        )

    def _record_step_completion(self, step_num: int, step_name: str, elapsed: int) -> None:
        index = self._read_json(self._index_file)
        ts = self._stamp()
        for s in index["steps"]:
            if s["step"] == step_num:
                s["completed_at"] = ts
                break
        self._write_json(self._index_file, index)
        self._commit_step(step_num, step_name)
        _qprint(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")

    def _record_step_blocked_exit(self, step_num: int, step_name: str, elapsed: int) -> None:
        index = self._read_json(self._index_file)
        ts = self._stamp()
        reason = ""
        for s in index["steps"]:
            if s["step"] == step_num:
                s["blocked_at"] = ts
                reason = s.get("blocked_reason", "")
                break
        self._write_json(self._index_file, index)
        print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
        print(f"    Reason: {reason}")
        self._update_top_index("blocked")
        sys.exit(2)

    def _record_step_retry(self, step_num: int, attempt: int, err_msg: str) -> None:
        index = self._read_json(self._index_file)
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "pending"
                s.pop("error_message", None)
                break
        self._write_json(self._index_file, index)
        _qprint(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")

    def _record_step_final_failure(self, step_num: int, step_name: str, err_msg: str, elapsed: int) -> None:
        index = self._read_json(self._index_file)
        ts = self._stamp()
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "error"
                s["error_message"] = f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}"
                s["failed_at"] = ts
                break
        self._write_json(self._index_file, index)
        self._commit_step(step_num, step_name)
        print(f"  ✗ Step {step_num}: {step_name} failed after {self.MAX_RETRIES} attempts [{elapsed}s]")
        print(f"    Error: {err_msg}")
        self._update_top_index("error")
        sys.exit(1)

    def _mark_step_interrupted(self, step_num: int) -> None:
        try:
            index = self._read_json(self._index_file)
        except SystemExit:
            return  # 인덱스가 손상된 경우 더 이상 손쓸 수 없음
        ts = self._stamp()
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "interrupted"
                s["interrupted_at"] = ts
                break
        self._write_json(self._index_file, index)

    def _execute_all_steps(self, guardrails: str):
        # H6: 무한 루프 방어 — 진행 보장 + 카운터 한도
        max_iterations = max(1, self._total) * (self.MAX_RETRIES + 2)
        iterations = 0

        while True:
            iterations += 1
            if iterations > max_iterations:
                print(
                    f"\n  ERROR: 무한 루프 의심 — {iterations - 1}회 반복 후에도 종료 조건 미달성. "
                    f"index.json을 확인하세요.",
                    file=sys.stderr,
                )
                sys.exit(1)

            index = self._read_json(self._index_file)
            sorted_steps = sorted(index["steps"], key=lambda s: s["step"])
            pending = next((s for s in sorted_steps if s["status"] == "pending"), None)
            if pending is None:
                _qprint("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._execute_single_step(pending, guardrails)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._run_git("add", "-A")
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                _qprint(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            _qprint(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'=' * 60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'=' * 60}")


def _is_trusted(flag: bool) -> bool:
    if flag:
        return True
    raw = os.environ.get("FORGE_TRUST", "").strip().lower()
    return raw in ("1", "true", "yes")


def _require_trust(flag: bool) -> None:
    if _is_trusted(flag):
        return
    print(
        "ERROR: 이 도구는 Claude에 대해 '--dangerously-skip-permissions'을 사용합니다.\n"
        "       Claude는 권한 확인 없이 임의 파일을 읽기/쓰기/실행하고 Bash 명령을\n"
        "       실행할 수 있습니다. 옵트인 후 다시 실행하세요.\n"
        "\n"
        "  옵트인 방법 (택 1):\n"
        "    FORGE_TRUST=1 python scripts/forge_full.py <phase-dir>\n"
        "    python scripts/forge_full.py <phase-dir> --trust\n"
        "\n"
        "  주의: FORGE_TRUST를 셸 rc 파일 등에 영구 설정하지 마세요. 매 실행마다\n"
        "        의식적으로 활성화하는 것을 권장합니다.\n",
        file=sys.stderr,
    )
    sys.exit(1)


def _install_signal_handlers() -> None:
    if sys.platform == "win32":
        return

    # SIGTERM을 KeyboardInterrupt로 변환하여 _execute_single_step의 finally 경로에 합류
    def _raise_kbi(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, _raise_kbi)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    parser.add_argument(
        "--trust", action="store_true", help="Opt-in to --dangerously-skip-permissions (also: FORGE_TRUST=1)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Bypass dirty git tree check on branch checkout / plan generation"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG-level forge logging to stderr")
    parser.add_argument("--strict", action="store_true", help="Fail when CLAUDE.md/docs contain {placeholder} patterns")
    parser.add_argument("--prompt", action="append", default=None, help="문서 기반 full splitter 입력 (반복 가능)")
    parser.add_argument("--doc", action="append", default=None, help="guardrail 문서 경로 (docs/ 하위 .md, 반복 가능)")
    parser.add_argument("--yes", action="store_true", help="splitter plan 승인 자동화")
    parser.add_argument("--quiet", action="store_true", help="진행/commit 출력 최소화")
    parser.add_argument(
        "--preset",
        choices=sorted(VALID_PRESETS),
        default="auto",
        help="auto=문서 기반 splitter, contract-tdd=고정 TDD 4-step",
    )
    parser.add_argument("--compact-docs", action="store_true", help="guardrail 문서를 핵심 섹션 중심으로 압축")
    parser.add_argument(
        "--docs-mode",
        choices=sorted(VALID_docs_MODES),
        default=None,
        help="root=docs/*.md, recursive=docs/**/*.md, explicit=--doc만",
    )
    parser.add_argument("--plan-only", action="store_true", help="plan을 생성/검증/출력만 하고 파일을 쓰지 않음")
    parser.add_argument(
        "--max-guardrail-bytes",
        type=int,
        default=DEFAULT_MAX_GUARDRAIL_BYTES,
        help=f"guardrail 최대 bytes (default: {DEFAULT_MAX_GUARDRAIL_BYTES})",
    )
    return parser


def _has_plan_input(args) -> bool:
    return bool(args.prompt or args.doc or args.plan_only or args.preset != "auto")


def _phase_dir_for(phase: str) -> Path:
    return ROOT / "phases" / "full" / phase


def _refuse_existing_phase_for_plan(phase: str) -> None:
    phase_dir = _phase_dir_for(phase)
    if not phase_dir.exists():
        return
    if (phase_dir / "index.json").exists() or list(phase_dir.glob("step*.md")):
        _err(f"기존 phases/full/{phase} phase가 있어 plan 생성으로 덮어쓰지 않습니다.")
    if any(phase_dir.iterdir()):
        _err(f"비어 있지 않은 phase 디렉토리가 있어 plan 생성 중단: {phase_dir}")


def _check_dirty_tree_for_plan(force: bool) -> None:
    if force:
        return
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0 and result.stdout.strip():
        _err(
            "작업 트리에 변경사항이 있어 신규 plan 생성을 중단합니다. "
            "commit/stash 후 재실행하거나 --force를 사용하세요."
        )


def _guardrails_from_args(args) -> dict:
    docs = []
    for d in args.doc or []:
        docs.append(d.lstrip("/"))
    mode = args.docs_mode
    if mode is None:
        mode = "explicit" if docs else "recursive"
    if mode == "explicit" and not docs:
        _err("--docs-mode=explicit은 --doc이 1개 이상 필요합니다.")
    return {"mode": mode, "docs": docs}


def _docs_for_readiness(guardrails: dict) -> list[Path]:
    loader = FullGuardrailLoader(ROOT, max_bytes=0)
    return loader._select_docs(guardrails["mode"], list(guardrails.get("docs") or []))


def _handle_readiness(readiness: dict) -> None:
    severity = readiness["severity"]
    if severity in ("clear", "warning"):
        if severity == "warning":
            for issue in readiness["issues"]:
                print(f"WARNING: {issue['file']}: {issue['message']}", file=sys.stderr)
        return
    print("ERROR: 문서 기반 plan 생성 전에 사용자 결정이 필요합니다.", file=sys.stderr)
    for issue in readiness["issues"]:
        print(
            f"  - [{issue['severity']}] {issue['file']}: {issue['message']}",
            file=sys.stderr,
        )
    sys.exit(2)


def _check_contract_frd_ready(docs: list[str], force: bool) -> None:
    if force or len(docs) != 1:
        return
    doc_path = FullGuardrailPathValidator(ROOT).validate_one(docs[0].lstrip("/"))
    readiness = FullDocReadinessChecker(ROOT).check([doc_path])
    if readiness["severity"] in ("question", "blocked"):
        _handle_readiness(readiness)


def _print_plan(plan: dict) -> None:
    print(f"Plan: {plan['phase']} (project: {plan['project']})")
    guardrails = plan.get("guardrails", {})
    print(f"Guardrails: {guardrails.get('mode')} ({len(guardrails.get('docs') or [])} docs)")
    for step in plan["steps"]:
        print(f"  [{step['step']}] {step['name']}: {step['brief']}")


def _confirm_plan(args) -> None:
    if args.yes or args.plan_only:
        return
    answer = input("Create this forge-full phase? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        _err("사용자가 plan 생성을 취소했습니다.")


def _create_plan(args) -> dict:
    StepExecutor._validate_phase_dir_name(args.phase_dir)
    _refuse_existing_phase_for_plan(args.phase_dir)
    if not args.plan_only:
        _check_dirty_tree_for_plan(args.force)
    guardrails = _guardrails_from_args(args)
    docs = _docs_for_readiness(guardrails)
    readiness = FullDocReadinessChecker(ROOT).check(docs)
    if args.preset == "contract-tdd":
        _check_contract_frd_ready(guardrails["docs"], args.force)
        plan = FullContractTddPlanBuilder(ROOT).build(
            args.phase_dir,
            guardrails["docs"],
            args.prompt or [],
            guardrails,
        )
    else:
        _handle_readiness(readiness)
        if not args.prompt:
            _err("신규 forge-full plan 생성에는 --prompt가 필요합니다.")
        plan = FullStepSplitter(ROOT).build(args.phase_dir, args.prompt or [], docs, guardrails)
    FullPlanValidator.validate(plan, phase_dir=args.phase_dir, root=ROOT)
    return plan


def main():
    parser = _build_parser()
    args = parser.parse_args()

    global _QUIET
    _QUIET = bool(args.quiet)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    _install_signal_handlers()
    _require_trust(args.trust)

    if _has_plan_input(args):
        if (_phase_dir_for(args.phase_dir) / "index.json").exists():
            _err(
                "기존 full phase에는 plan 생성 옵션(--prompt/--doc/--preset/--plan-only)을 "
                "사용하지 않습니다. 기존 phase 실행은 해당 옵션 없이 재실행하세요."
            )
        plan = _create_plan(args)
        _print_plan(plan)
        if args.plan_only:
            return
        _confirm_plan(args)
        FullPlanEmitter(ROOT).emit(plan)

    executor = StepExecutor(
        args.phase_dir,
        auto_push=args.push,
        force=args.force,
        strict=args.strict,
        quiet=args.quiet,
        compact_docs=args.compact_docs,
        max_guardrail_bytes=args.max_guardrail_bytes,
    )
    executor.run()


if __name__ == "__main__":
    main()
