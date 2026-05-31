#!/usr/bin/env python3
"""
Doc-Driven Review Executor — 첨부 문서가 현재 코드 변경점에 반영됐는지 Codex로 검증.

Usage:
    python3 scripts/doc_driven_review.py --docs <p1> [<p2>...] [options]

Options:
    --docs <path> [path...]       필수. 검증할 문서 경로 1개 이상
    --scope auto|working-tree|branch  기본 auto
    --base <ref>                  branch scope의 기준점. 기본 origin/main merge-base
    --model <name>                codex --model 통과
    --effort <level>              codex --effort 통과
    --background                  detach 실행, PID + log path 출력
    --repo-root <path>            기본 git rev-parse --show-toplevel
    --worktree <branch|path>      대상 워크트리 지정 (--repo-root 와 mutex). linked worktree 시 권장
    --dry-run                     codex 호출 skip, 생성 프롬프트만 stdout 출력
    --verbose                     DEBUG 로그
    --keep-patch                  종료 후 .patch 파일 보존 (디버깅)

Exit codes:
    0   정상 (Codex stdout 출력 완료)
    1   기타 (git 실패, 파일 IO 등)
    2   codex CLI 미설치
    3   리뷰할 변경 없음
    4   첨부 문서 합계 >200KB (사전 차단)
    5   --base ref 존재하지 않음
    6   --worktree 해석 실패 (branch/path 매칭 안 됨)
    130 KeyboardInterrupt
"""

import sys

# Encoding bootstrap — FIRST executable code (Windows cp949 콘솔 회피)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import argparse
import logging
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("doc_driven_review")

# ─── Constants ────────────────────────────────────────────────────────────────

TZ = timezone(timedelta(hours=9))

EXIT_OK = 0
EXIT_ERR = 1
EXIT_NO_CODEX = 2
EXIT_NO_CHANGES = 3
EXIT_DOC_TOO_BIG = 4
EXIT_NO_BASE = 5
EXIT_WORKTREE = 6
EXIT_KBI = 130

DOC_TOTAL_BYTES_LIMIT = 200_000        # 합산 200KB
SINGLE_DOC_BYTES_LIMIT = 100_000       # 단일 문서 100KB
PATCH_LINE_SOFT_LIMIT = 50_000         # 초과 시 경고
PATCH_BYTES_SOFT_LIMIT = 2_000_000     # 2MB 초과 시 Codex 처리 경고
UNTRACKED_PROBE_BYTES = 8_192          # binary 판별 헤드
REVIEW_COMMENTS_MAX = 20
TOP_PRIORITIES_MAX = 5

# 출력 스키마 검증용 정규식 — v1.2
H1_RE = re.compile(r"^# Code Review:", re.M)
SECTION_V2_RE = re.compile(
    r"^## (Summary|Severity 기준|Requirements Coverage|Top Priorities"
    r"|Review Comments|Overengineered|Conformance)\s*$",
    re.M,
)
COMMENT_BLOCK_RE = re.compile(
    r"^### \d+\. \[(CRITICAL|MAJOR|MINOR|SUGGESTION)\] ", re.M
)
CONFORMANCE_LINE_RE = re.compile(r"^Conformance:\s*(\d{1,3})%\s*$")
COUNTS_V2_RE = re.compile(
    r"^Counts:\s*Critical:\s*(\d+),\s*Major:\s*(\d+),\s*Minor:\s*(\d+)"
    r",\s*Suggestion:\s*(\d+)\s*$",
    re.M,
)
EXPECTED_SECTIONS_V2 = [
    "Summary", "Severity 기준", "Requirements Coverage",
    "Top Priorities", "Review Comments", "Overengineered", "Conformance",
]

# 제외 pathspec (branch-review:76-87 차용)
EXCLUDED_PATHSPECS: list[str] = [
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)yarn.lock",
    ":(exclude)Cargo.lock",
    ":(exclude)poetry.lock",
    ":(exclude)uv.lock",
    ":(exclude)Gemfile.lock",
    ":(exclude)dist",
    ":(exclude)build",
    ":(exclude)out",
    ":(exclude)node_modules",
    ":(exclude)*.min.js",
    ":(exclude)*.min.css",
    ":(exclude)*.map",
    ":(exclude)*.png",
    ":(exclude)*.jpg",
    ":(exclude)*.jpeg",
    ":(exclude)*.gif",
    ":(exclude)*.ico",
    ":(exclude)*.woff",
    ":(exclude)*.woff2",
    ":(exclude)*.ttf",
    ":(exclude)*.eot",
]

BINARY_EXTS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".db", ".sqlite", ".sqlite3",
})

# ─── Auto-context (cross-file caller detection) ───────────────────────────────

AUTO_CONTEXT_MAX_FILES = 10
AUTO_CONTEXT_MAX_BYTES = 100_000      # 합계 100KB 상한 (prompt 토큰 보호)
AUTO_CONTEXT_PER_FILE_LIMIT = 20_000  # 단일 파일 20KB 상한 (대형 파일은 head만 포함)
AUTO_CONTEXT_MIN_IDENT_LEN = 4        # 4자 미만 식별자 무시 (false positive 방지)

# 식별자 추출 패턴 — 언어별 (caller grep 토큰). 각 패턴은 group(1)이 식별자.
IDENTIFIER_PATTERNS: list[re.Pattern[str]] = [
    # C# / Java / Kotlin / TypeScript class / interface / record / enum / struct
    re.compile(r"\b(?:public|internal|private|protected)?\s*(?:static\s+|abstract\s+|sealed\s+|partial\s+)*(?:class|interface|struct|enum|record)\s+([A-Z][A-Za-z0-9_]+)"),
    # C# namespace (dotted)
    re.compile(r"\bnamespace\s+([A-Za-z_][A-Za-z0-9_.]+)"),
    # C# public method (CapitalCase)
    re.compile(r"\bpublic\s+(?:static\s+|virtual\s+|override\s+|async\s+)*(?:[A-Za-z_][A-Za-z0-9_<>,\s\[\]?]*\s+)([A-Z][A-Za-z0-9_]+)\s*\("),
    # Python def / class
    re.compile(r"^\s*def\s+([a-zA-Z_][A-Za-z0-9_]+)", re.M),
    re.compile(r"^\s*class\s+([A-Z][A-Za-z0-9_]+)", re.M),
    # Go func / type
    re.compile(r"\bfunc\s+(?:\([^)]+\)\s+)?([A-Z][A-Za-z0-9_]+)"),
    re.compile(r"\btype\s+([A-Z][A-Za-z0-9_]+)\s+(?:struct|interface|=)"),
    # TypeScript / JavaScript export
    re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:class|function|const|let|var|interface|type|enum)\s+([A-Za-z_][A-Za-z0-9_]+)"),
    # Rust pub fn / struct / enum / trait
    re.compile(r"\bpub\s+(?:fn|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]+)"),
    # Java public method (lowercase first char)
    re.compile(r"\bpublic\s+(?:static\s+|final\s+)?(?:[A-Za-z_][A-Za-z0-9_<>,\s\[\]?]*\s+)([a-z][A-Za-z0-9_]+)\s*\("),
]

# 흔한 false-positive 단어 (언어 키워드 + 표준 라이브러리 + 일반 동사)
IDENTIFIER_STOPWORDS: frozenset[str] = frozenset({
    "Main", "Program", "Test", "Tests", "TestCase", "Console", "System",
    "String", "Int", "Bool", "Boolean", "Object", "Array", "List", "Dict",
    "Map", "Set", "Tuple", "None", "True", "False", "Null", "Nil",
    "Integer", "Float", "Double", "Decimal", "Char", "Byte", "Long", "Short",
    "ToString", "Equals", "GetHashCode", "Clone", "Dispose",
    "Get", "Set", "Add", "Remove", "Update", "Delete", "Create", "Find",
    "WriteLine", "Write", "ReadLine", "Read",
    "Self", "This", "Super", "Base", "New", "Init",
    "Print", "Range", "Len", "Type", "Format",
})

# auto-context 대상에서 제외할 확장자 (doc 자체 + 메타 파일)
AUTO_CONTEXT_EXCLUDED_EXTS: frozenset[str] = frozenset({
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".lock", ".log", ".min.js", ".min.css", ".map", ".sql",
})

PROMPT_TEMPLATE = """\
# ROLE
You are a senior code reviewer. Produce a structured review report comparing the attached \
design documents against the code changes.

# DOCUMENTS
{documents_block}

# CODE CHANGES
- Snapshot patch (read this file directly): {patch_path}
- Scope: {scope}
- Base ref: {base_ref}

# REPO ROOT
{repo_root}

{unchanged_context_block}

# TASK
Compare DOCUMENTS against CODE CHANGES. Produce a rich review report in the EXACT format below.

# OUTPUT FORMAT — STRICT
No preamble before `# Code Review`. No epilogue after `Conformance: N%` line.

# Code Review: <primary-doc-stem>

## Summary
- **무엇을 하는 코드인지**: <2-3 lines>
- **핵심 문제**: <2-3 lines>
- **핵심 장점**: <1-2 lines, or `- (none)`>

## Severity 기준
- **Critical**: 장애, 보안, 데이터 손실 가능성 (또는 문서 핵심 요구 완전 누락)
- **Major**: 구조/성능/유지보수 큰 영향 (또는 문서 명시 요구 미충족)
- **Minor**: 가독성, 네이밍, 스타일 개선 (또는 문서 부수 요구)
- **Suggestion**: 더 나은 대안 제안 (문서 외 권장 사항)

## Requirements Coverage
| § | 요구사항 | 상태 | 코드 위치 | 비고 |
|---|---|---|---|---|
| 1 | <one-line summary of doc requirement §1> | ✓/⚠/✗ | <file:line or MISSING> | <see 비고 column rule below> |
| 2 | ... | ... | ... | ... |

(Enumerate every doc requirement. Use `✓` Implemented / `⚠` Partial / `✗` Missing.)

## Top Priorities
1. [<SEVERITY>] <one-line title> — <one-line impact>
2. [<SEVERITY>] ...
3. [<SEVERITY>] ...

(Max 5. If none, write `- (none)`.)

## Review Comments

### 1. [<SEVERITY>] <one-line title>

**Location**
`<file:line>` or `<file:line-start>-<line-end>` or `MISSING`

**Issue**
<1-3 lines explaining what is wrong>

**Why it matters**
<2-3 lines: quote doc text with `"..."` + describe impact>

**Suggestion**
<1-2 lines on fix direction>

**Example**
```<language-hint>
// 3-15 lines of corrected/example code
```

### 2. [<SEVERITY>] ...

(Sort by severity: Critical → Major → Minor → Suggestion. Each requirement gap, \
divergence, or improvement gets one block. Max 20 blocks total.)

## Overengineered
| 항목 | 코드 위치 | 설명 |
|---|---|---|
| <name> | <file:line> | <one-line> |

(Items outside the documented surface area. If none, write `- (none)` instead of the table.)

## Conformance
Counts: Critical: <N>, Major: <M>, Minor: <K>, Suggestion: <S>
<2-3 line rationale that INCLUDES weight arithmetic per RUBRIC below.
 Format: "Weights: §1(Major=2,✗), §2(Critical=4,⚠), §3(Minor=1,✓) → passed=X / total=Y → pct=Z%">

Conformance: <integer 0-100>%

# FIELD RULES
- SEVERITY: CRITICAL | MAJOR | MINOR | SUGGESTION
- Status symbols in Requirements Coverage: exactly ✓, ⚠, or ✗
- Code citations: real file:line. Verify via the snapshot patch.
- Example code: must be in a fenced code block with language hint
- Empty section: use `- (none)` (single bullet) when nothing applies
- Max 20 Review Comments blocks; Max 5 Top Priorities
- **Exact-string fidelity**: when the doc specifies a literal string (error message, output format, identifier, type name, namespace), quote it verbatim with `"..."` in BOTH the Issue and the Example. Do not paraphrase or translate. Mismatch by even one character must be flagged.
- **Compilable Example**: Example code blocks must compile standalone in the target language. Include required imports (`using`, `import`, `#include`, `from ... import`) and minimal class/function wrapper. Do not assume ambient context.
- **비고 column (Requirements Coverage)**: when status is ⚠ or ✗, cite (a) the exact doc clause violated and (b) the missing/wrong literal, in ≤120 chars. Example: `§2.4 메시지 "Both arguments must be positive." 누락`. For ✓, ≤40 chars sanity note is sufficient.
- **상태 기호 판정 기준 (엄격)**:
  - `✓` Implemented: 요구한 시그니처/네임스페이스/메서드/메시지/타입/예외/포맷이 모두 일치. 검증 가능한 doc literal이 모두 코드에 존재.
  - `⚠` Partial: 외형(시그니처, 클래스 위치)은 맞지만 본문 일부 로직만 구현. 예: 시그니처는 정확하나 일부 분기 누락. **명시 literal(메시지/상수/타입명)이 누락되면 ⚠가 아니라 ✗**.
  - `✗` Missing: 코드에 해당 요구가 전혀 없거나, 문서와 정반대 동작, 명시 literal(메시지/타입명/식별자) 부재, 또는 요구한 예외/검증 부재.
  - 의심스러우면 더 엄격한 쪽(✗ over ⚠, ⚠ over ✓) 선택.
- **연관 요구 통합 (행 정규화)**:
  - 같은 메서드/심볼/네임스페이스에 속한 여러 doc 요구는 **하나의 Requirements Coverage 행**으로 통합하라. 예: `§2.1` 시그니처 + `§2.2` validation + `§2.3` 예외 메시지 → `§2 Add 메서드 (시그니처 + validation + 메시지)` 1행.
  - 행 통합 시 상태는 가장 나쁜 것 우선(✗ > ⚠ > ✓).
  - 비고는 통합된 모든 sub-요구의 결함을 ≤120자 안에 ";"로 구분 나열.
  - Review Comments는 severity 단위로 별도 분리 가능 (Coverage 행과 1:1 대응 불요).
  - 통합 목적: Conformance 가중치 계산 시 같은 결함의 이중 카운트 방지.

# CONFORMANCE RUBRIC
- Assign a weight to each Requirements Coverage row based on the severity it would carry if missing:
  Critical=4, Major=2, Minor=1.
- Compute: `pct = round(100 * sum(passed_weight) / sum(total_weight))`
  - ✓ contributes its full weight to passed_weight
  - ⚠ contributes 0.5 × weight
  - ✗ contributes 0
  - total_weight = sum of all row weights (denominator always uses full weight)
- Suggestion-only Review Comments and Overengineered items do NOT enter the formula.
- The rationale under Counts MUST show the arithmetic per the format above.
- Round to nearest integer. 100% requires every row ✓.

# CONSTRAINTS
- Provide Suggestion + Example code blocks (helpful for fixes)
- Cite real file:line. Verify via the snapshot patch
- No commentary before `# Code Review` or after `Conformance: N%`
- Quote doc text in Why it matters with `"..."` when relevant
- **Cross-file ripple**: when a finding alters a public API surface (namespace move, signature change, type rename, member removal/addition), enumerate every caller visible in the snapshot patch under Suggestion as a bullet list of `file:line`. If no caller appears in the patch, state explicitly `No callers in patch`. Do not leave the impact implicit.
- **Overengineered 범위 제한**:
  - 다음 분류의 파일 변경은 Overengineered에 포함시키지 마라 (doc 범위 밖이어도 인프라/메타 변경으로 간주):
    - 빌드/패키지: `*.csproj`, `*.sln`, `*.fsproj`, `package.json`, `pnpm-workspace.yaml`, `tsconfig*.json`, `Cargo.toml`, `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`, `Pipfile*`, `poetry.lock`, `pom.xml`, `build.gradle*`, `Makefile`, `CMakeLists.txt`, `go.mod`, `go.sum`
    - VCS/도구 설정: `.gitignore`, `.gitattributes`, `.editorconfig`, `.prettierrc*`, `.eslintrc*`, `.stylelintrc*`, `.markdownlint*`
    - CI/CD: `.github/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci/`, `.travis.yml`
    - IDE: `.vscode/`, `.idea/`, `*.iml`
  - Overengineered는 오직 **doc에 없는 신규 public API surface**(클래스/메서드/엔드포인트/공개 함수)에만 한정한다.
  - 위 카테고리 변경은 Conformance 산정에도 영향 없음.
- **Use UNCHANGED CONTEXT for caller analysis**:
  - When reasoning about Cross-file ripple, **consult `# UNCHANGED CONTEXT` files in addition to the snapshot patch**.
  - Cite callers as `<file>:<line>` from EITHER the patch OR UNCHANGED CONTEXT.
  - Only write `No callers in patch or unchanged context` when truly no reference exists in either.
  - UNCHANGED CONTEXT files may be partially truncated (`// ... [truncated by DDR auto-context]`). Still treat them as authoritative for symbol presence.
"""


# ─── Exceptions ───────────────────────────────────────────────────────────────

class DocReviewError(RuntimeError):
    pass

class NoChangesError(DocReviewError):
    pass

class CodexUnavailableError(DocReviewError):
    pass

class DocTooBigError(DocReviewError):
    pass

class BaseRefError(DocReviewError):
    pass


# ─── Argparse ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="doc_driven_review",
        description="문서 기준으로 코드 변경점을 Codex가 검증",
    )
    p.add_argument("--docs", nargs="+", required=True, type=Path,
                   metavar="PATH", help="검증할 문서 경로 1개 이상")
    p.add_argument("--scope", choices=["auto", "working-tree", "branch"],
                   default="auto")
    p.add_argument("--base", default=None,
                   help="branch scope 기준점. 기본 origin/main merge-base")
    p.add_argument("--commit", default=None, metavar="<ref>",
                   help="특정 커밋(또는 A..B 범위) 지목해 그 변경분만 doc과 대조. "
                        "단일 ref면 <ref>^..<ref>. --scope/--base 무시. working-tree/branch 우회.")
    p.add_argument("--model", default=None, help="codex --model 통과")
    p.add_argument("--effort",
                   choices=["minimal", "low", "medium", "high", "xhigh"],
                   default=None)
    p.add_argument("--background", action="store_true",
                   help="detach 실행, PID + log path 출력")
    p.add_argument("--repo-root", type=Path, default=None, dest="repo_root")
    p.add_argument(
        "--worktree",
        metavar="<branch|path>",
        default=None,
        help="대상 워크트리 지정. branch명 또는 경로. "
             "linked worktree(forge-scope) 사용 시 권장. "
             "--repo-root 와 동시 사용 불가. 미지정 시 cwd 기준.",
    )
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="codex 호출 skip, 생성 프롬프트만 stdout")
    p.add_argument("--keep-patch", action="store_true", dest="keep_patch",
                   help="종료 후 .patch 파일 보존")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument(
        "--no-auto-context", action="store_true", dest="no_auto_context",
        help="Caller 자동 탐지 비활성화 (cross-file ripple 분석 약화). "
             "기본: 활성 — changed 파일 식별자 추출 후 git grep으로 unchanged 호출자 검색.",
    )
    return p.parse_args(argv)


# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(verbose: bool) -> None:
    log_dir = ROOT / ".claude" / "doc-driven-review-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"run-{ts}.log"

    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8")
    ]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


# ─── Git helpers ──────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=check,
    )


def find_repo_root(start: Path) -> Path:
    result = _git(["rev-parse", "--show-toplevel"], cwd=start, check=False)
    if result.returncode != 0:
        raise DocReviewError(f"git 레포 아님: {start}")
    return Path(result.stdout.strip())


def _git_info_dir(repo_root: Path) -> Path:
    """
    `.git/info` 디렉토리 경로 반환. worktree 토폴로지 무관.

    - main worktree: `<repo>/.git/info`
    - linked worktree: `<main-repo>/.git/info` (info는 common dir 소속, 모든 worktree 공유)
    - bare repo: `<repo>.git/info`

    부수효과: 디렉토리 부재 시 생성 (`parents=True, exist_ok=True`).
    """
    r = _git(["rev-parse", "--git-path", "info"], cwd=repo_root, check=False)
    if r.returncode != 0:
        raise DocReviewError(
            f"git rev-parse --git-path info 실패 ({repo_root}): {r.stderr.strip()}"
        )
    info = Path(r.stdout.strip())
    if not info.is_absolute():
        info = (repo_root / info).resolve()
    info.mkdir(parents=True, exist_ok=True)
    return info


ARTIFACT_MAX_AGE_DAYS = 7


def prune_old_artifacts(info_dir: Path) -> None:
    """오래된 bg 로그·stale patch 정리 (mtime 7일 경과). 실패 무시."""
    import time
    cutoff = time.time() - ARTIFACT_MAX_AGE_DAYS * 86400
    for pattern in ("doc-review-bg-*.log", "doc-review-*.patch"):
        for f in info_dir.glob(pattern):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass


def resolve_worktree(token: str, cwd: Path) -> Path:
    """
    `--worktree <token>` 인자 해석.

    경로 형태(`/`, `\\`, 절대경로, `./`/`../`): Path 즉시 해석.
    그 외: branch명으로 간주, `git worktree list --porcelain` 파싱.
    `refs/heads/<branch>` 접두 자동 처리.
    """
    looks_like_path = (
        not token.startswith("refs/")
        and (
            "/" in token
            or "\\" in token
            or Path(token).is_absolute()
            or token.startswith(".")
        )
    )
    if looks_like_path:
        p = Path(token).expanduser().resolve()
        if not p.is_dir():
            raise DocReviewError(f"--worktree 경로 존재하지 않음: {token}")
        verify = _git(["rev-parse", "--show-toplevel"], cwd=p, check=False)
        if verify.returncode != 0:
            raise DocReviewError(f"--worktree 경로가 git 레포 아님: {token}")
        return p

    r = _git(["worktree", "list", "--porcelain"], cwd=cwd, check=False)
    if r.returncode != 0:
        raise DocReviewError(
            f"git worktree list 실패 ({cwd}): {r.stderr.strip()}"
        )

    current_path: Optional[Path] = None
    target_full = f"refs/heads/{token}" if not token.startswith("refs/heads/") else token

    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree "):].strip())
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref == target_full and current_path is not None:
                return current_path.resolve()

    raise DocReviewError(
        f"--worktree 해석 실패 (branch/path 매칭 안 됨): {token}. "
        f"`git worktree list` 로 등록된 워크트리 확인하세요."
    )


def _merge_base(repo_root: Path, remote: str = "origin/main") -> Optional[str]:
    r = _git(["merge-base", remote, "HEAD"], cwd=repo_root, check=False)
    if r.returncode == 0:
        return r.stdout.strip()
    return None


def resolve_base_ref(repo_root: Path, base: Optional[str]) -> str:
    if base:
        r = _git(["rev-parse", "--verify", base], cwd=repo_root, check=False)
        if r.returncode != 0:
            raise BaseRefError(f"--base '{base}' 존재하지 않음.")
        return base

    for remote in ("origin/main", "upstream/main", "origin/master", "main", "master"):
        mb = _merge_base(repo_root, remote)
        if mb:
            log.debug("base 자동 결정: merge-base %s = %s", remote, mb[:8])
            return mb

    # fallback
    r = _git(["rev-parse", "HEAD~10"], cwd=repo_root, check=False)
    if r.returncode == 0:
        log.warning("base 자동 결정 실패, HEAD~10 사용")
        return r.stdout.strip()

    raise DocReviewError("base ref 자동 결정 실패. --base 인자로 명시 필요.")


def resolve_commit_diff_args(repo_root: Path, revspec: str) -> list[str]:
    """--commit 값 → git diff 인자. 단일커밋=<ref>^..<ref>(루트커밋은 --root). 범위(A..B)=그대로.

    유효성 미확인 시 BaseRefError.
    """
    if ".." in revspec:
        endpoint = revspec.split("..")[-1] or "HEAD"
        r = _git(["rev-parse", "--verify", "--quiet", endpoint], cwd=repo_root, check=False)
        if r.returncode != 0:
            raise BaseRefError(f"--commit 범위 해석 실패: {revspec}")
        return [revspec]
    r = _git(["rev-parse", "--verify", "--quiet", f"{revspec}^{{commit}}"],
             cwd=repo_root, check=False)
    if r.returncode != 0:
        raise BaseRefError(f"--commit 커밋 없음: {revspec}")
    parent = _git(["rev-parse", "--verify", "--quiet", f"{revspec}^"],
                  cwd=repo_root, check=False)
    if parent.returncode == 0:
        return [f"{revspec}^", revspec]
    return ["--root", revspec]   # 루트 커밋 (부모 없음)


def _has_working_tree_changes(repo_root: Path) -> bool:
    stat_staged = _git(["diff", "--shortstat", "--cached"], cwd=repo_root, check=False)
    stat_unstaged = _git(["diff", "--shortstat"], cwd=repo_root, check=False)
    status = _git(["status", "--short", "--untracked-files=all"], cwd=repo_root, check=False)

    return bool(
        stat_staged.stdout.strip()
        or stat_unstaged.stdout.strip()
        or status.stdout.strip()
    )


def determine_scope(
    repo_root: Path, requested: str, base: Optional[str]
) -> tuple[str, Optional[str]]:
    """Returns (scope_kind, resolved_base_or_none)."""
    if requested == "working-tree":
        return "working-tree", None
    if requested == "branch":
        resolved = resolve_base_ref(repo_root, base)
        return "branch", resolved

    # auto
    if _has_working_tree_changes(repo_root):
        log.debug("scope auto → working-tree")
        return "working-tree", None

    log.debug("scope auto → branch (변경 없음)")
    resolved = resolve_base_ref(repo_root, base)
    return "branch", resolved


# ─── Document reading ─────────────────────────────────────────────────────────

def read_attached_docs(paths: list[Path]) -> list[tuple[Path, str]]:
    results: list[tuple[Path, str]] = []
    total = 0
    for p in paths:
        if not p.is_file():
            raise DocReviewError(f"문서 파일 없음: {p}")
        raw = p.read_bytes()
        if len(raw) > SINGLE_DOC_BYTES_LIMIT:
            raise DocTooBigError(
                f"문서 단일 크기 100KB 초과: {p} ({len(raw)//1024}KB)"
            )
        total += len(raw)
        if total > DOC_TOTAL_BYTES_LIMIT:
            raise DocTooBigError(
                f"문서 합산 200KB 초과. (현재 {total//1024}KB)"
            )
        text = raw.decode("utf-8", errors="replace")
        results.append((p, text))
    return results


# ─── Untracked helpers ────────────────────────────────────────────────────────

def _is_excluded_path(path: Path) -> bool:
    name = path.name
    for pat in (
        "*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        "Cargo.lock", "poetry.lock", "uv.lock", "Gemfile.lock",
    ):
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return True
        elif name == pat:
            return True
    parts = path.parts
    for excl in ("dist", "build", "out", "node_modules"):
        if excl in parts:
            return True
    for ext in (".min.js", ".min.css", ".map"):
        if name.endswith(ext):
            return True
    return False


def is_binary_path(path: Path, repo_root: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        head = path.read_bytes()[:UNTRACKED_PROBE_BYTES]
        if b"\x00" in head:
            return True
    except OSError:
        return True
    r = _git(
        ["check-attr", "-a", "--", str(path.relative_to(repo_root))],
        cwd=repo_root, check=False,
    )
    if "linguist-generated: set" in r.stdout:
        return True
    return False


def list_untracked_text_files(repo_root: Path) -> list[Path]:
    r = _git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=repo_root, check=False,
    )
    if r.returncode != 0:
        return []
    paths: list[Path] = []
    for line in r.stdout.splitlines():
        p = repo_root / line.strip()
        if not p.is_file():
            continue
        if _is_excluded_path(p):
            continue
        if is_binary_path(p, repo_root):
            continue
        paths.append(p)
    return paths


# ─── Auto-context functions ───────────────────────────────────────────────────

def extract_identifiers_from_changed(
    repo_root: Path,
    scope: str,
    base: Optional[str],
    untracked: list[Path],
    commit_args: Optional[list[str]] = None,
) -> set[str]:
    """
    changed + untracked 파일에서 식별자(클래스/네임스페이스/메서드/함수명) 추출.
    caller 탐지의 git grep 토큰으로 사용.
    Returns: stopword 제외 후 4자 이상 식별자 집합.
    """
    changed_paths: set[str] = set()
    if scope == "commit":
        r = _git(["diff", "--name-only", *(commit_args or [])], cwd=repo_root, check=False)
        if r.returncode == 0:
            changed_paths.update(ln.strip() for ln in r.stdout.splitlines() if ln.strip())
    elif scope == "working-tree":
        for git_args in (["diff", "--name-only"], ["diff", "--name-only", "--cached"]):
            r = _git(git_args, cwd=repo_root, check=False)
            if r.returncode == 0:
                changed_paths.update(ln.strip() for ln in r.stdout.splitlines() if ln.strip())
    else:
        r = _git(["diff", "--name-only", f"{base}...HEAD"], cwd=repo_root, check=False)
        if r.returncode == 0:
            changed_paths.update(ln.strip() for ln in r.stdout.splitlines() if ln.strip())
    changed_paths.update(p.as_posix() for p in untracked)

    idents: set[str] = set()
    for rel in changed_paths:
        if not rel:
            continue
        fp = repo_root / rel
        if not fp.is_file():
            continue
        if fp.suffix.lower() in BINARY_EXTS:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.debug("auto-context: %s 읽기 실패 (%s)", fp, e)
            continue
        for pat in IDENTIFIER_PATTERNS:
            for m in pat.finditer(text):
                tok = m.group(1).strip()
                if not tok:
                    continue
                if tok in IDENTIFIER_STOPWORDS:
                    continue
                if len(tok) < AUTO_CONTEXT_MIN_IDENT_LEN:
                    continue
                idents.add(tok)

    log.debug(
        "auto-context: changed files=%d → 식별자 %d개 (sample: %s)",
        len(changed_paths), len(idents), sorted(idents)[:10],
    )
    return idents


def find_caller_candidates(
    repo_root: Path,
    identifiers: set[str],
    exclude_paths: set[str],
) -> list[tuple[Path, str]]:
    """
    `git grep -l --fixed-strings <ident>` 로 식별자를 사용하는 unchanged 파일 검색.
    Returns: [(rel_path, body), ...] — 매칭 식별자 개수 내림차순.
    """
    if not identifiers:
        return []

    score: dict[str, int] = {}
    for ident in sorted(identifiers):
        try:
            r = _git(
                ["grep", "-l", "--fixed-strings", "--", ident],
                cwd=repo_root, check=False,
            )
        except subprocess.SubprocessError as e:
            log.debug("auto-context: git grep '%s' 실패 (%s)", ident, e)
            continue
        if r.returncode not in (0, 1):
            continue
        for line in r.stdout.splitlines():
            rel = line.strip().replace("\\", "/")
            if not rel or rel in exclude_paths:
                continue
            score[rel] = score.get(rel, 0) + 1

    if not score:
        return []

    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))

    result: list[tuple[Path, str]] = []
    total_bytes = 0
    for rel, _s in ranked:
        if len(result) >= AUTO_CONTEXT_MAX_FILES:
            break
        p = repo_root / rel
        if not p.is_file():
            continue
        if p.suffix.lower() in BINARY_EXTS:
            continue
        if p.suffix.lower() in AUTO_CONTEXT_EXCLUDED_EXTS:
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(body) > AUTO_CONTEXT_PER_FILE_LIMIT:
            body = body[:AUTO_CONTEXT_PER_FILE_LIMIT] + "\n// ... [truncated by DDR auto-context]"
        bsize = len(body.encode("utf-8", errors="replace"))
        if total_bytes + bsize > AUTO_CONTEXT_MAX_BYTES:
            if bsize > AUTO_CONTEXT_MAX_BYTES // 4:
                continue
            else:
                break
        total_bytes += bsize
        result.append((Path(rel), body))

    log.info(
        "auto-context: %d 파일 / %d bytes 포함 (식별자 %d개로 검색)",
        len(result), total_bytes, len(identifiers),
    )
    return result


# ─── Patch composition ────────────────────────────────────────────────────────

def _run_git_diff(
    repo_root: Path, diff_args: list[str], out_fh
) -> None:
    cmd = ["git", "diff", *diff_args, "--", ":(top)", *EXCLUDED_PATHSPECS]
    result = subprocess.run(
        cmd, cwd=repo_root, stdout=out_fh, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode not in (0, 1):
        log.warning("git diff 비정상 종료: %s", result.stderr.strip())


def _append_untracked(path: Path, repo_root: Path, out_fh) -> int:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        log.warning("untracked 파일 읽기 실패 (skip): %s — %s", path, e)
        return 0

    rel = path.relative_to(repo_root).as_posix()
    lines = content.splitlines()
    hunk_header = f"@@ -0,0 +1,{len(lines)} @@"
    header = (
        f"diff --git a/{rel} b/{rel}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{rel}\n"
        f"{hunk_header}\n"
    )
    out_fh.write(header)
    for line in lines:
        out_fh.write(f"+{line}\n")
    out_fh.write("\n")
    return len(lines) + 6  # 헤더 라인 포함


def compose_patch(
    repo_root: Path,
    scope: str,
    base: Optional[str],
    untracked: list[Path],
    out_path: Path,
    commit_args: Optional[list[str]] = None,
) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_lines = 0

    with open(out_path, "w", encoding="utf-8", errors="replace") as fh:
        if scope == "commit":
            _run_git_diff(repo_root, commit_args or [], fh)
        elif scope == "working-tree":
            _run_git_diff(repo_root, [], fh)
            _run_git_diff(repo_root, ["--cached"], fh)
        else:
            _run_git_diff(repo_root, [f"{base}...HEAD"], fh)

        for upath in untracked:
            total_lines += _append_untracked(upath, repo_root, fh)

    # 총 라인 수 측정
    with open(out_path, encoding="utf-8", errors="replace") as fh:
        total_lines = sum(1 for _ in fh)

    patch_bytes = out_path.stat().st_size
    if total_lines > PATCH_LINE_SOFT_LIMIT:
        log.warning(
            "patch 라인 수 %d 초과 (soft limit %d). 분석 정확도 낮을 수 있음.",
            total_lines, PATCH_LINE_SOFT_LIMIT,
        )
        print(
            f"[doc-driven-review] 경고: patch {total_lines:,}라인 (권장 {PATCH_LINE_SOFT_LIMIT:,} 이하). "
            "Codex 분석 정확도 낮을 수 있음.",
            file=sys.stderr,
        )
    if patch_bytes > PATCH_BYTES_SOFT_LIMIT:
        log.warning("patch 크기 %dMB (soft limit 2MB).", patch_bytes // 1_000_000)

    return total_lines


# ─── Prompt building ──────────────────────────────────────────────────────────

def build_prompt(
    docs: list[tuple[Path, str]],
    patch_path: Path,
    scope: str,
    base: Optional[str],
    repo_root: Path,
    unchanged_context: Optional[list[tuple[Path, str]]] = None,
) -> str:
    doc_blocks: list[str] = []
    for path, content in docs:
        doc_blocks.append(f"## DOC: {path}\n{content}")
    documents_block = "\n\n".join(doc_blocks)

    if unchanged_context:
        ctx_blocks: list[str] = []
        for path, body in unchanged_context:
            ext = path.suffix.lower().lstrip(".")
            lang = ext if ext in {"cs", "py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "kt", "rb", "php", "cpp", "c", "h", "hpp"} else ""
            ctx_blocks.append(f"## FILE: {path.as_posix()}\n```{lang}\n{body}\n```")
        unchanged_block = (
            "# UNCHANGED CONTEXT (potential callers detected by symbol scan)\n"
            "These files are NOT in the patch but reference symbols from changed files. "
            "Consult them when evaluating cross-file ripple (caller impact, signature mismatches, "
            "namespace dependencies). Each file body is fully reproduced (or head-truncated if >20KB).\n\n"
            + "\n\n".join(ctx_blocks)
        )
    else:
        unchanged_block = (
            "# UNCHANGED CONTEXT\n"
            "(none — no caller candidates detected, auto-context disabled, or no identifiers extracted)"
        )

    return PROMPT_TEMPLATE.format(
        documents_block=documents_block,
        patch_path=patch_path.as_posix(),
        scope=scope,
        base_ref=base or "N/A",
        repo_root=repo_root.as_posix(),
        unchanged_context_block=unchanged_block,
    )


# ─── Output validation ────────────────────────────────────────────────────────

def validate_codex_output(
    stdout: str,
) -> tuple[bool, list[str], Optional[int]]:
    """
    Returns: (ok, errors, conformance_pct) — v1.2 느슨한 검증.
    """
    errors: list[str] = []

    # 1. # Code Review 헤더
    if not H1_RE.search(stdout):
        errors.append("'# Code Review:' 헤더 누락")

    # 2. 7개 섹션 존재 여부 (순서는 권장만, 누락 체크)
    sections_found = SECTION_V2_RE.findall(stdout)
    for expected in EXPECTED_SECTIONS_V2:
        if expected not in sections_found:
            errors.append(f"섹션 누락: {expected}")

    # 3. Counts 라인 (Suggestion 포함 4항목)
    if not COUNTS_V2_RE.search(stdout):
        errors.append("Counts 라인 형식 위반 (Critical/Major/Minor/Suggestion 4개 필요)")

    # 4. 마지막 비공백 라인이 Conformance: N%
    last_nonempty = next(
        (ln for ln in reversed(stdout.splitlines()) if ln.strip()), ""
    )
    m = CONFORMANCE_LINE_RE.match(last_nonempty)
    pct: Optional[int] = None
    if m:
        pct = int(m.group(1))
        if not (0 <= pct <= 100):
            errors.append(f"Conformance 범위 밖: {pct}")
            pct = None
    else:
        errors.append("Conformance: N% 마지막 라인 누락")

    # 5. Review Comments 블록 수 (max 20)
    comment_count = len(COMMENT_BLOCK_RE.findall(stdout))
    if comment_count > REVIEW_COMMENTS_MAX:
        errors.append(f"Review Comments {comment_count}개 (max {REVIEW_COMMENTS_MAX})")

    return (len(errors) == 0, errors, pct)


def format_violation_line(errors: list[str]) -> str:
    joined = "; ".join(errors)
    return f"[doc-driven-review] OUTPUT-SCHEMA-VIOLATION: {joined}"


# ─── Citation verification (인용 file:line 실재 확인) ──────────────────────────

# 인용 path:line 추출 — `file.ext:line` 또는 `file.ext:start-end`
CITATION_RE = re.compile(r"`?([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?`?")
CITATION_CHECK_MAX = 200  # 병리적 출력 방어


def extract_citations(output: str) -> list[tuple[str, int, Optional[int]]]:
    out: list[tuple[str, int, Optional[int]]] = []
    for m in CITATION_RE.finditer(output):
        path = m.group(1).replace("\\", "/")
        ls = int(m.group(2))
        le = int(m.group(3)) if m.group(3) else None
        out.append((path, ls, le))
        if len(out) >= CITATION_CHECK_MAX:
            break
    return out


def verify_citations(
    repo_root: Path, citations: list[tuple[str, int, Optional[int]]]
) -> list[str]:
    """인용 file:line 이 repo에 실재하는지 확인. 환각/범위초과 목록 반환(advisory)."""
    problems: list[str] = []
    seen: set[tuple[str, int, Optional[int]]] = set()
    for path, ls, le in citations:
        key = (path, ls, le)
        if key in seen:
            continue
        seen.add(key)
        p = repo_root / path
        if not p.is_file():
            problems.append(f"{path}:{ls} — 파일 없음")
            continue
        try:
            n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        hi = le or ls
        if hi > n:
            rng = f"{ls}-{le}" if le else f"{ls}"
            problems.append(f"{path}:{rng} — 라인 범위 초과(파일 {n}줄)")
    return problems


def write_review_file(
    repo_root: Path,
    docs: list[tuple[Path, str]],
    scope: str,
    base: Optional[str],
    output: str,
    pct: Optional[int],
) -> Path:
    """리뷰 결과를 <repo_root>/.review/<doc_stem>-review.md 에 저장."""
    review_dir = repo_root / ".review"
    review_dir.mkdir(exist_ok=True)

    first_stem = docs[0][0].stem
    if len(docs) > 1:
        stem = f"{first_stem}+{len(docs) - 1}more"
    else:
        stem = first_stem
    out_path = review_dir / f"{stem}-review.md"

    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M KST")
    doc_names = ", ".join(str(p) for p, _ in docs)
    conformance_line = f"{pct}%" if pct is not None else "N/A"

    header = (
        f"---\n"
        f"docs: {doc_names}\n"
        f"scope: {scope}\n"
        f"base: {base or 'N/A'}\n"
        f"date: {ts}\n"
        f"conformance: {conformance_line}\n"
        f"---\n\n"
    )

    out_path.write_text(header + output, encoding="utf-8")
    return out_path


# ─── Codex invocation ─────────────────────────────────────────────────────────

def _build_codex_cmd(model: Optional[str], effort: Optional[str]) -> list[str]:
    codex_path = shutil.which("codex")
    if not codex_path:
        raise CodexUnavailableError(
            "codex CLI 미설치. npm install -g @openai/codex 또는 `/codex:setup` 실행."
        )
    # Windows: .cmd/.bat 파일은 cmd /c를 통해 실행해야 함
    if os.name == "nt" and codex_path.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", codex_path, "exec", "--skip-git-repo-check"]
    else:
        cmd = [codex_path, "exec", "--skip-git-repo-check"]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    cmd.append("-")  # stdin 프롬프트
    return cmd


def invoke_codex_foreground(
    prompt: str,
    model: Optional[str],
    effort: Optional[str],
    repo_root: Path,
) -> tuple[int, str, str]:
    cmd = _build_codex_cmd(model, effort)
    log.debug("codex cmd: %s", cmd)
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_root,
            timeout=1800,
        )
    except FileNotFoundError:
        raise CodexUnavailableError(
            "codex CLI 실행 실패 (FileNotFoundError). PATH 확인."
        )
    except subprocess.TimeoutExpired:
        raise DocReviewError("codex 호출 1800초 timeout.")
    return proc.returncode, proc.stdout, proc.stderr


def _spawn_detached_foreground(argv: list[str], repo_root: Path) -> int:
    """--background: 자기 자신을 foreground로 detached 재실행(출력→log).

    child가 codex→스키마검증→인용검증→.review 저장 전 과정을 수행하므로
    background 비대칭이 사라지고 patch도 child가 자기 것을 정리한다(누수 해소).
    """
    child_argv = [a for a in argv if a != "--background"]
    info = _git_info_dir(repo_root)
    job_id = uuid.uuid4().hex[:8]
    log_file = info / f"doc-review-bg-{job_id}.log"

    extra: dict = {}
    if os.name == "nt":
        extra["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        extra["start_new_session"] = True

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), *child_argv],
            stdin=subprocess.DEVNULL,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=Path.cwd(),
            text=True,
            encoding="utf-8",
            **extra,
        )

    print(
        "[doc-driven-review] Background 시작됨.\n"
        f"PID: {proc.pid}\n"
        f"Log: {log_file}\n"
        f"확인: tail -f {log_file}  (Unix)  또는  Get-Content -Wait {log_file}  (PowerShell)\n"
        "완료 후 처리된 리뷰 + Conformance + 인용검증이 log 와 .review/ 에 저장됩니다.\n"
    )
    return EXIT_OK


# ─── Patch cleanup ────────────────────────────────────────────────────────────

def cleanup_patch(patch_path: Optional[Path], keep: bool) -> None:
    if keep or patch_path is None:
        return
    try:
        patch_path.unlink(missing_ok=True)
        log.debug("patch 삭제: %s", patch_path)
    except OSError as e:
        log.warning("patch 삭제 실패: %s — %s", patch_path, e)


# ─── Main orchestrator ────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    log.info("doc-driven-review 시작. docs=%s scope=%s", args.docs, args.scope)

    # repo root 결정
    if args.worktree and args.repo_root:
        print(
            "오류: --worktree 와 --repo-root 동시 지정 불가. 하나만 사용하세요.",
            file=sys.stderr,
        )
        return EXIT_ERR
    try:
        if args.worktree:
            repo_root = resolve_worktree(args.worktree, cwd=Path.cwd())
            log.info("worktree 해석: %s → %s", args.worktree, repo_root)
        elif args.repo_root:
            repo_root = args.repo_root
        else:
            repo_root = find_repo_root(Path.cwd())
    except DocReviewError as e:
        print(f"오류: {e}", file=sys.stderr)
        if args.worktree and "worktree" in str(e).lower():
            return EXIT_WORKTREE
        return EXIT_ERR

    # 오래된 bg 로그·stale patch 정리 (best-effort)
    try:
        prune_old_artifacts(_git_info_dir(repo_root))
    except Exception:  # noqa: BLE001
        pass

    # background: 자기 자신을 foreground로 detached 재실행 (비대칭 제거)
    if args.background:
        return _spawn_detached_foreground(argv, repo_root)

    # 문서 읽기
    try:
        docs = read_attached_docs(args.docs)
    except DocTooBigError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_DOC_TOO_BIG
    except DocReviewError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_ERR

    # scope 결정 — --commit 지목 시 working-tree/branch 우회
    commit_args: Optional[list[str]] = None
    if args.commit:
        try:
            commit_args = resolve_commit_diff_args(repo_root, args.commit)
        except BaseRefError as e:
            print(f"오류: {e}", file=sys.stderr)
            return EXIT_NO_BASE
        scope, resolved_base = "commit", args.commit
    else:
        try:
            scope, resolved_base = determine_scope(repo_root, args.scope, args.base)
        except NoChangesError:
            print("리뷰할 변경 없음. working-tree와 branch 모두 비어있습니다.", file=sys.stderr)
            return EXIT_NO_CHANGES
        except BaseRefError as e:
            print(f"오류: {e}", file=sys.stderr)
            return EXIT_NO_BASE
        except DocReviewError as e:
            print(f"오류: {e}", file=sys.stderr)
            return EXIT_ERR

    log.info("scope=%s base=%s", scope, resolved_base)

    # 변경 있는지 최종 확인 (branch scope에서 변경 없으면 NoChanges)
    if scope == "branch":
        r = _git(
            ["diff", "--shortstat", f"{resolved_base}...HEAD"],
            cwd=repo_root, check=False,
        )
        untracked = list_untracked_text_files(repo_root)
        if not r.stdout.strip() and not untracked:
            print("리뷰할 변경 없음. working-tree와 branch 모두 비어있습니다.", file=sys.stderr)
            return EXIT_NO_CHANGES

    # patch 합성
    ts = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    rand = uuid.uuid4().hex[:6]
    patch_path = _git_info_dir(repo_root) / f"doc-review-{ts}-{rand}.patch"
    # commit scope는 커밋된 노드 대상 → untracked 미포함
    untracked = [] if scope == "commit" else list_untracked_text_files(repo_root)

    try:
        total_lines = compose_patch(
            repo_root, scope, resolved_base, untracked, patch_path, commit_args=commit_args
        )
        log.info("patch 합성 완료: %d 라인 → %s", total_lines, patch_path)

        # 변경 0라인
        if total_lines == 0:
            print("리뷰할 변경 없음. patch가 비어있습니다.", file=sys.stderr)
            cleanup_patch(patch_path, args.keep_patch)
            return EXIT_NO_CHANGES

        # Auto-context: cross-file caller 탐지
        unchanged_ctx: Optional[list[tuple[Path, str]]] = None
        if not args.no_auto_context:
            try:
                idents = extract_identifiers_from_changed(
                    repo_root, scope, resolved_base, untracked, commit_args=commit_args
                )
                exclude: set[str] = set()
                if scope == "commit":
                    r = _git(["diff", "--name-only", *(commit_args or [])],
                             cwd=repo_root, check=False)
                    if r.returncode == 0:
                        exclude.update(
                            ln.strip().replace("\\", "/")
                            for ln in r.stdout.splitlines() if ln.strip()
                        )
                elif scope == "working-tree":
                    for gargs in (["diff", "--name-only"],
                                  ["diff", "--name-only", "--cached"]):
                        r = _git(gargs, cwd=repo_root, check=False)
                        if r.returncode == 0:
                            exclude.update(
                                ln.strip().replace("\\", "/")
                                for ln in r.stdout.splitlines() if ln.strip()
                            )
                else:
                    r = _git(["diff", "--name-only", f"{resolved_base}...HEAD"],
                             cwd=repo_root, check=False)
                    if r.returncode == 0:
                        exclude.update(
                            ln.strip().replace("\\", "/")
                            for ln in r.stdout.splitlines() if ln.strip()
                        )
                exclude.update(p.as_posix() for p in untracked)
                unchanged_ctx = find_caller_candidates(repo_root, idents, exclude)
            except Exception as e:  # noqa: BLE001
                log.warning("auto-context 실패 (계속 진행): %s", e, exc_info=args.verbose)
                unchanged_ctx = None
        else:
            log.info("auto-context 비활성화 (--no-auto-context)")

        # 프롬프트 합성
        prompt = build_prompt(docs, patch_path, scope, resolved_base, repo_root, unchanged_ctx)
        log.debug("프롬프트 길이: %d 자", len(prompt))

        # dry-run
        if args.dry_run:
            print(prompt)
            cleanup_patch(patch_path, args.keep_patch)
            return EXIT_OK

        # Codex 호출 (background는 main 초반에 detached fg로 분기됨 → 여기는 항상 fg)
        try:
            rc, stdout, stderr = invoke_codex_foreground(
                prompt, args.model, args.effort, repo_root
            )
        except CodexUnavailableError as e:
            print(f"오류: {e}", file=sys.stderr)
            cleanup_patch(patch_path, args.keep_patch)
            return EXIT_NO_CODEX
        except DocReviewError as e:
            print(f"오류: {e}", file=sys.stderr)
            cleanup_patch(patch_path, args.keep_patch)
            return EXIT_ERR

        if stderr.strip():
            log.debug("codex stderr: %s", stderr.strip())

        # 출력 검증
        ok, errors, pct = validate_codex_output(stdout)
        output = stdout
        if not ok:
            log.warning("스키마 위반: %s", errors)
            output = output.rstrip("\n") + "\n" + format_violation_line(errors) + "\n"
        else:
            log.info("검증 통과. Conformance: %s%%", pct)

        # 인용 검증 (file:line 실재 확인 — 환각 차단, advisory)
        cite_problems = verify_citations(repo_root, extract_citations(stdout))
        if cite_problems:
            log.warning("인용 검증 실패 %d건", len(cite_problems))
            shown = "; ".join(cite_problems[:10])
            more = "" if len(cite_problems) <= 10 else f" (+{len(cite_problems) - 10} more)"
            output = output.rstrip("\n") + (
                f"\n[doc-driven-review] CITATION-CHECK: {len(cite_problems)}건 미검증 — {shown}{more}\n"
            )

        print(output, end="")

        # 리뷰 파일 저장
        try:
            review_path = write_review_file(
                repo_root, docs, scope, resolved_base, output, pct
            )
            print(f"\n[doc-driven-review] Review saved: {review_path}")
            log.info("review 저장: %s", review_path)
        except OSError as e:
            log.warning("review 파일 저장 실패: %s", e)

        # foreground 성공: codex non-zero exit는 경고만
        if rc != 0:
            log.warning("codex exit code %d", rc)

        cleanup_patch(patch_path, args.keep_patch)
        return EXIT_OK

    except Exception as e:
        log.exception("예상치 못한 오류")
        print(f"오류: {e}", file=sys.stderr)
        cleanup_patch(patch_path, args.keep_patch)
        return EXIT_ERR


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(EXIT_KBI)
