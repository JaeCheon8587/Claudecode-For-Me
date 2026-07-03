#!/usr/bin/env python3
"""
Docs Conformance — 요구사항서(기준) ↔ 생성 설계문서 정합을 Codex로 1회 채점.

task-write/ssot-write 가 작성한 설계문서(FRD/TASK/ADR/FC/PRD/ADR-CATALOG)가
원래 요구사항서를 몇 % 반영했는지 codex 로 채점하고, 부족 항목·보강 지시를
전용 출력 템플릿으로 돌려준다. 루프(재검증·보강)는 호출자(task-write/
ssot-write SKILL)가 관장하며, 본 스크립트는 **1회 검증**만 수행한다.

기준(reference)과 검증 대상(targets)을 명시 경로로 받으므로 git diff 를 쓰지
않는다 → reference 가 대상에 섞여 자기 자신을 채점하는 오염이 구조적으로 없다.
codex 호출 plumbing 은 doc_driven_review.py 에서 import 재사용한다(원본 무수정).

Usage:
    python3 scripts/docs_conformance.py --reference <req.md> --targets <d1.md> [<d2.md> ...]

Options:
    --reference <path>      필수. 기준 요구사항서 1개 (불변).
    --targets <path> [...]  필수. 채점할 생성 설계문서 1개 이상.
    --model <name>          codex --model 통과.
    --effort <level>        codex --effort 통과.
    --repo-root <path>      기본 git rev-parse --show-toplevel.
    --dry-run               codex 호출 skip, 생성 프롬프트만 stdout.
    --verbose               DEBUG 로그.

Exit codes:
    0   정상 (Codex stdout 출력 완료)
    1   기타 오류
    2   codex CLI 미설치
    4   문서 크기 초과 (단일 100KB / 합산 200KB)
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
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# 형제 모듈(같은 ./scripts/) import 가능하도록 스크립트 디렉토리를 경로에 추가
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from doc_driven_review import (  # noqa: E402  codex plumbing 재사용 (원본 무수정)
    CodexUnavailableError,
    DocReviewError,
    DocTooBigError,
    find_repo_root,
    invoke_codex_foreground,
    read_attached_docs,
)

log = logging.getLogger("docs_conformance")

TZ = timezone(timedelta(hours=9))

EXIT_OK = 0
EXIT_ERR = 1
EXIT_NO_CODEX = 2
EXIT_DOC_TOO_BIG = 4
EXIT_KBI = 130

# 출력 마지막 비공백 라인 검증/추출 — `Conformance: N%`
CONFORMANCE_LINE_RE = re.compile(r"^Conformance:\s*(\d{1,3})%\s*$")
# multiline 마지막 매치 추출 (호출자 파싱과 동일 규칙)
CONFORMANCE_ANY_RE = re.compile(r"^Conformance:\s*(\d{1,3})%\s*$", re.M)


PROMPT_TEMPLATE = """\
# ROLE
You are a requirements-conformance auditor. Judge how completely the GENERATED
DESIGN DOCUMENTS reflect the REFERENCE REQUIREMENT. The reference is the immutable
ground truth; the generated documents are what you score against it.

You audit requirement→document coverage ONLY. Do NOT judge code, file:line, or
implementation detail — these are design documents, not code.

# REFERENCE REQUIREMENT (ground truth)
## 기준: {reference_path}
{reference_body}

# GENERATED DESIGN DOCUMENTS (under audit)
{targets_block}

# TASK
Enumerate EVERY discrete requirement in the REFERENCE. For each, decide whether it
is reflected in the GENERATED DESIGN DOCUMENTS and where. Then output the report in
the EXACT format below.

# OUTPUT FORMAT — STRICT
No preamble before `# 요구사항 정합 검증`. No epilogue after the `Conformance: N%` line.

# 요구사항 정합 검증: {reference_stem}

## 요약
- 기준 요구사항서: {reference_path}
- 검증 대상: {targets_names}
- 요구 항목 <N>개 — ✓반영 <a> / ⚠부분 <b> / ✗누락 <c>
- 총평: <2줄 이내>

## 요구 반영 표
| # | 요구 항목 (요구사항서 근거) | 상태 | 반영 위치 | 부족 내용 |
|---|---|---|---|---|
| 1 | <요구 한 줄 + §/문장 근거> | ✓/⚠/✗ | <문서명 §절 / MISSING> | <✓면 "-", ⚠·✗면 무엇이 어떻게 부족한지 ≤120자> |

## 부족 항목 (⚠·✗ 만, 심각도 순, 최대 15)

### 1. [✗] <요구 제목>
- 근거: "<요구사항서 원문 인용>"
- 현재: <생성문서에서 어떻게 누락/부족한가>
- 보강: <대상 문서·절 + 추가/수정할 내용 1~2줄>

## Conformance
Counts: ✓ <a>, ⚠ <b>, ✗ <c> (총 <N>)
산식: passed = ✓×1 + ⚠×0.5 = <P> / total = <N> → round(100×P/N)
Conformance: <integer 0-100>%

# FIELD RULES
- 요구 반영 표: 요구사항서의 모든 요구를 1행씩 enumerate. 한 요구가 여러 문서에
  분산되면 "반영 위치" 열에 `;` 로 나열. 같은 대상의 연관 요구는 1행 통합하되 상태는
  최악 우선(✗ > ⚠ > ✓).
- 상태 기호: 정확히 ✓ / ⚠ / ✗ 중 하나.
  - ✓ 반영: 요구가 생성문서에 구체적·검증 가능하게 담김(명시 literal·기준 포함).
  - ⚠ 부분: 외형은 있으나 핵심 일부 누락. 명시 항목(완료조건·제약·메시지)이 빠지면 ✗.
  - ✗ 누락: 생성문서에 해당 요구가 없거나 정반대. 의심스러우면 더 엄격한 쪽 선택.
- 부족 항목: ⚠·✗ 인 요구마다 1블록. **보강 지시**(어느 문서 어느 절에 무엇을 추가/수정)를
  반드시 포함 — 호출자가 이 지시로 문서를 고친다. 없으면 `- (없음)`.
- 코드 경로/클래스/메서드/file:line 채점·인용 금지. 요구↔문서 정합만 본다.

# CONFORMANCE RUBRIC
- 요구 항목마다 가중치 균일 = 1.
- passed = (✓ 개수 × 1) + (⚠ 개수 × 0.5). total = 전체 요구 개수 N.
- pct = round(100 × passed / N). 정수로 반올림. 100% 는 전 요구 ✓ 일 때만.
- "산식" 줄에 위 계산을 그대로 노출한다.
- 마지막 줄은 반드시 `Conformance: <정수>%` (뒤에 다른 텍스트 금지).
"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="docs_conformance",
        description="요구사항서 기준으로 생성 설계문서 정합을 Codex가 채점",
    )
    p.add_argument("--reference", required=True, type=Path,
                   metavar="PATH", help="기준 요구사항서 1개 (불변)")
    p.add_argument("--targets", required=True, nargs="+", type=Path,
                   metavar="PATH", help="채점할 생성 설계문서 1개 이상")
    p.add_argument("--model", default=None, help="codex --model 통과")
    p.add_argument("--effort",
                   choices=["minimal", "low", "medium", "high", "xhigh"],
                   default=None)
    p.add_argument("--repo-root", type=Path, default=None, dest="repo_root")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="codex 호출 skip, 생성 프롬프트만 stdout")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args(argv)


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )


def dedupe_targets(reference: Path, targets: list[Path]) -> list[Path]:
    """reference 와 동일 경로를 targets 에서 제거(자기 채점 방지). 순서·중복 정리."""
    ref_resolved = reference.resolve()
    seen: set[Path] = set()
    out: list[Path] = []
    for t in targets:
        tr = t.resolve()
        if tr == ref_resolved:
            continue
        if tr in seen:
            continue
        seen.add(tr)
        out.append(t)
    return out


def build_prompt(
    reference: tuple[Path, str],
    targets: list[tuple[Path, str]],
) -> str:
    ref_path, ref_body = reference
    target_blocks = "\n\n".join(
        f"## 대상: {p}\n{body}" for p, body in targets
    )
    targets_names = ", ".join(str(p) for p, _ in targets)
    return PROMPT_TEMPLATE.format(
        reference_path=ref_path,
        reference_stem=ref_path.stem,
        reference_body=ref_body,
        targets_block=target_blocks,
        targets_names=targets_names,
    )


def extract_conformance(stdout: str) -> Optional[int]:
    """stdout 의 마지막 `Conformance: N%` 추출 (0-100 범위 검증)."""
    matches = CONFORMANCE_ANY_RE.findall(stdout)
    if not matches:
        return None
    try:
        pct = int(matches[-1])
    except ValueError:
        return None
    return pct if 0 <= pct <= 100 else None


def validate_output(stdout: str) -> tuple[bool, list[str], Optional[int]]:
    """느슨한 스키마 검증 — 헤더 + 마지막 Conformance 라인."""
    errors: list[str] = []
    if not re.search(r"^# 요구사항 정합 검증:", stdout, re.M):
        errors.append("'# 요구사항 정합 검증:' 헤더 누락")
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
    return (len(errors) == 0, errors, pct)


def write_review_file(
    repo_root: Path,
    reference: Path,
    targets: list[Path],
    output: str,
    pct: Optional[int],
) -> Path:
    """리뷰 결과를 <repo_root>/.review/req-conformance-<ref_stem>.md 에 저장."""
    review_dir = repo_root / ".review"
    review_dir.mkdir(exist_ok=True)
    out_path = review_dir / f"req-conformance-{reference.stem}.md"

    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M KST")
    target_names = ", ".join(str(t) for t in targets)
    conformance_line = f"{pct}%" if pct is not None else "N/A"
    header = (
        f"---\n"
        f"reference: {reference}\n"
        f"targets: {target_names}\n"
        f"date: {ts}\n"
        f"conformance: {conformance_line}\n"
        f"---\n\n"
    )
    out_path.write_text(header + output, encoding="utf-8")
    return out_path


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)

    # repo root
    try:
        repo_root = args.repo_root if args.repo_root else find_repo_root(Path.cwd())
    except DocReviewError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_ERR

    targets = dedupe_targets(args.reference, args.targets)
    if not targets:
        print("오류: 채점할 대상 문서가 없습니다 (reference 와 동일 경로만 지정됨).",
              file=sys.stderr)
        return EXIT_ERR

    # 문서 읽기 (크기·인코딩 제한 재사용)
    try:
        ref_docs = read_attached_docs([args.reference])
        target_docs = read_attached_docs(targets)
    except DocTooBigError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_DOC_TOO_BIG
    except DocReviewError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_ERR

    prompt = build_prompt(ref_docs[0], target_docs)
    log.debug("프롬프트 길이: %d 자", len(prompt))

    if args.dry_run:
        print(prompt)
        return EXIT_OK

    try:
        rc, stdout, stderr = invoke_codex_foreground(
            prompt, args.model, args.effort, repo_root
        )
    except CodexUnavailableError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_NO_CODEX
    except DocReviewError as e:
        print(f"오류: {e}", file=sys.stderr)
        return EXIT_ERR

    if stderr.strip():
        log.debug("codex stderr: %s", stderr.strip())

    ok, errors, pct = validate_output(stdout)
    output = stdout
    if not ok:
        log.warning("스키마 위반: %s", errors)
        output = output.rstrip("\n") + "\n[docs-conformance] OUTPUT-SCHEMA-VIOLATION: " \
            + "; ".join(errors) + "\n"
    else:
        log.info("검증 통과. Conformance: %s%%", pct)

    print(output, end="")

    try:
        review_path = write_review_file(
            repo_root, args.reference, targets, output, pct
        )
        print(f"\n[docs-conformance] Review saved: {review_path}")
    except OSError as e:
        log.warning("review 파일 저장 실패: %s", e)

    if rc != 0:
        log.warning("codex exit code %d", rc)
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(EXIT_KBI)
