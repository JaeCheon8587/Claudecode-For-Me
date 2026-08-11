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
    run   --role scout|explorer|coder --report <ABS>
          (--spec <ABS> | --mission "<한 줄>" [--context "<시작점>"])  단일 위임
    wave  --manifest <ABS json> [--dry-run]                        N개 병렬 보장

wave 는 manifest 의 모든 job 을 ThreadPoolExecutor(max_workers=N) 로
동시 기동한다 — 큐잉 없음. N개 병렬 실행은 코드가 보장한다.

호출측 비용 설계 (오케스트레이터의 context 가 이 시스템에서 제일 비싸다):
  - 인라인 미션: --mission 을 주면 스펙 파일을 스크립트가 합성해
    <report>-spec.md 로 남긴다. 호출측은 Write 없이 Bash 1콜로 끝난다.
    쓰기 역할(coder)은 제외 — TARGET FILES 고정이 계약이라 한 줄로 못 쓴다.
  - stdout 화물 분리: 읽기 전용 역할의 리시트는 제어 필드만 stdout 에
    싣고, path:line 목록(화물)은 REPORT 파일에만 남긴다. 상세가 필요하면
    호출측이 REPORT 를 명시적으로 읽는다. --full-receipt 로 해제.

Exit codes:
    0  OK (BLOCKED 리시트 포함 — BLOCKED 는 유효한 결과)
    1  일반 오류 / wave 에서 1개 이상 job 실패
    2  외부 CLI 없음 (codex 미설치)
    3  리시트 추출·구조 검증 실패
    4  SPEC 위반 (TARGET FILES 밖 변경 — script-verified)
    5  타임아웃
    6  에이전트 실행 실패 (rc != 0 + 리시트 마커 없음 — 쿼터/크레딧 소진 포함)
    7  fact 미검증 (읽기 전용 역할의 path:line 주장이 파일과 불일치 — script-verified)
"""

# Encoding bootstrap — FIRST executable code (Windows cp949 콘솔 회피)
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import re
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
EXIT_FACTS_UNVERIFIED = 7

RECEIPT_MARKER = "## RECEIPT"
RECEIPT_MAX_LINES = 30

REQUIRED_FIELDS = {
    "scout": ("FOUND", "SEARCHED", "CONFIDENCE"),
    # explorer 는 native explorer 의 "노동" 필드만 물려받은 축소 계약이다.
    # 판단 필드(ANSWER/MAP/RISKS)는 요구하지 않는다 — 프리앰블이 금지한다.
    "explorer": ("KEY FACTS", "COVERAGE", "CONFIDENCE"),
    "coder": ("STATUS", "CHANGED", "SPEC", "VERIFY"),
}

# 합성 스펙의 RETURN 에 쓰는 계약 전체 필드 — 프리앰블 리시트 스키마와 1:1.
# REQUIRED_FIELDS 를 재사용하면 안 된다: 그쪽은 스크립트가 강제하는 부분집합
# 이라 scout 의 RELATED/UNCERTAIN 이 빠져 계약이 조용히 축소된다.
SPEC_RETURN = {
    "scout": ("FOUND", "RELATED", "SEARCHED", "UNCERTAIN", "CONFIDENCE"),
    "explorer": ("STATUS", "COVERAGE", "CONFIDENCE", "UNCERTAIN",
                 "FACTS FILE", "KEY FACTS"),
    "coder": ("STATUS", "CHANGED", "SPEC", "VERIFY", "RISKS"),
}

# 인라인 미션(--mission)이 허용되는 역할. coder 는 제외한다 — ext-coder 적격은
# TARGET FILES 절대경로·축자 시그니처·VERIFY 단일 명령을 스펙에 적을 수 있을 때
# 성립하므로(JUDGMENT-FREE 게이트) 한 줄 미션으로 표현될 수 없고, TARGET FILES
# 없는 합성 스펙은 porcelain 대조에서 전량 거짓 위반(exit 4)이 된다.
INLINE_MISSION_ROLES = frozenset({"scout", "explorer"})

# stdout 요약에서 원문 그대로 싣는 제어 필드 / 건수로 접는 화물 필드.
# coder 는 항목이 없다 = 항상 리시트 전문 출력 (VERIFY·SPEC 판정이 호출측 몫).
# VERIFIED 는 스크립트가 주입하는 제어 필드다 — 요약 모드에서 접히면 검증
# 사실이 stdout 에서 사라지므로 반드시 제어 쪽에 있어야 한다.
CONTROL_FIELDS = {
    "scout": ("SEARCHED", "UNCERTAIN", "CONFIDENCE", "VERIFIED"),
    "explorer": ("STATUS", "COVERAGE", "CONFIDENCE", "UNCERTAIN",
                 "FACTS FILE", "VERIFIED"),
}
CARGO_FIELDS = {
    "scout": ("FOUND", "RELATED"),
    "explorer": ("KEY FACTS",),
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

# path:line 주장을 파일과 대조하는 역할 — WRITE_ROLES 의 읽기 전용 대응물.
# coder 는 제외한다: 그쪽 검증은 porcelain 스코프 대조(exit 4)가 담당하고,
# CHANGED 는 위치 주장이 아니라 변경 보고라 같은 방식으로 반증할 수 없다.
VERIFY_ROLES = frozenset({"scout", "explorer"})

# 인용이 실재하는데 라인 번호만 어긋난 경우를 찾는 탐색 창(±줄).
# 실측 근거: explorer facts 90건 중 7건이 offset -2~+3 의 드리프트였고
# 날조는 0건이었다. 지배적 실패 모드가 드리프트라 자동 교정이 성립한다.
DRIFT_WINDOW = 5

# 이보다 짧은 인용은 어느 줄에나 걸려 반증력이 없다 → unparsed 로 센다.
MIN_EVIDENCE_CHARS = 4

# fact 경로를 basename 으로 되찾을 때 훑지 않을 디렉터리.
_SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage",
              "__pycache__", ".venv", "venv", "bin", "obj"}

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


def _synth_spec_path(report: Path) -> Path:
    """--mission 으로 합성한 스펙이 남는 경로. _raw_path 와 같은 유도 방식."""
    return report.with_name(report.stem + "-spec.md")


def _synth_spec(role: str, mission: str, context, report: Path,
                timeout: int) -> str:
    """한 줄 미션 → 표준 위임 스펙 텍스트.

    CONSTRAINTS 는 합성하지 않는다 — 역할 프리앰블이 이미 규정한다
    (ext_preambles/scout.md 의 Rules 절). 중복 제거가 이 모드의 요점이다.
    """
    parts = [f"TASK: {mission.strip()}"]
    if context and context.strip():
        parts.append(f"CONTEXT: {context.strip()}")
    parts += [f"TIMEOUT: {timeout}",
              "LEDGER: none",
              f"REPORT: {report}",
              f"RETURN: {' / '.join(SPEC_RETURN[role])}"]
    return "\n\n".join(parts) + "\n"


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


# 화물 불릿에서 파일 수를 세기 위한 최소 파서. 라인번호 뒤에 태그·구분자가
# 오도록 앵커링한다 — `.+?:\d+` 만으로는 Windows 드라이브 경로("E:\...")의
# 콜론에서 잘못 끊긴다.
_CARGO_BULLET_RX = re.compile(
    r"^-\s+(?P<loc>.+?):(?P<line>\d+)\s*(?=\[|[—–-]|$)")
_TRUNC_MARK = "[ext] (receipt truncated"


def _fold_cargo(label: str, lines: list) -> str:
    """화물 필드(FOUND/RELATED/KEY FACTS)를 한 줄 건수로 접는다."""
    head = lines[0].strip()
    inline = head[len(label) + 1:].strip() if len(head) > len(label) + 1 else ""
    bullets = [ln for ln in lines[1:] if ln.strip().startswith("- ")]
    if not bullets:
        return f"{label}: {inline or '(none)'}"
    files = {m.group("loc").strip().replace("\\", "/").casefold()
             for m in (_CARGO_BULLET_RX.match(ln.strip()) for ln in bullets)
             if m}
    n = len(bullets)
    if inline:  # 8건 초과 집계 모드: 에이전트가 쓴 요약을 살리고 줄 수만 덧붙임
        return f"{label}: {inline} [{n} lines]"
    if files:
        unit = "file" if len(files) == 1 else "files"
        return f"{label}: {n} across {len(files)} {unit}"
    return f"{label}: {n}"


def _control_summary(role: str, receipt: str):
    """읽기 전용 역할의 리시트에서 제어 필드만 남긴 stdout 요약.

    화물(path:line 목록)은 건수로 접는다 — 그 상세는 REPORT 파일에 전문으로
    남아 있고, 필요할 때 호출측이 명시적으로 읽는 편이 싸다.

    형태를 못 알아보면 None 을 돌려 호출측이 리시트 전문으로 폴백한다.
    정보를 조용히 잃지 않는 것이 요약보다 우선한다.
    """
    control = CONTROL_FIELDS.get(role)
    cargo = CARGO_FIELDS.get(role)
    if not control or not cargo:
        return None

    known = {f.upper(): f for f in tuple(control) + tuple(cargo)}
    blocks = []  # [(label|None, [lines])]
    cur = None
    for ln in receipt.splitlines():
        stripped = ln.strip()
        label = next((orig for up, orig in known.items()
                      if stripped.upper().startswith(up + ":")), None)
        if label is not None:
            cur = (label, [ln])
            blocks.append(cur)
        elif stripped.startswith(_TRUNC_MARK):
            blocks.append((None, [ln]))  # 절단 표시는 항상 보존
            cur = None
        elif cur is not None:
            cur[1].append(ln)
        # 소유 필드가 없는 줄은 버린다 (제어도 화물도 아님)

    if not any(lbl in control for lbl, _ in blocks if lbl):
        return None  # 제어 필드를 하나도 못 찾음 = 미상 형태 → 전문 폴백

    out = []
    for label, lines in blocks:
        if label is None or label in control:
            out.extend(lines)
        else:
            out.append(_fold_cargo(label, lines))
    return "\n".join(out).strip() or None


# ------------------------------------------------------------ fact 검사기

# 검증용 파서. _CARGO_BULLET_RX 와 달리 evidence(rest)를 캡처하고, 교정을 위해
# 라인번호의 위치(span)를 원문 기준으로 잡을 수 있도록 raw 줄에 매칭한다.
# 태그는 선택 — scout 의 RELATED 줄에는 태그가 없다.
# 프리앰블은 `- <path>:<line> [tag] — "<evidence>"` 하나를 규정하지만 실제 출력은
# 실행마다 흔들린다(실측 스모크 3회). 계약을 지킨 형태만 파싱하면 커버리지가
# 조용히 무너지므로, 모호하지 않은 변형은 흡수한다:
#   · `:98-100` 라인 범위 — 없으면 하이픈이 구분자로 먹혀 뒤 숫자가 evidence 에 붙음
#   · `:476/478/481` 묶음 — 첫 번째를 대표로 삼는다
#   · `- :473 …` 경로 생략 — 앞 불릿의 경로를 상속한다(같은 목록 안에서 무모호)
_FACT_LINE_RX = re.compile(
    r"^\s*-\s+(?P<loc>.*?):(?P<line>\d+)(?:[-/,]\d+)*\s*(?:\[[a-z|]+\])?\s*"
    r"[—–-]\s*(?P<rest>.*)$")

# fact 를 주장하려 한 불릿("- <경로>:<번호> …")인데 계약 형식이 아닌 것을 세기
# 위한 느슨한 패턴. 집계 불릿(`- src/a.py (12 hits) …`)과 서술 불릿(`- Note: …`)
# 은 라인번호가 없어 여기 안 걸린다 — 그 둘은 형식 붕괴가 아니라 정상이다.
_LOOSE_FACT_RX = re.compile(r"^\s*-\s+\S*?:\d+\b")

# 인용이 소스의 줄바꿈을 넘어가는 경우가 있다 — 에이전트가 wrap 된 한 문장을
# 한 줄로 이어 인용한다. 시작 줄부터 이만큼까지 이어붙여 대조한다.
MAX_WRAP_SPAN = 3

_basename_cache = {}
_source_cache = {}


def _evidence_candidates(rest: str):
    """evidence 후보 목록 — 하나라도 매치하면 통과로 본다.

    한 줄에 인용이 여러 개인 경우가 있어(explorer KEY FACTS 의
    `"A" -> :300 "B"` 형태) "마지막 구분자까지" 규칙 하나로는 두 인용을
    이어붙여 실패한다. 최단·최장·무구분자 셋을 만들어 관대하게 판정한다 —
    날조는 어느 후보로도 매치되지 않으므로 관대함이 반증력을 깎지 않는다.

    구분자는 첫 글자로 정한다 — 실행마다 다르다(실측 4회: 큰따옴표 / 백틱 /
    작은따옴표). 첫 글자만 보므로 본문 안의 아포스트로피는 영향이 없다.
    """
    r = rest.strip()
    out = []
    if r and r[0] in "\"`'":
        delim = r[0]
        nxt = r.find(delim, 1)
        last = r.rfind(delim)
        if nxt > 0:
            out.append(r[1:nxt])
        if last > nxt:
            out.append(r[1:last])
    # 구분자가 아예 없으면 축자 인용이 아니라 서술이다("FOOTER_FIELDS injects
    # ... control field"). 서술은 반증할 수 없으므로 후보를 만들지 않고
    # unparsed 로 흘려보낸다 — 원문을 후보로 쓰면 거짓 실패가 된다(실측 스모크).
    seen = []
    for c in dict.fromkeys(out):
        n = _normalize_evidence(c)
        if n and n not in seen:
            seen.append(n)
    return seen


def _normalize_evidence(s: str) -> str:
    s = s.strip()
    while s.startswith("..."):
        s = s[3:]
    while s.endswith("..."):
        s = s[:-3]
    # 에이전트가 내부 따옴표를 이스케이프할 때도, 안 할 때도 있다(실측).
    return " ".join(s.replace('\\"', '"').split())


def _resolve_fact_path(loc: str, repo: Path):
    """fact 가 가리키는 파일을 찾는다. 반환: (path|None, "ok"|"absent"|"ambiguous").

    explorer facts 본문은 저장소 루트에서 해석되지 않는 맨 파일명을 쓴다
    (`ext_dispatch.py:283`, 실제 위치는 `scripts/ext_dispatch.py`) — 실측
    90건 전부. basename 으로 되찾되 **유일 매치일 때만** 채택한다.

    0건과 2건 이상을 구분하는 것이 중요하다: 0건은 그런 파일이 저장소에
    없다는 뜻이라 반증된 주장(failed)이고, 2건 이상은 어느 것인지 모른다는
    뜻이라 판정 불가(unparsed)다. 틀린 파일에 대조하면 거짓 실패가 된다.
    """
    p = Path(loc.strip().strip('"').strip("`"))
    cand = p if p.is_absolute() else repo / p
    try:
        if cand.is_file():
            return cand, "ok"
    except OSError:
        return None, "ambiguous"
    key = (str(repo), p.name)
    if key not in _basename_cache:
        hits = []
        try:
            for h in repo.rglob(p.name):
                if any(part in _SKIP_DIRS for part in h.parts):
                    continue
                if h.is_file():
                    hits.append(h)
                    if len(hits) > 1:
                        break
        except OSError:
            hits = [None, None]  # 훑지 못했으면 판정 불가 쪽으로
        _basename_cache[key] = (hits[0], "ok") if len(hits) == 1 else (
            None, "absent" if not hits else "ambiguous")
    return _basename_cache[key]


def _source_lines(path: Path):
    """파일 내용을 정규화해 캐시. facts 90건이 한 파일을 가리키므로 필수."""
    key = str(path)
    if key not in _source_cache:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _source_cache[key] = None
            return None
        lines = text.lstrip("﻿").splitlines()
        _source_cache[key] = tuple(" ".join(ln.split()) for ln in lines)
    return _source_cache[key]


def _matches_at(lines: tuple, k: int, cands: list) -> bool:
    """k 번째 줄에 인용이 있나. wrap 된 문장은 다음 줄까지 이어붙여 본다.

    이어붙이기는 인용이 이 줄에서 **시작**할 때만 허용한다. 무조건 이어붙이면
    실제로는 k+1 에 있는 인용이 k 에서도 통과해 드리프트 탐지가 죽는다.
    """
    if not 1 <= k <= len(lines):
        return False
    first = lines[k - 1]
    if any(c in first for c in cands):
        return True
    if not first:
        return False
    starters = [c for c in cands if c.startswith(first)]
    if not starters:
        return False
    joined = first
    for off in range(1, MAX_WRAP_SPAN):
        if k + off > len(lines):
            break
        joined = joined + " " + lines[k + off - 1]
        if any(c in joined for c in starters):
            return True
    return False


def _matches_near(lines: tuple, k: int, cands: list) -> bool:
    """마지막 관문 — 공백을 무시하고 k 주변 창에서 인용을 찾는다.

    에이전트는 물리적 줄이 아니라 **구문 단위**를 인용한다. wrap 을 넘어 한 줄로
    재구성하면서 여는 괄호가 앞줄에서 딸려오거나 들여쓰기 공백이 사라진다(실측
    스모크: `(None, "absent" ...)` 의 `(` 는 앞줄 끝에 있었다). 판정 대상은
    그 텍스트가 거기 실재하는가이지 에이전트의 렌더링 방식이 아니다.

    라인 번호 정밀도는 앞선 드리프트 탐색이 이미 책임진다 — 여기까지 온 건
    창 안 어느 한 줄로도 떨어지지 않는 인용뿐이라 교정할 대상이 없다.
    """
    lo = max(1, k - 1)
    hi = min(len(lines), k + MAX_WRAP_SPAN)
    blob = "".join(lines[lo - 1:hi]).replace(" ", "")
    return any(c.replace(" ", "") in blob for c in cands if c.strip())


def _classify_fact(loc: str, lineno: int, rest: str, repo: Path):
    """단일 fact 판정. 반환: (grade, detail, corrected_line|None)."""
    cands = [c for c in _evidence_candidates(rest)
             if len(c) >= MIN_EVIDENCE_CHARS]
    if not cands:
        return "unparsed", "no falsifiable verbatim quote", None
    path, how = _resolve_fact_path(loc, repo)
    if how == "absent":
        return "failed", f"{loc}:{lineno} — no such file in repo", None
    if path is None:
        return "unparsed", "path not uniquely resolvable in repo", None
    lines = _source_lines(path)
    if lines is None:
        return "unparsed", "file unreadable", None
    if _matches_at(lines, lineno, cands):
        return "verified", None, None
    # 드리프트 탐색 — 창 안에서 유일할 때만 교정한다.
    hits = [k for k in range(max(1, lineno - DRIFT_WINDOW),
                             min(len(lines), lineno + DRIFT_WINDOW) + 1)
            if k != lineno and _matches_at(lines, k, cands)]
    if len(hits) == 1:
        return "drifted", f"{loc}:{lineno} -> :{hits[0]}", hits[0]
    if len(hits) > 1:
        return "failed", (f"{loc}:{lineno} — evidence matches {len(hits)} lines "
                          f"within +-{DRIFT_WINDOW}, ambiguous"), None
    if _matches_near(lines, lineno, cands):
        return "verified", None, None
    if not 1 <= lineno <= len(lines):
        return "failed", (f"{loc}:{lineno} — file has {len(lines)} lines"), None
    actual = lines[lineno - 1]
    return "failed", (f"{loc}:{lineno} — that line is "
                      f"\"{actual[:60]}\""), None


def _verify_fact_text(text: str, repo: Path):
    """텍스트의 fact 불릿을 대조하고, 드리프트는 라인번호를 교정해 돌려준다.

    반환: (교정된 text, stats)
    """
    stats = {"verified": 0, "drifted": [], "failed": [], "unparsed": 0,
             "near": 0, "total": 0}
    out = []
    last_loc = None
    for raw in text.splitlines():
        if not raw.strip().startswith("- "):
            out.append(raw)
            continue
        m = _FACT_LINE_RX.match(raw)
        if not m:
            # `path:line` 모양을 갖췄는데 계약 형식이 아니면 near — 집계 불릿이나
            # 서술 불릿(둘 다 라인번호가 없다)과 구별해야 형식 붕괴를 짚을 수 있다.
            if _LOOSE_FACT_RX.match(raw):
                stats["near"] += 1
            stats["unparsed"] += 1
            stats["total"] += 1
            out.append(raw)
            continue
        stats["total"] += 1
        loc = m.group("loc").strip()
        if not loc:  # `- :473 …` — 앞 불릿의 경로를 상속
            loc = last_loc
        if loc:
            last_loc = loc
        else:
            stats["unparsed"] += 1
            out.append(raw)
            continue
        grade, detail, fixed = _classify_fact(
            loc, int(m.group("line")), m.group("rest"), repo)
        if grade == "verified":
            stats["verified"] += 1
            out.append(raw)
        elif grade == "drifted":
            stats["drifted"].append(detail)
            out.append(raw[:m.start("line")] + str(fixed)
                       + raw[m.end("line"):])
        elif grade == "failed":
            stats["failed"].append(detail)
            out.append(raw)
        else:
            stats["unparsed"] += 1
            out.append(raw)
    return "\n".join(out), stats


def _facts_file_path(receipt: str, report: Path):
    """explorer 의 FACTS FILE. 리시트 선언값 우선, 없으면 REPORT 에서 유도."""
    declared = _parse_field_value(receipt, "FACTS FILE")
    if declared:
        return Path(declared.strip().strip('"').strip("`"))
    return report.with_name(report.stem + "-facts.md")


def _verify_facts(receipt: str, role: str, repo: Path, report: Path):
    """리시트(+ explorer 의 facts 본문)를 대조·교정한다.

    반환: (교정된 receipt, result dict). facts 본문은 제자리에서 다시 쓴다 —
    하위 노드가 읽는 것이 그쪽이므로 교정이 반영돼야 의미가 있다.
    """
    receipt, r_stats = _verify_fact_text(receipt, repo)
    result = {"receipt": r_stats, "facts": None, "facts_file": None,
              "truncated": _TRUNC_MARK in receipt}
    if role == "explorer":
        fpath = _facts_file_path(receipt, report)
        result["facts_file"] = str(fpath)
        if fpath.is_file():
            original = fpath.read_text(encoding="utf-8", errors="replace")
            fixed, f_stats = _verify_fact_text(original, repo)
            result["facts"] = f_stats
            if f_stats["drifted"]:
                fpath.write_text(fixed, encoding="utf-8")
        else:
            result["facts"] = "missing"
    return receipt, result


def _failed_facts(result: dict):
    out = list(result["receipt"]["failed"])
    facts = result.get("facts")
    if isinstance(facts, dict):
        out += facts["failed"]
    return out


def _format_collapse(stats) -> bool:
    """fact 를 주장한 불릿이 있는데 단 하나도 대조되지 않음 = 계약 불일치.

    집계 모드(`FOUND: 12 across 3 files`)나 서술 불릿만 있는 경우와 구별해야
    한다. 그쪽은 검사할 대상이 없는 정상이고, 이쪽은 대상이 있는데 형식이
    어긋나 전량 건너뛴 상태다 — 무증상으로 두면 미검증 실행이 건강한 실행과
    구별되지 않는다(실측: explorer 1회차 59건 전량, exit 0).
    """
    return (isinstance(stats, dict) and stats.get("near", 0) > 0
            and stats["total"] - stats["unparsed"] == 0)


def _unverifiable(result: dict):
    """검사가 성립하지 않은 대상의 설명. 없으면 None."""
    hit = []
    if _format_collapse(result["receipt"]):
        hit.append(f"receipt {result['receipt']['near']} bullets")
    if _format_collapse(result.get("facts")):
        hit.append(f"facts file {result['facts']['near']} bullets")
    return ", ".join(hit) or None


def _append_verified_field(receipt: str, result: dict) -> str:
    """리시트 말미에 VERIFIED 요약을 붙인다.

    coder 의 _override_spec_field 와 같은 계열 — 스크립트가 검증한 사실을
    에이전트 자기신고 옆에 나란히 둔다.
    """
    r = result["receipt"]
    ok = r["verified"] + len(r["drifted"])
    judgeable = r["total"] - r["unparsed"]
    scope = " of visible facts (receipt truncated)" if result["truncated"] else ""
    if _format_collapse(r):
        head = (f"VERIFIED: NOTHING CHECKED — {r['near']} receipt fact bullets "
                f"do not match the contract format, 0 checked")
    elif judgeable == 0:
        head = (f"VERIFIED: no checkable path:line facts "
                f"({r['unparsed']} unparsed) — script-checked")
    else:
        head = (f"VERIFIED: {ok}/{judgeable} facts{scope} "
                f"({len(r['drifted'])} drifted, {r['unparsed']} unparsed)"
                f" — script-checked")
    lines = [head]

    facts = result.get("facts")
    if facts == "missing":
        lines.append(f"  ! FACTS FILE not found: {result['facts_file']}")
    elif _format_collapse(facts):
        lines.append(f"  ! facts file: NOTHING CHECKED — {facts['near']} fact "
                     f"bullets do not match the contract format, 0 checked")
    elif isinstance(facts, dict):
        f_ok = facts["verified"] + len(facts["drifted"])
        lines.append(
            f"  facts file: {f_ok}/{facts['total'] - facts['unparsed']} "
            f"({len(facts['drifted'])} drifted, {facts['unparsed']} unparsed)")

    drifted = list(r["drifted"])
    if isinstance(facts, dict):
        drifted += facts["drifted"]
    for d in drifted[:3]:
        lines.append(f"  ~ {d}")
    if len(drifted) > 3:
        lines.append(f"  ~ (+{len(drifted) - 3} more line numbers corrected)")

    for f in _failed_facts(result)[:5]:
        lines.append(f"  ! {f}")

    return receipt + "\n" + "\n".join(lines)


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
    report_path = Path(job["report"])
    raw_path = _raw_path(report_path)
    repo = Path(job.get("repo") or Path.cwd())
    mission = job.get("mission")
    # 인라인 미션이면 스펙을 스크립트가 합성해 <report>-spec.md 에 남긴다.
    if mission:
        spec_path = _synth_spec_path(report_path)
    elif job.get("spec"):
        spec_path = Path(job["spec"])
    else:
        spec_path = None

    result = {"status": "error", "exit": EXIT_ERR, "role": role,
              "agent": agent,
              "spec": str(spec_path) if spec_path else None,
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

    if mission and job.get("spec"):
        result["status"] = "spec and mission are mutually exclusive"
        return result
    if spec_path is None:
        result["status"] = "job needs either spec or mission"
        return result
    if mission:
        if role not in INLINE_MISSION_ROLES:
            result["status"] = (f"inline mission not allowed for role: {role}"
                                " (write roles need a spec file with "
                                "TARGET FILES)")
            return result
        context = job.get("context")
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(
            _synth_spec(role, mission, context, report_path, timeout),
            encoding="utf-8")
        if role == "explorer" and not (context or "").strip():
            # 프리앰블은 구체적 시작점이 없으면 BLOCKED 로 반송한다. "구체적"은
            # 기계 판정이 불가하므로 경고만 낸다 (stderr — 리시트 추출 창 밖).
            with _print_lock:
                print("[ext] WARNING: explorer mission without context — the "
                      "preamble requires concrete starting points and will "
                      "return STATUS: BLOCKED without them.", file=sys.stderr)
    elif not spec_path.is_file():
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

    # 읽기 전용 역할의 대응물: 스코프 대신 사실을 대조한다. 드리프트는 여기서
    # 교정되므로 하위 스펙이 맞는 라인 번호를 받는다.
    if role in VERIFY_ROLES:
        receipt, verdict = _verify_facts(receipt, role, repo, report_path)
        receipt = _append_verified_field(receipt, verdict)
        failed = _failed_facts(verdict)
        unverifiable = _unverifiable(verdict)
        if failed:
            status = (f"facts-unverified: {len(failed)} of "
                      f"{verdict['receipt']['total']}")
            if unverifiable:
                status += f" (+unverifiable: {unverifiable})"
            exit_code = EXIT_FACTS_UNVERIFIED
        elif unverifiable:
            # 치명은 아니다 — 사실이 틀렸다는 증거가 아니라 대조가 성립하지
            # 않았다는 뜻이고, 수확물 자체는 여전히 쓸 수 있다. 다만 검증된
            # 것으로 취급하면 안 되므로 status 로 반드시 드러낸다.
            status = f"facts-unverifiable: {unverifiable} unparseable"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# ext {role} receipt ({agent})\n\nspec: {spec_path}\n"
        f"raw: {raw_path}\n\n{RECEIPT_MARKER}\n{receipt}\n",
        encoding="utf-8")

    result.update(status=status, exit=exit_code, receipt=receipt)
    return result


# ---------------------------------------------------------------- commands

def _print_receipt(res: dict, full: bool) -> None:
    """리시트 출력. 읽기 전용 역할의 성공 결과만 제어 요약으로 접는다.

    실패(exit != 0)는 항상 전문 — 진단에는 화물까지 필요하고, 실패는 드물다.
    """
    receipt = res["receipt"]
    if not receipt:
        return
    summary = None
    if not full and res["exit"] == EXIT_OK:
        summary = _control_summary(res["role"], receipt)
    if summary is None:
        print(receipt)
        return
    print(f"[ext] {res['role']} {res['status']}")
    print(summary)
    print(f"data: {res['report']}")


def cmd_run(args) -> int:
    if bool(args.spec) == bool(args.mission):
        _err("exactly one of --spec / --mission is required", EXIT_ERR)
    if args.context and not args.mission:
        _err("--context is only valid with --mission", EXIT_ERR)
    job = {"spec": args.spec, "report": args.report, "role": args.role,
           "agent": args.agent, "repo": args.repo}
    if args.mission:
        job["mission"] = args.mission
    if args.context:
        job["context"] = args.context
    if args.model:
        job["model"] = args.model
    if args.effort:
        job["effort"] = args.effort
    if args.timeout:
        job["timeout"] = args.timeout
    res = _execute_job(job, args.dry_run)
    _print_receipt(res, args.full_receipt)
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
        name = Path(res["spec"]).name if res["spec"] else f"job{i}"
        print(f"\n=== JOB {i}: {name} (exit {res['exit']}, {res['status']}) ===")
        _print_receipt(res, args.full_receipt)

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
    p_run.add_argument("--spec", default=None,
                       help="스펙 파일 절대경로 (--mission 과 배타)")
    p_run.add_argument("--mission", default=None,
                       help="인라인 미션 한 줄 — 스펙을 스크립트가 합성해 "
                            "<report>-spec.md 에 남긴다 (--spec 과 배타). "
                            "읽기 전용 역할 전용")
    p_run.add_argument("--context", default=None,
                       help="인라인 미션의 CONTEXT (시작점·제약). "
                            "--mission 과 함께만 유효")
    p_run.add_argument("--report", required=True, help="리포트 절대경로")
    p_run.add_argument("--role", required=True, choices=sorted(REQUIRED_FIELDS))
    p_run.add_argument("--agent", default="codex", choices=sorted(INVOKERS))
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--effort", default=None)
    p_run.add_argument("--timeout", type=int, default=None)
    p_run.add_argument("--repo", default=None, help="실행 cwd (기본: 현재)")
    p_run.add_argument("--full-receipt", action="store_true",
                       help="읽기 전용 역할도 리시트 전문을 stdout 에 출력")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_wave = sub.add_parser("wave", help="N개 병렬 위임 (동시 기동 보장)")
    p_wave.add_argument("--manifest", required=True,
                        help='JSON: {"jobs":[{report,role,spec|mission,...}]}')
    p_wave.add_argument("--full-receipt", action="store_true",
                        help="읽기 전용 역할도 리시트 전문을 stdout 에 출력")
    p_wave.add_argument("--dry-run", action="store_true")
    p_wave.set_defaults(func=cmd_wave)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
