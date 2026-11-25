import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.deps import base_context, get_db, require_user, templates
from app.models import list_audit_logs

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    entity_type: str = "",
    action: str = "",
    q: str = "",
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    logs = list_audit_logs(conn, entity_type=entity_type, action=action, q=q)
    return templates.TemplateResponse(
        request,
        "audit.html",
        base_context(
            request,
            conn,
            active_nav="audit",
            logs=logs,
            entity_type=entity_type,
            action=action,
            q=q,
        ),
    )
