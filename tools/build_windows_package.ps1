param(
    [switch]$SkipInstaller,
    [string]$IsccPath
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "lumbar-rehab-assistant.spec"
$Installer = Join-Path $Root "installer\yu-an.iss"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project interpreter not found: $Python"
}

$PreflightArgs = @((Join-Path $Root "tools\preflight_windows_package.py"))
if ($SkipInstaller) { $PreflightArgs += "--skip-installer" }
if ($IsccPath) { $PreflightArgs += @("--iscc-path", $IsccPath) }
& $Python @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw "Packaging preflight failed with exit code $LASTEXITCODE"
}

Push-Location $Root
try {
    & $Python -m PyInstaller --noconfirm --clean $Spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    if (-not $SkipInstaller) {
        $ResolveArgs = @((Join-Path $Root "tools\preflight_windows_package.py"), "--print-iscc-path")
        if ($IsccPath) { $ResolveArgs += @("--iscc-path", $IsccPath) }
        $Compiler = & $Python @ResolveArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup compiler resolution failed."
        }
        & $Compiler $Installer
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed with exit code $LASTEXITCODE"
        }
    }
}
finally {
    Pop-Location
}

