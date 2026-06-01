#!/usr/bin/env python3
"""
DDR Loop — doc-driven-review(검증) ↔ fix(claude) 수렴 루프 오케스트레이터.

DDR(Codex)로 문서↔코드 conformance를 채점하고, 임계 미달이면 그 리포트를
claude(-p)에게 넘겨 코드를 고친 뒤 재검증한다. 임계 도달 또는 최대 반복 cap까지 반복.

핵심 분리: 검증자=Codex(DDR), 수정자=Claude. 같은 모델이 짠 코드를 같은 모델이
채점하는 self-grading 마스킹을 피한다. forge_scope.py·doc_driven_review.py 원본은
건드리지 않고 재사용만 한다.

Usage:
    python3 scripts/ddr_loop.py --docs <p1> [<p2>...] [options]

Options:
    --docs <path> [path...]       필수. 검증할 문서 경로 1개 이상 (DDR 통과)
    --worktree <branch|path>      대상 워크트리. fix는 이 워크트리 안에서 수행 (--commit 과 mutex)
    --commit <ref>                커밋 노드 검증. fix cwd = repo root (--worktree 와 mutex)
    --scope auto|working-tree|branch  기본 auto. DDR 통과
    --base <ref>                  branch scope 기준점. DDR 통과
    --max-iter <N>                최대 반복 횟수. 기본 10
    --threshold <pct>             목표 conformance %. 기본 95
    --commit-each                 라운드별 fix를 타깃에 커밋 (기본 off = 미커밋 누적)
    --model <name>                codex(DDR) --model 통과
    --effort <level>              codex(DDR) --effort 통과
    --fix-model <name>            fix용 claude 모델. 기본 claude-sonnet-4-6 (최신 Sonnet)
    --fix-effort <level>          fix claude --effort (low|medium|high|xhigh|max). 기본 high
    --trust                       fix claude에 --dangerously-skip-permissions 부여 (자동 수정 필수)
    --quiet                       진행 로그 억제
    --verbose                     DEBUG 로그
    --dry-run                     DDR 1회만 돌리고 fix 없이 conformance 출력

Exit codes:
    0   임계 도달 (수렴 성공)
    1   기타 오류
    2   codex CLI 미설치 (DDR EXIT_NO_CODEX 전파)
    3   리뷰할 변경 없음 (DDR EXIT_NO_CHANGES 전파)
    7   cap 도달·임계 미달
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
import subprocess
import uuid
from pathlib import Path
from typing import Optional

# 형제 모듈(같은 ./scripts/) import 가능하도록 스크립트 디렉토리를 경로에 추가
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from forge_scope import ClaudeInvoker  # noqa: E402  fix 수정자 (claude -p)
from doc_driven_review import (  # noqa: E402  타깃 해석 재사용
    find_repo_root,
    resolve_worktree,
)

log = logging.getLogger("ddr_loop")

EXIT_OK = 0
EXIT_ERR = 1
EXIT_NO_CODEX = 2
EXIT_NO_CHANGES = 3
EXIT_CAP = 7
EXIT_KBI = 130

DDR_SCRIPT = SCRIPT_DIR / "doc_driven_review.py"
DEFAULT_MAX_ITER = 10
DEFAULT_THRESHOLD = 95
DEFAULT_FIX_MODEL = "claude-sonnet-4-6"  # 최신 Sonnet
DEFAULT_FIX_EFFORT = "high"              # claude --effort 레벨

# DDR stdout 의 codex 리포트에서 conformance 추출.
# stdout 마지막 라인은 "[doc-driven-review] Review saved: ..." 이므로
# 단순 lastline 이 아니라 multiline 검색 후 마지막 매치를 사용한다.
CONFORMANCE_RE = re.compile(r"^Conformance:\s*(\d{1,3})%\s*$", re.M)
REVIEW_SAVED_RE = re.compile(r"Review saved:\s*(.+?)\s*$", re.M)


# ─── 인자 파싱 ──────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ddr_loop",
        description="doc-driven-review ↔ fix 수렴 루프",
    )
    p.add_argument("--docs", nargs="+", required=True, type=Path,
                   help="검증할 문서 경로 1개 이상")
    p.add_argument("--worktree", default=None, metavar="<branch|path>",
                   help="대상 워크트리 (--commit 과 mutex)")
    p.add_argument("--commit", default=None, metavar="<ref>",
                   help="커밋 노드 검증 (--worktree 과 mutex)")
    p.add_argument("--scope", choices=["auto", "working-tree", "branch"],
                   default="auto")
    p.add_argument("--base", default=None, help="branch scope 기준점")
    p.add_argument("--max-iter", type=int, default=DEFAULT_MAX_ITER,
                   dest="max_iter")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    p.add_argument("--commit-each", action="store_true", dest="commit_each",
                   help="라운드별 fix를 타깃에 커밋")
    p.add_argument("--model", default=None, help="codex(DDR) --model 통과")
    p.add_argument("--effort", default=None, help="codex(DDR) --effort 통과")
    p.add_argument("--fix-model", default=DEFAULT_FIX_MODEL, dest="fix_model")
    p.add_argument("--fix-effort", default=DEFAULT_FIX_EFFORT, dest="fix_effort",
                   choices=["low", "medium", "high", "xhigh", "max"],
                   help=f"fix claude --effort 레벨. 기본 {DEFAULT_FIX_EFFORT}")
    p.add_argument("--trust", action="store_true",
                   help="fix claude 에 --dangerously-skip-permissions 부여")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    return p.parse_args(argv)


def setup_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)


# ─── conformance 추출 ───────────────────────────────────────────────────────────

def extract_conformance(ddr_stdout: str) -> Optional[int]:
    """DDR stdout 의 codex 리포트에서 마지막 Conformance: N% 를 추출."""
    matches = CONFORMANCE_RE.findall(ddr_stdout)
    if not matches:
        return None
    try:
        pct = int(matches[-1])
    except ValueError:
        return None
    return pct if 0 <= pct <= 100 else None


def extract_review_path(ddr_stdout: str) -> Optional[str]:
    m = list(REVIEW_SAVED_RE.finditer(ddr_stdout))
    return m[-1].group(1) if m else None


# ─── DDR 호출 (검증자, subprocess) ──────────────────────────────────────────────

def run_ddr(args: argparse.Namespace) -> tuple[int, str, str]:
    """doc_driven_review.py 를 subprocess 로 호출. (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(DDR_SCRIPT), "--docs", *[str(d) for d in args.docs]]
    if args.commit:
        cmd += ["--commit", args.commit]
    else:
        cmd += ["--scope", args.scope]
        if args.base:
            cmd += ["--base", args.base]
    if args.worktree:
        cmd += ["--worktree", args.worktree]
    if args.model:
        cmd += ["--model", args.model]
    if args.effort:
        cmd += ["--effort", args.effort]
    if args.verbose:
        cmd += ["--verbose"]
    log.debug("DDR cmd: %s", cmd)
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=Path.cwd(),
    )
    return proc.returncode, proc.stdout, proc.stderr


# ─── fix 프롬프트 (수정자) ──────────────────────────────────────────────────────

def build_fix_prompt(ddr_stdout: str, docs: list[Path]) -> str:
    doc_list = "\n".join(f"- {d}" for d in docs)
    return f"""You are fixing code so it conforms to specification documents.

## Specification documents (source of truth)
{doc_list}

## Independent conformance review (from Codex — a separate reviewer)
The review below compared the current code against the documents above.
Your job: raise conformance.

- Resolve every **Missing** item (implement what the docs require but code lacks).
- Resolve every **Improve** item (fix logic/signature/literal gaps flagged as ⚠ or ✗).
- For **Overengineered** items, remove additions that go beyond the documents' scope.

{ddr_stdout}

## Rules
- Edit only source/test code in the working tree. Do NOT touch `.review/` — it is read-only review output.
- Do NOT add public APIs or behavior beyond what the documents specify.
- If a fix breaks the build or tests, fix those too.
- Make the minimal changes needed to raise conformance. No unrelated refactors.
- Do NOT commit. Stop when the findings above are addressed.
"""


# ─── 라운드 커밋 ────────────────────────────────────────────────────────────────

def git_commit_all(target_dir: Path, message: str) -> bool:
    """타깃 디렉토리에서 변경 전체를 커밋. 변경 없으면 False."""
    subprocess.run(["git", "add", "-A"], cwd=target_dir, check=False,
                   capture_output=True, text=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=target_dir, check=False,
    )
    if staged.returncode == 0:  # 스테이지 변경 없음
        return False
    r = subprocess.run(
        ["git", "commit", "-m", message], cwd=target_dir, check=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        log.warning("커밋 실패: %s", r.stderr.strip())
        return False
    return True


# ─── scope ↔ commit-each 상호작용 가드 ──────────────────────────────────────────

def warn_scope_commit_combo(args: argparse.Namespace) -> None:
    if args.commit:
        return
    if args.commit_each and args.scope == "working-tree":
        log.warning(
            "[ddr-loop] 경고: --commit-each + --scope working-tree — "
            "커밋 후 작업트리가 비어 다음 라운드 DDR이 변경을 못 봅니다. "
            "--scope branch 또는 auto 권장."
        )
    elif not args.commit_each and args.scope == "branch":
        log.warning(
            "[ddr-loop] 경고: --scope branch + 미커밋 모드 — "
            "fix가 미커밋 상태라 branch diff에 안 나타나 진전이 안 보일 수 있습니다. "
            "--scope working-tree/auto 또는 --commit-each 권장."
        )


# ─── 종료 리포트 ────────────────────────────────────────────────────────────────

def render_trajectory(traj: list[Optional[int]]) -> str:
    return " → ".join(f"{p}%" if p is not None else "N/A" for p in traj)


def report(traj: list[Optional[int]], threshold: int, max_iter: int,
           converged: bool, review_path: Optional[str],
           last_stdout: str) -> None:
    iters = len(traj)
    print(f"\n[ddr-loop] iterations: {iters}/{max_iter}")
    final = traj[-1] if traj else None
    mark = "✅ threshold {0}% 도달".format(threshold) if converged \
        else f"⛔ threshold {threshold}% 미달 (cap)"
    print(f"[ddr-loop] conformance: {render_trajectory(traj)}  {mark}")
    if review_path:
        print(f"[ddr-loop] review: {review_path}")
    if not converged:
        # 남은 findings — Top Priorities 섹션 인용
        block = _extract_section(last_stdout, "Top Priorities")
        if block:
            print("\n[ddr-loop] 남은 우선순위 findings:")
            print(block)


def _extract_section(stdout: str, name: str) -> Optional[str]:
    """## <name> 섹션부터 다음 ## 직전까지 추출."""
    pat = re.compile(rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", re.M | re.S)
    m = pat.search(stdout)
    if not m:
        return None
    body = m.group(1).strip()
    return body or None


# ─── 메인 루프 ──────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose, args.quiet)

    if args.worktree and args.commit:
        print("오류: --worktree 와 --commit 동시 지정 불가.", file=sys.stderr)
        return EXIT_ERR
    if args.max_iter < 1:
        print("오류: --max-iter 는 1 이상이어야 합니다.", file=sys.stderr)
        return EXIT_ERR
    if not (0 <= args.threshold <= 100):
        print("오류: --threshold 는 0~100 범위.", file=sys.stderr)
        return EXIT_ERR

    # fix 타깃 디렉토리 해석
    try:
        if args.worktree:
            target_dir = resolve_worktree(args.worktree, cwd=Path.cwd())
        else:
            target_dir = find_repo_root(Path.cwd())
    except Exception as e:  # noqa: BLE001  (DocReviewError 등)
        print(f"오류: 타깃 디렉토리 해석 실패 — {e}", file=sys.stderr)
        return EXIT_ERR
    log.info("[ddr-loop] fix 타깃: %s", target_dir)

    warn_scope_commit_combo(args)

    # fix 수정자 (claude -p) — 세션 재사용으로 라운드 간 맥락 누적
    invoker = ClaudeInvoker(
        trust=args.trust,
        cwd=target_dir,
        model=args.fix_model,
        effort=args.fix_effort,
        session_id=str(uuid.uuid4()),
        use_session=True,
    )

    traj: list[Optional[int]] = []
    last_stdout = ""
    review_path: Optional[str] = None
    converged = False

    for i in range(1, args.max_iter + 1):
        log.info("[ddr-loop] === iteration %d/%d: 검증(DDR) ===", i, args.max_iter)
        rc, stdout, stderr = run_ddr(args)
        last_stdout = stdout
        rp = extract_review_path(stdout)
        if rp:
            review_path = rp

        if rc == EXIT_NO_CODEX:
            print("오류: codex CLI 미설치 — DDR 검증 불가.", file=sys.stderr)
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            return EXIT_NO_CODEX
        if rc == EXIT_NO_CHANGES:
            print("[ddr-loop] 리뷰할 변경 없음 — 루프 종료.", file=sys.stderr)
            if i == 1:
                return EXIT_NO_CHANGES
            break
        if rc not in (EXIT_OK,):
            print(f"오류: DDR 비정상 종료 (exit {rc}).", file=sys.stderr)
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            return rc or EXIT_ERR

        pct = extract_conformance(stdout)
        traj.append(pct)
        if pct is None:
            log.warning("[ddr-loop] conformance 파싱 실패 (스키마 위반 가능) — 계속")
        else:
            log.info("[ddr-loop] conformance = %d%% (threshold %d%%)", pct, args.threshold)

        # dry-run: 1회 검증만
        if args.dry_run:
            print(stdout, end="")
            report(traj, args.threshold, args.max_iter,
                   converged=(pct is not None and pct >= args.threshold),
                   review_path=review_path, last_stdout=last_stdout)
            return EXIT_OK

        if pct is not None and pct >= args.threshold:
            converged = True
            break

        if i == args.max_iter:
            break  # cap — 마지막 라운드는 fix 안 함

        # ── fix 패스 (claude) ──
        log.info("[ddr-loop] === iteration %d: 개선(claude) ===", i)
        fix_prompt = build_fix_prompt(stdout, args.docs)
        frc, fout, ferr = invoker.call(fix_prompt)
        if frc != 0:
            log.warning("[ddr-loop] fix claude exit %d — 계속 진행. stderr: %s",
                        frc, ferr.strip()[:500])

        if args.commit_each:
            committed = git_commit_all(target_dir, f"fix: ddr-loop iter {i}")
            log.info("[ddr-loop] 라운드 %d 커밋: %s", i,
                     "완료" if committed else "변경 없음")

    report(traj, args.threshold, args.max_iter, converged, review_path, last_stdout)
    return EXIT_OK if converged else EXIT_CAP


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(EXIT_KBI)
