#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Local release build helper (PowerShell port)
# - builds sdist/wheel
# - generates SHA256SUMS
# - builds a PyInstaller single-file binary for the current OS
# - builds a docker image (if docker found)
# - collects artifacts under release/<version>/

# Change to repository root (parent of the scripts directory)
$ScriptFile = $MyInvocation.MyCommand.Definition
$ScriptRoot = Split-Path -Parent $ScriptFile
$RepoRoot = Split-Path -Parent $ScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path -Path 'VERSION')) {
    Write-Error "VERSION file not found"
    exit 1
}

$VERSION = (Get-Content -Path 'VERSION' -Raw).Trim()
Write-Host "Building release for version: $VERSION"

# choose python: prefer .venv\Scripts\python.exe, otherwise python3 or python from PATH
$venvPython = Join-Path -Path '.venv\Scripts' -ChildPath 'python.exe'
if (Test-Path $venvPython) {
    $PYTHON = $venvPython
} else {
    $py3 = Get-Command python3 -ErrorAction SilentlyContinue
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py3 -and $py3.Path) { $PYTHON = $py3.Path }
    elseif ($py -and $py.Path) { $PYTHON = $py.Path }
    else { Write-Error "Python not found in .venv or PATH"; exit 1 }
}

Write-Host "Using python: $PYTHON"

Write-Host "==> Building python distributions"
uv run --with build python -m build

Write-Host "==> Creating SHA256SUMS"
$distDir = Join-Path -Path $RepoRoot -ChildPath 'dist'
if (-not (Test-Path $distDir)) { New-Item -ItemType Directory -Path $distDir | Out-Null }
$distFiles = Get-ChildItem -Path $distDir -File -ErrorAction SilentlyContinue | Sort-Object Name
$shaFile = Join-Path -Path $distDir -ChildPath 'SHA256SUMS'

$sb = New-Object System.Text.StringBuilder
foreach ($f in $distFiles) {
    $hash = Get-FileHash -Algorithm SHA256 -Path $f.FullName
    $sb.AppendLine("$($hash.Hash.ToLower())  $($f.Name)") | Out-Null
}
$sb.ToString() | Set-Content -Path $shaFile -NoNewline
Write-Host "SHA256SUMS written to $shaFile"

Write-Host "==> Building PyInstaller single-file (current OS)"
if (Test-Path 'app\main.py') {
    uv run --with pyinstaller pyinstaller --additional-hooks-dir hooks --onefile 'app/main.py' --name anibridge

    if ($IsWindows) { $PLATFORM = 'windows' }
    elseif ($IsLinux) { $PLATFORM = 'linux' }
    elseif ($IsMacOS) { $PLATFORM = 'darwin' }
    else { $PLATFORM = 'unknown' }

    $platformDir = Join-Path -Path (Join-Path -Path 'release' -ChildPath $VERSION) -ChildPath $PLATFORM
    New-Item -ItemType Directory -Path $platformDir -Force | Out-Null

    $binA = Join-Path -Path 'dist' -ChildPath 'anibridge'
    $binB = Join-Path -Path 'dist' -ChildPath 'anibridge.exe'
    if (Test-Path $binA) {
        Copy-Item -Path $binA -Destination $platformDir -Force
    } elseif (Test-Path $binB) {
        Copy-Item -Path $binB -Destination $platformDir -Force
    } else {
        Write-Host "PyInstaller did not produce expected binary in dist/ (ok to continue)."
    }
} else {
    Write-Host "No app/main.py entrypoint found — skipping PyInstaller step."
}

Write-Host "==> Building Docker image"
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    $remote = (& git config --get remote.origin.url 2>$null) -join "`n"
    if ($remote) {
        if ($remote -match '[:/](.+/.+?)(\.git)?$') { $IMAGE = "ghcr.io/$($matches[1])" }
        else { $IMAGE = 'ghcr.io/youruser/anibridge' }
    } else { $IMAGE = 'ghcr.io/youruser/anibridge' }

    try {
        docker build -t "${IMAGE}:${VERSION}" -t "${IMAGE}:v${VERSION}" .
    } catch {
        Write-Host "docker build failed: $_"
    }
} else {
    Write-Host "docker not found — skipping docker build"
}

Write-Host "==> Collecting artifacts into release/$VERSION/dist"
$targetDist = Join-Path -Path (Join-Path -Path 'release' -ChildPath $VERSION) -ChildPath 'dist'
New-Item -ItemType Directory -Path $targetDist -Force | Out-Null
Get-ChildItem -Path 'dist' -File -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $targetDist -Force -ErrorAction SilentlyContinue
}

Write-Host "Done. Artifacts are in: release/$VERSION/"
Write-Host " - Python dists: release/$VERSION/dist/"
Write-Host " - PyInstaller binary (if built): release/$VERSION/<platform>/"

exit 0
