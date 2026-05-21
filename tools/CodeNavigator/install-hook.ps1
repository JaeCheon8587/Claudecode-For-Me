# Register CodeNavigator pre-commit hook for this git repo.
# Usage: .\install-hook.ps1 [-Repo <path>]
param([string]$Repo = ".")

$gitDir = git -C $Repo rev-parse --git-dir 2>$null
if (-not $gitDir) { Write-Error "Not a git repo: $Repo"; exit 1 }

$dst = Join-Path $gitDir "hooks\pre-commit"
$src = Join-Path $PSScriptRoot ".githooks\pre-commit"

if (Test-Path $dst) {
    Write-Warning "Existing hook at $dst — skipping. Manual merge required."
    exit 1
}

Copy-Item $src $dst
Write-Host "Hook installed: $dst"
Write-Host "Note: pre-commit hook uses bash. On Windows, ensure Git Bash or WSL is available."
