#!/usr/bin/env bash
# tools/quality/build.sh — 전체 build (dotnet build + python py_compile)
# 사용: build.sh --all
# exit: 0=pass, 1=fail, 2=env

set -euo pipefail
IFS=$'\n\t'

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

usage() {
    echo "usage: build.sh --all" >&2
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

cd "$(git rev-parse --show-toplevel)"
START=$SECONDS

# ── C# build ───────────────────────────────────────────────
require_cmd dotnet "winget install Microsoft.DotNet.SDK.9 또는 https://dotnet.microsoft.com/download"

SLN="Src/OrderManagingSystem.sln"
if [[ ! -f "$SLN" ]]; then
    fail "build-cs" "$SLN (없음)" "솔루션 파일 경로 확인"
fi

echo "→ dotnet build $SLN" >&2
BUILD_LOG="$(mktemp)"
trap 'rm -f "$BUILD_LOG"' EXIT
if ! dotnet build "$SLN" -c Debug --nologo --verbosity minimal >"$BUILD_LOG" 2>&1; then
    # 첫 에러 줄 추출
    FIRST_ERR="$(grep -E 'error [A-Z]+[0-9]+' "$BUILD_LOG" | head -1 || true)"
    [[ -z "$FIRST_ERR" ]] && FIRST_ERR="$(tail -3 "$BUILD_LOG" | head -1)"
    cat "$BUILD_LOG" >&2
    fail "dotnet-build" "${FIRST_ERR:-$SLN}" "dotnet build $SLN"
fi

# ── Python syntax check ─────────────────────────────────────
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

PY_FILES=()
while IFS= read -r -d '' f; do
    PY_FILES+=("$f")
done < <(find scripts -maxdepth 1 -name 'forge_*.py' -print0 2>/dev/null)

if [[ ${#PY_FILES[@]} -gt 0 ]]; then
    echo "→ python -m py_compile (${#PY_FILES[@]} forge_*.py)" >&2
    if ! "$PY_CMD" -m py_compile "${PY_FILES[@]}" 2>&1; then
        fail "py-compile" "${PY_FILES[0]}" "$PY_CMD -m py_compile ${PY_FILES[0]}"
    fi
fi

ELAPSED=$((SECONDS - START))
echo "PASS: build (${ELAPSED}s, sln + ${#PY_FILES[@]} py)"
