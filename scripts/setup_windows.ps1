param(
    [int]$Port = 8000,
    [string]$CallingAet = "DICOMDB"
)

$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $AppDir

Write-Host "=== DicomDB Windows Setup ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment (.venv)..."
    python -m venv .venv
}

Write-Host "Installing dependencies from requirements.txt..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

$EnvFile = Join-Path $AppDir ".env"
if (-not (Test-Path $EnvFile)) {
    $PortInput = Read-Host "HTTP Port [$Port]"
    if ($PortInput) { $Port = [int]$PortInput }

    $AetInput = Read-Host "Default Calling AE Title for C-ECHO [$CallingAet]"
    if ($AetInput) { $CallingAet = $AetInput.Trim() }

    $SecretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object {[char]$_})

    @"
DICOMDB_HOST=0.0.0.0
DICOMDB_PORT=$Port
DICOMDB_DB_PATH=data/pacs_inventory.db
DICOMDB_SECRET_KEY=$SecretKey
DICOMDB_USERNAME=pacsadmin
DICOMDB_DEFAULT_PASSWORD=changeme
DICOMDB_CALLING_AET=$CallingAet
"@ | Set-Content -Path $EnvFile -Encoding UTF8

    Write-Host "Created .env with generated secret key." -ForegroundColor Green
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

$SetPw = Read-Host "Set the shared pacsadmin password now? (y/N)"
if ($SetPw -match "^[Yy]") {
    & .\.venv\Scripts\python.exe scripts\set_password.py
}

$AddFw = Read-Host "Add Windows Firewall inbound rule for TCP port $Port? (y/N)"
if ($AddFw -match "^[Yy]") {
    New-NetFirewallRule -DisplayName "DicomDB HTTP ($Port)" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    Write-Host "Firewall rule added for TCP port $Port." -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete! Start DicomDB with:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe run.py"
