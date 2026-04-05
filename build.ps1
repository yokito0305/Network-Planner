[CmdletBinding()]
param(
    [string]$AppName = "NetworkPlanner",
    [switch]$SkipPyInstallerInstall,
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

function Remove-DirectoryWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$Retries = 3
    )

    if (-not (Test-Path $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            Remove-Item -Recurse -Force $Path
            return
        }
        catch {
            if ($attempt -eq $Retries) {
                throw "Unable to remove '$Path'. It may be locked by a running app. Close any running NetworkPlanner process and retry."
            }
        }
    }
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found: $pythonExe"
}

if (-not $SkipClean) {
    Remove-DirectoryWithRetry -Path "bin"
    Remove-DirectoryWithRetry -Path "bin_tmp"
    Remove-DirectoryWithRetry -Path "build\pyinstaller"
}

if (-not $SkipPyInstallerInstall) {
    & $pythonExe -m pip install pyinstaller
}

& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name $AppName `
    --distpath "bin_tmp" `
    --workpath "build/pyinstaller" `
    --specpath "build/pyinstaller" `
    --contents-directory "lib" `
    "main.py"

$distRoot = Join-Path $projectRoot ("bin_tmp\" + $AppName)
$distExe = Join-Path $distRoot ($AppName + ".exe")
$distLib = Join-Path $distRoot "lib"

if (-not (Test-Path $distExe)) {
    throw "Packaged executable not found: $distExe"
}

if (-not (Test-Path $distLib)) {
    throw "Packaged dependency folder not found: $distLib"
}

New-Item -ItemType Directory -Path "bin" -Force | Out-Null
Move-Item -Path $distExe -Destination (Join-Path $projectRoot ("bin\" + $AppName + ".exe"))
Move-Item -Path $distLib -Destination (Join-Path $projectRoot "bin\lib")

if (Test-Path "bin_tmp") {
    Remove-DirectoryWithRetry -Path "bin_tmp"
}

Write-Host "Build completed."
Write-Host "Executable: bin\$AppName.exe"
Write-Host "Dependencies: bin\lib"
