# codenav-prefer.ps1
# PreToolUse hook for Grep|Glob. Denies first C#-flavored call so Claude
# uses `codenav search` first. Approves on second call (fallback) or
# when the codenav index is too stale to trust.
#
# Approve = exit 0 with empty stdout.
# Deny    = exit 0 with hookSpecificOutput JSON (permissionDecision=deny).

$ErrorActionPreference = "Stop"

function Write-Approve {
    exit 0
}

function Write-Deny([string]$reason) {
    $payload = @{
        hookSpecificOutput = @{
            hookEventName            = "PreToolUse"
            permissionDecision       = "deny"
            permissionDecisionReason = $reason
        }
    } | ConvertTo-Json -Compress -Depth 5
    [Console]::Out.Write($payload)
    exit 0
}

# --- Read stdin JSON ---
try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { Write-Approve }
    $event = $raw | ConvertFrom-Json
} catch {
    Write-Approve
}

$toolName  = [string]$event.tool_name
$toolInput = $event.tool_input
if (-not $toolInput) { Write-Approve }
if ($toolName -ne "Grep" -and $toolName -ne "Glob") { Write-Approve }

# --- C# signal detection ---
$pattern = [string]$toolInput.pattern
$glob    = [string]$toolInput.glob
$path    = [string]$toolInput.path
$ftype   = [string]$toolInput.type

$csSignal = $false
if ($ftype -eq "cs") { $csSignal = $true }
if (-not $csSignal -and $glob -and ($glob -match "\.cs(\b|$)")) { $csSignal = $true }
if (-not $csSignal -and $pattern -and ($pattern -match "\.cs(\b|$)")) { $csSignal = $true }
if (-not $csSignal -and $path -and ($path -match "\.cs$")) { $csSignal = $true }
if (-not $csSignal -and $pattern -and ($pattern -match "^[A-Z][a-zA-Z0-9]{2,}$")) { $csSignal = $true }

if (-not $csSignal) { Write-Approve }

# --- Stale ratio check ---
$projectDir = $env:CLAUDE_PROJECT_DIR
if (-not $projectDir) { $projectDir = (Get-Location).Path }
$dbPath = Join-Path $projectDir ".codenav\index.sqlite"
if (-not (Test-Path $dbPath)) { Write-Approve }

$staleRatio = -1.0
try {
    $statusJob = Start-Job -ScriptBlock {
        param($root)
        & codenav --root $root status 2>&1
    } -ArgumentList $projectDir
    if (Wait-Job -Job $statusJob -Timeout 2) {
        $statusOut = Receive-Job -Job $statusJob
        Remove-Job -Job $statusJob -Force
        $total = 0; $stale = 0
        foreach ($line in ($statusOut -split "`n")) {
            if ($line -match "^Classes\s*:\s*(\d+)") { $total = [int]$Matches[1] }
            elseif ($line -match "^Stale\s*:\s*(\d+)")   { $stale = [int]$Matches[1] }
        }
        if ($total -gt 0) { $staleRatio = $stale / $total }
    } else {
        Stop-Job -Job $statusJob -ErrorAction SilentlyContinue
        Remove-Job -Job $statusJob -Force -ErrorAction SilentlyContinue
    }
} catch {
    $staleRatio = -1.0
}
if ($staleRatio -ge 0.30) { Write-Approve }

# --- Session counter ---
$sessionId = $env:CLAUDE_SESSION_ID
if (-not $sessionId) { $sessionId = "default" }
$stateDir = Join-Path $env:TEMP "codenav-prefer"
if (-not (Test-Path $stateDir)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}
$counterFile = Join-Path $stateDir "$sessionId-$toolName.txt"
$count = 0
if (Test-Path $counterFile) {
    try { $count = [int](Get-Content -Path $counterFile -Raw).Trim() } catch { $count = 0 }
}

if ($count -ge 1) { Write-Approve }

Set-Content -Path $counterFile -Value "1" -NoNewline
Write-Deny 'use: codenav search "<keywords>" --limit 5'
