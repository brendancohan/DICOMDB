import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.deps import base_context, get_db, require_user, templates
from app.dicom_utils import find_conflicts

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/conflicts", response_class=HTMLResponse)
def conflicts_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    conflicts = find_conflicts(conn)
    return templates.TemplateResponse(
        request,
        "conflicts.html",
        base_context(request, conn, active_nav="conflicts", conflicts=conflicts),
    )
