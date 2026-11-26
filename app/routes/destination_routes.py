import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_editor_label
from app.config import settings
from app.deps import base_context, get_db, require_user, templates
from app.models import (
    DESTINATION_TYPES,
    delete_destination,
    get_destination,
    get_destination_modalities,
    get_setting,
    list_destinations,
    save_destination,
)

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/destinations", response_class=HTMLResponse)
def destinations_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    destinations = list_destinations(conn)
    return templates.TemplateResponse(
        request,
        "destinations.html",
        base_context(
            request,
            conn,
            active_nav="destinations",
            destinations=destinations,
            dest_types=DESTINATION_TYPES,
        ),
    )


@router.post("/destinations")
def create_destination(
    request: Request,
    name: str = Form(...),
    dest_type: str = Form("PACS"),
    ae_title: str = Form(""),
    ip_address: str = Form(""),
    port: str = Form(""),
    notes: str = Form(""),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    save_destination(
        conn,
        dest_id=None,
        data={
            "name": name,
            "dest_type": dest_type,
            "ae_title": ae_title,
            "ip_address": ip_address,
            "port": port,
            "notes": notes,
        },
        editor_label=get_editor_label(request, editor_label),
    )
    return RedirectResponse(url="/destinations", status_code=303)


@router.get("/destinations/{dest_id}", response_class=HTMLResponse)
def destination_detail(
    dest_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    dest = get_destination(conn, dest_id)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    routed_modalities = get_destination_modalities(conn, dest_id)
    return templates.TemplateResponse(
        request,
        "destination_detail.html",
        base_context(
            request,
            conn,
            active_nav="destinations",
            dest=dest,
            routed_modalities=routed_modalities,
            dest_types=DESTINATION_TYPES,
            default_calling_aet=get_setting(conn, "calling_aet", settings.calling_aet),
        ),
    )


@router.post("/destinations/{dest_id}/edit")
def edit_destination(
    dest_id: int,
    request: Request,
    name: str = Form(...),
    dest_type: str = Form("PACS"),
    ae_title: str = Form(""),
    ip_address: str = Form(""),
    port: str = Form(""),
    notes: str = Form(""),
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    save_destination(
        conn,
        dest_id=dest_id,
        data={
            "name": name,
            "dest_type": dest_type,
            "ae_title": ae_title,
            "ip_address": ip_address,
            "port": port,
            "notes": notes,
        },
        editor_label=get_editor_label(request, editor_label),
    )
    return RedirectResponse(url=f"/destinations/{dest_id}", status_code=303)


@router.post("/destinations/{dest_id}/delete")
def remove_destination(
    dest_id: int,
    request: Request,
    editor_label: str = Form(""),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    delete_destination(conn, dest_id, get_editor_label(request, editor_label))
    return RedirectResponse(url="/destinations", status_code=303)
