param(
    [string]$DbPath = "data\pacs_inventory.db",
    [string]$BackupDir = "backups",
    [int]$KeepDays = 30
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$DestPath = Join-Path $BackupDir "pacs_inventory_$Timestamp.db"

# Use SQLite online backup API (safe while WAL mode is active)
$PyCode = @"
import sqlite3
src = sqlite3.connect(r'$DbPath')
dst = sqlite3.connect(r'$DestPath')
with dst:
    src.backup(dst)
src.close()
dst.close()
"@

& .\.venv\Scripts\python.exe -c $PyCode
Write-Host "Backed up database to $DestPath"

Get-ChildItem -Path $BackupDir -Filter "pacs_inventory_*.db" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
    Remove-Item -Force
