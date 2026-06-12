#!/usr/bin/env python3
"""docs-add-task 산출 문서를 Codex 가 2축(prompt 의도 + v0.7 룰)으로 1회 검증.

루프(반복·임계·fix)는 docs-add-task SKILL.md Phase 12 가 제어한다.
본 스크립트는 '1회 검증 + conformance% 반환' 만 담당한다(stateless).

Codex 호출 인프라(CLI 경로 탐색·Windows .cmd 처리·timeout·미설치 예외)는
sibling doc_driven_review.py 에서 import 재사용한다 — 중복 구현 방지.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))  # sibling import 보장

from doc_driven_review import (  # noqa: E402  (sys.path 조정 후 import)
    invoke_codex_foreground,
    CodexUnavailableError,
    DocReviewError,
)

# ─── Exit codes (doc_driven_review.py 컨벤션과 정합) ─────────────────────────────
EXIT_OK = 0
EXIT_ERR = 1
EXIT_NO_CODEX = 2          # doc_driven_review.py:61 과 동일 의미
EXIT_BAD_INPUT = 4

# conformance 추출 — ddr_loop.py:88 과 동일 패턴
CONFORMANCE_LINE_RE = re.compile(r"^Conformance:\s*(\d{1,3})%\s*$", re.M)

# 문서 본문 임베드 soft cap
PER_DOC_CAP = 80_000
TOTAL_CAP = 240_000


# ─── manifest ───────────────────────────────────────────────────────────────────

def load_manifest(path: Path) -> dict:
    """휘발 manifest(JSON) 로드 + 최소 검증. 비거나 깨지면 예외."""
    if not path.is_file():
        raise FileNotFoundError(f"manifest 파일 없음: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest 최상위가 object 가 아님")
    created = data.get("created", [])
    modified = data.get("modified", [])
    if not created and not modified:
        raise ValueError("manifest 비어있음 (created/modified 모두 0건)")
    return data


# ─── 문서 본문 블록 ───────────────────────────────────────────────────────────────

def build_documents_block(repo_root: Path, manifest: dict) -> str:
    """created/modified 문서 본문을 prompt 임베드용 블록으로 직렬화.

    파일을 직접 읽어 임베드 → codex exec 의 파일접근 의존도↓, 결정성↑.
    soft cap 초과 시 head 절단(표식) 또는 omit(표식).
    """
    created = list(manifest.get("created", []))
    modified = list(manifest.get("modified", []))
    blocks: list[str] = []
    total = 0

    def emit(rel: str, tag: str, note: str = "") -> None:
        nonlocal total
        p = repo_root / rel
        if not p.is_file():
            blocks.append(f"## [{tag}] {rel}\n(파일 없음 — 검증 대상이나 누락)")
            return
        body = p.read_text(encoding="utf-8", errors="replace")
        if len(body) > PER_DOC_CAP:
            body = body[:PER_DOC_CAP] + "\n... [truncated by docs_verify]"
        if total + len(body) > TOTAL_CAP:
            blocks.append(f"## [{tag}] {rel}\n... [omitted — total budget exceeded]")
            return
        total += len(body)
        hdr = f"## [{tag}] {rel}" + (f"  (변경 요지: {note})" if note else "")
        blocks.append(f"{hdr}\n```markdown\n{body}\n```")

    for rel in created:
        emit(rel, "CREATED")
    for m in modified:
        if isinstance(m, dict):
            emit(m.get("path", ""), "MODIFIED", m.get("summary", ""))
        else:  # 문자열 경로만 준 경우도 허용
            emit(str(m), "MODIFIED")
    return "\n\n".join(blocks) if blocks else "(검증 대상 문서 없음)"


# ─── Codex prompt ─────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """\
# ROLE
You are a strict reviewer of v0.7 per-App SSOT design documents produced by an automated
doc-writing skill. Judge ONLY the documents listed below against TWO axes. Do not review code.

# ORIGINAL TASK PROMPT (Axis A ground truth)
{user_prompt}

# MODE
{mode}   (NEW = new feature / FRD newly created; CHANGE = existing FRD updated)

# CHANGED DOCUMENTS (the work to verify)
{documents_block}

# AXIS A - PROMPT INTENT
Did the documents actually capture what the ORIGINAL TASK PROMPT asked for?
Check: feature purpose, scope, completion state, edge/error cases the prompt implies.
Missing intent = X; partial = ~; fully captured = OK.

# AXIS B - V0.7 RULES (Standards)
Check each rule below against the documents:
- FRD meta table = 6 rows (문서 ID/버전/기능 ID/상태/작성 가정/관련 문서). TASK meta = 5 rows.
- FRD has all 20 sections (§1..§20); TASK has §1..§12.
- FRD §16 = exactly 3 rows (FC / ADR / ADR-CATALOG) AND each "필요" declaration is actually
  performed in the corresponding doc (declaration-execution match).
- FC 5 tables consistency rule: 기능상태 -> 허용 구현상태/테스트상태 combos must hold
  (Draft->Not Started/미작성, In Progress->Implementing|Blocked / 미작성|작성중, Done->Implemented/통과 ...).
- Bidirectional citation ban: TASK body MUST NOT contain markdown links to permanent SSOT
  (PRD/FC/FRD/ADR). Permanent SSOT MUST NOT cite TASK IDs. Flag any violation.
- AC/TC/Q IDs contiguous (no dup/gap), formatted AC-F<NNN>-<n> / TC-/ Q-.
- ADR-CATALOG Proposed row doc-id == the new ADR file's 문서 ID.
- Doc-id <-> filename match (<App>-FRD-NNN.md <-> meta 문서 ID).

# OUTPUT FORMAT - STRICT
No preamble before `# Doc Verify`. No epilogue after the `Conformance: N%` line.
Use the EXACT structure below. Status symbols: use OK / ~ / X exactly as defined above.

# Doc Verify: {app}

## Summary
- **무엇을 만든/고친 작업인지**: <2-3 lines>
- **핵심 결함**: <2-3 lines, or `- (none)`>

## Axis A - Prompt Intent
| 의도 항목 | 상태 | 근거(문서 §/행) |
|---|---|---|
| <prompt 가 요구한 항목> | OK/~/X | <파일 §위치 또는 MISSING> |

(Enumerate every distinct intent in the prompt. One row each.)

## Axis B - v0.7 Rules
| 룰 | 상태 | 근거 |
|---|---|---|
| FRD 메타 6행 | OK/X | <파일> |
| §16 선언-실행 일치 | OK/~/X | <...> |
| 양방향 인용 금지 | OK/X | <위반 위치 또는 OK> |

(Enumerate every rule checked above. One row each.)

## Defects
(Each actionable defect, sorted Critical -> Major -> Minor. If none: `- (none)`.)
- `<file>:<line-or-§>` | [A|B] | [CRITICAL|MAJOR|MINOR] | <문제 1줄>. Fix: <조치 1줄>.

## Conformance
Counts: Critical: <N>, Major: <M>, Minor: <K>
Weights: <axis-row weight arithmetic per RUBRIC>
Conformance: <integer 0-100>%

# CONFORMANCE RUBRIC
- Weight each Axis-A and Axis-B row by severity-if-failed: Critical=4, Major=2, Minor=1.
- pct = round(100 * sum(passed_weight) / sum(total_weight)); OK=full, ~=0.5x, X=0.
- total_weight = sum of all row full weights (A + B). Round to nearest int. 100% requires all OK.

# FIELD RULES
- Status symbols: exactly OK / ~ / X.
- Exact-string fidelity: when a doc must contain a literal (status code, message, ID),
  quote it verbatim with "..."; one-char mismatch = defect.
- Cite real `<file>:<section-or-line>` from the CHANGED DOCUMENTS block.
"""


def build_prompt(
    repo_root: Path, app: str, mode: str, user_prompt: str, manifest: dict
) -> str:
    return PROMPT_TEMPLATE.format(
        user_prompt=(user_prompt or "").strip() or "(원본 prompt 미전달)",
        mode=mode,
        documents_block=build_documents_block(repo_root, manifest),
        app=app,
    )


def extract_conformance(stdout: str) -> Optional[int]:
    """stdout 의 마지막 Conformance: N% 를 추출. 없거나 범위 밖이면 None."""
    matches = CONFORMANCE_LINE_RE.findall(stdout)
    if not matches:
        return None
    try:
        pct = int(matches[-1])
    except ValueError:
        return None
    return pct if 0 <= pct <= 100 else None


# ─── CLI ──────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="docs_verify",
        description="docs-add-task 산출 문서 2축 Codex 검증 (단일 라운드)",
    )
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--app", required=True)
    p.add_argument("--prompt", required=True, help="원본 사용자 prompt (Axis A)")
    p.add_argument("--mode", choices=["NEW", "CHANGE"], required=True)
    p.add_argument("--manifest-file", type=Path, required=True, dest="manifest_file")
    p.add_argument("--model", default=None, help="codex --model 통과")
    # 기본 None — codex config.toml 의 reasoning effort 기본값 사용.
    # --effort 명시는 `codex exec --effort` 를 지원하는 codex 빌드에서만 안전(opt-in).
    p.add_argument("--effort", choices=["low", "medium", "high"], default=None)
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="codex 호출 skip, 생성 프롬프트만 stdout")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = args.repo.resolve()

    try:
        manifest = load_manifest(args.manifest_file)
    except FileNotFoundError as e:
        print(f"[docs-verify] {e}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[docs-verify] manifest 오류: {e}", file=sys.stderr)
        return EXIT_BAD_INPUT

    prompt = build_prompt(repo_root, args.app, args.mode, args.prompt, manifest)

    if args.dry_run:
        print(prompt)
        return EXIT_OK

    try:
        _rc, out, err = invoke_codex_foreground(
            prompt, args.model, args.effort, repo_root
        )
    except CodexUnavailableError as e:
        print(f"[docs-verify] {e}", file=sys.stderr)
        return EXIT_NO_CODEX
    except DocReviewError as e:  # timeout 등
        print(f"[docs-verify] {e}", file=sys.stderr)
        return EXIT_ERR

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    if err.strip():
        print(err, file=sys.stderr)

    pct = extract_conformance(out)
    if pct is None:
        print("[docs-verify] WARN: Conformance 라인 추출 실패", file=sys.stderr)
        return EXIT_ERR  # SKILL 은 이 경우 보수적으로 fix 라운드 진행
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
