# DicomDB

Lightweight internal PACS modality inventory and configuration database built with **FastAPI**, **SQLite (WAL mode)**, and **Jinja2**.

## Features

- **Modality Inventory**: Searchable/filterable table of all imaging modalities with custom column visibility toggles.
- **Modular Multi-AE-Title Support**: Add unlimited AE Titles, roles (Store, MWL, MPPS, Print, etc.), IP overrides, and ports per device.
- **Dynamic Custom Fields**: Add new fields (`text`, `number`, `dropdown`, `boolean`, `date`, `textarea`, `url`) from the UI without code changes or database migrations.
- **Routing & Reverse Lookup**: Track PACS, VNA, Worklist, AI, and Print destinations and see every modality routed to a given server.
- **DICOM Validation & Connectivity**: Duplicate AE Title / IP:Port conflict detection plus live **TCP** and **DICOM C-ECHO** (`pynetdicom`) test buttons.
- **Assisted `.docx` Import**: Upload legacy Word documents to view extracted tables/text alongside a pre-filled Add Modality form.
- **Audit Log & Exports**: Full change history with optional staff initials, plus **CSV**, **Excel (`.xlsx`)**, and printable **Downtime Binder** exports.

## Quickstart (Local / Windows Server)

1. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e .
   ```
2. Copy `.env.example` to `.env` and set a strong `DICOMDB_SECRET_KEY`:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Set the shared account password:
   ```powershell
   .\.venv\Scripts\python.exe scripts\set_password.py
   ```
4. Run the server:
   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```
   Open `http://localhost:8000` in your browser.

## Windows Server Service & Backups

- **Run as a Windows Service**: Use `scripts\install_windows_service.ps1` with [NSSM](https://nssm.cc/).
- **Scheduled Hot Backups**: Schedule `scripts\backup_db.ps1` in Windows Task Scheduler (uses SQLite's online backup API, safe with WAL mode).

## Running Tests

```bash
pytest -v
```
