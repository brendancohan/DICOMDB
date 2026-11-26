# DicomDB

## Overview
- **Purpose:** Lightweight internal PACS modality inventory and configuration web database replacing unstandardized Word documents. Supports dynamic user-defined fields, modular multi-AE-title devices, routing/reverse-lookup, DICOM validation and `C-ECHO` testing, audit logging, `.docx` import assistance, and downtime exports.
- **Primary Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, SQLite (WAL mode), `pynetdicom`, `python-docx`, `openpyxl`, and local-only CSS/JS. Targeted for Windows Server deployment via NSSM.

## Commands
- **Install / Setup (Linux/dev):** `uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"`
- **Install / Setup (Windows Server):** `python -m venv .venv && .\.venv\Scripts\python.exe -m pip install -e .`
- **Run / Dev:** `.venv/bin/python run.py` (or `.\.venv\Scripts\python.exe run.py` on Windows; configure port via `DICOMDB_PORT` in `.env`)
- **Set Shared Password:** `.venv/bin/python scripts/set_password.py`
- **Test:** `.venv/bin/pytest -v`

## Repository Layout
- `run.py` — Uvicorn entry point reading host/port from `app/config.py`.
- `app/` — Core backend: `config.py`, `database.py` (SQLite WAL schema), `auth.py` (`scrypt` + signed session cookie), `models.py` (CRUD, dynamic fields, audit diffs), `dicom_utils.py`, `docx_importer.py`, `exports.py`, `deps.py`, `main.py`.
- `app/routes/` — FastAPI routers (`auth_routes.py`, `modality_routes.py`, `field_routes.py`, `destination_routes.py`, `conflict_routes.py`, `audit_routes.py`, `import_routes.py`, `export_routes.py`).
- `app/templates/` & `app/static/` — Jinja2 HTML templates and local-only `app.css` / `app.js`.
- `scripts/` — Windows Server helpers (`set_password.py`, `backup_db.ps1`, `install_windows_service.ps1`).
- `tests/` — Pytest suite using isolated temporary SQLite databases (`conftest.py`).

## Project-Specific Conventions & Guardrails
- **Offline / Intranet Ready:** Keep all CSS/JS local under `app/static/`—never add external CDN links.
- **Windows Server Portability:** Prefer Python stdlib (e.g., `hashlib.scrypt`) and wheel-backed dependencies; avoid native build requirements.
- **Dynamic Fields:** Store custom values in `modalities.custom_fields` JSON governed by `field_definitions`. Archive fields rather than hard-deleting them so historical data is preserved.
- **DICOM & Connectivity:** Validate AE Titles (≤ 16 printable ASCII chars, no `\`). Run blocking TCP/`C-ECHO` checks via `asyncio.to_thread()` with short timeouts. Never store PHI in the database or repo.
- **Audit Trail:** Every create/update/delete/archive mutation must record an `audit_log` entry via `record_audit()`.
- **Do Not Commit:** `.env`, `data/`, `*.db*`, or `.venv/` (all ignored in `.gitignore`).
- **Verification:** Run `.venv/bin/pytest -v` after changes; tests must use isolated temp SQLite fixtures and never touch `data/pacs_inventory.db`.
