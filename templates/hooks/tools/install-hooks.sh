#!/usr/bin/env bash
# tools/install-hooks.sh — core.hooksPath 설정 + 환경 점검
# 사용: bash tools/install-hooks.sh
# 스코프: 레포 로컬 (--local). 글로벌 미수정.

set -euo pipefail

if [[ "${HOOKS_DEBUG:-}" == "1" ]]; then set -x; fi

cd "$(git rev-parse --show-toplevel)"

TARGET="tools/hooks"
CURRENT="$(git config --local --get core.hooksPath || true)"

# ── 1. core.hooksPath 설정 ────────────────────────────────
if [[ -z "$CURRENT" || "$CURRENT" == "$TARGET" ]]; then
    git config --local core.hooksPath "$TARGET"
    echo "✓ core.hooksPath → $TARGET (레포 로컬, 다른 레포 영향 없음)"
else
    {
        echo "FAIL: install-hooks"
        echo "target: core.hooksPath 이미 다른 값으로 설정됨 ($CURRENT)"
        echo "next: 의도적이라면 'git config --local core.hooksPath $TARGET' 직접 실행"
    } >&2
    exit 1
fi

# ── 2. 실행 권한 (Windows core.fileMode 무관 추적) ────────
chmod +x tools/hooks/* tools/quality/*.sh tools/install-hooks.sh 2>/dev/null || true
echo "✓ chmod +x 적용 — Windows에서 권한 추적 필요 시 다음 명령 1회 실행:"
echo "    git update-index --chmod=+x tools/hooks/pre-commit tools/hooks/pre-push tools/install-hooks.sh tools/quality/lint.sh tools/quality/build.sh tools/quality/test.sh tools/quality/secret-scan.sh tools/quality/dependency-check.sh"

# ── 3. prerequisite 점검 (부재 시 경고만, install 자체는 성공) ──
WARN=0
warn_if_missing() {
    local cmd="$1" install="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "⚠  $cmd 부재 — 첫 훅 실행 시 exit 2 발생" >&2
        echo "    설치: $install" >&2
        WARN=1
    fi
}

has_winget_gitleaks() {
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

    [[ -n "$package_root" && -d "$package_root" ]] || return 1
    find "$package_root" -path '*Gitleaks.Gitleaks*' -name gitleaks.exe -print -quit 2>/dev/null | grep -q .
}

warn_if_missing "dotnet"   "winget install Microsoft.DotNet.SDK.9 또는 https://dotnet.microsoft.com/download"

if ! command -v gitleaks >/dev/null 2>&1 && ! has_winget_gitleaks; then
    echo "⚠  gitleaks 부재 — 첫 훅 실행 시 exit 2 발생" >&2
    echo "    설치: winget install Gitleaks.Gitleaks 또는 scoop install gitleaks" >&2
    WARN=1
fi

# python은 둘 중 하나만 있어도 OK
if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    echo "⚠  python/python3 부재 — 첫 훅 실행 시 exit 2 발생" >&2
    echo "    설치: https://www.python.org/downloads/" >&2
    WARN=1
fi

if ! command -v ruff >/dev/null 2>&1; then
    if ! (python -m ruff --version >/dev/null 2>&1 || python3 -m ruff --version >/dev/null 2>&1); then
        echo "⚠  ruff 부재 — 첫 훅 실행 시 exit 2 발생" >&2
        echo "    설치: python -m pip install -r requirements-dev.txt 또는 winget install astral-sh.ruff" >&2
        WARN=1
    fi
fi

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    :
elif ! ( python -c "import pytest" 2>/dev/null || python3 -c "import pytest" 2>/dev/null ); then
    echo "⚠  pytest 미설치 — pre-push test 단계에서 exit 2" >&2
    echo "    설치: python -m pip install -r requirements-dev.txt" >&2
    WARN=1
fi

if [[ "$WARN" == "1" ]]; then
    echo ""
    echo "설치 완료. 위 도구를 갖춘 후 git commit/push 시 훅이 자동 발화합니다."
else
    echo "✓ 사전 도구 점검 통과"
    echo ""
    echo "설치 완료. git commit/push 시 훅이 자동 발화합니다."
fi
