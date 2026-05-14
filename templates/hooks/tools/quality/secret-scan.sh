#!/usr/bin/env bash
# tools/quality/secret-scan.sh — gitleaks 래퍼
# 사용: secret-scan.sh --staged | --all
# exit: 0=pass, 1=fail(secret 발견), 2=env(gitleaks 부재)
#
# 정책: secret scan 우회는 어떤 경우에도 금지.

set -euo pipefail
IFS=$'\n\t'

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

usage() {
    echo "usage: secret-scan.sh --staged | --all" >&2
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

resolve_gitleaks() {
    if command -v gitleaks >/dev/null 2>&1; then
        GITLEAKS_CMD=(gitleaks)
        return
    fi

    local local_appdata="${LOCALAPPDATA:-}"
    if [[ -n "$local_appdata" && "$(command -v cygpath || true)" ]]; then
        local_appdata="$(cygpath "$local_appdata")"
    fi

    local package_root=""
    if [[ -n "$local_appdata" ]]; then
        package_root="$local_appdata/Microsoft/WinGet/Packages"
    elif [[ -n "${USERPROFILE:-}" && "$(command -v cygpath || true)" ]]; then
        package_root="$(cygpath "$USERPROFILE")/AppData/Local/Microsoft/WinGet/Packages"
    fi

    if [[ -n "$package_root" && -d "$package_root" ]]; then
        local found
        found="$(find "$package_root" -path '*Gitleaks.Gitleaks*' -name gitleaks.exe -print -quit 2>/dev/null || true)"
        if [[ -n "$found" && -x "$found" ]]; then
            GITLEAKS_CMD=("$found")
            return
        fi
    fi

    {
        echo "FAIL: env"
        echo "target: gitleaks (PATH/winget package 부재)"
        echo "next: $GITLEAKS_INSTALL"
    } >&2
    exit 2
}

[[ "$#" -ne 1 ]] && usage

GITLEAKS_INSTALL="winget install Gitleaks.Gitleaks 또는 scoop install gitleaks (https://github.com/gitleaks/gitleaks#installing)"
GITLEAKS_CMD=()

resolve_gitleaks

# 버전 경고 (v8 미만은 옵션 다름)
GL_VER="$("${GITLEAKS_CMD[@]}" version 2>/dev/null | head -1 || true)"
case "$GL_VER" in
    v7.*|7.*|v6.*|6.*)
        echo "WARN: gitleaks $GL_VER < v8, --staged/--no-banner 호환 미보장" >&2
        ;;
esac

cd "$(git rev-parse --show-toplevel)"
START=$SECONDS

case "$1" in
    --staged)
        echo "→ gitleaks protect --staged" >&2
        if ! "${GITLEAKS_CMD[@]}" protect --staged --redact --no-banner --exit-code 1; then
            fail "gitleaks" "staged changes" "git restore --staged <file> 후 secret 제거 — 우회 금지"
        fi
        ;;
    --all)
        echo "→ gitleaks detect (full history)" >&2
        if ! "${GITLEAKS_CMD[@]}" detect --redact --no-banner --exit-code 1; then
            fail "gitleaks" "history" "위 출력의 leaked secret을 git filter-repo 등으로 제거 — 우회 금지"
        fi
        ;;
    *)
        usage
        ;;
esac

ELAPSED=$((SECONDS - START))
echo "PASS: secret-scan (${ELAPSED}s, $1)"
