#!/usr/bin/env bash
# tools/quality/dependency-check.sh — env/버전 점검 + Python 레이어 검사기 호출
# 사용: dependency-check.sh --all
# exit: 0=pass, 1=레이어 위반, 2=env(도구 부재 또는 인자 오류)
#
# 정책:
#   - HOOKS_SKIP_TESTS=1 은 본 스크립트를 스킵하지 않는다 (test 단계에만 적용).
#   - 레이어 규칙 SSOT: tools/quality/dependency_check.py
#     (그 안에서 Docs/ARCHITECTURE.md §3.2 §4.4 §6.1 §7.1 박제).

set -euo pipefail
IFS=$'\n\t'

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

usage() {
    echo "usage: dependency-check.sh --all" >&2
    exit 2
}

env_fail() {
    {
        echo "FAIL: $1"
        echo "target: $2"
        echo "next: $3"
    } >&2
    exit 2
}

[[ "$#" -ne 1 || "$1" != "--all" ]] && usage

cd "$(git rev-parse --show-toplevel)"
START=$SECONDS
REQ_FILE="requirements-dev.txt"
TMP_FILES=()

cleanup() {
    if [[ ${#TMP_FILES[@]} -gt 0 ]]; then
        rm -f "${TMP_FILES[@]}"
    fi
}
trap cleanup EXIT

# ── env-dotnet ─────────────────────────────────────────────
if ! command -v dotnet >/dev/null 2>&1; then
    env_fail "env-dotnet" "dotnet (PATH 부재)" \
        "winget install Microsoft.DotNet.SDK.9 또는 https://dotnet.microsoft.com/download"
fi

# ── env-python ─────────────────────────────────────────────
PY_CMD=""
if command -v python >/dev/null 2>&1; then
    PY_CMD="python"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
else
    env_fail "env-python" "python/python3 (PATH 부재)" \
        "https://www.python.org/downloads/"
fi

# ── env-pip ────────────────────────────────────────────────
if ! "$PY_CMD" -m pip --version >/dev/null 2>&1; then
    env_fail "env-pip" "pip (python module 부재)" \
        "$PY_CMD -m ensurepip --upgrade 또는 Python 재설치"
fi

if [[ ! -f "$REQ_FILE" ]]; then
    env_fail "env-requirements" "$REQ_FILE (없음)" \
        "requirements-dev.txt 복구 후 재실행"
fi

# ── env-ruff ───────────────────────────────────────────────
if ! command -v ruff >/dev/null 2>&1 \
        && ! "$PY_CMD" -m ruff --version >/dev/null 2>&1; then
    env_fail "env-ruff" "ruff (PATH/module 부재)" \
        "pip install ruff 또는 winget install astral-sh.ruff"
fi

# ── env-pytest ─────────────────────────────────────────────
if ! "$PY_CMD" -c "import pytest" >/dev/null 2>&1; then
    env_fail "env-pytest" "pytest (미설치)" \
        "$PY_CMD -m pip install pytest"
fi

# ── python-version-pin ─────────────────────────────────────
echo "→ python requirements version pins" >&2
PIN_LOG="$(mktemp)"
TMP_FILES+=("$PIN_LOG")
if ! "$PY_CMD" - "$REQ_FILE" >"$PIN_LOG" 2>&1 <<'PY'
from __future__ import annotations

import importlib.metadata as metadata
import sys
from pathlib import Path

req_file = Path(sys.argv[1])
for raw in req_file.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].strip()
    if not line:
        continue
    if "==" not in line:
        print(f"unsupported requirement pin: {raw}")
        sys.exit(2)
    name, expected = [part.strip() for part in line.split("==", 1)]
    try:
        installed = metadata.version(name)
    except metadata.PackageNotFoundError:
        print(f"{name} missing (expected {name}=={expected})")
        sys.exit(1)
    if installed != expected:
        print(f"{name}=={installed} (expected {name}=={expected})")
        sys.exit(1)
PY
then
    FIRST="$(grep -m1 -E '\S' "$PIN_LOG" || true)"
    [[ -z "$FIRST" ]] && FIRST="requirements-dev.txt 버전 핀 불일치"
    env_fail "python-version-pin" "$FIRST" \
        "$PY_CMD -m pip install -r requirements-dev.txt"
fi

# ── python-pip-check ───────────────────────────────────────
echo "→ python -m pip check" >&2
PIP_LOG="$(mktemp)"
TMP_FILES+=("$PIP_LOG")
if ! "$PY_CMD" -m pip check >"$PIP_LOG" 2>&1; then
    FIRST="$(grep -m1 -E '\S' "$PIP_LOG" || true)"
    [[ -z "$FIRST" ]] && FIRST="pip check 출력 비어 있음"
    env_fail "python-pip-check" "$FIRST" \
        "$PY_CMD -m pip check 후 안내된 충돌 패키지 해소 (가상환경/사용자 사이트 권장)"
fi

# ── python-requirements-resolve ────────────────────────────
echo "→ python -m pip install --dry-run -r requirements-dev.txt" >&2
DRY_LOG="$(mktemp)"
TMP_FILES+=("$DRY_LOG")
if ! "$PY_CMD" -m pip install --dry-run --disable-pip-version-check \
        -r "$REQ_FILE" >"$DRY_LOG" 2>&1; then
    FIRST="$(grep -m1 -E '\S' "$DRY_LOG" || true)"
    [[ -z "$FIRST" ]] && FIRST="pip dry-run 출력 비어 있음"
    env_fail "python-requirements-resolve" "$FIRST" \
        "$PY_CMD -m pip install -r requirements-dev.txt"
fi

# ── 레이어 의존성 검사 (Python 위임) ────────────────────────
echo "→ python dependency_check" >&2
set +e
"$PY_CMD" tools/quality/dependency_check.py
PY_RC=$?
set -e

case "$PY_RC" in
    0) ;;  # 통과
    1) exit 1 ;;  # 레이어 위반 — Python 이 표준 3줄 출력. 그대로 종료.
    2) env_fail "csproj-parse" "tools/quality/dependency_check.py" \
           "csproj XML 구문 확인 또는 본 검사기 로그 참조" ;;
    *) env_fail "dependency_check.py" "exit code $PY_RC" \
           "tools/quality/dependency_check.py 실행 로그 확인" ;;
esac

ELAPSED=$((SECONDS - START))
echo "PASS: dependency-check (${ELAPSED}s, env + pins + layer)"
