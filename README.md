# DicomDB

Lightweight internal PACS modality inventory and configuration database built with **FastAPI**, **SQLite (WAL mode)**, and **Jinja2**.

## Features

- **Modality Inventory**: Searchable/filterable table of all imaging modalities with custom column visibility toggles and one-click **Clone**.
- **Modular Multi-AE-Title Support**: Add unlimited AE Titles, roles (Store, MWL, MPPS, Print, etc.), IP overrides, and ports per device.
- **Dynamic Custom Fields**: Add new fields (`text`, `number`, `dropdown`, `boolean`, `date`, `textarea`, `url`) from the UI without code changes or database migrations.
- **Routing & Reverse Lookup**: Track PACS, VNA, Worklist, AI, and Print destinations and see every modality routed to a given server.
- **DICOM Validation & Connectivity**: Duplicate AE Title / IP:Port conflict detection plus live **TCP** and **DICOM C-ECHO** (`pynetdicom`) test buttons with configurable **Calling AE Title** (global default + per-test override) and **Test All**.
- **Assisted `.docx` Import**: Upload legacy Word documents to view extracted tables/text alongside a pre-filled Add Modality form.
- **Audit Log, Backup & Exports**: Full change history with optional staff initials, Web UI **Admin / Backup** (download/restore `.db` + change shared password), plus **CSV**, **Excel (`.xlsx`)**, and printable **Downtime Binder** exports.

---

## Quickstart (Windows Server)

### Option A: Automated Setup (Recommended)
Run the interactive setup script in PowerShell:
```powershell
.\scripts\setup_windows.ps1
```
Then start the server:
```powershell
.\.venv\Scripts\python.exe run.py
```

### Option B: Manual Setup
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts\set_password.py
.\.venv\Scripts\python.exe run.py
```

Open `http://localhost:8000` (or your configured `DICOMDB_PORT`) and sign in with `pacsadmin` and your password.

---

## Windows Server Service & Nightly Backups

### Run as a Windows Service (NSSM)
```powershell
.\scripts\install_windows_service.ps1 -NssmPath "C:\nssm\nssm.exe"
```

**If PowerShell scripts are disabled on the server**, run NSSM directly from an Administrator Command Prompt (replace `C:\DicomDB` with your actual path):
```cmd
C:\nssm\nssm.exe install DicomDB C:\DicomDB\.venv\Scripts\python.exe C:\DicomDB\run.py
C:\nssm\nssm.exe set DicomDB AppDirectory C:\DicomDB
C:\nssm\nssm.exe set DicomDB DisplayName "DicomDB PACS Inventory"
C:\nssm\nssm.exe set DicomDB Start SERVICE_AUTO_START
C:\nssm\nssm.exe set DicomDB AppStdout C:\DicomDB\data\service_stdout.log
C:\nssm\nssm.exe set DicomDB AppStderr C:\DicomDB\data\service_stderr.log
C:\nssm\nssm.exe start DicomDB
```
*(Or run `C:\nssm\nssm.exe install DicomDB` and enter those three fields in the NSSM GUI.)*

### Schedule Nightly Hot Backups (Task Scheduler)
Uses SQLite's online `.backup()` API (safe with WAL mode).

**Without PowerShell scripts (pure Python):**
Create a daily 2:00 AM task in Task Scheduler (`taskschd.msc`) with:
- **Program/script:** `C:\DicomDB\.venv\Scripts\python.exe`
- **Arguments:** `scripts\backup_db.py`
- **Start in:** `C:\DicomDB`

**Or via PowerShell:**
```powershell
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\DicomDB\scripts\backup_db.ps1" -WorkingDirectory "C:\DicomDB"
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
Register-ScheduledTask -TaskName "DicomDB Nightly Backup" -Action $Action -Trigger $Trigger -RunLevel Highest
```

### Upgrading / Patching
Your database (`data/`) and configuration (`.env`) are git-ignored and untouched during upgrades:
```powershell
nssm stop DicomDB
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
nssm start DicomDB
```

---

## Troubleshooting

| Issue | Fix |
| :--- | :--- |
| **Port 8000 already in use** | Set `DICOMDB_PORT=8080` in `.env` and restart. |
| **Staff can't reach the page** | Allow the port in Windows Firewall: `New-NetFirewallRule -DisplayName "DicomDB HTTP" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow` |
| **Corporate SSL / proxy error on `pip install`** | Run `.\.venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
| **Air-gapped / offline server** | On an internet-connected PC: `pip download -d wheelhouse -r requirements.txt`, copy `wheelhouse\` to the server, then `.\.venv\Scripts\python.exe -m pip install --no-index --find-links=wheelhouse -r requirements.txt` |
| **`C-ECHO` rejected by modality** | Whitelist DicomDB's Calling AE Title on the modality, or set a whitelisted Calling AET under **Admin / Backup -> DICOM Settings** (or inline on the device page). |
| **Health check** | `GET /health` returns `{"status": "ok", "db": "ok"}` without requiring login. |

---

## Running Tests & Troubleshooting Verification

The test suite is **100% safe to run on a production server**—every test uses an isolated temporary SQLite database and never touches `data/pacs_inventory.db`. Run it after a `git pull` upgrade, a Python upgrade, or when troubleshooting to verify authentication, multi-AE-title CRUD, dynamic fields, routing, DICOM validation, Calling AET overrides, `.docx` import, exports, and backup/restore.

**Windows Server (PowerShell):**
```powershell
.\.venv\Scripts\python.exe -m pip install pytest httpx
.\.venv\Scripts\pytest.exe -v
```

**Linux / Dev:**
```bash
.venv/bin/pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
