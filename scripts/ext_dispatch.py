#!/usr/bin/env python3
"""ext_dispatch — 외부 코딩 에이전트(Codex CLI) 위임 하네스 (위성 고도).

오케스트레이션은 하지 않는다. 전송 계층만 담당한다:
스펙 파일 + 역할 프리앰블 → 외부 CLI 실행 → raw 캡처 → 리시트 추출·구조 검증
→ (coder) git diff 대조 → stdout 리시트 + 마지막 줄 JSON.

판단(재시도·폴백·수용·폐기)은 전부 호출한 오케스트레이터의 몫이다.

역할은 전부 "노동" 계약이다 — 위치(scout) / 사실(explorer) / 타이핑(coder).
종합·판정·문서 저작은 외부로 내리지 않는다: 판단을 외부에 맡기면 그 검증이
다시 내부 모델의 읽기를 요구해 절약이 상쇄된다.

Subcommands:
    run   --spec <ABS> --report <ABS> --role scout|explorer|coder  단일 위임
    wave  --manifest <ABS json> [--dry-run]                        N개 병렬 보장

wave 는 manifest 의 모든 job 을 ThreadPoolExecutor(max_workers=N) 로
동시 기동한다 — 큐잉 없음. N개 병렬 실행은 코드가 보장한다.

Exit codes:
    0  OK (BLOCKED 리시트 포함 — BLOCKED 는 유효한 결과)
    1  일반 오류 / wave 에서 1개 이상 job 실패
    2  외부 CLI 없음 (codex 미설치)
    3  리시트 추출·구조 검증 실패
    4  SPEC 위반 (TARGET FILES 밖 변경 — script-verified)
    5  타임아웃
    6  에이전트 실행 실패 (rc != 0 + 리시트 마커 없음 — 쿼터/크레딧 소진 포함)
"""

# Encoding bootstrap — FIRST executable code (Windows cp949 콘솔 회피)
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXIT_OK = 0
EXIT_ERR = 1
EXIT_NO_AGENT = 2
EXIT_BAD_RECEIPT = 3
EXIT_SPEC_VIOLATION = 4
EXIT_TIMEOUT = 5
EXIT_AGENT_ERROR = 6

RECEIPT_MARKER = "## RECEIPT"
RECEIPT_MAX_LINES = 30

REQUIRED_FIELDS = {
    "scout": ("FOUND", "SEARCHED", "CONFIDENCE"),
    # explorer 는 native explorer 의 "노동" 필드만 물려받은 축소 계약이다.
    # 판단 필드(ANSWER/MAP/RISKS)는 요구하지 않는다 — 프리앰블이 금지한다.
    "explorer": ("KEY FACTS", "COVERAGE", "CONFIDENCE"),
    "coder": ("STATUS", "CHANGED", "SPEC", "VERIFY"),
}

DEFAULTS = {
    "scout": {"timeout": 300, "effort": "max"},
    "explorer": {"timeout": 600, "effort": "max"},
    "coder": {"timeout": 1200, "effort": "max"},
}
# gpt-5.5 는 릴레이의 openai 크레딧 풀 소진으로 항상 즉사한다
# ("Your workspace is out of credits" → rc 1 → exit 6, 미션 적격성 무관).
# 살아있는 풀은 z-ai 계열 — 여기가 ext 경로의 기본값이어야 한다.
DEFAULT_MODEL = "zai/glm-5.2"

# 작업 트리를 수정하는 역할 — 실행 전후 porcelain 대조 대상.
# scout/explorer 는 읽기 전용이라 대조를 생략한다.
WRITE_ROLES = frozenset({"coder"})

# rc != 0 + 리시트 부재일 때만 스캔하는 원인 추정 시그널 (소문자 부분 매칭).
QUOTA_SIGNALS = ("quota", "usage limit", "credit", "rate limit",
                 "insufficient", "429")

PREAMBLE_DIR = Path(__file__).resolve().parent / "ext_preambles"

_print_lock = threading.Lock()


def _err(msg: str, code: int) -> None:
    print(f"[ext] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- invokers

def _invoke_codex(prompt: str, model: str, effort: str, timeout: int,
                  cwd: str):
    """codex exec 실행. returns (stdout, stderr, returncode).

    effort 는 CLI 플래그가 아니라 config 키로 전달한다
    (requirement-spec/SKILL.md:119 — `--effort` 플래그는 존재하지 않음).
    stderr 는 호출측에서 raw 파일에만 기록한다 — stdout 과 합치면
    리시트(출력 말미) 뒤에 stderr 가 붙어 추출 창을 오염시킨다.
    """
    codex_path = shutil.which("codex")
    if not codex_path:
        raise FileNotFoundError("codex CLI not found on PATH")
    cmd = [codex_path, "exec", "--skip-git-repo-check",
           "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-"]
    if codex_path.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=cwd, timeout=timeout,
    )
    return proc.stdout or "", proc.stderr or "", proc.returncode


INVOKERS = {"codex": _invoke_codex}  # 확장점: 실행기 추가 = 함수 1개 + 엔트리 1개


# ---------------------------------------------------------------- helpers

def _raw_path(report: Path) -> Path:
    return report.with_name(report.stem + "-raw.txt")


def _load_prompt(spec_path: Path, role: str) -> str:
    preamble_path = PREAMBLE_DIR / f"{role}.md"
    if not preamble_path.is_file():
        raise FileNotFoundError(f"preamble missing: {preamble_path}")
    preamble = preamble_path.read_text(encoding="utf-8")
    spec = spec_path.read_text(encoding="utf-8")
    return preamble.rstrip() + "\n\n" + spec.strip() + "\n"


def _extract_receipt(raw: str):
    """마지막 ## RECEIPT 마커 이후를 리시트로 추출. 없으면 None."""
    idx = raw.rfind(RECEIPT_MARKER)
    if idx < 0:
        return None
    body = raw[idx + len(RECEIPT_MARKER):].strip("\n")
    lines = [ln.rstrip() for ln in body.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    truncated = False
    if len(lines) > RECEIPT_MAX_LINES:
        lines = lines[:RECEIPT_MAX_LINES]
        truncated = True
    receipt = "\n".join(lines).strip()
    if not receipt:
        return None
    if truncated:
        receipt += f"\n[ext] (receipt truncated to {RECEIPT_MAX_LINES} lines)"
    return receipt


def _validate_fields(receipt: str, role: str):
    missing = [f for f in REQUIRED_FIELDS[role]
               if f"{f}:" not in receipt]
    return missing


def _detect_quota_signal(text: str):
    """쿼터/크레딧 계열 시그널 탐지. 매칭 문자열 or None (원인 표기용)."""
    lowered = text.lower()
    for sig in QUOTA_SIGNALS:
        if sig in lowered:
            return sig
    return None


def _git_porcelain(repo: str):
    # core.quotepath=false: 비ASCII(한글) 경로가 8진 이스케이프로 인용되면
    # TARGET FILES 대조가 항상 어긋나 거짓 위반(exit 4)을 만든다.
    # -uall: 새 디렉터리 전체가 untracked 면 porcelain 기본값은 파일이 아니라
    # 디렉터리("doc/")로 접어 보고한다 — TARGET FILES("doc/out.md")와 절대
    # 매칭되지 않아, 새 디렉터리에 산출물을 만드는 정상 미션이 전부 거짓
    # 위반(exit 4)이 된다.
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain",
         "-uall"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=repo,
    )
    if proc.returncode != 0:
        return None  # git repo 아님 → 대조 생략 (JSON 에 명시)
    entries = set()
    for line in proc.stdout.splitlines():
        if len(line) > 3:
            path = line[3:].strip().strip('"')
            if " -> " in path:  # rename: 신경로 채택
                path = path.split(" -> ", 1)[1].strip().strip('"')
            entries.add(path)
    return entries


def _norm(path: str, repo: Path) -> str:
    p = Path(path.strip().strip('"'))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(repo.resolve())
        except ValueError:
            return str(p.resolve()).replace("\\", "/").casefold()
    return str(p).replace("\\", "/").casefold()


# 표준 위임 템플릿의 필드 라벨 — TARGET FILES 블록의 종결자.
# 명시 목록 방식인 이유: `^[A-Z][A-Z ]*:` 류 정규식은 Windows 드라이브
# 경로("E:\...")를 필드로 오인하고, 단순 isupper+무공백 검사는
# "CHANGE SPEC:" 같은 멀티워드 라벨을 통과시켜 블록이 안 닫힌다.
_SPEC_FIELDS = ("TASK", "CONTEXT", "CHANGE SPEC", "CONSTRAINTS", "VERIFY",
                "AUTHORITY", "BUDGET", "TIMEOUT", "LEDGER", "REPORT",
                "RETURN")


def _is_field_label(stripped: str) -> bool:
    upper = stripped.upper()
    return any(upper.startswith(f + ":") for f in _SPEC_FIELDS)


def _parse_target_files(spec_text: str):
    """스펙의 TARGET FILES: 블록에서 경로 목록 추출."""
    targets = []
    in_block = False
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("TARGET FILES:"):
            in_block = True
            rest = stripped[len("TARGET FILES:"):].strip()
            if rest and rest.lower() != "none":
                targets.append(rest)
            continue
        if in_block:
            if _is_field_label(stripped):
                break
            if stripped.startswith(("-", "*")):
                targets.append(stripped.lstrip("-* ").strip())
            elif stripped:
                targets.append(stripped)
    return [t for t in targets if t]


def _parse_field_value(spec_text: str, field: str):
    """스펙에서 단일 라인 필드 값 추출 (예: LEDGER)."""
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(field.upper() + ":"):
            value = stripped[len(field) + 1:].strip()
            return value if value and value.lower() != "none" else None
    return None


def _spec_violations(spec_text: str, pre: set, post: set,
                     repo: Path, exempt: list):
    """실행 전후 porcelain 차집합 중 TARGET FILES 밖 경로 반환."""
    new_changes = post - pre
    targets = {_norm(t, repo) for t in _parse_target_files(spec_text)}
    exempt_norm = {_norm(str(e), repo) for e in exempt}
    violations = []
    for path in sorted(new_changes):
        n = _norm(path, repo)
        if n in targets or n in exempt_norm:
            continue
        if any(n.startswith(t.rstrip("/") + "/") for t in targets):
            continue  # 디렉터리 타겟 허용
        violations.append(path)
    return violations


def _override_spec_field(receipt: str, violations: list) -> str:
    lines = receipt.splitlines()
    note = f"exceeded (script-verified: {', '.join(violations)})"
    for i, ln in enumerate(lines):
        if ln.strip().upper().startswith("SPEC:"):
            indent = ln[:len(ln) - len(ln.lstrip())]
            lines[i] = f"{indent}SPEC: {note}"
            return "\n".join(lines)
    return receipt + f"\nSPEC: {note}"


# ---------------------------------------------------------------- job core

def _execute_job(job: dict, dry_run: bool) -> dict:
    """단일 job 실행. 결과 dict {status, exit, role, spec, report, raw, receipt}."""
    role = job["role"]
    agent = job.get("agent", "codex")
    spec_path = Path(job["spec"])
    report_path = Path(job["report"])
    raw_path = _raw_path(report_path)
    repo = Path(job.get("repo") or Path.cwd())

    result = {"status": "error", "exit": EXIT_ERR, "role": role,
              "agent": agent, "spec": str(spec_path),
              "report": str(report_path), "raw": str(raw_path),
              "receipt": None, "reason": None}

    # 역할 검증이 DEFAULTS 조회보다 먼저다 — 순서가 뒤집히면 미등록 역할이
    # KeyError 로 터져, wave 에서 job 하나가 나머지 결과까지 삼킨다.
    if role not in REQUIRED_FIELDS:
        result["status"] = f"unknown role: {role}"
        return result

    model = job.get("model", DEFAULT_MODEL)
    effort = job.get("effort", DEFAULTS[role]["effort"])
    timeout = int(job.get("timeout", DEFAULTS[role]["timeout"]))

    if agent not in INVOKERS:
        result["status"] = f"unknown agent: {agent}"
        result["exit"] = EXIT_NO_AGENT
        return result
    if not spec_path.is_file():
        result["status"] = f"spec not found: {spec_path}"
        return result

    try:
        prompt = _load_prompt(spec_path, role)
    except FileNotFoundError as exc:
        result["status"] = str(exc)
        return result

    if dry_run:
        with _print_lock:
            print(f"[ext] DRY-RUN job role={role} agent={agent} "
                  f"model={model} effort={effort} timeout={timeout}s")
            print(f"[ext]   spec={spec_path}")
            print(f"[ext]   report={report_path} raw={raw_path}")
            print(f"[ext]   prompt head: "
                  f"{prompt.splitlines()[0][:80] if prompt else '(empty)'}")
        result.update(status="dry-run", exit=EXIT_OK)
        return result

    pre_snapshot = _git_porcelain(str(repo)) if role in WRITE_ROLES else None

    try:
        out, err, rc = INVOKERS[agent](prompt, model, effort, timeout,
                                       str(repo))
    except FileNotFoundError:
        result.update(status="no-codex", exit=EXIT_NO_AGENT)
        return result
    except subprocess.TimeoutExpired as exc:
        partial = ""
        if exc.stdout:
            partial = exc.stdout if isinstance(exc.stdout, str) \
                else exc.stdout.decode("utf-8", "replace")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            partial + f"\n[ext] TIMEOUT after {timeout}s\n", encoding="utf-8")
        result.update(status="timeout", exit=EXIT_TIMEOUT)
        return result

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw = out
    if err:
        raw += "\n--- STDERR (raw only, excluded from receipt window) ---\n" \
               + err
    raw_path.write_text(raw + f"\n[ext] agent exit code: {rc}\n",
                        encoding="utf-8")

    # 리시트는 stdout 에서만 추출 — stderr 가 뒤에 붙으면 추출 창이 오염됨
    receipt = _extract_receipt(out)
    if receipt is None:
        if rc != 0:
            # CLI 는 돌았지만 비정상 종료 + 리시트 부재 = 에이전트 실행 실패
            # (쿼터 소진·인증 실패·크래시). 리시트 불량(3)으로 분류하면
            # 오케스트레이터가 죽은 크레딧 풀에 재시도 1회를 낭비한다.
            signal = _detect_quota_signal(out + "\n" + err)
            if signal:
                result["reason"] = f"quota-signal: {signal}"
            result.update(
                status=f"agent-error: exit {rc}"
                       + (f" ({signal})" if signal else ""),
                exit=EXIT_AGENT_ERROR)
            return result
        result.update(status="invalid: RECEIPT marker missing",
                      exit=EXIT_BAD_RECEIPT)
        return result
    missing = _validate_fields(receipt, role)
    if missing:
        result.update(
            status=f"invalid: fields missing {','.join(missing)}",
            exit=EXIT_BAD_RECEIPT, receipt=receipt)
        return result

    exit_code = EXIT_OK
    status = "ok"
    if role in WRITE_ROLES and pre_snapshot is not None:
        post_snapshot = _git_porcelain(str(repo))
        if post_snapshot is not None:
            spec_text = spec_path.read_text(encoding="utf-8")
            exempt = [report_path, raw_path, spec_path]
            ledger = _parse_field_value(spec_text, "LEDGER")
            if ledger:  # 스펙이 LEDGER 를 지시했다면 그 기록은 위반이 아님
                exempt.append(Path(ledger))
            violations = _spec_violations(
                spec_text, pre_snapshot, post_snapshot, repo,
                exempt=exempt)
            if violations:
                receipt = _override_spec_field(receipt, violations)
                status = f"violation: {', '.join(violations)}"
                exit_code = EXIT_SPEC_VIOLATION
    elif role in WRITE_ROLES and pre_snapshot is None:
        status = "ok (git unavailable — SPEC not script-verified)"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# ext {role} receipt ({agent})\n\nspec: {spec_path}\n"
        f"raw: {raw_path}\n\n{RECEIPT_MARKER}\n{receipt}\n",
        encoding="utf-8")

    result.update(status=status, exit=exit_code, receipt=receipt)
    return result


# ---------------------------------------------------------------- commands

def cmd_run(args) -> int:
    job = {"spec": args.spec, "report": args.report, "role": args.role,
           "agent": args.agent, "repo": args.repo}
    if args.model:
        job["model"] = args.model
    if args.effort:
        job["effort"] = args.effort
    if args.timeout:
        job["timeout"] = args.timeout
    res = _execute_job(job, args.dry_run)
    if res["receipt"]:
        print(res["receipt"])
    summary = {k: res[k] for k in
               ("status", "exit", "role", "agent", "spec", "report", "raw",
                "reason")}
    print(json.dumps(summary, ensure_ascii=False))
    return res["exit"]


def cmd_wave(args) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        _err(f"manifest not found: {manifest_path}", EXIT_ERR)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        jobs = manifest["jobs"]
        assert isinstance(jobs, list) and jobs
    except (json.JSONDecodeError, KeyError, AssertionError):
        _err("manifest must be JSON with non-empty 'jobs' list", EXIT_ERR)

    n = len(jobs)
    print(f"[ext] wave: launching {n} jobs concurrently "
          f"(max_workers={n}, no queueing)")
    # N개 동시 기동 보장: max_workers = job 수. 하네스 병렬성에 무의존.
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(_execute_job, job, args.dry_run)
                   for job in jobs]
        results = [f.result() for f in futures]  # 제출 순서 = 출력 순서

    for i, res in enumerate(results, 1):
        name = Path(res["spec"]).name
        print(f"\n=== JOB {i}: {name} (exit {res['exit']}, {res['status']}) ===")
        if res["receipt"]:
            print(res["receipt"])

    ok = all(r["exit"] == EXIT_OK for r in results)
    summary = {
        "status": "ok" if ok else "partial",
        "jobs": [{k: r[k] for k in
                  ("status", "exit", "role", "agent", "spec", "report", "raw",
                   "reason")}
                 for r in results],
    }
    print()
    print(json.dumps(summary, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_ERR


def main() -> int:
    parser = argparse.ArgumentParser(prog="ext_dispatch")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="단일 ext 위임")
    p_run.add_argument("--spec", required=True, help="스펙 파일 절대경로")
    p_run.add_argument("--report", required=True, help="리포트 절대경로")
    p_run.add_argument("--role", required=True, choices=sorted(REQUIRED_FIELDS))
    p_run.add_argument("--agent", default="codex", choices=sorted(INVOKERS))
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--effort", default=None)
    p_run.add_argument("--timeout", type=int, default=None)
    p_run.add_argument("--repo", default=None, help="실행 cwd (기본: 현재)")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_wave = sub.add_parser("wave", help="N개 병렬 위임 (동시 기동 보장)")
    p_wave.add_argument("--manifest", required=True,
                        help='JSON: {"jobs":[{spec,report,role,...}]}')
    p_wave.add_argument("--dry-run", action="store_true")
    p_wave.set_defaults(func=cmd_wave)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
