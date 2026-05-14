#!/usr/bin/env bash
# tools/quality/lint.sh — staged/all 모드 lint (dotnet format + ruff)
# 사용: lint.sh --all | --staged | --staged --fix
# exit: 0=pass, 1=fail, 2=env

set -euo pipefail
IFS=$'\n\t'

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

usage() {
    cat <<'EOF' >&2
usage: lint.sh --all
       lint.sh --staged [--fix]
EOF
    exit 2
}

fail() {
    local check="$1" target="$2" next="$3"
    {
        echo "FAIL: $check"
        echo "target: $target"
        echo "next: $next"
    } >&2
    exit 1
}

require_cmd() {
    local name="$1" install="$2"
    if ! command -v "$name" >/dev/null 2>&1; then
        {
            echo "FAIL: env"
            echo "target: $name (PATH 부재)"
            echo "next: $install"
        } >&2
        exit 2
    fi
}

resolve_ruff() {
    if command -v ruff >/dev/null 2>&1; then
        RUFF_CMD=(ruff)
        return
    fi

    local py_cmd=""
    if command -v python >/dev/null 2>&1; then
        py_cmd="python"
    elif command -v python3 >/dev/null 2>&1; then
        py_cmd="python3"
    fi

    if [[ -n "$py_cmd" ]] && "$py_cmd" -m ruff --version >/dev/null 2>&1; then
        RUFF_CMD=("$py_cmd" -m ruff)
        return
    fi

    {
        echo "FAIL: env"
        echo "target: ruff (PATH/module 부재)"
        echo "next: pip install ruff 또는 winget install astral-sh.ruff"
    } >&2
    exit 2
}

repo_root() { git rev-parse --show-toplevel; }

# ── 인자 파싱 ──────────────────────────────────────────────
MODE=""
FIX=0
for arg in "$@"; do
    case "$arg" in
        --all) MODE="all" ;;
        --staged) MODE="staged" ;;
        --fix) FIX=1 ;;
        -h|--help) usage ;;
        *) echo "unknown arg: $arg" >&2; usage ;;
    esac
done
[[ -z "$MODE" ]] && usage
[[ "$FIX" == "1" && "$MODE" != "staged" ]] && { echo "--fix는 --staged와만 사용" >&2; exit 2; }

ROOT="$(repo_root)"
cd "$ROOT"

START=$SECONDS

# ── 대상 수집 ──────────────────────────────────────────────
CS_FILES=()
PY_FILES=()
RUFF_CMD=()
TARGET_COUNT=0

if [[ "$MODE" == "staged" ]]; then
    # NUL 구분으로 한글/공백 경로 안전
    while IFS= read -r -d '' f; do
        [[ -z "$f" ]] && continue
        # tools/ 자체 변경은 lint 자기참조 방지 (ruff.toml extend-exclude과 함께 이중 안전망)
        case "$f" in
            tools/*) continue ;;
        esac
        case "$f" in
            *.cs) CS_FILES+=("$f"); TARGET_COUNT=$((TARGET_COUNT+1)) ;;
            *.py) PY_FILES+=("$f"); TARGET_COUNT=$((TARGET_COUNT+1)) ;;
        esac
    done < <(git diff -z --name-only --cached --diff-filter=ACMR)
fi

# ── C# 포맷/lint ────────────────────────────────────────────
if [[ "$MODE" == "all" ]] || [[ ${#CS_FILES[@]} -gt 0 ]]; then
    require_cmd dotnet "winget install Microsoft.DotNet.SDK.9 또는 https://dotnet.microsoft.com/download"

    SLN="Src/OrderManagingSystem.sln"
    if [[ ! -f "$SLN" ]]; then
        fail "lint-cs" "$SLN (없음)" "솔루션 파일 경로 확인"
    fi

    if [[ "$FIX" == "1" && ${#CS_FILES[@]} -gt 0 ]]; then
        # 자동 수정: --include 좁힘
        INCLUDE_CSV="$(IFS=,; echo "${CS_FILES[*]}")"
        echo "→ dotnet format (fix, ${#CS_FILES[@]} files)" >&2
        if ! dotnet format "$SLN" --include "$INCLUDE_CSV" --verbosity quiet; then
            fail "dotnet-format-fix" "${CS_FILES[0]}" "dotnet format $SLN --include $INCLUDE_CSV"
        fi
    elif [[ "$MODE" == "all" ]]; then
        echo "→ dotnet format --verify-no-changes (all)" >&2
        if ! dotnet format "$SLN" --verify-no-changes --verbosity quiet; then
            fail "dotnet-format" "$SLN" "dotnet format $SLN"
        fi
    else
        # staged & not fix
        INCLUDE_CSV="$(IFS=,; echo "${CS_FILES[*]}")"
        echo "→ dotnet format --verify-no-changes (staged ${#CS_FILES[@]})" >&2
        if ! dotnet format "$SLN" --include "$INCLUDE_CSV" --verify-no-changes --verbosity quiet; then
            fail "dotnet-format" "${CS_FILES[0]}" "dotnet format $SLN --include $INCLUDE_CSV"
        fi
    fi
fi

# ── Python 포맷/lint ────────────────────────────────────────
if [[ "$MODE" == "all" ]] || [[ ${#PY_FILES[@]} -gt 0 ]]; then
    resolve_ruff

    if [[ "$MODE" == "all" ]]; then
        TARGETS=(scripts)
    else
        TARGETS=("${PY_FILES[@]}")
    fi

    if [[ "$FIX" == "1" ]]; then
        # scripts/는 보호 디렉토리 — --fix 절대 적용 X
        FIX_TARGETS=()
        for f in "${PY_FILES[@]}"; do
            case "$f" in
                scripts/*) echo "WARN: skip --fix on protected $f" >&2 ;;
                *) FIX_TARGETS+=("$f") ;;
            esac
        done
        if [[ ${#FIX_TARGETS[@]} -gt 0 ]]; then
            echo "→ ruff format/check --fix (${#FIX_TARGETS[@]} files)" >&2
            if ! "${RUFF_CMD[@]}" format "${FIX_TARGETS[@]}" >&2; then
                fail "ruff-format-fix" "${FIX_TARGETS[0]}" "ruff format ${FIX_TARGETS[0]}"
            fi
            if ! "${RUFF_CMD[@]}" check --fix "${FIX_TARGETS[@]}" >&2; then
                fail "ruff-lint-fix" "${FIX_TARGETS[0]}" "ruff check --fix ${FIX_TARGETS[0]} 또는 수동 수정"
            fi
        fi
    else
        echo "→ ruff format --check (${#TARGETS[@]} targets)" >&2
        if ! "${RUFF_CMD[@]}" format --check "${TARGETS[@]}"; then
            fail "ruff-format" "${TARGETS[0]}" "ruff format ${TARGETS[0]}"
        fi
        echo "→ ruff check (${#TARGETS[@]} targets)" >&2
        if ! "${RUFF_CMD[@]}" check "${TARGETS[@]}"; then
            fail "ruff-lint" "${TARGETS[0]}" "ruff check --fix ${TARGETS[0]} 또는 수동 수정"
        fi
    fi
fi

ELAPSED=$((SECONDS - START))
if [[ "$MODE" == "all" ]]; then
    echo "PASS: lint (${ELAPSED}s, all targets)"
elif [[ $TARGET_COUNT -eq 0 ]]; then
    echo "PASS: lint (${ELAPSED}s, no eligible staged files)"
else
    echo "PASS: lint (${ELAPSED}s, ${TARGET_COUNT} targets)"
fi
