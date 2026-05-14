#!/usr/bin/env bash
# tools/quality/test.sh — 전체 unit test (dotnet test + pytest)
# 사용: test.sh --all
# 환경: HOOKS_SKIP_TESTS=1 → 즉시 SKIP exit 0 (긴급 hotfix용 가시화 — secret/build는 스킵 불가)
# exit: 0=pass, 1=fail, 2=env

set -euo pipefail
IFS=$'\n\t'

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

usage() {
    echo "usage: test.sh --all" >&2
    exit 2
}

fail() {
    {
        echo "FAIL: $1"
        echo "target: $2"
        echo "next: $3"
    } >&2
    exit 1
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        {
            echo "FAIL: env"
            echo "target: $1 (PATH 부재)"
            echo "next: $2"
        } >&2
        exit 2
    fi
}

[[ "$#" -ne 1 || "$1" != "--all" ]] && usage

if [[ "${HOOKS_SKIP_TESTS:-}" == "1" ]]; then
    echo "WARN: tests skipped via HOOKS_SKIP_TESTS" >&2
    echo "PASS: test (0s, skipped)"
    exit 0
fi

cd "$(git rev-parse --show-toplevel)"
START=$SECONDS

# ── C# test ────────────────────────────────────────────────
require_cmd dotnet "winget install Microsoft.DotNet.SDK.9 또는 https://dotnet.microsoft.com/download"

SLN="Src/OrderManagingSystem.sln"
echo "→ dotnet test $SLN (--no-build, Unit only)" >&2
TEST_LOG="$(mktemp)"
trap 'rm -f "$TEST_LOG"' EXIT
# Integration 키워드가 없는 현재 레포 상태에선 필터가 무해(전체 실행과 동일)
if ! dotnet test "$SLN" -c Debug --no-build --nologo --verbosity minimal \
        --filter "FullyQualifiedName!~Integration" >"$TEST_LOG" 2>&1; then
    FIRST_FAIL="$(grep -E 'Failed [^[:space:]]+|FAIL:' "$TEST_LOG" | head -1 || true)"
    [[ -z "$FIRST_FAIL" ]] && FIRST_FAIL="$(tail -5 "$TEST_LOG" | head -1)"
    cat "$TEST_LOG" >&2
    fail "dotnet-test" "${FIRST_FAIL:-$SLN}" "dotnet test $SLN -c Debug"
fi

# ── Python pytest ──────────────────────────────────────────
PY_CMD=""
if command -v python >/dev/null 2>&1; then PY_CMD="python"
elif command -v python3 >/dev/null 2>&1; then PY_CMD="python3"
else
    {
        echo "FAIL: env"
        echo "target: python (PATH 부재)"
        echo "next: https://www.python.org/downloads/"
    } >&2
    exit 2
fi

if ! "$PY_CMD" -c "import pytest" >/dev/null 2>&1; then
    {
        echo "FAIL: env"
        echo "target: pytest (미설치)"
        echo "next: $PY_CMD -m pip install pytest"
    } >&2
    exit 2
fi

PY_TESTS=()
while IFS= read -r -d '' f; do
    PY_TESTS+=("$f")
done < <(find scripts -maxdepth 1 -name 'test_*.py' -print0 2>/dev/null)

if [[ ${#PY_TESTS[@]} -gt 0 ]]; then
    echo "→ pytest (${#PY_TESTS[@]} files)" >&2
    PYT_LOG="$(mktemp)"
    if ! "$PY_CMD" -m pytest "${PY_TESTS[@]}" -q --no-header >"$PYT_LOG" 2>&1; then
        FIRST_FAIL="$(grep -E '^FAILED |^E ' "$PYT_LOG" | head -1 || true)"
        [[ -z "$FIRST_FAIL" ]] && FIRST_FAIL="$(tail -3 "$PYT_LOG" | head -1)"
        cat "$PYT_LOG" >&2
        rm -f "$PYT_LOG"
        fail "pytest" "${FIRST_FAIL:-${PY_TESTS[0]}}" "$PY_CMD -m pytest ${PY_TESTS[0]} -vv"
    fi
    rm -f "$PYT_LOG"
fi

ELAPSED=$((SECONDS - START))
echo "PASS: test (${ELAPSED}s, sln + ${#PY_TESTS[@]} py)"
