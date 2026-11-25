param(
    [string]$ServiceName = "DicomDB",
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [string]$AppDir = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"
$PythonExe = Join-Path $AppDir ".venv\Scripts\python.exe"
$RunScript = Join-Path $AppDir "run.py"

if (-not (Test-Path $NssmPath)) {
    Write-Error "NSSM not found at $NssmPath. Download from https://nssm.cc/ and pass -NssmPath."
}

& $NssmPath install $ServiceName $PythonExe $RunScript
& $NssmPath set $ServiceName AppDirectory $AppDir
& $NssmPath set $ServiceName DisplayName "DicomDB PACS Inventory"
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppStdout (Join-Path $AppDir "data\service_stdout.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $AppDir "data\service_stderr.log")
& $NssmPath start $ServiceName

Write-Host "Service '$ServiceName' installed and started."
