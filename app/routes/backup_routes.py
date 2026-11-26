import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.auth import authenticate_user, get_editor_label, set_password
from app.backup_utils import (
    create_backup_bytes,
    list_safety_backups,
    restore_database_from_bytes,
)
from app.config import settings
from app.deps import base_context, get_db, require_user, templates
from app.dicom_utils import validate_ae_title
from app.models import get_setting, record_audit, set_setting

router = APIRouter(dependencies=[Depends(require_user)])

_SAFETY_FILENAME_RE = re.compile(r"^pre_restore_\d{8}_\d{6}\.db$")


def _backup_context(
    request: Request,
    conn: sqlite3.Connection,
    message: str = "",
    error: str = "",
) -> dict:
    return base_context(
        request,
        conn,
        active_nav="backup",
        safety_backups=list_safety_backups(settings.db_path),
        default_calling_aet=get_setting(conn, "calling_aet", settings.calling_aet),
        message=message,
        error=error,
    )


@router.get("/backup", response_class=HTMLResponse)
def backup_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "backup.html", _backup_context(request, conn))


@router.get("/backup/download")
def download_backup() -> Response:
    data = create_backup_bytes(settings.db_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"dicomdb_backup_{stamp}.db"
    return Response(
        content=data,
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/backup/safety/{filename}")
def download_safety_backup(filename: str) -> Response:
    if not _SAFETY_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid safety backup filename")
    path = Path(settings.db_path).parent / "pre_restore_backups" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Safety backup not found")
    return Response(
        content=path.read_bytes(),
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/backup/restore", response_class=HTMLResponse)
async def restore_backup(
    request: Request,
    file: UploadFile = File(...),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    content = await file.read()
    try:
        safety_name = restore_database_from_bytes(settings.db_path, content)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "backup.html",
            _backup_context(request, conn, error=str(exc)),
            status_code=400,
        )

    record_audit(
        conn,
        "database",
        None,
        file.filename or "backup.db",
        "restore",
        get_editor_label(request, editor_label),
        {"safety_backup": safety_name},
    )
    conn.commit()

    return templates.TemplateResponse(
        request,
        "backup.html",
        _backup_context(
            request,
            conn,
            message=f"Database restored successfully from '{file.filename}'. Safety snapshot saved as '{safety_name}'.",
        ),
    )


@router.post("/backup/settings", response_class=HTMLResponse)
def update_dicom_settings(
    request: Request,
    calling_aet: str = Form(...),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    aet = calling_aet.strip()
    issues = validate_ae_title(aet)
    if issues:
        return templates.TemplateResponse(
            request,
            "backup.html",
            _backup_context(request, conn, error=f"Invalid Calling AE Title: {' '.join(issues)}"),
            status_code=400,
        )
    old_aet = get_setting(conn, "calling_aet", settings.calling_aet)
    set_setting(conn, "calling_aet", aet)
    record_audit(
        conn,
        "settings",
        None,
        "calling_aet",
        "update",
        get_editor_label(request, editor_label),
        {"calling_aet": {"old": old_aet, "new": aet}},
    )
    conn.commit()
    return templates.TemplateResponse(
        request,
        "backup.html",
        _backup_context(request, conn, message=f"Default Calling AE Title updated to '{aet}'."),
    )


@router.post("/backup/password", response_class=HTMLResponse)
def change_shared_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    if not authenticate_user(conn, settings.username, current_password):
        return templates.TemplateResponse(
            request,
            "backup.html",
            _backup_context(request, conn, error="Current password is incorrect."),
            status_code=400,
        )
    if not new_password or new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "backup.html",
            _backup_context(request, conn, error="New passwords did not match or were empty."),
            status_code=400,
        )
    set_password(conn, new_password)
    record_audit(
        conn,
        "settings",
        None,
        settings.username,
        "update",
        get_editor_label(request, editor_label),
        {"password": "updated"},
    )
    conn.commit()
    return templates.TemplateResponse(
        request,
        "backup.html",
        _backup_context(request, conn, message="Shared account password updated."),
    )
