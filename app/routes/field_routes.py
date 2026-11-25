import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_editor_label
from app.deps import base_context, get_db, require_user, templates
from app.models import (
    FIELD_TYPES,
    create_field_definition,
    list_field_definitions,
    move_field_order,
    toggle_archive_field,
    update_field_definition,
)

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/fields", response_class=HTMLResponse)
def fields_page(
    request: Request,
    show_archived: int = 0,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    fields = list_field_definitions(conn, include_archived=bool(show_archived))
    return templates.TemplateResponse(
        request,
        "fields.html",
        base_context(
            request,
            conn,
            active_nav="fields",
            fields=fields,
            field_types=FIELD_TYPES,
            show_archived=bool(show_archived),
        ),
    )


@router.post("/fields")
def create_field(
    request: Request,
    label: str = Form(...),
    field_type: str = Form("text"),
    options_text: str = Form(""),
    section: str = Form("General"),
    show_in_table: str = Form(""),
    is_required: str = Form(""),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    options = [o.strip() for o in options_text.split(",") if o.strip()]
    create_field_definition(
        conn,
        label=label,
        field_type=field_type,
        options=options,
        section=section,
        show_in_table=bool(show_in_table),
        is_required=bool(is_required),
        editor_label=get_editor_label(request, editor_label),
    )
    return RedirectResponse(url="/fields", status_code=303)


@router.post("/fields/{field_id}/update")
def edit_field(
    field_id: int,
    request: Request,
    label: str = Form(...),
    options_text: str = Form(""),
    section: str = Form("General"),
    show_in_table: str = Form(""),
    is_required: str = Form(""),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    options = [o.strip() for o in options_text.split(",") if o.strip()]
    update_field_definition(
        conn,
        field_id=field_id,
        label=label,
        options=options,
        section=section,
        show_in_table=bool(show_in_table),
        is_required=bool(is_required),
        editor_label=get_editor_label(request, editor_label),
    )
    return RedirectResponse(url="/fields", status_code=303)


@router.post("/fields/{field_id}/toggle-archive")
def archive_field(
    field_id: int,
    request: Request,
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    toggle_archive_field(conn, field_id, get_editor_label(request, editor_label))
    return RedirectResponse(url="/fields", status_code=303)


@router.post("/fields/{field_id}/move")
def move_field(
    field_id: int,
    direction: str = Form(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    move_field_order(conn, field_id, direction)
    return RedirectResponse(url="/fields", status_code=303)
