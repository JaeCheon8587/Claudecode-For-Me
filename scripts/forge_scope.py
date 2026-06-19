#!/usr/bin/env python3
"""
Forge Scope Executor — 사용자 prompt 또는 단일 doc 입력으로 step을 자동 분할하고 순차 실행한다.

forge_full.py의 경량(scoped) 변종. 차이점 두 가지:
1. 가드레일은 CLAUDE.md + index.json의 `docs_scope` 화이트리스트만 결합 (docs/*.md 전체 자동 인입 X).
2. 첫 실행 시 사용자 prompt/doc → 단일 Claude 호출로 step 분할 plan 생성 → 사용자 승인 후 파일 일괄 기록.

Usage:
    python3 scripts/forge_scope.py <phase-dir> [--prompt="..."]... [--doc=<path>]...
                                   [--push] [--trust] [--force] [--verbose] [--yes]

Environment:
    FORGE_TRUST=1            --trust 대신 사용 가능 (--dangerously-skip-permissions 옵트인)
    FORGE_CLAUDE_TIMEOUT     Claude CLI 타임아웃(초). 미설정 시 1800.
    FORGE_DEFAULT_SLN        다수 sln 존재 시 기본값 (repo root 기준 상대경로). 예: Src/Foo/Foo.sln
                             forge-scope.json의 default_sln 키보다 우선. --sln CLI가 최우선.
"""

import sys

# Encoding bootstrap (must be FIRST executable code) — Windows cp949 콘솔 회피
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import argparse
import atexit
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import stat as _stat
import subprocess
import threading
import time
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("forge_scope")

# --- Constants (forge_full.py에서 import 금지 — 재선언) ---
PHASE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
STEP_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STEP_FILE_RE = re.compile(r"^step\d+\.md$")
DOC_REL_RE = re.compile(r"^[Dd]ocs/[A-Za-z0-9._/-]+\.md$")
ALLOWED_STATUS = frozenset({"pending", "completed", "error", "blocked", "interrupted"})
PROMPT_ARGV_LIMIT = 8_000 if os.name == "nt" else 100_000
PLACEHOLDER_RE = re.compile(r"\{[^}\n]+\}")
PHASES_SUBDIR = "scoped"
DOC_BYTES_LIMIT = 200_000
SPLIT_PROMPT_BYTES_LIMIT = 800_000
MAX_STEPS_PER_PLAN = 30
SUMMARY_CHAR_LIMIT = 240
COMPACT_DOC_BYTES_LIMIT = 24_000
TZ = timezone(timedelta(hours=9))
EXIT_OK, EXIT_ERR, EXIT_BLOCKED, EXIT_KBI = 0, 1, 2, 130
VALID_PRESETS = frozenset({"auto", "frd-implementation", "contract-tdd"})
# child claude가 실제 쓰는 빌트인 tool 최소 집합 (lean 모드). 파일 읽기/수정/쓰기 +
# bash(dotnet/git/rg) + grep/glob. MCP/skill은 lean 플래그로 별도 차단된다.
DEFAULT_CHILD_TOOLS = "Bash,Edit,Read,Write,Grep,Glob"


def _docs_dirname(root: Path) -> str:
    """디스크상의 실제 docs 디렉토리 이름('docs' 또는 'Docs')을 반환.

    대소문자 무시 FS(Windows)에서도 os.scandir는 저장된 실제 이름을 보고하므로 정확하다.
    둘 다 없으면 기본값 'docs'."""
    try:
        for e in os.scandir(root):
            if e.is_dir() and e.name in ("docs", "Docs"):
                return e.name
    except OSError:
        pass
    return "docs"


class SlnResolveError(RuntimeError):
    """sln 경로 해석 실패 (다수/부재 등)."""


def _read_forge_config_str(root: Path, key: str) -> str | None:
    """consumer repo의 forge-scope.json에서 문자열 키 읽기. 부재/파싱 실패/비문자열 시 None."""
    cfg = root / "forge-scope.json"
    if not cfg.is_file():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("forge-scope.json 파싱 실패(무시): %s", e)
        return None
    val = data.get(key)
    return val if isinstance(val, str) and val.strip() else None


def _read_default_sln_from_config(root: Path) -> str | None:
    """consumer repo의 forge-scope.json에서 default_sln 읽기. 부재/파싱 실패 시 None."""
    return _read_forge_config_str(root, "default_sln")


def _validate_target_rel(root: Path, raw: str) -> str:
    """test 타깃 csproj 상대경로 검증 — root 하위 + 존재. rel(posix) 반환. 위반 시 ValueError."""
    p = (root / raw).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError as e:
        raise ValueError(f"repo root 밖을 가리킵니다: {raw}") from e
    if not p.exists():
        raise ValueError(f"경로 없음: {raw}")
    return p.relative_to(root).as_posix()


def resolve_ac_test_target(root: Path, cli_test_target: str | None) -> str | None:
    """single-step AC(`dotnet test`)와 warmup restore가 공유하는 테스트 타깃(rel csproj posix).

    우선순위: CLI --test-target > forge-scope.json test_target > 단일 Src/Tests/**/*.csproj.
    스코프 불가/무효 경로면 None → 호출부가 풀 sln fallback. warmup·AC가 같은 함수를
    쓰므로 warmup 스코프 ⊇ AC build 스코프가 보장되어 `--no-restore`가 깨지지 않는다.
    """
    raw = cli_test_target or _read_forge_config_str(root, "test_target")
    if raw:
        try:
            return _validate_target_rel(root, raw)
        except ValueError as e:
            log.warning("test_target 무시 — %s", e)
            return None
    test_projects = sorted(root.glob("Src/Tests/**/*.csproj"))
    if len(test_projects) == 1:
        return test_projects[0].relative_to(root).as_posix()
    return None


def resolve_sln_path(
    arg_sln: str | None,
    root: Path,
    *,
    strict: bool,
) -> Path | None:
    """contract-tdd 등에서 사용할 sln 경로 결정.

    우선순위:
    1. arg_sln (CLI --sln=...) — 명시 경로 검증 후 반환
    2. FORGE_DEFAULT_SLN 환경변수
    3. forge-scope.json 의 default_sln 키 (consumer repo root)
    4. Src/*.sln → Src/*/*.sln auto-detect
       - 1개 = 자동 채택
       - 0개 = None (strict=False) 또는 SlnResolveError (strict=True)
       - 다수 = 후보 목록과 함께 SlnResolveError (strict 무관: 다수는 항상 명시 강제)
    """
    if arg_sln:
        p = (root / arg_sln).resolve()
        if not p.is_file():
            raise SlnResolveError(f"--sln 경로 없음: {arg_sln}")
        try:
            p.relative_to(root.resolve())
        except ValueError as e:
            raise SlnResolveError(
                f"--sln 은 repo root({root}) 하위여야 합니다: {arg_sln}"
            ) from e
        return p
    env_sln = os.environ.get("FORGE_DEFAULT_SLN", "").strip()
    if env_sln:
        return resolve_sln_path(env_sln, root, strict=strict)
    cfg_sln = _read_default_sln_from_config(root)
    if cfg_sln:
        return resolve_sln_path(cfg_sln, root, strict=strict)
    src_dir = root / "Src"
    if not src_dir.is_dir():
        if strict:
            raise SlnResolveError("Src/ 디렉터리 부재. --sln 명시 필요.")
        return None
    candidates: list[Path] = sorted(src_dir.glob("*.sln"))
    if not candidates:
        candidates = sorted(src_dir.glob("*/*.sln"))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        if strict:
            raise SlnResolveError(
                "Src/*.sln / Src/*/*.sln 모두 부재. --sln 명시 필요."
            )
        return None
    rels = [c.relative_to(root).as_posix() for c in candidates]
    raise SlnResolveError(
        "Src/ 하위 다수 sln 발견 — --sln 또는 FORGE_DEFAULT_SLN 또는 forge-scope.json 명시 필요.\n"
        "  후보:\n" + "\n".join(f"    - {r}" for r in rels)
    )

COMPACT_DOC_HEADINGS = (
    "## 1. 기능 개요",
    "## 4. 기본 흐름",
    "## 5. 대안 흐름",
    "## 7. 상세 기능 요구사항",
    "## 8. 입력값",
    "## 9. 출력값",
    "## 12. 데이터 처리 규칙",
    "## 14. 관련 API",
    "## 17. 테스트 기준",
)

REQUIRED_STEP_HEADINGS = (
    "## 읽어야 할 파일",
    "## 작업",
    "## Acceptance Criteria",
    "## 검증 절차",
    "## 금지사항",
)

# --quiet 모드 플래그. main()에서 args.quiet에 따라 설정된다.
# 부모 Claude Code 세션의 stdout 누적을 줄이기 위해 진행 표시기·헤더·step별
# 진행 메시지를 억제하고, 최종 phase 완료 한 줄 + 에러만 출력한다.
_QUIET = False


def _qprint(*args, **kwargs) -> None:
    """_QUIET이 True면 no-op, 아니면 print 위임."""
    if _QUIET:
        return
    print(*args, **kwargs)


def _fmt_tokens(n: int) -> str:
    """output_tokens를 짧게 표기. 1000 이상은 '1.2k'."""
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def _truncate_text(text: str, limit: int) -> str:
    """긴 summary/error/doc 조각이 후속 prompt를 계속 비대하게 만들지 않도록 자른다."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + " ... [truncated]"


def _compact_markdown_doc(text: str) -> str:
    """FRD류 문서에서 구현에 필요한 핵심 H2 섹션만 남긴다.

    Markdown 전문을 prompt에 매번 주입하면 scoped 실행의 이점이 사라진다. 구조화된
    문서는 구현 판단에 필요한 섹션만 추출하고, 구조를 알 수 없는 문서는 상한까지
    앞부분만 사용한다.
    """
    preamble = text.split("\n## ", 1)[0].strip()
    sections: list[str] = []
    for heading in COMPACT_DOC_HEADINGS:
        pattern = re.compile(
            rf"^{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s|\Z)",
            re.MULTILINE,
        )
        match = pattern.search(text)
        if match:
            sections.append(f"{heading}\n{match.group(1).strip()}")
    if sections:
        compact = "\n\n".join([preamble] + sections if preamble else sections)
    else:
        compact = text[:COMPACT_DOC_BYTES_LIMIT]
    return _truncate_text(compact, COMPACT_DOC_BYTES_LIMIT)


def _is_nested_under_claude() -> bool:
    """현재 프로세스가 Claude Code 부모 세션 내부에서 spawn됐는지 감지.

    True인 경우 ClaudeInvoker는 자식 claude CLI에 --dangerously-skip-permissions를
    붙이지 않는다. 부모 하네스가 nested skip-perm spawn을 자율 루프 방지 차원에서
    차단하므로(v2.1.128~), 그 플래그를 떼고 부모 권한 컨텍스트를 상속받아 호출한다.
    """
    for var in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_PROJECT_DIR"):
        if os.environ.get(var):
            return True
    if os.environ.get("AI_AGENT", "").startswith("claude-code"):
        return True
    return False


def _bare_is_safe() -> bool:
    """--bare 플래그를 자식 claude에 붙여도 안전한 환경인지 판정.

    --bare는 CLAUDE.md/hooks/plugins뿐 아니라 OAuth 로그인 자격 증명도 함께 스킵한다.
    따라서 ANTHROPIC_API_KEY가 환경에 없으면 자식이 "Not logged in"으로 즉시 종료된다.
    API key가 설정된 경우에만 True를 반환하여 token 절감용 --bare를 활성화한다.
    """
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다."""
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


# ============================================================================
# PhaseConfig — phase 이름 검증, 경로 해석, phases/full/ 접근 거부
# ============================================================================
class PhaseConfig:
    """phase 디렉토리 경로를 검증·해석한다. phases/full/ 접근은 여기서 차단된다."""

    def __init__(self, phase_dir_name: str, root: Optional[Path] = None):
        self._validate_name(phase_dir_name)
        if root is None:
            root = ROOT
        self._phase_dir_name = phase_dir_name
        self._root = root
        self._phases_dir = root / "phases" / PHASES_SUBDIR
        self._phase_dir = self._phases_dir / phase_dir_name
        self._index_file = self._phase_dir / "index.json"
        self._top_index_file = self._phases_dir / "index.json"
        self._verify_resolution()

    @property
    def phase_dir_name(self) -> str:
        return self._phase_dir_name

    @property
    def phase_dir(self) -> Path:
        return self._phase_dir

    @property
    def phases_dir(self) -> Path:
        return self._phases_dir

    @property
    def index_file(self) -> Path:
        return self._index_file

    @property
    def top_index_file(self) -> Path:
        return self._top_index_file

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            print("ERROR: phase 디렉토리 이름이 비어 있습니다.", file=sys.stderr)
            sys.exit(EXIT_ERR)
        if Path(name).is_absolute():
            print(f"ERROR: 절대경로는 허용되지 않습니다: {name}", file=sys.stderr)
            sys.exit(EXIT_ERR)
        bad = [c for c in ("/", "\\", ":", "..") if c in name]
        if bad:
            print(
                f"ERROR: phase 디렉토리 이름에 금지된 문자/시퀀스 포함: {bad} ({name!r})",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        if not PHASE_NAME_RE.match(name):
            print(
                f"ERROR: phase 디렉토리 이름은 [A-Za-z0-9._-] 만 허용됩니다: {name!r}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

    def _verify_resolution(self) -> None:
        try:
            phase_resolved = self._phase_dir.resolve()
            phases_resolved = self._phases_dir.resolve()
        except (OSError, RuntimeError) as e:
            print(f"ERROR: phase 경로 해석 실패: {e}", file=sys.stderr)
            sys.exit(EXIT_ERR)
        if phases_resolved not in phase_resolved.parents and phase_resolved != phases_resolved:
            print(
                f"ERROR: phase 경로가 phases/scoped/ 디렉토리 밖을 가리킵니다: {phase_resolved}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        # phases/full/ 직접 접근 명시적 거부 (방어선)
        full_dir = (self._root / "phases" / "full").resolve()
        if full_dir == phase_resolved or full_dir in phase_resolved.parents:
            print(
                "ERROR: phases/full/ 접근 금지 — forge_full.py를 사용하세요.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)


# ============================================================================
# ScopeValidator — docs_scope 항목 path-traversal 검증
# ============================================================================
class ScopeValidator:
    """docs_scope 항목을 검증한다. ROOT/docs/ 외부를 가리키면 거부한다."""

    def __init__(self, root: Optional[Path] = None):
        if root is None:
            root = ROOT
        self._root = root.resolve()
        self._docs_root = (root / _docs_dirname(root)).resolve()

    def validate_many(self, entries: Iterable[str]) -> list[Path]:
        """모든 항목을 검증하여 절대 경로 리스트를 반환한다. 첫 위반 시 ValueError."""
        return [self._validate_one(e) for e in entries]

    def _validate_one(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel:
            raise ValueError(f"docs_scope 항목 비정상 (빈 문자열 또는 비-문자열): {rel!r}")
        if len(rel) > 256:
            raise ValueError(f"docs_scope 경로가 너무 깁니다 (>256): {rel}")
        if Path(rel).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", rel):
            raise ValueError(f"절대 경로 금지: {rel}")
        if "\\" in rel:
            raise ValueError(f"백슬래시 금지 — '/' 사용: {rel}")
        parts = rel.split("/")
        if any(seg in ("", ".", "..") for seg in parts):
            raise ValueError(f"경로 traversal 금지 (빈/. /.. 세그먼트): {rel}")
        if not DOC_REL_RE.match(rel):
            raise ValueError(f"docs/ 하위 .md 파일만 허용됩니다: {rel}")
        candidate = (self._root / rel).resolve()
        if self._docs_root not in candidate.parents and candidate != self._docs_root:
            raise ValueError(f"docs/ 디렉토리 외부를 가리킵니다: {candidate}")
        if not candidate.is_file():
            raise FileNotFoundError(f"docs_scope 파일 없음: {rel}")
        return candidate


# ============================================================================
# GuardrailLoader — CLAUDE.md + 화이트리스트만 결합
# ============================================================================
class GuardrailLoader:
    """CLAUDE.md와 docs_scope에 명시된 파일만 결합한다. docs/*.md 전체를 인입하지 않는다."""

    def __init__(self, root: Path, validator: ScopeValidator, *, strict: bool = False, compact_docs: bool = False):
        self._root = root
        self._validator = validator
        self._strict = strict
        self._compact_docs = compact_docs

    def load(self, docs_scope: list[str]) -> str:
        sections = []
        claude_md = self._root / "CLAUDE.md"
        if claude_md.exists():
            text = claude_md.read_text(encoding="utf-8")
            self._warn_placeholders(claude_md, text)
            sections.append(f"## 프로젝트 규칙 (CLAUDE.md)\n\n{text}")
        if not docs_scope:
            _qprint("  docs_scope가 비어 있어 CLAUDE.md만 가드레일로 주입됩니다.")
        else:
            paths = self._validator.validate_many(docs_scope)
            # 정렬하지 않음 — 사용자가 기록한 순서를 그대로 보존
            for p in paths:
                text = p.read_text(encoding="utf-8")
                self._warn_placeholders(p, text)
                rel = p.relative_to(self._root).as_posix()
                if self._compact_docs:
                    text = _compact_markdown_doc(text)
                    sections.append(f"## {rel} (compact)\n\n{text}")
                else:
                    sections.append(f"## {rel}\n\n{text}")
        return "\n\n---\n\n".join(sections) if sections else ""

    def _warn_placeholders(self, path: Path, text: str) -> None:
        matches = PLACEHOLDER_RE.findall(text)
        if not matches:
            return
        sample = matches[0]
        log.warning(
            "%s: placeholder 감지 — %d건 (예: %s).",
            path,
            len(matches),
            sample,
        )
        if self._strict:
            print(
                f"ERROR: --strict 모드 — placeholder가 남아 있습니다: {path}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)


def _extract_usage(raw_stdout: str) -> Optional[dict]:
    """`claude -p --output-format json`의 stdout에서 usage 정보를 추출.

    응답 wrapper 위치는 CLI 버전에 따라 다를 수 있어 여러 후보를 탐색한다.
    찾지 못하면 None 반환 (호출자는 모니터링 정보 누락으로만 처리).
    """
    if not raw_stdout or not raw_stdout.strip():
        return None
    candidates = []
    # 1) 단일 JSON 객체
    try:
        candidates.append(json.loads(raw_stdout))
    except json.JSONDecodeError:
        pass
    # 2) JSON Lines 마지막 줄(이벤트 스트림에서 final result)
    if not candidates:
        for line in reversed([ln for ln in raw_stdout.splitlines() if ln.strip()]):
            try:
                candidates.append(json.loads(line))
                break
            except json.JSONDecodeError:
                continue
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        # 후보 키 경로: usage / response.usage / message.usage
        usage = obj.get("usage")
        if isinstance(usage, dict):
            return usage
        for nested_key in ("response", "message", "result"):
            nested = obj.get(nested_key)
            if isinstance(nested, dict):
                u = nested.get("usage")
                if isinstance(u, dict):
                    return u
    return None


# ============================================================================
# ClaudeInvoker — Claude CLI 호출 (trust 게이트 내부화)
# ============================================================================
class ClaudeInvoker:
    """Claude CLI 호출의 단일 진입점. --dangerously-skip-permissions는 trust=True에서만 부여."""

    DEFAULT_TIMEOUT_SEC = 1800

    def __init__(
        self,
        *,
        trust: bool,
        timeout_sec: Optional[int] = None,
        cwd: Optional[Path] = None,
        session_id: Optional[str] = None,
        use_session: bool = False,
        use_bare: bool = False,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        lean: bool = True,
        child_tools: str = DEFAULT_CHILD_TOOLS,
        exclude_dynamic_sys_prompt: bool = False,
    ):
        self._trust = trust
        self._cwd = cwd if cwd is not None else ROOT
        self._timeout = timeout_sec or self._resolve_timeout_env()
        # 세션 재사용: 첫 호출 시 --session-id로 UUID 고정, 이후 -r로 이어 받음.
        # CLAUDE.md auto-discovery·hooks·plugins은 forge_scope가 직접 가드레일을 박으므로
        # use_bare=True로 중복 로드를 차단해 토큰 절감.
        self._session_id = session_id
        self._use_session = use_session
        self._use_bare = use_bare
        self._model = model
        self._effort = effort  # claude --effort (low|medium|high|xhigh|max). None이면 미부여(세션 기본).
        # lean: API key 유무와 무관하게 MCP 함대/skill cold-load를 차단(--full-fleet로 끔).
        self._lean = lean
        self._child_tools = child_tools
        self._exclude_dynamic_sys_prompt = exclude_dynamic_sys_prompt
        self._first_session_call = True

    def call(self, prompt: str) -> tuple[int, str, str]:
        """Claude를 호출하고 (returncode, stdout, stderr)를 반환한다."""
        cmd, stdin_input = self._route(prompt)
        return self._execute(cmd, stdin_input)

    def _build_cmd(self) -> list[str]:
        cmd = [shutil.which("claude") or "claude", "-p"]
        if self._use_bare and _bare_is_safe():
            cmd.append("--bare")
        if self._trust and not _is_nested_under_claude():
            cmd.append("--dangerously-skip-permissions")
        # Lean startup — API key 유무와 무관(절대 _bare_is_safe() 경유 금지).
        # OAuth regime(--bare 미적용)에서도 MCP 함대·plugin skill cold-load를 차단해
        # 호출당 startup 세금을 제거한다. --bare와 공존해도 중복 차감일 뿐 무해.
        if self._lean:
            cmd += [
                "--mcp-config", '{"mcpServers": {}}', "--strict-mcp-config",
                "--disable-slash-commands",
                "--tools", self._child_tools,
            ]
        if self._exclude_dynamic_sys_prompt:
            cmd.append("--exclude-dynamic-system-prompt-sections")
        cmd += ["--output-format", "json"]
        if self._model:
            cmd += ["--model", self._model]
        if self._effort:
            cmd += ["--effort", self._effort]
        if self._use_session and self._session_id:
            if self._first_session_call:
                cmd += ["--session-id", self._session_id]
                self._first_session_call = False
            else:
                cmd += ["-r", self._session_id]
        return cmd

    def _route(self, prompt: str) -> tuple[list[str], Optional[str]]:
        base = self._build_cmd()
        if len(prompt) > PROMPT_ARGV_LIMIT:
            return base, prompt
        return base + [prompt], None

    def _execute(self, cmd: list[str], stdin_input: Optional[str]) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                input=stdin_input,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            print(
                "ERROR: 'claude' 명령을 찾을 수 없습니다.\n"
                "       Claude Code CLI가 설치되어 있고 PATH에 등록되어 있는지 확인하세요.\n"
                "       설치: https://docs.claude.com/en/docs/claude-code",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        except subprocess.TimeoutExpired as e:
            partial_stdout = e.stdout or ""
            partial_stderr = e.stderr or ""
            if isinstance(partial_stdout, bytes):
                partial_stdout = partial_stdout.decode("utf-8", errors="replace")
            if isinstance(partial_stderr, bytes):
                partial_stderr = partial_stderr.decode("utf-8", errors="replace")
            print(
                f"\n  WARN: Claude CLI 타임아웃 ({self._timeout}s) — retry 루프로 진입",
                file=sys.stderr,
            )
            return -1, partial_stdout, (f"Claude CLI timed out after {self._timeout}s.\n" + partial_stderr)

    @classmethod
    def _resolve_timeout_env(cls) -> int:
        raw = os.environ.get("FORGE_CLAUDE_TIMEOUT", "").strip()
        if not raw:
            return cls.DEFAULT_TIMEOUT_SEC
        try:
            v = int(raw)
            if v <= 0:
                raise ValueError
            return v
        except ValueError:
            log.warning(
                "FORGE_CLAUDE_TIMEOUT=%r 무효 — 기본값 %d 사용",
                raw,
                cls.DEFAULT_TIMEOUT_SEC,
            )
            return cls.DEFAULT_TIMEOUT_SEC


def _is_dir_link(p: Path) -> bool:
    """junction(Windows reparse) 또는 symlink면 True."""
    try:
        if p.is_symlink():
            return True
        if os.name == "nt":
            attrs = p.lstat().st_file_attributes  # type: ignore[attr-defined]
            return bool(attrs & _stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False
    return False


def _make_dir_link(src: Path, dst: Path) -> None:
    """dst → src 디렉토리 링크. Windows=junction(mklink /J, 관리자 불필요), Unix=symlink."""
    if os.name == "nt":
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            raise OSError(r.stderr.strip() or r.stdout.strip() or "mklink /J 실패")
    else:
        os.symlink(src, dst, target_is_directory=True)


# ============================================================================
# WorktreeManager — phase별 .worktrees/<phase>/ 격리 작업 트리 보장
# ============================================================================
class WorktreeManager:
    """phase 시작 시 `.worktrees/<phase>/`에 git worktree를 생성/attach 한다.

    워크트리는 메인 repo와 독립된 working tree를 갖고, branch `feat-<phase>`에
    바인딩된다. phase의 모든 산출물(phases/scoped/, step 코드, commit)은 이
    워크트리 안에서만 발생하고, 메인 repo의 작업 트리는 영향을 받지 않는다.

    완료 후 정리는 사용자가 명시적으로 수행한다 (`git worktree remove` 또는
    forge_cancel.py).
    """

    def __init__(self, main_root: Path, phase_name: str, *, force: bool):
        self._main_root = main_root
        self._phase = phase_name
        self._force = force
        self._worktree_path = main_root / ".worktrees" / phase_name
        self._branch = f"feat-{phase_name}"

    @property
    def worktree_path(self) -> Path:
        return self._worktree_path

    @property
    def branch(self) -> str:
        return self._branch

    def ensure(self) -> Path:
        """워크트리를 보장하고 워크트리 root path를 반환한다."""
        registered = self._registered_worktree_path()
        if registered is not None:
            if registered.resolve() != self._worktree_path.resolve():
                print(
                    f"  ERROR: branch '{self._branch}'가 이미 다른 워크트리에 attach되어 있습니다: {registered}\n"
                    "  Hint: 기존 워크트리를 정리하거나 다른 phase 이름을 사용하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
            if not registered.exists():
                print(
                    f"  ERROR: 워크트리가 등록되어 있으나 디렉토리가 없습니다 (stale): {registered}\n"
                    "  Hint: 메인 repo에서 `git worktree prune` 후 재실행하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
            _qprint(f"  Worktree: {self._worktree_path} (재사용)")
            self._ensure_submodules()
            return self._worktree_path

        if self._worktree_path.exists():
            print(
                f"  ERROR: 디렉토리는 존재하지만 워크트리로 등록되지 않았습니다: {self._worktree_path}\n"
                "  Hint: 수동으로 디렉토리를 삭제하거나 `git worktree prune` 후 재시도하세요.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

        self._worktree_path.parent.mkdir(parents=True, exist_ok=True)

        if self._branch_exists():
            r = self._git("worktree", "add", str(self._worktree_path), self._branch)
        else:
            r = self._git("worktree", "add", "-b", self._branch, str(self._worktree_path))
        if r.returncode != 0:
            print(
                f"  ERROR: 워크트리 생성 실패 ({self._worktree_path}).\n"
                f"  {r.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        _qprint(f"  Worktree: {self._worktree_path} (생성, branch={self._branch})")
        self._ensure_submodules()
        return self._worktree_path

    def _branch_exists(self) -> bool:
        return self._git("rev-parse", "--verify", "--quiet", self._branch).returncode == 0

    def _registered_worktree_path(self) -> Optional[Path]:
        r = self._git("worktree", "list", "--porcelain")
        if r.returncode != 0:
            return None
        current_path: Optional[Path] = None
        target_ref = f"refs/heads/{self._branch}"
        for line in r.stdout.splitlines():
            if line.startswith("worktree "):
                current_path = Path(line[len("worktree ") :])
            elif line.startswith("branch ") and current_path is not None:
                if line[len("branch ") :].strip() == target_ref:
                    return current_path
        return None

    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + list(args),
            cwd=self._main_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _submodule_entries(self) -> list[tuple[str, str]]:
        """워크트리 .gitmodules 에서 (submodule name, path) 목록."""
        gm = self._worktree_path / ".gitmodules"
        r = self._git("config", "-f", str(gm), "--get-regexp", r"submodule\..*\.path")
        out: list[tuple[str, str]] = []
        for line in r.stdout.splitlines():
            key, _, path = line.partition(" ")
            # key = submodule.<name>.path
            name = key[len("submodule."):-len(".path")] if key.startswith("submodule.") else ""
            if name and path.strip():
                out.append((name, path.strip()))
        return out

    def _ensure_submodules(self) -> None:
        """워크트리 서브모듈을 메인 repo의 populate된 서브모듈로 링크(junction/symlink).

        git submodule update 를 쓰지 않는다 — 네트워크/내부망 의존 없이 메인 working files 를
        공유한다. 링크 후 submodule.<name>.ignore=all 로 status/commit 에서 무시되게 해
        dirty 가드 트립과 gitlink churn 을 막는다.
        """
        if not (self._worktree_path / ".gitmodules").exists():
            return
        for name, rel in self._submodule_entries():
            src = self._main_root / rel
            dst = self._worktree_path / rel
            if not src.is_dir() or not any(src.iterdir()):
                _qprint(f"  Submodule 링크 skip (메인 미populate): {rel}")
                continue
            try:
                if _is_dir_link(dst):
                    _qprint(f"  Submodule 링크 재사용: {rel}")
                else:
                    if dst.exists():
                        os.rmdir(dst)  # 빈 gitlink 디렉토리 (내용 있으면 OSError→skip)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    _make_dir_link(src, dst)
                    _qprint(f"  Submodule 링크: {rel} → 메인")
                # status/commit 에서 서브모듈 무시 (dirty 가드·gitlink churn 방지)
                subprocess.run(
                    ["git", "config", f"submodule.{name}.ignore", "all"],
                    cwd=self._worktree_path, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
            except OSError as e:
                _qprint(f"  Submodule 링크 실패(무시): {rel} — {e}")


# ============================================================================
# GitOperations — 2단계 commit (워크트리 컨텍스트에서 동작)
# ============================================================================
class GitOperations:
    """git 작업의 단일 boundary. dirty-tree 검사, two-step commit. cwd는 워크트리 root."""

    def __init__(self, cwd: Path, *, force: bool):
        self._cwd = cwd
        self._force = force

    def two_step_commit(self, *, feat_msg: str, chore_msg: str, reset_paths: list[str]) -> None:
        self._run("add", "-A")
        for p in reset_paths:
            self._run("reset", "HEAD", "--", p)
        if self._run("diff", "--cached", "--quiet").returncode != 0:
            r = self._run("commit", "-m", feat_msg)
            if r.returncode == 0:
                _qprint(f"  Commit: {feat_msg}")
            else:
                log.warning("코드 커밋 실패: %s", r.stderr.strip())
        self._run("add", "-A")
        if self._run("diff", "--cached", "--quiet").returncode != 0:
            r = self._run("commit", "-m", chore_msg)
            if r.returncode != 0:
                log.warning("housekeeping 커밋 실패: %s", r.stderr.strip())

    def commit_chore(self, msg: str) -> bool:
        self._run("add", "-A")
        if self._run("diff", "--cached", "--quiet").returncode != 0:
            r = self._run("commit", "-m", msg)
            return r.returncode == 0
        return False

    def push(self, branch: str) -> None:
        r = self._run("push", "-u", "origin", branch)
        if r.returncode != 0:
            print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
            sys.exit(EXIT_ERR)
        _qprint(f"  ✓ Pushed to origin/{branch}")

    # ---- 커밋 메시지 재작성용 read/rewrite 헬퍼 (cwd=워크트리) ----

    def head_sha(self) -> Optional[str]:
        r = self._run("rev-parse", "HEAD")
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None

    def commits_since(self, base: str) -> list[str]:
        """base..HEAD 커밋 해시를 oldest→newest 순으로 반환. 실패/없음 시 빈 리스트."""
        r = self._run("rev-list", "--reverse", f"{base}..HEAD")
        if r.returncode != 0:
            return []
        return [h for h in r.stdout.split() if h]

    def commit_subject(self, sha: str) -> str:
        return self._run("show", "-s", "--format=%s", sha).stdout.strip()

    def commit_body(self, sha: str) -> str:
        return self._run("show", "-s", "--format=%B", sha).stdout

    def commit_diff(self, sha: str, max_bytes: int) -> str:
        """단일 커밋의 stat+patch. max_bytes로 절단."""
        r = self._run("show", "--stat", "-p", "--format=", sha)
        return (r.stdout or "")[:max_bytes]

    def recent_subjects(self, ref: str, n: int) -> list[str]:
        """ref 이하 최근 n개 커밋 subject (스타일 예시용)."""
        r = self._run("log", f"-n{n}", "--format=%s", ref)
        if r.returncode != 0:
            return []
        return [s for s in r.stdout.splitlines() if s.strip()]

    def rebuild_messages(self, base: str, new_msgs: dict) -> bool:
        """base..HEAD를 동일 tree로 재생성하되 new_msgs[sha]가 있으면 메시지를 교체한다.

        author/committer ident+date를 보존한다. 모든 커밋 재구성에 성공한 뒤에만
        현재 브랜치를 새 tip으로 이동한다(중간 실패 시 원본 무손상).
        """
        shas = self.commits_since(base)
        if not shas:
            return False
        parent = base
        for sha in shas:
            tree = self._run("rev-parse", f"{sha}^{{tree}}").stdout.strip()
            if not tree:
                return False
            msg = new_msgs.get(sha) or self.commit_body(sha)
            ident = self._run(
                "show", "-s", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI", sha
            ).stdout.splitlines()
            env = {}
            if len(ident) >= 6:
                an, ae, ai, cn, ce, ci = ident[:6]
                env = {
                    "GIT_AUTHOR_NAME": an, "GIT_AUTHOR_EMAIL": ae, "GIT_AUTHOR_DATE": ai,
                    "GIT_COMMITTER_NAME": cn, "GIT_COMMITTER_EMAIL": ce, "GIT_COMMITTER_DATE": ci,
                }
            r = self._run("commit-tree", tree, "-p", parent, "-m", msg, env=env)
            new = r.stdout.strip()
            if r.returncode != 0 or not new:
                log.warning("commit-tree 실패 (%s): %s", sha[:8], r.stderr.strip())
                return False
            parent = new
        return self._run("reset", "--hard", parent).returncode == 0

    def _run(self, *args, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        run_env = None
        if env:
            run_env = {**os.environ, **env}
        return subprocess.run(
            ["git"] + list(args),
            cwd=self._cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
        )


# ============================================================================
# IndexStore — index.json 로드/저장/검증/상태전이
# ============================================================================
class IndexStore:
    """phase index.json + top-level index.json의 단일 owner. 모든 status 전이는 여기를 통과."""

    def __init__(self, cfg: PhaseConfig):
        self._cfg = cfg

    @staticmethod
    def stamp() -> str:
        return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    def load(self) -> dict:
        return self._read_json(self._cfg.index_file)

    def save(self, idx: dict) -> None:
        self._write_json(self._cfg.index_file, idx)

    def validate_schema(self, idx: dict) -> None:
        def _err(msg: str):
            print(
                f"ERROR: {self._cfg.index_file} 스키마 위반 — {msg}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

        if not isinstance(idx, dict):
            _err("최상위는 객체여야 합니다.")
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
        scope = idx.get("docs_scope")
        if scope is not None:
            if not isinstance(scope, list):
                _err("'docs_scope'는 배열이어야 합니다.")
            for i, e in enumerate(scope):
                if not isinstance(e, str):
                    _err(f"docs_scope[{i}]는 문자열이어야 합니다.")

    def get_docs_scope(self) -> list[str]:
        idx = self.load()
        return list(idx.get("docs_scope") or [])

    def get_total(self) -> int:
        return len(self.load().get("steps", []))

    def get_meta(self) -> tuple[str, str]:
        """(project, phase_name) 반환."""
        idx = self.load()
        return (
            idx.get("project", "project"),
            idx.get("phase", self._cfg.phase_dir_name),
        )

    def first_pending(self) -> Optional[dict]:
        idx = self.load()
        for s in sorted(idx["steps"], key=lambda x: x["step"]):
            if s["status"] == "pending":
                return s
        return None

    def ensure_created_at(self) -> None:
        idx = self.load()
        if "created_at" not in idx:
            idx["created_at"] = self.stamp()
            self.save(idx)

    def ensure_git_base(self, sha: Optional[str]) -> None:
        """phase 시작 시점의 HEAD를 1회 기록(커밋 메시지 재작성의 base ref). 재실행 시 보존."""
        if not sha:
            return
        idx = self.load()
        if "git_base" not in idx:
            idx["git_base"] = sha
            self.save(idx)

    def get_git_base(self) -> Optional[str]:
        return self.load().get("git_base")

    def ensure_started_at(self, step_num: int) -> None:
        idx = self.load()
        for s in idx["steps"]:
            if s["step"] == step_num and "started_at" not in s:
                s["started_at"] = self.stamp()
                self.save(idx)
                return

    def read_step_status(self, step_num: int) -> str:
        return next(
            (s.get("status", "pending") for s in self.load()["steps"] if s["step"] == step_num),
            "pending",
        )

    def read_step_error(self, step_num: int) -> str:
        return next(
            (
                s.get("error_message", "Step did not update status")
                for s in self.load()["steps"]
                if s["step"] == step_num
            ),
            "Step did not update status",
        )

    def child_status_file(self, step_num: int) -> Path:
        return self._cfg.phase_dir / f"step{step_num}-status.json"

    def ingest_child_status(self, step_num: int) -> str:
        """자식이 쓴 step{N}-status.json 을 읽어 index.json 에 프로그램적으로 반영.

        자식이 거대한 중첩 index.json 을 손수편집하다 JSON 을 깨뜨리는 사고를
        원천 차단한다(자식은 작은 status 파일만 새로 쓴다). status 파일이 없거나
        깨졌으면 'pending' 을 반환해 기존 재시도 로직이 동작한다.
        """
        sf = self.child_status_file(step_num)
        if not sf.exists():
            return "pending"
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "pending"
        status = data.get("status", "pending")
        if status not in ALLOWED_STATUS:
            return "pending"
        idx = self.load()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["status"] = status
                if data.get("summary"):
                    s["summary"] = data["summary"]
                if status == "error" and data.get("error_message"):
                    s["error_message"] = data["error_message"]
                if status == "blocked" and data.get("blocked_reason"):
                    s["blocked_reason"] = data["blocked_reason"]
                break
        self.save(idx)
        return status

    def completed_count(self) -> int:
        return sum(1 for s in self.load()["steps"] if s["status"] == "completed")

    def step_summaries(self) -> str:
        idx = self.load()
        sorted_steps = sorted(idx["steps"], key=lambda s: s["step"])
        lines = [
            f"- Step {s['step']} ({s['name']}): {_truncate_text(str(s['summary']), SUMMARY_CHAR_LIMIT)}"
            for s in sorted_steps
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def mark_completed(self, step_num: int) -> None:
        idx = self.load()
        ts = self.stamp()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["completed_at"] = ts
                break
        self.save(idx)

    def mark_blocked(self, step_num: int, reason: str) -> None:
        idx = self.load()
        ts = self.stamp()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["status"] = "blocked"
                s["blocked_reason"] = reason
                s["blocked_at"] = ts
                break
        self.save(idx)

    def mark_blocked_at(self, step_num: int) -> str:
        idx = self.load()
        ts = self.stamp()
        reason = ""
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["blocked_at"] = ts
                reason = s.get("blocked_reason", "")
                break
        self.save(idx)
        return reason

    def reset_for_retry(self, step_num: int) -> None:
        # 직전 시도의 status 파일을 지워 재시도가 stale 결과를 읽지 않게 한다.
        sf = self.child_status_file(step_num)
        try:
            sf.unlink()
        except OSError:
            pass
        idx = self.load()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["status"] = "pending"
                s.pop("error_message", None)
                break
        self.save(idx)

    def mark_error(self, step_num: int, err_msg: str, max_retries: int) -> None:
        idx = self.load()
        ts = self.stamp()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["status"] = "error"
                s["error_message"] = f"[{max_retries}회 시도 후 실패] {err_msg}"
                s["failed_at"] = ts
                break
        self.save(idx)

    def mark_interrupted(self, step_num: int) -> None:
        try:
            idx = self.load()
        except SystemExit:
            return
        ts = self.stamp()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["status"] = "interrupted"
                s["interrupted_at"] = ts
                break
        self.save(idx)

    def finalize(self) -> None:
        idx = self.load()
        idx["completed_at"] = self.stamp()
        self.save(idx)

    def update_top(self, status: str) -> None:
        top_file = self._cfg.top_index_file
        if not top_file.exists():
            return
        top = self._read_json(top_file)
        ts = self.stamp()
        ts_key = {
            "completed": "completed_at",
            "error": "failed_at",
            "blocked": "blocked_at",
        }.get(status)
        for phase in top.get("phases", []):
            if phase.get("dir") == self._cfg.phase_dir_name:
                phase["status"] = status
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(top_file, top)

    def upsert_top(self) -> None:
        """top-level index.json에 본 phase 항목을 추가하거나 갱신한다."""
        top_file = self._cfg.top_index_file
        if top_file.exists():
            top = self._read_json(top_file)
            if not isinstance(top, dict) or "phases" not in top:
                print(
                    f"ERROR: {top_file}의 형식이 손상되었습니다 (top-level 객체에 'phases' 누락). 수동으로 복구하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
            if not isinstance(top["phases"], list):
                print(
                    f"ERROR: {top_file}의 'phases' 필드가 배열이 아닙니다. 수동으로 복구하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
        else:
            top = {"phases": []}
        for phase in top["phases"]:
            if isinstance(phase, dict) and phase.get("dir") == self._cfg.phase_dir_name:
                if not phase.get("status"):
                    phase["status"] = "pending"
                self._write_json(top_file, top)
                return
        top["phases"].append(
            {
                "dir": self._cfg.phase_dir_name,
                "status": "pending",
            }
        )
        self._write_json(top_file, top)

    # ---- 인라인 실행 지원: attempt counter(OI-2) + 메인 repo 누수 baseline(OI-1) ----

    def increment_attempt(self, step_num: int) -> int:
        """record-step 호출당 step의 attempts를 +1 하고 반환한다(하드 백스톱 카운터)."""
        idx = self.load()
        for s in idx["steps"]:
            if s["step"] == step_num:
                s["attempts"] = int(s.get("attempts", 0)) + 1
                self.save(idx)
                return s["attempts"]
        return 0

    def get_attempts(self, step_num: int) -> int:
        return next(
            (int(s.get("attempts", 0)) for s in self.load()["steps"] if s["step"] == step_num),
            0,
        )

    def set_root_baseline(self, lines: list[str]) -> None:
        """scaffold 시점 메인 repo(ROOT)의 dirty 기준선을 index.json에 저장한다."""
        idx = self.load()
        idx["root_dirty_baseline"] = list(lines)
        self.save(idx)

    def get_root_baseline(self) -> list[str]:
        return list(self.load().get("root_dirty_baseline") or [])

    @staticmethod
    def _read_json(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(
                f"ERROR: {p} JSON 파싱 실패 (line {e.lineno}, col {e.colno}): {e.msg}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

    @staticmethod
    def _write_json(p: Path, data: dict) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# ============================================================================
# StepSplitter — 자동 step 분할 (단일 Claude 호출)
# ============================================================================
class StepSplitter:
    """첫 실행 전용. prompt+doc → 단일 Claude 호출 → strict JSON plan → 사용자 승인 → 파일 일괄 기록."""

    PARSE_RETRIES = 1  # 1회 재시도

    def __init__(
        self,
        cfg: PhaseConfig,
        invoker: ClaudeInvoker,
        validator: ScopeValidator,
        *,
        yes: bool,
        compact_docs: bool = False,
        max_steps: Optional[int] = None,
    ):
        self._cfg = cfg
        self._invoker = invoker
        self._validator = validator
        self._yes = yes
        self._compact_docs = compact_docs
        self._max_steps = max_steps or MAX_STEPS_PER_PLAN

    def needs_split(self) -> bool:
        if not self._cfg.phase_dir.is_dir():
            return True
        return not any(p.is_file() and STEP_FILE_RE.match(p.name) for p in self._cfg.phase_dir.iterdir())

    def run(self, user_prompts: list[str], doc_paths: list[Path]) -> None:
        prompt = self._build_split_prompt(user_prompts, doc_paths)
        plan = self._call_with_retry(prompt)
        self._validate_plan(plan)
        if not self._confirm(plan):
            _qprint("  사용자가 계획을 승인하지 않았습니다. 디렉토리를 생성하지 않고 종료합니다.")
            sys.exit(EXIT_ERR)
        self._emit_files(plan)
        _qprint(f"  ✓ {len(plan['steps'])}개 step.md 파일이 생성되었습니다.")

    # ---- 내부 헬퍼 ----

    def _build_split_prompt(self, user_prompts: list[str], doc_paths: list[Path]) -> str:
        # 읽기 출처는 항상 ROOT(프로젝트 루트). 워크트리 cfg.root 아님 — 가드레일/문서는
        # source-of-truth인 메인 repo에서 읽어 staleness·중복복사를 제거한다.
        claude_md = ROOT / "CLAUDE.md"
        guardrail_text = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""

        joined_prompts = "\n\n---\n\n".join(p for p in user_prompts if p) or "(없음)"

        doc_sections = []
        for path in doc_paths:
            text = path.read_text(encoding="utf-8")
            if self._compact_docs:
                text = _compact_markdown_doc(text)
            clipped = text[:DOC_BYTES_LIMIT]
            note = "" if len(text) <= DOC_BYTES_LIMIT else (f"\n\n... ({len(text) - DOC_BYTES_LIMIT}자 생략) ...")
            rel = path.relative_to(ROOT).as_posix()
            doc_sections.append(f"### {rel}\n\n```\n{clipped}{note}\n```")
        docs_block = "\n\n".join(doc_sections) if doc_sections else "(첨부 문서 없음)"

        body = (
            "당신은 harness_framework 프로젝트의 시니어 개발자입니다. "
            "사용자가 제시한 기능 요구사항을 Forge가 순차 실행할 수 있는 step 계획으로 분해하세요.\n\n"
            "## 가드레일 (반드시 준수)\n\n"
            f"{guardrail_text}\n\n"
            "## 사용자 요구사항\n\n"
            f"{joined_prompts}\n\n"
            "## 첨부 문서\n\n"
            f"{docs_block}\n\n"
            "## 출력 규칙 (위반 시 거부됨)\n\n"
            "1. 출력은 **단 하나의 JSON 객체**여야 한다. 마크다운 펜스, 설명문, 인사말 금지.\n"
            "2. 스키마:\n"
            "```\n"
            "{\n"
            f'  "phase": "{self._cfg.phase_dir_name}",\n'
            '  "project": "<프로젝트명>",\n'
            '  "docs_scope": ["docs/<file>.md", ...],\n'
            '  "steps": [\n'
            "    {\n"
            '      "step": 0,\n'
            '      "name": "<kebab-case-slug>",\n'
            '      "brief": "<한 줄 요약 ≤160자>",\n'
            '      "body": "<step{N}.md 본문 전체 — 5개 H2 섹션 모두 포함>"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
            "3. 각 step의 body는 아래 5개 H2 섹션을 모두 포함해야 한다 (순서 고정):\n"
            "   ## 읽어야 할 파일\n"
            "   ## 작업\n"
            "   ## Acceptance Criteria\n"
            "   ## 검증 절차\n"
            "   ## 금지사항\n"
            "4. body 내부의 AC는 실제로 실행 가능한 셸 명령으로 작성한다.\n"
            "5. docs_scope에는 step body가 실제로 참조하는 파일만 포함한다 (전체 docs/ 덤프 금지).\n"
            f"6. step 번호는 0부터 시작하며 연속해야 한다. step 수는 1~{self._max_steps}개.\n"
            "7. 사용자 요구사항이 비어 있거나 거부 사유에 해당하면, 다음 객체를 그대로 반환한다:\n"
            f'   {{"phase":"{self._cfg.phase_dir_name}","refusal":"<사유>"}}\n\n'
            "지금 위 스키마에 맞춰 JSON만 출력하세요."
        )

        if len(body) > SPLIT_PROMPT_BYTES_LIMIT:
            print(
                f"ERROR: splitter prompt가 {len(body)}바이트 — {SPLIT_PROMPT_BYTES_LIMIT} 한계를 초과합니다.\n"
                "       --doc 파일이 너무 큽니다. 일부 내용만 사용하거나 prompt를 짧게 작성하세요.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

        return body

    def _call_with_retry(self, prompt: str) -> dict:
        last_err = ""
        followup_prompt = prompt
        for attempt in range(1 + self.PARSE_RETRIES):
            tag = "Step 자동 분할 plan 생성" + (f" [retry {attempt}]" if attempt > 0 else "")
            with progress_indicator(tag):
                returncode, stdout, stderr = self._invoker.call(followup_prompt)
            if returncode != 0:
                last_err = f"Claude CLI 비정상 종료 (code {returncode}): {stderr[:500]}"
                followup_prompt = self._retry_prompt(prompt, last_err)
                continue
            try:
                plan = self._parse_plan(stdout)
                return plan
            except ValueError as e:
                last_err = str(e)
                followup_prompt = self._retry_prompt(prompt, last_err)
                continue
        print(
            "ERROR: step 자동 분할 실패. 수동으로 phases/scoped/<phase-dir>/index.json + "
            "step{N}.md 파일을 작성한 뒤 재실행하세요.\n"
            f"       마지막 에러: {last_err}",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERR)

    @staticmethod
    def _retry_prompt(original: str, err_msg: str) -> str:
        return (
            f"이전 응답이 다음 사유로 거부되었습니다: {err_msg}\n\n"
            "응답은 반드시 단 하나의 JSON 객체여야 하며, 마크다운 펜스/설명문 없이 순수 JSON만 "
            "출력하세요. 아래 원본 지시를 다시 따르세요.\n\n"
            "---\n\n"
            f"{original}"
        )

    def _parse_plan(self, raw_stdout: str) -> dict:
        if not raw_stdout.strip():
            raise ValueError("Claude 응답이 비어 있습니다.")
        result_text = self._extract_result_text(raw_stdout)
        result_text = self._strip_fences(result_text)
        try:
            obj = json.loads(result_text)
        except json.JSONDecodeError as e:
            preview = result_text[:300].replace("\n", "\\n")
            raise ValueError(f"plan JSON 파싱 실패 (line {e.lineno}, col {e.colno}): {e.msg}. 응답 미리보기: {preview}")
        if not isinstance(obj, dict):
            raise ValueError("plan 최상위는 JSON 객체여야 합니다.")
        if "refusal" in obj:
            reason = obj.get("refusal", "(사유 미상)")
            print(f"\nERROR: auto-split 거부됨: {reason}", file=sys.stderr)
            sys.exit(EXIT_ERR)
        return obj

    @staticmethod
    def _extract_result_text(raw: str) -> str:
        """`claude --output-format json`의 wrapper에서 실제 응답을 추출.

        지원 형태:
          - {"is_error": false, "result": "<json string>"}
          - {"is_error": false, "result": {<dict>}}  ← dict이면 dumps로 직렬화
          - {"text": "<json string>"}
          - 줄바꿈으로 구분된 stream 이벤트 JSON Lines (마지막 result 이벤트 사용)
          - wrapper가 아닌 raw JSON
        """
        # 1) 단일 JSON wrapper 시도
        try:
            wrapper = json.loads(raw)
            extracted = StepSplitter._extract_from_wrapper(wrapper)
            if extracted is not None:
                return extracted
        except json.JSONDecodeError:
            pass
        # 2) JSON Lines (stream events) — 마지막에서 result/text를 찾는다
        for line in reversed([ln for ln in raw.splitlines() if ln.strip()]):
            try:
                obj = json.loads(line)
                extracted = StepSplitter._extract_from_wrapper(obj)
                if extracted is not None:
                    return extracted
            except json.JSONDecodeError:
                continue
        # 3) fallback: raw 그대로
        return raw

    @staticmethod
    def _extract_from_wrapper(wrapper) -> Optional[str]:
        if not isinstance(wrapper, dict):
            return None
        if wrapper.get("is_error") is True:
            err = wrapper.get("result") or wrapper.get("error") or "unknown"
            raise ValueError(f"Claude 호출 에러: {err}")
        for key in ("result", "text", "content"):
            if key in wrapper:
                val = wrapper[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    return json.dumps(val, ensure_ascii=False)
        return None

    @staticmethod
    def _strip_fences(text: str) -> str:
        s = text.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines)
        return s.strip()

    def _validate_plan(self, plan: dict) -> None:
        def _err(msg: str):
            raise ValueError(msg)

        for key in ("phase", "project", "docs_scope", "steps"):
            if key not in plan:
                _err(f"plan에 '{key}' 키 없음.")
        if plan["phase"] != self._cfg.phase_dir_name:
            _err(
                f"plan.phase='{plan['phase']}'가 phase 디렉토리 이름 '{self._cfg.phase_dir_name}'과 일치하지 않습니다."
            )
        if not isinstance(plan["project"], str) or not plan["project"].strip():
            _err("plan.project는 비어 있지 않은 문자열이어야 합니다.")
        if len(plan["project"]) > 80:
            _err("plan.project가 80자를 초과합니다.")

        if not isinstance(plan["docs_scope"], list):
            _err("plan.docs_scope는 배열이어야 합니다.")
        try:
            self._validator.validate_many(plan["docs_scope"])
        except (ValueError, FileNotFoundError) as e:
            _err(f"docs_scope 검증 실패: {e}")

        steps = plan["steps"]
        if not isinstance(steps, list):
            _err("plan.steps는 배열이어야 합니다.")
        if not steps:
            _err("plan.steps가 비어 있습니다.")
        if len(steps) > self._max_steps:
            _err(f"step 수 {len(steps)}가 한계 {self._max_steps}을 초과합니다.")

        seen_nums = set()
        seen_names = set()
        body_total = 0
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                _err(f"steps[{i}]는 객체여야 합니다.")
            for key, typ in (
                ("step", int),
                ("name", str),
                ("brief", str),
                ("body", str),
            ):
                if key not in s:
                    _err(f"steps[{i}]에 '{key}' 키 없음.")
                if not isinstance(s[key], typ) or (typ is int and isinstance(s[key], bool)):
                    _err(f"steps[{i}].{key} 타입 불일치 (기대: {typ.__name__}).")
            if s["step"] in seen_nums:
                _err(f"steps[{i}]: step 번호 중복 ({s['step']}).")
            seen_nums.add(s["step"])
            if s["name"] in seen_names:
                _err(f"steps[{i}]: name 중복 ('{s['name']}').")
            seen_names.add(s["name"])
            if not STEP_NAME_RE.match(s["name"]):
                _err(f"steps[{i}].name='{s['name']}'은 kebab-case가 아닙니다.")
            if len(s["name"]) > 40:
                _err(f"steps[{i}].name이 40자를 초과합니다.")
            if not s["brief"].strip():
                _err(f"steps[{i}].brief가 비어 있습니다.")
            if len(s["brief"]) > 160:
                _err(f"steps[{i}].brief가 160자를 초과합니다.")
            for heading in REQUIRED_STEP_HEADINGS:
                pattern = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
                if not pattern.search(s["body"]):
                    _err(f"steps[{i}].body에 필수 H2 헤딩 '{heading}'이 없습니다.")
            body_total += len(s["body"])
        if body_total > 1_000_000:
            _err(f"step body 합계가 1MB를 초과합니다 ({body_total} bytes).")

        sorted_nums = sorted(seen_nums)
        if sorted_nums != list(range(len(steps))):
            _err(f"step 번호는 0..{len(steps) - 1} 연속이어야 합니다. 현재: {sorted_nums}")

    def _confirm(self, plan: dict) -> bool:
        _qprint("\n" + "=" * 60)
        _qprint(f"  Plan: {plan['phase']} (project: {plan['project']})")
        _qprint("=" * 60)
        if plan["docs_scope"]:
            _qprint(f"  docs_scope ({len(plan['docs_scope'])}개):")
            for d in plan["docs_scope"]:
                _qprint(f"    - {d}")
        else:
            _qprint("  docs_scope: (없음 — CLAUDE.md만 가드레일로 주입됨)")
        _qprint(f"  steps ({len(plan['steps'])}개):")
        for s in plan["steps"]:
            _qprint(f"    [{s['step']}] {s['name']}: {s['brief']}")
        _qprint("=" * 60)
        if self._yes:
            _qprint("  --yes 플래그로 자동 승인됨.")
            return True
        try:
            ans = input("  이 계획대로 step.md 파일을 생성할까요? [y/N] ").strip().lower()
        except EOFError:
            print("  비대화 환경에서 입력 없음 — 거부 처리. --yes 플래그를 사용하세요.")
            return False
        return ans in ("y", "yes")

    def _emit_files(self, plan: dict) -> None:
        # 기존 step.md/index.json 보존 가드 — 부분 상태 덮어쓰기 방지
        final_dir = self._cfg.phase_dir
        if final_dir.is_dir():
            existing = [p.name for p in final_dir.iterdir() if STEP_FILE_RE.match(p.name) or p.name == "index.json"]
            if existing:
                print(
                    f"ERROR: {final_dir}에 이미 파일이 있습니다 ({existing}).\n"
                    "       기존 산출물을 보존하기 위해 emit를 중단합니다.\n"
                    "       다시 자동 분할을 원하면 디렉토리를 비우고 재실행하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
        index = {
            "project": plan["project"],
            "phase": plan["phase"],
            "docs_scope": list(plan["docs_scope"]),
            "steps": [
                {"step": s["step"], "name": s["name"], "status": "pending"}
                for s in sorted(plan["steps"], key=lambda x: x["step"])
            ],
        }

        # atomic write: 임시 디렉토리에 모두 작성한 후 한 번에 rename으로 이동.
        # KeyboardInterrupt/OSError 발생 시 임시 파일만 cleanup, final_dir는 pristine.
        temp_dir = final_dir.parent / f".{final_dir.name}.splitter-tmp"
        self._cleanup_temp(temp_dir)
        try:
            temp_dir.mkdir(parents=True, exist_ok=False)
            for s in plan["steps"]:
                (temp_dir / f"step{s['step']}.md").write_text(
                    s["body"],
                    encoding="utf-8",
                )
            (temp_dir / "index.json").write_text(
                json.dumps(index, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            # final_dir이 비어있는 디렉토리면 제거 후 rename, 부재면 그냥 rename.
            if final_dir.is_dir():
                try:
                    final_dir.rmdir()  # 위 가드로 비어있어야 함
                except OSError:
                    raise OSError(f"{final_dir}가 비어있지 않아 atomic rename 불가. 디렉토리를 비우고 재실행하세요.")
            temp_dir.rename(final_dir)
        except KeyboardInterrupt:
            self._cleanup_temp(temp_dir)
            raise  # main의 top-level handler가 130으로 처리
        except OSError as e:
            self._cleanup_temp(temp_dir)
            print(f"ERROR: 파일 작성 실패 — {e}", file=sys.stderr)
            sys.exit(EXIT_ERR)

    @staticmethod
    def _cleanup_temp(temp_dir: Path) -> None:
        if not temp_dir.exists():
            return
        try:
            for p in temp_dir.iterdir():
                try:
                    p.unlink()
                except OSError:
                    pass
            temp_dir.rmdir()
        except OSError:
            pass  # best-effort


# ============================================================================
# DeterministicPlanBuilder — splitter 호출 없이 single-step phase 생성
# ============================================================================
class DeterministicPlanBuilder:
    """토큰 절감용 고정 plan 생성기.

    작은 FRD 구현/토큰 테스트에서는 plan 생성을 위해 별도 Claude 호출을 쓰는
    비용이 더 크다. 이 빌더는 index.json + step0.md를 로컬에서 생성해 splitter
    호출을 완전히 제거한다.
    """

    def __init__(self, cfg: PhaseConfig, *, preset: str, sln_path: Path | None = None,
                 test_target: str | None = None):
        self._cfg = cfg
        self._preset = preset
        self._sln_path = sln_path
        self._cli_test_target = test_target  # --test-target (검증된 rel) 또는 None

    def build(self, user_prompts: list[str], doc_paths: list[Path]) -> dict:
        if self._preset == "contract-tdd":
            return self._build_contract_tdd_plan(user_prompts, doc_paths)
        return self._build_single_step_plan(user_prompts, doc_paths)

    def _build_single_step_plan(self, user_prompts: list[str], doc_paths: list[Path]) -> dict:
        if self._preset == "frd-implementation":
            self._require_single_doc(doc_paths, preset="frd-implementation")
        # doc_paths는 ScopeValidator(ROOT)가 만든 ROOT-절대경로 → ROOT 기준 상대화.
        docs_scope = [p.relative_to(ROOT).as_posix() for p in doc_paths]
        step_name = self._step_name(docs_scope)
        return {
            "project": self._project_name(),
            "phase": self._cfg.phase_dir_name,
            "docs_scope": docs_scope,
            "steps": [
                {
                    "step": 0,
                    "name": step_name,
                    "brief": self._brief(docs_scope),
                    "body": self._body(step_name, docs_scope, user_prompts),
                },
            ],
        }

    def _build_contract_tdd_plan(self, user_prompts: list[str], doc_paths: list[Path]) -> dict:
        self._require_single_doc(doc_paths, preset="contract-tdd")
        # doc_paths는 ScopeValidator(ROOT)가 만든 ROOT-절대경로 → ROOT 기준 상대화.
        docs_scope = [p.relative_to(ROOT).as_posix() for p in doc_paths]
        doc_rel = docs_scope[0]
        return {
            "project": self._project_name(),
            "phase": self._cfg.phase_dir_name,
            "docs_scope": docs_scope,
            "steps": [
                {
                    "step": 0,
                    "name": "contract-skeleton",
                    "brief": f"{doc_rel} 계약 표면(interface/DTO/route skeleton) 생성",
                    "body": self._contract_skeleton_body(docs_scope, user_prompts),
                },
                {
                    "step": 1,
                    "name": "red-tests",
                    "brief": f"{doc_rel} 요구사항을 검증하는 실패 테스트 추가",
                    "body": self._red_tests_body(docs_scope, user_prompts),
                },
                {
                    "step": 2,
                    "name": "green-implementation",
                    "brief": f"{doc_rel} red 테스트 통과를 위한 최소 구현",
                    "body": self._green_implementation_body(docs_scope, user_prompts),
                },
                {
                    "step": 3,
                    "name": "refactor-and-regression",
                    "brief": f"{doc_rel} 정리 및 전체 회귀 검증",
                    "body": self._refactor_and_regression_body(
                        docs_scope,
                        user_prompts,
                    ),
                },
            ],
        }

    @staticmethod
    def _require_single_doc(doc_paths: list[Path], *, preset: str) -> None:
        if len(doc_paths) != 1:
            print(
                f"ERROR: --preset={preset}은 --doc 문서 1개가 필요합니다.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

    def _project_name(self) -> str:
        claude_md = ROOT / "CLAUDE.md"
        if claude_md.exists():
            for line in claude_md.read_text(encoding="utf-8").splitlines():
                if line.startswith("# 프로젝트:"):
                    return _truncate_text(line.removeprefix("# 프로젝트:").strip(), 80)
        return _truncate_text(ROOT.name, 80)

    def _step_name(self, docs_scope: list[str]) -> str:
        if docs_scope:
            stem = Path(docs_scope[0]).stem
            return self._slug(f"implement-{stem}")
        return self._slug(self._cfg.phase_dir_name or "scoped-task")

    def _brief(self, docs_scope: list[str]) -> str:
        if self._preset == "frd-implementation" and docs_scope:
            return f"{docs_scope[0]} 요구사항을 단일 step으로 구현"
        if docs_scope:
            return f"{', '.join(docs_scope)} 기준 scoped 작업 수행"
        return "사용자 prompt 기준 scoped 작업 수행"

    @staticmethod
    def _slug(raw: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
        slug = slug or "scoped-task"
        if len(slug) > 40:
            slug = slug[:40].rstrip("-") or "scoped-task"
        return slug

    def _body(self, step_name: str, docs_scope: list[str], user_prompts: list[str]) -> str:
        prompt_lines = [f"- {p.strip()}" for p in user_prompts if p and p.strip()] or [
            "- docs_scope 문서 요구사항을 구현한다."
        ]
        doc_lines = [f"- `{d}`" for d in docs_scope] or ["- docs_scope 없음: 사용자 prompt와 코드 컨텍스트만 사용"]
        commands = "\n".join(self._acceptance_commands())
        docs_text = "\n".join(doc_lines)
        prompt_text = "\n".join(prompt_lines)
        return (
            f"# Step 0: {step_name}\n\n"
            "## 읽어야 할 파일\n\n"
            "아래 입력만 기준으로 작업 범위를 확정하라. compact docs가 이미 "
            "가드레일로 주입되므로 원문은 세부 확인이 필요할 때만 연다.\n\n"
            "- `CLAUDE.md`\n"
            f"{docs_text}\n"
            "- 구현에 필요한 코드 파일은 `rg`로 좁혀서 읽는다.\n\n"
            "## 작업\n\n"
            "다음 요구사항만 수행한다.\n\n"
            f"{prompt_text}\n\n"
            "- splitter를 다시 호출하거나 추가 phase를 만들지 않는다.\n"
            "- docs_scope 밖 문서 요구사항을 추측해 확장하지 않는다.\n"
            "- 구현, 필요한 테스트, 필요한 계약/출력 연결만 최소 범위로 수정한다.\n\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            f"{commands}\n"
            "```\n\n"
            "## 검증 절차\n\n"
            "1. 위 AC 커맨드를 실행한다.\n"
            f"2. `phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/index.json`의 "
            "step 0 상태를 갱신한다.\n"
            "3. 성공 시 `summary`는 생성/수정한 핵심 파일과 검증 결과만 200자 "
            "이내로 적는다.\n\n"
            "## 금지사항\n\n"
            "- `docs/**`, `CLAUDE.md`, `PHASE_SCHEMA.md`, `.claude/commands/**`, "
            "`scripts/forge_full.py`를 수정하지 마라. 이유: 이번 step은 구현 전용이다.\n"
            "- FRD/prompt 밖 기능을 추가하지 마라. 이유: 토큰 테스트와 구현 범위를 "
            "오염시킨다.\n"
            "- 진행 확인용 반복 로그 조회나 불필요한 `git log`/`tail`을 하지 마라. "
            "이유: 부모 세션 토큰 누적을 줄이기 위함이다.\n"
        )

    def _acceptance_commands(self) -> list[str]:
        root = self._cfg.root
        # 공유 해석기(warmup과 동일): CLI --test-target > config > 단일 Src/Tests csproj.
        # dotnet test 가 빌드를 겸하므로 별도 풀 sln dotnet build 는 두지 않는다.
        target = resolve_ac_test_target(root, self._cli_test_target)
        if target:
            return [f"dotnet test {target} --no-restore"]
        # 스코프 불가 → 전체 sln(test 가 빌드 겸함, 별도 build 제거). 느릴 수 있어 경고.
        sln = self._sln_path
        if sln is None:
            try:
                sln = resolve_sln_path(None, root, strict=False)
            except SlnResolveError:
                sln = None
        if sln is not None:
            rel = sln.relative_to(root).as_posix()
            log.warning(
                "test 스코프 타깃을 좁히지 못해 전체 sln(%s)을 빌드/테스트합니다 — 느릴 수 있습니다. "
                "forge-scope.json 의 test_target 키로 대상 테스트 프로젝트를 지정하면 빨라집니다.",
                rel,
            )
            return [f"dotnet test {rel} --no-restore"]
        if (root / "package.json").exists():
            return ["npm test"]
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
            return ["python -m pytest"]
        return ["git diff --check"]

    # ---- contract-tdd helpers ----

    @staticmethod
    def _prompt_lines(user_prompts: list[str]) -> list[str]:
        lines = [f"- {p.strip()}" for p in user_prompts if p and p.strip()]
        return lines or ["- docs_scope 문서 요구사항을 따른다."]

    @staticmethod
    def _doc_lines(docs_scope: list[str]) -> list[str]:
        return [f"- `{d}`" for d in docs_scope]

    def _solution_path_rel(self) -> str:
        """contract-tdd 가 사용할 sln 경로 (repo root 기준 posix)."""
        if self._sln_path is None:
            raise RuntimeError(
                "contract-tdd preset 는 sln 이 필요합니다. "
                "--sln=<path> 명시 또는 Src/ 에 단일 sln 배치 필요."
            )
        return self._sln_path.relative_to(self._cfg.root).as_posix()

    def _config_test_target(self) -> str | None:
        """forge-scope.json test_target — 검증 후 rel. 무효 시 warn+None."""
        raw = _read_forge_config_str(self._cfg.root, "test_target")
        if not raw:
            return None
        try:
            return _validate_target_rel(self._cfg.root, raw)
        except ValueError as e:
            log.warning("forge-scope.json test_target 무시 — %s", e)
            return None

    def _scoped_test_target(self) -> str | None:
        """test 스코프 타깃: CLI --test-target > forge-scope.json test_target. 둘 다 없으면 None."""
        return self._cli_test_target or self._config_test_target()

    def _test_target(self) -> str:
        """테스트 빌드 타깃: CLI override > config > 단일 Src/Tests csproj > 전체 sln.

        풀 솔루션 빌드는 대규모 sln에서 매우 느리다. test 타깃을 좁히면 그 테스트가
        참조하는 production 프로젝트만 transitive 빌드되어 30~50%+ 절감된다.
        1순위: CLI --test-target (작업 문서 기반 추론, 휘발성).
        2순위: forge-scope.json test_target (사용자 명시).
        3순위: `Src/Tests/` 하위 단일 `*.csproj` 자동 감지.
        4순위: 전체 sln (안전 fallback — 느릴 수 있음).
        """
        scoped = self._scoped_test_target()
        if scoped:
            return scoped
        test_projects = sorted(self._cfg.root.glob("Src/Tests/**/*.csproj"))
        if len(test_projects) == 1:
            return test_projects[0].relative_to(self._cfg.root).as_posix()
        return self._solution_path_rel()

    def _solution_test_command(self, *, with_filter: bool) -> str:
        # filter 있는 step(1, 2)은 좁은 테스트 타깃으로 빌드 스코프 축소.
        # filter 없는 step(3, 회귀)은 전체 sln 강제 — 미참조 프로젝트 회귀까지 잡는다.
        target = self._test_target() if with_filter else self._solution_path_rel()
        base = f"dotnet test {target} --no-restore"
        if with_filter:
            return base + ' --filter "<feature-specific-filter>"'
        return base

    def _phase_index_rel(self) -> str:
        return f"phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/index.json"

    def _contract_skeleton_body(self, docs_scope: list[str], user_prompts: list[str]) -> str:
        prompt_text = "\n".join(self._prompt_lines(user_prompts))
        docs_text = "\n".join(self._doc_lines(docs_scope))
        index_rel = self._phase_index_rel()
        return (
            "# Step 0: contract-skeleton\n\n"
            "## 읽어야 할 파일\n\n"
            "- `CLAUDE.md`\n"
            f"{docs_text}\n"
            "- 구현 대상 영역의 기존 interface/DTO/route 파일은 `rg`로 좁혀서 읽는다.\n\n"
            "## 작업\n\n"
            "이번 step의 목적은 step1 테스트와 step2 구현이 의존할 **계약 표면**을 먼저 만드는 것이다.\n\n"
            "다음 요구사항만 수행한다.\n\n"
            f"{prompt_text}\n\n"
            "허용 작업 (모두 **신규 타입 추가**에 한정한다):\n\n"
            "- 신규 interface 추가\n"
            "- 신규 request/response DTO 추가\n"
            "- 신규 enum/constant 추가\n"
            "- 신규 use case port/interface 추가\n"
            "- 신규 controller route skeleton 추가\n"
            "- 신규 repository/client method signature 추가 (기존 repository 인터페이스에 메서드 추가도 허용)\n"
            "- 컴파일 통과를 위한 최소 skeleton (미구현부는 "
            "`throw new NotImplementedException();` 또는 명확한 placeholder)\n"
            "- DI 등록은 build 통과를 위해 필요한 경우에만 최소로 수행하고, "
            "실제 동작 가능한 구현처럼 보이지 않게 제한한다.\n\n"
            "**기존 도메인 entity 스키마 변경 금지**:\n\n"
            "- `Order`, `OrderItem`, `Payment` 등 기존 도메인 entity의 public "
            "필드/property/생성자/메서드 시그니처를 추가·수정·삭제하지 않는다.\n"
            "- FRD가 기존 entity에 부재한 필드(예: `Order.UnitPrice`)를 전제로 한다면, "
            "해당 필드를 직접 추가하지 말고 본 step을 `blocked` 상태로 마크하라.\n"
            f'- `blocked` 처리 절차: `{index_rel}` 의 step 0 `status`를 `"blocked"` 로 '
            "`blocked_reason` 에 (a) 부재 필드 목록, (b) 어느 FRD 규칙이 그 필드를 요구하는지, "
            "(c) FRD §19 결정 요청 — 세 항목을 한 줄로 기록한 뒤 즉시 종료한다. "
            "이후는 사용자가 docs/PRD/FRD를 갱신하고 retry한다.\n\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            "git diff --stat HEAD\n"
            "```\n\n"
            "**본 step은 `dotnet build`를 실행하지 않는다.** 이유: skeleton의 컴파일은 step 1의 "
            "`dotnet test`가 빌드를 겸하면서 검증한다. 4-step 합산 빌드 횟수를 4회 → 3회로 줄여 "
            "wall clock(특히 production-scale 코드베이스에서 step 0 자체의 풀 sln 빌드 비용)을 제거한다.\n\n"
            "## 검증 절차\n\n"
            "1. `git diff --stat HEAD` 를 실행해 변경 파일 목록을 확인한다.\n"
            "2. 변경 파일에 `Domain/Orders/Order.cs` 등 기존 도메인 entity 파일이 포함됐는지 확인한다. "
            "포함됐다면 step을 `blocked` 로 전환한다.\n"
            "3. 변경 파일이 모두 신규 파일이거나 신규 시그니처 추가에 한정되는지 검토한다. "
            "(skeleton 컴파일 검증은 step 1에 위임한다.)\n"
            f"4. `{index_rel}` 의 step 0 status를 갱신한다.\n"
            "5. summary에는 생성/수정한 contract·interface·DTO 파일, "
            "실제 구현이 없음, 기존 entity 변경 없음 여부를 200자 이내로 기록한다.\n\n"
            "## 금지사항\n\n"
            "- **기존 도메인 entity 스키마 변경 금지**. 이유: F009의 `Order.cs` 필드 추가가 "
            "F002·F003·F007 컴파일을 깨뜨려 step 0가 14분 이상 소요된 회귀 사례를 차단한다. "
            "부재 필드는 `blocked` 처리한다.\n"
            "- 실제 비즈니스 로직 구현 금지. 이유: step2 green-implementation의 책임이다.\n"
            "- 조건문/반복문 기반 처리 로직 작성 금지. 이유: 계약 표면만 만든다.\n"
            "- 저장소 I/O 구현 금지. 이유: step2 책임이다.\n"
            "- 테스트를 통과시킬 수 있는 실제 구현 금지. 이유: step1이 의도한 이유로 실패해야 한다.\n"
            "- `docs/**`, `CLAUDE.md`, `PHASE_SCHEMA.md`, `.claude/commands/**`, "
            "`scripts/forge_full.py` 수정 금지. 이유: 본 step 범위 밖이다.\n"
            "- 범위 밖 리팩터링 금지. 이유: 외과적 수정 원칙.\n"
        )

    def _red_tests_body(self, docs_scope: list[str], user_prompts: list[str]) -> str:
        prompt_text = "\n".join(self._prompt_lines(user_prompts))
        docs_text = "\n".join(self._doc_lines(docs_scope))
        test_cmd = self._solution_test_command(with_filter=True)
        index_rel = self._phase_index_rel()
        return (
            "# Step 1: red-tests\n\n"
            "## 읽어야 할 파일\n\n"
            "- `CLAUDE.md`\n"
            f"{docs_text}\n"
            "- step0에서 추가/수정한 interface·DTO·route skeleton\n"
            "- 기존 테스트 프로젝트 구조 (fixture/fake/stub 패턴 확인)\n\n"
            "## 작업\n\n"
            "이번 step의 목적은 구현 전에 **실패하는 테스트**를 먼저 작성하는 것이다.\n\n"
            "다음 요구사항만 수행한다.\n\n"
            f"{prompt_text}\n\n"
            "허용 작업:\n\n"
            "- FRD 요구사항을 검증하는 단위 테스트/통합 테스트 추가\n"
            "- test fixture, fake, stub 추가\n"
            "- 테스트 프로젝트 참조 추가가 필요한 경우 최소 수정\n\n"
            "**중요 — 본 step의 성공 기준**:\n\n"
            "- 테스트 통과가 아니다.\n"
            "- 새로 작성한 테스트가 **의도한 이유**로 **실패해야** 한다.\n"
            "- 실패 이유는 step2 구현이 아직 없기 때문이어야 한다.\n\n"
            "허용되는 실패:\n\n"
            "- `NotImplementedException` 발생\n"
            "- expected/actual mismatch\n"
            "- placeholder 반환으로 인한 assertion 실패\n\n"
            "허용되지 않는 실패:\n\n"
            "- 컴파일 실패\n"
            "- 테스트 프로젝트 로딩 실패\n"
            "- null reference 같은 테스트 자체 버그\n"
            "- 환경 문제(SDK/패키지/경로 오류)\n\n"
            "특히 **컴파일 실패**, namespace 오류, 테스트 인프라 오류는 허용하지 않는다.\n\n"
            "**컴파일 실패가 step 0 skeleton 결함에서 비롯된 경우** (예: 누락된 using, 잘못된 시그니처, "
            "기존 entity 미존재 필드 참조): 본 step에서 step 0 산출물을 수정하지 마라. 대신 본 step을 "
            "`blocked` 로 마크하고 `blocked_reason` 에 (a) 컴파일 에러 메시지 1~2줄, "
            "(b) 결함 위치(파일:라인), (c) `step 0 skeleton 결함이므로 step 0를 pending으로 reset 후 재실행 권장` "
            "을 기록한 뒤 즉시 종료한다. 이유: step 0가 build 검증을 생략했으므로 "
            "step 1이 첫 컴파일 게이트 역할을 한다.\n\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            f"{test_cmd}\n"
            "```\n\n"
            "위 명령은 **실패해야** 한다. 실패의 이유는 위에 명시한 **의도한 이유**(step2 미구현)이어야 한다.\n\n"
            "## 검증 절차\n\n"
            f"1. `{test_cmd}` 를 실행한다.\n"
            "2. 실패한 테스트명과 실패 이유를 확인한다.\n"
            "3. 실패가 의도한 red 상태인지 확인한다 (컴파일 실패·인프라 오류이면 본 step은 미완료).\n"
            f"4. `{index_rel}` 의 step 1 status를 갱신한다.\n"
            "5. **본 step의 status를 `completed`로 마크하는 조건은 단 두 가지다**: "
            "(a) 새로 추가한 테스트가 의도한 이유로 실패했고, (b) 컴파일·인프라 오류가 아니다. "
            "이 두 조건이 모두 만족하면 즉시 `completed`로 마크하라. **테스트를 통과시키려 하지 마라** — "
            "테스트가 통과해버렸다면 본 step은 실패다(green 신호 위조).\n"
            "6. summary 권장 형식: `red OK: 추가 N개 테스트 / 실패 사유: "
            "<NotImplementedException|assertion mismatch|placeholder>` — "
            "이 형식이면 후속 step이 의도된 red인지 즉시 판정 가능하다. 200자 이내.\n\n"
            "## 금지사항\n\n"
            "- 제품 코드 실제 구현 금지. 이유: step2의 책임이다.\n"
            "- step0 계약을 테스트 통과 목적으로 변경 금지. 이유: 계약은 step0에서 고정된다.\n"
            "- 테스트 skip/ignore 처리 금지. 이유: red 신호를 가린다.\n"
            "- 약한 assertion 작성 금지 (예: 항상 true). 이유: red 신호를 가린다.\n"
            "- compile-only 테스트 금지. 이유: 동작 검증이 본 step의 목적이다.\n"
            "- 테스트가 의도하지 않게 통과하도록 expected를 placeholder 반환값에 맞추는 것 금지. 이유: red 위조이다.\n"
        )

    def _green_implementation_body(self, docs_scope: list[str], user_prompts: list[str]) -> str:
        prompt_text = "\n".join(self._prompt_lines(user_prompts))
        docs_text = "\n".join(self._doc_lines(docs_scope))
        test_cmd = self._solution_test_command(with_filter=True)
        index_rel = self._phase_index_rel()
        return (
            "# Step 2: green-implementation\n\n"
            "## 읽어야 할 파일\n\n"
            "- `CLAUDE.md`\n"
            f"{docs_text}\n"
            "- step0의 interface·DTO·route skeleton\n"
            "- step1에서 추가한 실패 테스트 파일 전체\n\n"
            "## 작업\n\n"
            "이번 step의 목적은 step1 실패 테스트를 통과시키는 **최소 제품 코드**를 구현하는 것이다.\n\n"
            "다음 요구사항만 수행한다.\n\n"
            f"{prompt_text}\n\n"
            "허용 작업:\n\n"
            "- step1 테스트를 통과시키는 application/domain/infrastructure/controller 코드 구현\n"
            "- 컴파일 오류 해결을 위한 최소 수정\n\n"
            "테스트 파일 수정은 **원칙적으로 금지**한다. 단 namespace/import/fixture wiring 같은 "
            "컴파일 보정은 허용하되 summary에 반드시 이유와 범위를 기록한다.\n\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            f"{test_cmd}\n"
            "```\n\n"
            "(`dotnet test`는 빌드를 겸한다 — 별도 `dotnet build`를 추가로 실행하지 마라.)\n\n"
            "## 검증 절차\n\n"
            "1. step1에서 작성한 테스트가 green으로 바뀌었는지 확인한다.\n"
            f"2. `{test_cmd}` 1회만 실행한다(빌드 겸용). 추가 `dotnet build`는 시간 낭비이므로 금지.\n"
            "3. step1 테스트를 삭제·완화·우회하지 않았는지 직접 diff로 확인한다.\n"
            f"4. `{index_rel}` 의 step 2 status를 갱신한다.\n"
            "5. summary에는 구현 핵심 파일, step1 테스트 green 전환 결과, "
            "테스트 삭제·완화 없음 여부를 200자 이내로 기록한다.\n\n"
            "## 금지사항\n\n"
            "- step1 **테스트 삭제** 금지. 이유: red 신호 무력화이다.\n"
            "- assertion 완화 금지 (expected를 actual에 맞추는 변경 포함). 이유: 테스트 의미가 사라진다.\n"
            "- expected value 변경 금지. 이유: 동일한 assertion 완화 패턴이다.\n"
            "- 테스트 skip/ignore 처리 금지. 이유: red 신호 무력화이다.\n"
            "- filter 조작으로 일부 테스트만 통과한 것처럼 만들기 금지. 이유: green 신호 위조이다.\n"
            "- FRD 범위 밖 기능 추가 금지. 이유: scoped 작업 원칙.\n"
            "- 대규모 리팩터링 금지. 이유: step3의 책임이다.\n"
        )

    def _refactor_and_regression_body(self, docs_scope: list[str], user_prompts: list[str]) -> str:
        prompt_text = "\n".join(self._prompt_lines(user_prompts))
        docs_text = "\n".join(self._doc_lines(docs_scope))
        full_test_cmd = self._solution_test_command(with_filter=False)
        index_rel = self._phase_index_rel()
        return (
            "# Step 3: refactor-and-regression\n\n"
            "## 읽어야 할 파일\n\n"
            "- `CLAUDE.md`\n"
            f"{docs_text}\n"
            "- step0~step2에서 추가/수정한 모든 코드 (정리 대상 식별)\n\n"
            "## 작업\n\n"
            "이번 step의 목적은 구현 후 **정리**와 **전체 회귀 검증**을 수행하는 것이다.\n\n"
            "다음 요구사항만 수행한다.\n\n"
            f"{prompt_text}\n\n"
            "허용 작업:\n\n"
            "- 중복 제거\n"
            "- naming 정리\n"
            "- placeholder 제거 (step0 잔여 `NotImplementedException` 등)\n"
            "- 불필요한 using 제거\n"
            "- 작은 구조 정리\n"
            f"- phase summary 갱신 (= `{index_rel}` 의 해당 step summary/status 갱신)\n\n"
            "## Acceptance Criteria\n\n"
            "```bash\n"
            f"{full_test_cmd}\n"
            "git diff --check\n"
            "```\n\n"
            "(`dotnet test`는 빌드를 겸한다 — 별도 `dotnet build`를 추가로 실행하지 마라. "
            "test 명령에 filter가 없는 점에 주의 — 전체 회귀를 강제한다.)\n\n"
            "## 검증 절차\n\n"
            f"1. `{full_test_cmd}` 를 실행한다 (filter 없이 전체 테스트, 빌드 겸용).\n"
            "2. `git diff --check` 를 실행한다.\n"
            f"3. `{index_rel}` 의 step 3 status를 갱신한다.\n"
            "4. summary에는 정리 내용, 전체 test 결과, `git diff --check` 결과를 "
            "200자 이내로 기록한다.\n\n"
            "## 금지사항\n\n"
            "- 새 기능 추가 금지. 이유: 정리 step이다.\n"
            "- 테스트 의미 변경 금지. 이유: 회귀 신호를 가린다.\n"
            "- 테스트 삭제/skip 금지. 이유: 회귀 신호를 가린다.\n"
            "- 문서 변경 금지. 이유: 본 step 범위 밖이다.\n"
            "- 큰 구조 변경 금지. 이유: 외과적 수정 원칙.\n"
        )


# ============================================================================
# 인라인 실행 공용 헬퍼 — 메인 repo 누수 baseline + step 완료 commit
# ============================================================================
def _root_porcelain() -> list[str]:
    """메인 repo(ROOT)의 `git status --porcelain` 라인 정렬 집합.

    인라인 세션이 워크트리 대신 메인 repo에 코드를 잘못 떨군 경우를 record-step이
    탐지하기 위한 기준선/현재값 비교용(OI-1).
    """
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return sorted(l for l in (r.stdout or "").splitlines() if l.strip())


def commit_completed_step(
    store: "IndexStore",
    git: "GitOperations",
    cfg: "PhaseConfig",
    phase_name: str,
    step_num: int,
    step_name: str,
) -> None:
    """완료된 step을 2단계 commit(feat 코드 + chore 아티팩트)으로 기록한다.

    child 경로(StepExecutor._on_success)와 인라인 경로(ForgeScope.record_step)가
    동일 commit 규칙을 공유하도록 추출한 함수. index.json·step{N}-output.json·
    step{N}-status.json 은 reset_paths로 feat 에서 빼 chore 로 보낸다(feat=코드만).
    """
    store.mark_completed(step_num)
    output_rel = f"phases/{PHASES_SUBDIR}/{cfg.phase_dir_name}/step{step_num}-output.json"
    index_rel = f"phases/{PHASES_SUBDIR}/{cfg.phase_dir_name}/index.json"
    status_rel = f"phases/{PHASES_SUBDIR}/{cfg.phase_dir_name}/step{step_num}-status.json"
    git.two_step_commit(
        feat_msg=StepExecutor.FEAT_MSG.format(phase=phase_name, num=step_num, name=step_name),
        chore_msg=StepExecutor.CHORE_MSG.format(phase=phase_name, num=step_num),
        reset_paths=[output_rel, index_rel, status_rel],
    )


# ============================================================================
# StepExecutor — 단일 step 라이프사이클 (재시도 + commit)
# ============================================================================
class StepExecutor:
    """phase 안의 단일 step 실행. 재시도, status 전이, 2단계 commit를 담당."""

    MAX_RETRIES = 3
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"

    def __init__(
        self,
        cfg: PhaseConfig,
        store: IndexStore,
        git: GitOperations,
        invoker: ClaudeInvoker,
        *,
        guardrails: str,
        project: str,
        phase_name: str,
        total: int,
    ):
        self._cfg = cfg
        self._store = store
        self._git = git
        self._invoker = invoker
        self._guardrails = guardrails
        self._project = project
        self._phase_name = phase_name
        self._total = total
        # 첫 호출에서만 가드레일·작업 규칙 전체를 prompt에 박는다.
        # 이후 호출은 동일 세션을 -r로 이어 받으므로 재주입 불필요 → 캐시 적중.
        self._is_first_call = True
        # 마지막 claude 호출의 output_tokens — ForgeScope의 timings 진단에서 읽는다.
        self.last_output_tokens = 0

    def run(self, step: dict) -> None:
        """단일 step을 retry 포함하여 실행. 완료/실패/blocked 시 sys.exit으로 종료할 수 있음."""
        step_num, step_name = step["step"], step["name"]
        done_count = self._store.completed_count()
        prev_error: Optional[str] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            elapsed = self._run_attempt(step, prev_error, attempt, done_count)
            # 자식이 쓴 step{N}-status.json 을 index.json 에 프로그램적으로 반영(손수편집 금지).
            status = self._store.ingest_child_status(step_num)
            if status == "completed":
                self._on_success(step_num, step_name, elapsed)
                return
            if status == "blocked":
                self._on_blocked(step_num, step_name, elapsed)
                # _on_blocked는 sys.exit
            err_msg = self._store.read_step_error(step_num)
            if attempt < self.MAX_RETRIES:
                prev_error = err_msg
                self._store.reset_for_retry(step_num)
                _qprint(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                self._on_final_failure(step_num, step_name, err_msg, elapsed)
                # _on_final_failure는 sys.exit

    # ---- 내부 헬퍼 ----

    def _run_attempt(self, step: dict, prev_error: Optional[str], attempt: int, done_count: int) -> int:
        step_num, step_name = step["step"], step["name"]
        step_context = self._store.step_summaries()
        preamble = self._build_preamble(step_context, prev_error)
        tag = f"Step {step_num}/{self._total - 1} ({done_count} done): {step_name}"
        if self._is_first_call:
            tag += " [session-init]"
        if attempt > 1:
            tag += f" [retry {attempt}/{self.MAX_RETRIES}]"
        try:
            with progress_indicator(tag) as pi:
                self._invoke_claude(step, preamble)
                return int(pi.elapsed)
        except KeyboardInterrupt:
            self._store.mark_interrupted(step_num)
            print(
                f"\n  ⚠ Interrupted. Step {step_num} ({step_name}) marked as 'interrupted'.",
                file=sys.stderr,
            )
            sys.exit(EXIT_KBI)

    def _build_preamble(self, step_context: str, prev_error: Optional[str]) -> str:
        commit_example = self.FEAT_MSG.format(phase=self._phase_name, num="N", name="<step-name>")
        retry_section = ""
        if prev_error:
            retry_section = f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n{prev_error}\n\n---\n\n"
        if self._is_first_call:
            # 첫 호출: 가드레일·작업 규칙 전체 주입. 이 prompt가 세션 컨텍스트가 되어
            # 후속 -r 호출에서 cache_read로 재사용된다.
            return (
                f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
                f"{self._guardrails}\n\n---\n\n"
                f"{step_context}{retry_section}"
                f"## 작업 규칙 (이후 step에도 동일 적용)\n\n"
                f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
                f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
                f"3. 기존 테스트를 깨뜨리지 마라.\n"
                f"4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
                f"5. **index.json 은 절대 수정하지 마라 (forge 가 소유·관리한다).** 대신 이 step 의 결과를 "
                f"`phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/step<현재step번호>-status.json` 파일에 "
                f"JSON 한 객체로 새로 기록하라:\n"
                f'   - AC 통과 → {{"status": "completed", "summary": "<이 step 산출물 한 줄 요약>"}}\n'
                f'   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → {{"status": "error", "error_message": "<원인>"}}\n'
                f'   - 사용자 개입이 필요한 경우 → {{"status": "blocked", "blocked_reason": "<이유>"}} 기록 후 즉시 중단\n'
                f"   이 파일은 작은 단일 객체이므로 유효한 JSON 으로 정확히 작성하라.\n"
                f"6. 모든 변경사항을 커밋하라:\n"
                f"   {commit_example}\n\n---\n\n"
            )
        # 후속 호출: 가드레일·작업 규칙은 세션 컨텍스트에 이미 있음. 변동 부분만 전달.
        return f"## 다음 step을 수행하세요\n\n{step_context}{retry_section}"

    def _invoke_claude(self, step: dict, preamble: str) -> None:
        step_num, step_name = step["step"], step["name"]
        step_file = self._cfg.phase_dir / f"step{step_num}.md"
        if not step_file.exists():
            self._handle_missing_step_file(step_num, step_name, step_file)
            return
        prompt = preamble + step_file.read_text(encoding="utf-8")
        returncode, stdout, stderr = self._invoker.call(prompt)
        if returncode != 0:
            print(f"\n  WARN: Claude가 비정상 종료됨 (code {returncode})")
            if stderr:
                print(f"  stderr: {stderr[:500]}")
        usage = _extract_usage(stdout)
        if usage:
            cr = usage.get("cache_read_input_tokens", 0) or 0
            cw = usage.get("cache_creation_input_tokens", 0) or 0
            inp = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            _qprint(f"    usage: in={inp} out={out} cache_read={cr} cache_create={cw}")
        self.last_output_tokens = (usage or {}).get("output_tokens", 0) or 0
        self._persist_step_output(
            step_num,
            {
                "step": step_num,
                "name": step_name,
                "exitCode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "usage": usage,
            },
        )
        # 첫 호출 성공 후 다음 호출부터는 incremental preamble + -r 모드.
        # returncode != 0 시에도 세션은 생성됐을 수 있어 토글 (재시도는 같은 세션 이어 받기).
        if self._is_first_call:
            self._is_first_call = False

    def _handle_missing_step_file(self, step_num: int, step_name: str, step_file: Path) -> None:
        reason = f"step{step_num}.md 파일이 없습니다 ({step_file}). 작성 후 status를 'pending'으로 reset하세요."
        self._store.mark_blocked(step_num, reason)
        self._persist_step_output(
            step_num,
            {
                "step": step_num,
                "name": step_name,
                "exitCode": -2,
                "stdout": "",
                "stderr": reason,
            },
        )

    def _persist_step_output(self, step_num: int, payload: dict) -> None:
        out_path = self._cfg.phase_dir / f"step{step_num}-output.json"
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _commit_step(self, step_num: int, step_name: str) -> None:
        output_rel = f"phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/index.json"
        feat_msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
        chore_msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
        self._git.two_step_commit(
            feat_msg=feat_msg,
            chore_msg=chore_msg,
            reset_paths=[output_rel, index_rel],
        )

    def _on_success(self, step_num: int, step_name: str, elapsed: int) -> None:
        commit_completed_step(
            self._store, self._git, self._cfg, self._phase_name, step_num, step_name
        )
        _qprint(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")

    def _on_blocked(self, step_num: int, step_name: str, elapsed: int) -> None:
        reason = self._store.mark_blocked_at(step_num)
        print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
        print(f"    Reason: {reason}")
        self._store.update_top("blocked")
        sys.exit(EXIT_BLOCKED)

    def _on_final_failure(self, step_num: int, step_name: str, err_msg: str, elapsed: int) -> None:
        self._store.mark_error(step_num, err_msg, self.MAX_RETRIES)
        self._commit_step(step_num, step_name)
        print(f"  ✗ Step {step_num}: {step_name} failed after {self.MAX_RETRIES} attempts [{elapsed}s]")
        print(f"    Error: {err_msg}")
        self._store.update_top("error")
        sys.exit(EXIT_ERR)


# ============================================================================
# ForgeScope — composition root
# ============================================================================
class ForgeScope:
    """전체 흐름 조립체. run() = (필요시 splitter) → 가드레일 → 브랜치 → step 순회 → finalize."""

    def __init__(self, args: argparse.Namespace):
        self._args = args
        # --- 계측: 구간별 wall-clock. atexit으로 종료 경로(성공/blocked/error/KBI) 모두에서
        #     1줄 [timings] 요약을 best-effort 출력한다. ---
        self._t0 = time.monotonic()
        self._timings: list[tuple[str, float]] = []        # (label, seconds)
        self._step_usage: list[tuple[int, int]] = []        # (step_num, output_tokens)
        self._timings_printed = False
        atexit.register(self._emit_timings_summary)
        # 기본: phase 시작 시 .worktrees/<phase>/ 격리 워크트리를 보장한다. 이후 모든
        # 컴포넌트(PhaseConfig·GitOperations·GuardrailLoader·ClaudeInvoker)는
        # 메인 repo가 아닌 워크트리 root를 기준으로 동작한다.
        # --no-worktree: 워크트리를 만들지 않고 메인 repo(ROOT)에서 직접 실행한다.
        # 산출물·step 코드·commit이 현재 브랜치에 직접 기록되며 격리가 없다.
        self._no_worktree = bool(getattr(args, "no_worktree", False))
        if self._no_worktree:
            self._wt = None
            worktree_root = ROOT
            _qprint(f"  Worktree: 생성 안 함 — 메인 repo에서 직접 실행 ({ROOT})")
        else:
            self._wt = WorktreeManager(ROOT, args.phase_dir, force=args.force)
            with self._timed("worktree"):
                worktree_root = self._wt.ensure()
        # 워크트리/in-place 공통: 가드레일은 ROOT에서 읽으므로 ROOT에 CLAUDE.md만 있으면 된다.
        # (워크트리로의 docs/CLAUDE.md 복사는 폐지 — 읽기 ROOT / 쓰기 worktree 모델.)
        self._verify_root_guardrail(ROOT)
        self._cfg = PhaseConfig(args.phase_dir, root=worktree_root)
        # docs_scope 검증·문서 읽기는 ROOT(메인 repo) 기준. 워크트리(worktree_root)는
        # 코드/phase 산출물 "쓰기" 전용 — 복사 없이 ROOT의 docs를 직접 읽는다.
        self._validator = ScopeValidator(ROOT)
        trust = _is_trusted(args.trust)
        # invoker 2종 분리:
        # - splitter_invoker: 일회성 strict-JSON 호출. 세션 미공유.
        # - step_invoker: phase 단위 UUID로 세션 공유. step 0 첫 호출 시 가드레일이
        #   conversation에 캐시되고, step 1+에서 -r로 이어 받아 cache_read 적중.
        # cwd=worktree_root 명시로 자식 claude가 워크트리에서 파일 I/O 수행.
        # splitter·step 모두 Opus 4.8 + effort high 가 기본 (--step-model/--step-effort 로 override).
        step_model = getattr(args, "step_model", None) or "claude-opus-4-8"
        step_effort = getattr(args, "step_effort", None) or "high"
        lean = not bool(getattr(args, "full_fleet", False))
        child_tools = getattr(args, "child_tools", None) or DEFAULT_CHILD_TOOLS
        self._splitter_invoker = ClaudeInvoker(
            trust=trust, use_bare=True, cwd=worktree_root,
            model=step_model, effort=step_effort,
            lean=lean, child_tools=child_tools,
        )
        self._phase_session_id = str(uuid.uuid4())
        self._step_invoker = ClaudeInvoker(
            trust=trust,
            session_id=self._phase_session_id,
            use_session=True,
            use_bare=True,
            model=step_model,
            effort=step_effort,
            cwd=worktree_root,
            lean=lean,
            child_tools=child_tools,
            # 세션 -r 재사용 시 동적 섹션을 첫 user 메시지로 빼 prompt-cache 적중률↑.
            exclude_dynamic_sys_prompt=True,
        )
        compact_docs = (
            bool(getattr(args, "compact_docs", False))
            or (getattr(args, "preset", "auto") in ("frd-implementation", "contract-tdd"))
            or bool(getattr(args, "single_step", False))
        )
        self._guardrail_loader = GuardrailLoader(
            ROOT,
            self._validator,
            strict=args.strict,
            compact_docs=compact_docs,
        )
        self._git = GitOperations(self._cfg.root, force=args.force)
        self._splitter: Optional[StepSplitter] = None  # lazy

    @staticmethod
    def _verify_root_guardrail(root: Path) -> None:
        """ROOT(메인 repo)에 가드레일 CLAUDE.md가 있는지 확인하고, 없으면 fail-fast.

        워크트리/in-place 두 모드 공통 가드. forge-scope는 docs·CLAUDE.md를 ROOT에서
        직접 읽으므로(워크트리로의 복사 폐지) ROOT에 CLAUDE.md만 있으면 충분하다.
        없으면 가드레일 없이 코드가 생성되는 사고를 막기 위해 즉시 중단한다.
        """
        if (root / "CLAUDE.md").exists():
            return
        print(
            "ERROR: 가드레일 CLAUDE.md가 ROOT에 없습니다.\n"
            f"  경로: {root / 'CLAUDE.md'}\n"
            "  가드레일 없이 코드가 생성되는 것을 막기 위해 중단합니다.\n"
            "  부트스트랩(단계 2)을 먼저 수행하거나 CLAUDE.md를 생성한 뒤 재실행하세요.",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERR)

    @contextlib.contextmanager
    def _timed(self, label: str):
        """구간 wall-clock을 self._timings에 기록. 예외/sys.exit 시에도 finally로 기록."""
        t = time.monotonic()
        try:
            yield
        finally:
            self._timings.append((label, time.monotonic() - t))

    def _emit_timings_summary(self) -> None:
        """[timings] 1줄 요약을 stderr로 출력. atexit 등록 — 모든 종료 경로에서 1회만."""
        if self._timings_printed or not self._timings:
            return
        self._timings_printed = True
        usage_by_step = dict(self._step_usage)
        parts = []
        for label, secs in self._timings:
            tok = ""
            if label.startswith("step"):
                try:
                    n = int(label[4:])
                except ValueError:
                    n = None
                if n is not None and n in usage_by_step:
                    tok = f"(out={_fmt_tokens(usage_by_step[n])})"
            parts.append(f"{label}={secs:.1f}s{tok}")
        total = time.monotonic() - self._t0
        print("[timings] " + " ".join(parts) + f" total={total:.1f}s", file=sys.stderr)
        if getattr(self._args, "timings", False):
            for label, secs in self._timings:
                print(f"  [timings] {label:<14}{secs:8.1f}s", file=sys.stderr)

    def run(self) -> int:
        self._check_external_dirty()
        self._check_frd_consistency()
        self._maybe_run_splitter()
        self._verify_phase_dir_state()
        store = IndexStore(self._cfg)
        idx = store.load()
        store.validate_schema(idx)
        store.upsert_top()
        project, phase_name = store.get_meta()
        total = store.get_total()

        self._print_header(phase_name, total)
        self._check_blockers(store)
        # 브랜치/작업 트리는 ForgeScope.__init__의 WorktreeManager가 이미 보장함.
        with self._timed("warmup"):
            self._warmup_dotnet()
        try:
            with self._timed("guardrail"):
                guardrails = self._guardrail_loader.load(store.get_docs_scope())
        except (ValueError, FileNotFoundError) as e:
            print(
                f"ERROR: 가드레일 로딩 실패 — index.json의 docs_scope를 확인하세요: {e}",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        store.ensure_created_at()
        # 커밋 메시지 AI 재작성용 base ref(첫 step 커밋 전 HEAD)를 1회 기록. 워크트리 모드만.
        if not self._no_worktree:
            store.ensure_git_base(self._git.head_sha())

        # 인라인 모드: scaffold(워크트리·plan·warmup·가드레일)까지만 하고 매니페스트를
        # stdout으로 넘긴 뒤 종료. step 실행은 호출 세션이 인라인으로 수행한다(자식 spawn 0).
        if getattr(self._args, "scaffold_only", False):
            self._emit_scaffold_manifest(store)
            return EXIT_OK

        executor = StepExecutor(
            self._cfg,
            store,
            self._git,
            self._step_invoker,
            guardrails=guardrails,
            project=project,
            phase_name=phase_name,
            total=total,
        )
        self._execute_all(store, executor, total)
        self._finalize(store, phase_name)
        return EXIT_OK

    # ---- 인라인 실행 (scaffold-only / record-step / finalize) ----

    def _emit_scaffold_manifest(self, store: IndexStore) -> None:
        """scaffold 결과(워크트리·step 목록·docs_scope·메인repo baseline)를 JSON으로 출력."""
        if not self._no_worktree:
            store.set_root_baseline(_root_porcelain())
        idx = store.load()
        steps = [
            {
                "step": s["step"],
                "name": s["name"],
                "status": s["status"],
                "step_file": str((self._cfg.phase_dir / f"step{s['step']}.md").resolve()),
            }
            for s in sorted(idx.get("steps", []), key=lambda x: x["step"])
        ]
        manifest = {
            "root": str(ROOT.resolve()),
            "worktree": str(self._cfg.root.resolve()),
            "phase_dir": str(self._cfg.phase_dir.resolve()),
            "phase": self._cfg.phase_dir_name,
            "docs_scope": store.get_docs_scope(),
            "no_worktree": self._no_worktree,
            "root_dirty_baseline": store.get_root_baseline(),
            "steps": steps,
        }
        print(json.dumps(manifest, ensure_ascii=False))

    def _git_worktree_dirty(self) -> bool:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self._cfg.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return bool((r.stdout or "").strip())

    def _record_result(
        self, result: str, n: int, *, attempts: int = 0, max_attempts: int = 0, message: str = ""
    ) -> int:
        print(
            json.dumps(
                {
                    "result": result,
                    "step": n,
                    "attempts": attempts,
                    "max": max_attempts,
                    "message": message,
                },
                ensure_ascii=False,
            )
        )
        return {
            "completed": EXIT_OK,
            "retry": EXIT_OK,
            "blocked": EXIT_BLOCKED,
            "error": EXIT_ERR,
        }[result]

    def record_step(self, n: int) -> int:
        """인라인 세션이 끝낸 step N을 수확한다(사후가드→counter→gate→ingest→commit)."""
        store = IndexStore(self._cfg)
        store.validate_schema(store.load())
        _, phase_name = store.get_meta()
        steps = store.load()["steps"]
        if not any(s["step"] == n for s in steps):
            return self._record_result("error", n, message=f"step {n} 없음")
        # 1) OI-1 사후가드: 인라인 세션이 메인 repo(ROOT)에 누수했는지 baseline 대비 탐지.
        if not self._no_worktree:
            leaked = sorted(set(_root_porcelain()) - set(store.get_root_baseline()))
            if leaked:
                return self._record_result(
                    "error", n,
                    message=f"메인 repo 누수 {leaked} — 작업을 워크트리({self._cfg.root})로 옮겨 재실행",
                )
        # 2) 워크트리 무변경 = step 미수행
        if not self._git_worktree_dirty():
            return self._record_result("error", n, message="워크트리에 변경 없음 — step 미수행")
        # 3) OI-2 하드 백스톱 counter
        attempts = store.increment_attempt(n)
        max_attempts = getattr(self._args, "max_attempts", StepExecutor.MAX_RETRIES)
        # 4) status ingest (OI-4: step{N}-status.json 재사용)
        status = store.ingest_child_status(n)
        if status == "completed":
            # 5) TDD gate: 이전 step 미완이면 거부(red→green 순서 보존)
            prev_incomplete = [
                s["step"]
                for s in store.load()["steps"]
                if s["step"] < n and s["status"] != "completed"
            ]
            if prev_incomplete:
                return self._record_result(
                    "error", n, attempts=attempts, max_attempts=max_attempts,
                    message=f"이전 step 미완 {prev_incomplete} — 순서대로 진행하라",
                )
            step_name = next(s["name"] for s in store.load()["steps"] if s["step"] == n)
            commit_completed_step(store, self._git, self._cfg, phase_name, n, step_name)
            return self._record_result("completed", n, attempts=attempts, max_attempts=max_attempts)
        if status == "blocked":
            store.update_top("blocked")
            return self._record_result(
                "blocked", n, attempts=attempts, max_attempts=max_attempts,
                message=store.read_step_error(n),
            )
        # 6) 미완(pending/error) — 백스톱 판정
        if attempts >= max_attempts:
            store.mark_error(n, store.read_step_error(n), max_attempts)
            store.update_top("error")
            return self._record_result(
                "error", n, attempts=attempts, max_attempts=max_attempts,
                message="최대 시도 초과",
            )
        store.reset_for_retry(n)
        return self._record_result("retry", n, attempts=attempts, max_attempts=max_attempts)

    def finalize_only(self) -> int:
        """모든 step 완료 후 phase를 마감한다(finalize+top index+push)."""
        store = IndexStore(self._cfg)
        store.validate_schema(store.load())
        pending = [s["step"] for s in store.load()["steps"] if s["status"] != "completed"]
        if pending:
            print(
                json.dumps({"result": "error", "message": f"미완 step {pending}"}, ensure_ascii=False)
            )
            return EXIT_ERR
        _, phase_name = store.get_meta()
        self._finalize(store, phase_name)
        print(json.dumps({"result": "finalized", "phase": phase_name}, ensure_ascii=False))
        return EXIT_OK

    # ---- 내부 헬퍼 ----

    def _maybe_run_splitter(self) -> None:
        # max_steps는 splitter._validate_plan에서 step 수 상한 검사에 쓰인다.
        # contract-tdd는 deterministic 4-step이므로 --single-step과 동시 지정돼도
        # 4-step plan이 검증을 통과해야 한다. preset 분기로 cap을 풀어준다.
        preset = getattr(self._args, "preset", "auto")
        if preset == "contract-tdd":
            max_steps = None
        elif getattr(self._args, "single_step", False):
            max_steps = 1
        else:
            max_steps = None
        splitter = StepSplitter(
            self._cfg,
            self._splitter_invoker,
            self._validator,
            yes=self._args.yes,
            compact_docs=bool(getattr(self._args, "compact_docs", False)),
            max_steps=max_steps,
        )
        prompts = list(self._args.prompt or [])
        doc_args = list(self._args.doc or [])
        if not splitter.needs_split():
            if prompts or doc_args:
                _qprint(
                    "  알림: phases/{}/{}/에 이미 step.md가 존재합니다 — "
                    "auto-split을 스킵하고 기존 step.md로 실행합니다. "
                    "--prompt/--doc 인자는 무시됩니다.".format(
                        PHASES_SUBDIR,
                        self._cfg.phase_dir_name,
                    ),
                )
            return
        doc_paths = self._resolve_doc_paths(doc_args)
        if not prompts and not doc_paths:
            print(
                f"ERROR: phases/{PHASES_SUBDIR}/{self._cfg.phase_dir_name}/에 step.md가 없습니다.\n"
                "       최초 실행에는 --prompt 또는 --doc 옵션이 1개 이상 필요합니다.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        if self._uses_deterministic_plan():
            preset = getattr(self._args, "preset", "auto")
            sln_path: Path | None = None
            if preset == "contract-tdd":
                try:
                    sln_path = resolve_sln_path(
                        getattr(self._args, "sln", None),
                        self._cfg.root,
                        strict=True,
                    )
                except SlnResolveError as e:
                    print(f"ERROR: {e}", file=sys.stderr)
                    sys.exit(EXIT_ERR)
            test_target_rel: str | None = None
            raw_tt = getattr(self._args, "test_target", None)
            if raw_tt:
                try:
                    test_target_rel = _validate_target_rel(self._cfg.root, raw_tt)
                except ValueError as e:
                    print(f"ERROR: --test-target {e}", file=sys.stderr)
                    sys.exit(EXIT_ERR)
            builder = DeterministicPlanBuilder(
                self._cfg,
                preset=preset if preset != "auto" else "single-step",
                sln_path=sln_path,
                test_target=test_target_rel,
            )
            plan = builder.build(prompts, doc_paths)
            splitter._validate_plan(plan)
            if not splitter._confirm(plan):
                _qprint("  사용자가 계획을 승인하지 않았습니다. 디렉토리를 생성하지 않고 종료합니다.")
                sys.exit(EXIT_ERR)
            splitter._emit_files(plan)
            _qprint("  ✓ splitter 호출 없이 single-step phase가 생성되었습니다.")
            return
        splitter.run(prompts, doc_paths)

    def _uses_deterministic_plan(self) -> bool:
        preset = getattr(self._args, "preset", "auto")
        return (
            preset == "frd-implementation"
            or preset == "contract-tdd"
            or bool(getattr(self._args, "single_step", False))
        )

    def _resolve_doc_paths(self, doc_args: list[str]) -> list[Path]:
        # leading slash 정규화 + 중복 제거 (사용자가 같은 doc을 두 번 지정해도 1회만 처리)
        seen: set[str] = set()
        unique_args: list[str] = []
        for d in doc_args:
            normalized = d.lstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_args.append(normalized)
        resolved: list[Path] = []
        for normalized in unique_args:
            try:
                paths = self._validator.validate_many([normalized])
            except (ValueError, FileNotFoundError) as e:
                print(f"ERROR: --doc={normalized} 검증 실패: {e}", file=sys.stderr)
                sys.exit(EXIT_ERR)
            resolved.append(paths[0])
        return resolved

    def _verify_phase_dir_state(self) -> None:
        if not self._cfg.phase_dir.is_dir():
            print(f"ERROR: {self._cfg.phase_dir} not found", file=sys.stderr)
            sys.exit(EXIT_ERR)
        if not self._cfg.index_file.exists():
            existing = [p.name for p in self._cfg.phase_dir.iterdir()]
            print(
                f"ERROR: {self._cfg.index_file}가 없습니다.\n"
                "       이전 자동 분할이 중간에 실패했을 가능성이 있습니다 "
                f"(현재 디렉토리: {existing}).\n"
                "       다음 중 하나를 선택하세요:\n"
                f"       1) {self._cfg.phase_dir}를 비우고 --prompt/--doc과 함께 자동 분할 재실행\n"
                "       2) index.json을 직접 작성한 뒤 재실행",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)

    def _print_header(self, phase_name: str, total: int) -> None:
        _qprint(f"\n{'=' * 60}")
        _qprint("  Forge Scope Executor")
        _qprint(f"  Phase: {phase_name} | Steps: {total}")
        if self._args.push:
            _qprint("  Auto-push: enabled")
        _qprint(f"{'=' * 60}")

    def _check_external_dirty(self) -> None:
        """Phase 시작 전 워크트리에 무관 변경이 있으면 중단.

        워크트리 재실행 시 사용자가 수동으로 변경한 미커밋 파일이 step commit에
        흡수되어 phase 산출물에 섞이는 사고를 차단한다. 메인 repo의 dirty는
        영향 없음(워크트리는 독립 working tree). --force로 우회 가능.
        """
        if self._args.force:
            return
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self._cfg.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        print(
            "ERROR: 워크트리에 commit되지 않은 변경이 있습니다.\n"
            "       step commit이 이를 흡수해 phase 산출물에 무관 파일이 섞일 수 있습니다.\n"
            f"       워크트리: {self._cfg.root}\n"
            "       다음 중 하나를 선택하세요:\n"
            "         1) 워크트리에서 git stash 또는 commit 후 재실행\n"
            "         2) --force 로 우회 (의도된 흡수 — 권장하지 않음)\n"
            "       현재 dirty 파일:",
            file=sys.stderr,
        )
        print(result.stdout, file=sys.stderr)
        sys.exit(EXIT_ERR)

    def _check_frd_consistency(self) -> None:
        """contract-tdd 진입 전 FRD에 미결 항목이 있으면 phase·branch 생성 없이 abort.

        FRD §19(또는 동등 절)에 "결정 필요" / "정합되지 않" 등의 미결 마커가 있으면
        contract-tdd가 step 0 cascade를 일으키기 전에 사용자 결정을 강제한다.
        부작용 0(branch·phase dir·commit 미생성). --force로 우회 가능.
        """
        if getattr(self._args, "preset", "auto") != "contract-tdd":
            return
        if self._args.force:
            return
        doc_args = list(self._args.doc or [])
        if len(doc_args) != 1:
            return
        doc_rel = doc_args[0].lstrip("/")
        doc_path = ROOT / doc_rel
        if not doc_path.exists():
            return
        text = doc_path.read_text(encoding="utf-8")
        # 미확인/미결/Open 절 섹션 찾기
        section_re = re.compile(
            r"^##\s*(?:\d+\.\s*)?(?:미확인|미결|Open\s*(?:Issues|Questions))",
            re.MULTILINE | re.IGNORECASE,
        )
        section_match = section_re.search(text)
        if not section_match:
            return
        section_text = text[section_match.start() :]
        next_h2 = re.search(r"\n##\s", section_text[2:])
        if next_h2:
            section_text = section_text[: next_h2.start() + 2]
        # 미결 마커 확인
        if not re.search(
            r"결정.{0,4}필요|정합.{0,8}되지\s*않|다음\s*중\s*하나|TBD|undecided",
            section_text,
        ):
            return
        marker_match = re.search(
            r"(결정.{0,4}필요|정합.{0,8}되지\s*않|다음\s*중\s*하나|TBD|undecided)",
            section_text,
        )
        marker = marker_match.group(1) if marker_match else "(미결 마커)"
        print(
            "ERROR: FRD 미결 항목 감지 — contract-tdd 가드 작동.\n"
            "       산출물(branch·phase dir·commit) 생성 안 됨.\n"
            f"\n  FRD       : {doc_rel}\n"
            f"  Phase     : {self._cfg.phase_dir_name} (미생성)\n"
            f"  미결 마커 : {marker}\n"
            "\n  Claude Code parent agent: .claude/commands/forge-scope.md\n"
            "  의 §F (FRD 미결 항목 복구 흐름) 절차를 따라 처리하라.\n"
            "  요지: (1) 사용자에게 결정 옵션을 물어 1회 답을 받고,\n"
            "        (2) 답에 따라 docs/PRD·FRD·ADR + Src/** 코드를 적절히 갱신하고,\n"
            "        (3) 동일 forge-scope 명령을 재실행하라(가드는 이번에 통과해야 함).\n"
            "\n  옵트아웃: --force 로 본 가드 우회 가능 (cascade 위험).\n",
            file=sys.stderr,
        )
        sys.exit(EXIT_BLOCKED)

    def _warmup_dotnet(self) -> None:
        """첫 step의 NuGet restore + Roslyn warmup 비용을 사전에 한 번에 끝낸다.

        single-step/frd는 AC(`dotnet test <target> --no-restore`)와 **동일 타깃만** restore해
        풀 sln cold restore를 제거한다. contract-tdd는 step3 회귀가 풀 sln --no-restore 이므로
        풀 sln restore를 유지한다(cold start 14분 회귀 차단). 스코프 csproj restore는 전이
        project ref 패키지까지 받아 동일 타깃 test build를 충족한다.

        sln/타깃이 없으면 silent skip(다른 프로젝트 호환). restore 실패는 fatal 아님.
        """
        root = self._cfg.root
        preset = getattr(self._args, "preset", "auto")
        target = None
        if preset != "contract-tdd":
            target = resolve_ac_test_target(root, getattr(self._args, "test_target", None))
        if target:
            cmd = ["dotnet", "restore", str(root / target)]
            label = target
        else:
            try:
                sln = resolve_sln_path(getattr(self._args, "sln", None), root, strict=False)
            except SlnResolveError:
                return
            if sln is None:
                return
            cmd = ["dotnet", "restore", str(sln)]
            label = sln.relative_to(root).as_posix()
        _qprint(f"  Warmup: dotnet restore {label}")
        try:
            result = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.warning("dotnet warmup 스킵: %s", e)
            return
        if result.returncode != 0:
            log.warning(
                "dotnet warmup 실패(무시): %s",
                (result.stderr or "").strip()[:300],
            )
            return
        _qprint("  Warmup: 완료")

    @staticmethod
    def _check_blockers(store: IndexStore) -> None:
        idx = store.load()
        for s in sorted(idx["steps"], key=lambda x: x["step"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print("  Fix and reset status to 'pending' to retry.")
                sys.exit(EXIT_ERR)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print("  Resolve and reset status to 'pending' to retry.")
                sys.exit(EXIT_BLOCKED)

    def _execute_all(self, store: IndexStore, executor: StepExecutor, total: int) -> None:
        max_iterations = max(1, total) * (StepExecutor.MAX_RETRIES + 2)
        iterations = 0
        while True:
            iterations += 1
            if iterations > max_iterations:
                print(
                    f"\n  ERROR: 무한 루프 의심 — {iterations - 1}회 반복 후에도 종료 조건 미달성. "
                    "index.json을 확인하세요.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_ERR)
            pending = store.first_pending()
            if pending is None:
                _qprint("\n  All steps completed!")
                return
            store.ensure_started_at(pending["step"])
            with self._timed(f"step{pending['step']}"):
                executor.run(pending)
            self._step_usage.append((pending["step"], executor.last_output_tokens))

    def _finalize(self, store: IndexStore, phase_name: str) -> None:
        store.finalize()
        store.update_top("completed")
        msg = f"chore({phase_name}): mark phase completed"
        if self._git.commit_chore(msg):
            _qprint(f"  ✓ {msg}")
        with self._timed("commit-msg"):
            self._maybe_rewrite_commit_messages(store, phase_name)
        if self._args.push:
            self._git.push(self._push_branch(phase_name))
        if _QUIET:
            print(f"Phase '{phase_name}' completed.")
        else:
            print(f"\n{'=' * 60}")
            print(f"  Phase '{phase_name}' completed!")
            print(f"{'=' * 60}")

    def _maybe_rewrite_commit_messages(self, store: IndexStore, phase_name: str) -> None:
        """phase 완료 후 feat(코드) 커밋 메시지를 AI로 repo 스타일 재작성한다.

        옵트인(--ai-commit-msg, 기본 OFF). 워크트리 모드만. chore housekeeping 커밋은
        템플릿 유지. 실패해도 완료 흐름을 막지 않는다(원본 커밋 보존).
        """
        if self._no_worktree or not getattr(self._args, "ai_commit_msg", False):
            return
        try:
            base = store.get_git_base()
            if not base:
                return
            shas = self._git.commits_since(base)
            if not shas:
                return
            feats = [s for s in shas if self._git.commit_subject(s).startswith("feat(")]
            if not feats:
                return
            style = self._git.recent_subjects(base, 15)
            new_msgs: dict = {}
            invoker = ClaudeInvoker(
                trust=_is_trusted(self._args.trust),
                use_bare=True,
                cwd=self._cfg.root,
                model=getattr(self._args, "step_model", None) or "claude-opus-4-8",
                effort=getattr(self._args, "step_effort", None) or "high",
                lean=not bool(getattr(self._args, "full_fleet", False)),
                child_tools=getattr(self._args, "child_tools", None) or DEFAULT_CHILD_TOOLS,
            )
            for sha in feats:
                diff = self._git.commit_diff(sha, 12_000)
                if not diff.strip():
                    continue
                msg = self._gen_commit_message(invoker, diff, style)
                if msg:
                    new_msgs[sha] = msg
            if not new_msgs:
                return
            if self._git.rebuild_messages(base, new_msgs):
                _qprint(f"  ✓ 커밋 메시지 {len(new_msgs)}개 AI 재작성 완료")
            else:
                log.warning("커밋 메시지 재작성 실패 — 원본 커밋 유지")
        except Exception as e:  # noqa: BLE001 — 완료 흐름 비차단
            log.warning("커밋 메시지 재작성 중 예외(무시): %s", e)

    @staticmethod
    def _gen_commit_message(invoker: "ClaudeInvoker", diff: str, style: list[str]) -> Optional[str]:
        examples = "\n".join(f"- {s}" for s in style[:15]) or "(없음)"
        prompt = (
            "다음 git 변경(diff)에 대한 커밋 메시지 1개를 생성하라.\n"
            "아래 이 저장소의 기존 커밋 subject 스타일을 그대로 따르라(접두사·언어·형식):\n"
            f"{examples}\n\n"
            "규칙: 커밋 메시지 본문만 출력. 설명·코드펜스(```)·따옴표 금지. "
            "첫 줄은 50자 내외 제목, 필요 시 빈 줄 후 본문.\n\n"
            f"--- diff ---\n{diff}\n"
        )
        try:
            rc, stdout, _ = invoker.call(prompt)
            if rc != 0 or not stdout.strip():
                return None
            text = StepSplitter._extract_result_text(stdout)
            text = StepSplitter._strip_fences(text).strip()
            text = text.strip("`'\" \n")
            return text or None
        except Exception:  # noqa: BLE001
            return None

    def _push_branch(self, phase_name: str) -> str:
        """push 대상 브랜치. 워크트리 모드=feat-<phase>, no-worktree 모드=현재 브랜치."""
        if not self._no_worktree:
            return f"feat-{phase_name}"
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self._cfg.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        branch = r.stdout.strip()
        if r.returncode != 0 or not branch or branch == "HEAD":
            print(
                "ERROR: --no-worktree + --push 이지만 현재 브랜치를 확인할 수 없습니다 "
                "(detached HEAD 등). 수동으로 push 하세요.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERR)
        return branch


# ============================================================================
# Trust 게이트
# ============================================================================
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
        "    FORGE_TRUST=1 python scripts/forge_scope.py <phase-dir> ...\n"
        "    python scripts/forge_scope.py <phase-dir> ... --trust\n"
        "\n"
        "  주의: FORGE_TRUST를 셸 rc 파일 등에 영구 설정하지 마세요. 매 실행마다\n"
        "        의식적으로 활성화하는 것을 권장합니다.\n",
        file=sys.stderr,
    )
    sys.exit(EXIT_ERR)


def _install_signal_handlers() -> None:
    if sys.platform == "win32":
        return

    def _raise_kbi(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, _raise_kbi)


# ============================================================================
# main
# ============================================================================
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Forge Scope Executor — selective-doc + auto-step-split phase runner."),
    )
    parser.add_argument("phase_dir", help="Phase directory name (e.g. login-feature)")
    parser.add_argument(
        "--prompt",
        action="append",
        default=None,
        help="자유 텍스트 요구사항 (반복 지정 가능). 첫 실행 시 --doc과 함께 사용.",
    )
    parser.add_argument(
        "--doc",
        action="append",
        default=None,
        help="첨부 문서 경로 (docs/ 하위 .md, 반복 지정 가능).",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="완료 후 git push (-u origin feat-<phase>)",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="Opt-in to --dangerously-skip-permissions (또는 FORGE_TRUST=1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="브랜치 checkout 시 dirty tree 검사 우회.",
    )
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help=(
            "워크트리를 생성하지 않고 현재 작업 트리(메인 repo)에서 직접 실행한다. "
            "산출물·step 코드·commit이 현재 브랜치에 직접 기록된다 (격리 없음)."
        ),
    )
    parser.add_argument(
        "--ai-commit-msg",
        action="store_true",
        help=(
            "phase 완료 후 feat(코드) 커밋 메시지를 AI로 repo 스타일 재작성한다(추가 claude 호출 1회). "
            "워크트리 모드에서만 동작하며 chore housekeeping 커밋은 항상 템플릿 유지. 기본 OFF."
        ),
    )
    parser.add_argument(
        # 하위호환: 기본값이 이미 OFF이므로 no-op. 과거 호출자 무중단용.
        "--no-ai-commit-msg",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="DEBUG 레벨 로그를 stderr로 출력.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="auto-split plan을 사용자 확인 없이 자동 승인 (CI/비대화 환경).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="가드레일 문서에 {placeholder}가 남아 있으면 실패.",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(VALID_PRESETS),
        default="auto",
        help=(
            "초기 step 생성 방식. auto=Claude splitter 사용, "
            "frd-implementation=문서 1개로 splitter 없이 단일 구현 step 생성, "
            "contract-tdd=문서 1개로 contract/red/green/regression 4-step 생성."
        ),
    )
    parser.add_argument(
        "--sln",
        default=None,
        help=(
            "contract-tdd 가 사용할 .sln 경로 (repo root 기준). "
            "미지정 시 Src/*.sln (1단계) 또는 Src/*/*.sln (2단계) auto-detect. "
            "다수 발견 시 명시 필요."
        ),
    )
    parser.add_argument(
        "--test-target",
        default=None,
        help=(
            "검증(dotnet test) 대상 테스트 프로젝트(.csproj, repo root 기준 상대경로). "
            "풀 솔루션 빌드 회피용 스코프. 우선순위: 이 플래그 > forge-scope.json test_target "
            "> Src/Tests 단일 자동감지 > 전체 sln. 작업 문서 기준 1회 지정(휘발성)."
        ),
    )
    parser.add_argument(
        "--single-step",
        action="store_true",
        help="초기 실행 시 Claude splitter 호출 없이 고정 single-step plan을 생성.",
    )
    parser.add_argument(
        "--compact-docs",
        action="store_true",
        help="docs_scope 문서를 핵심 섹션만 압축해 splitter/step guardrail에 주입.",
    )
    parser.add_argument(
        "--step-model",
        default="claude-opus-4-8",
        help=("splitter·step·commit-msg 실행에 사용할 Claude 모델 이름 (default: claude-opus-4-8)."),
    )
    parser.add_argument(
        "--step-effort",
        default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
        help=("Claude --effort 레벨 (default: high). 지능↔토큰 트레이드오프 다이얼."),
    )
    parser.add_argument(
        "--full-fleet",
        action="store_true",
        help=(
            "child claude에 MCP 서버·plugin skill 전체 로드를 허용한다. "
            "기본은 lean(MCP 0개 + skill off + 최소 --tools)으로 호출당 startup 세금을 "
            "제거한다. 디버깅/특수 도구가 필요할 때만 사용."
        ),
    )
    parser.add_argument(
        "--child-tools",
        default=DEFAULT_CHILD_TOOLS,
        help=(
            f"lean 모드에서 child claude에 허용할 빌트인 tool 목록(콤마/공백 구분). "
            f"기본 {DEFAULT_CHILD_TOOLS}."
        ),
    )
    parser.add_argument(
        "--timings",
        action="store_true",
        help=(
            "phase 구간별 wall-clock 상세 테이블을 출력한다. "
            "(미지정이어도 완료 시 [timings] 요약 한 줄은 항상 출력된다.)"
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "부모 세션 stdout 누적 절감용. 진행 표시기·헤더·step별 진행 메시지를 "
            "억제하고 phase 완료 한 줄 + 에러만 출력한다."
        ),
    )
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help=(
            "워크트리·plan·warmup·가드레일까지만 수행하고 step 매니페스트(JSON)를 stdout으로 "
            "출력한 뒤 종료한다. step 실행은 호출 세션이 인라인으로 수행한다(자식 claude spawn 0)."
        ),
    )
    parser.add_argument(
        "--record-step",
        type=int,
        default=None,
        metavar="N",
        help=(
            "인라인 세션이 끝낸 step N을 수확한다: 사후가드(메인repo 누수·워크트리 무변경) → "
            "attempt counter → TDD 순서 gate → status ingest → 2단계 commit → index 전이. "
            "result JSON을 stdout으로 출력."
        ),
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="phase 마감: finalize + top-index 갱신 + (옵션) push. 모든 step 완료 후 1회 호출.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=StepExecutor.MAX_RETRIES,
        help=(
            "record-step 하드 백스톱: step당 record 호출 누적이 이 값에 도달하고도 completed가 "
            "아니면 강제 error 처리한다(기본 3). 세션이 SKILL.md cap을 무시해도 결정적으로 끊긴다."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    global _QUIET
    _QUIET = bool(getattr(args, "quiet", False))

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    _install_signal_handlers()
    _require_trust(args.trust)

    try:
        forge = ForgeScope(args)
        if args.record_step is not None:
            sys.exit(forge.record_step(args.record_step))
        if args.finalize:
            sys.exit(forge.finalize_only())
        sys.exit(forge.run())
    except KeyboardInterrupt:
        print("\n  ⚠ Interrupted (top-level).", file=sys.stderr)
        sys.exit(EXIT_KBI)


if __name__ == "__main__":
    main()
