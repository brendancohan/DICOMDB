import asyncio
import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.auth import get_editor_label
from app.config import settings
from app.deps import base_context, get_db, require_user, templates
from app.dicom_utils import test_dicom_echo, test_tcp_connection, validate_ae_title
from app.models import (
    MODALITY_STATUSES,
    MODALITY_TYPES,
    ROUTE_DIRECTIONS,
    delete_modality,
    get_modality,
    list_audit_logs,
    list_destinations,
    list_field_definitions,
    list_locations,
    list_modalities,
    save_modality,
)

router = APIRouter(dependencies=[Depends(require_user)])


class TcpTestRequest(BaseModel):
    host: str
    port: int


class EchoTestRequest(BaseModel):
    host: str
    port: int
    called_aet: str


@router.get("/", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    q: str = "",
    modality_type: str = "",
    status: str = "",
    location: str = "",
    destination_id: Optional[int] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    modalities = list_modalities(
        conn,
        q=q,
        modality_type=modality_type,
        status=status,
        location=location,
        destination_id=destination_id,
    )
    field_defs = list_field_definitions(conn)
    destinations = list_destinations(conn)
    locations = list_locations(conn)
    return templates.TemplateResponse(
        request,
        "inventory.html",
        base_context(
            request,
            conn,
            active_nav="inventory",
            modalities=modalities,
            field_defs=field_defs,
            destinations=destinations,
            locations=locations,
            modality_types=MODALITY_TYPES,
            modality_statuses=MODALITY_STATUSES,
            filters={
                "q": q,
                "modality_type": modality_type,
                "status": status,
                "location": location,
                "destination_id": destination_id or "",
            },
        ),
    )


@router.get("/modalities/new", response_class=HTMLResponse)
def new_modality_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "modality_form.html",
        base_context(
            request,
            conn,
            active_nav="inventory",
            modality={
                "id": None,
                "device_name": "",
                "modality_type": "CT",
                "manufacturer": "",
                "model": "",
                "location": "",
                "ip_address": "",
                "status": "Active",
                "notes": "",
                "custom_fields": {},
                "ae_titles": [{"ae_title": "", "role_label": "Store", "ip_address": "", "port": "", "notes": ""}],
                "routes": [],
            },
            field_defs=list_field_definitions(conn),
            destinations=list_destinations(conn),
            modality_types=MODALITY_TYPES,
            modality_statuses=MODALITY_STATUSES,
            route_directions=ROUTE_DIRECTIONS,
            warnings=[],
        ),
    )


async def _parse_modality_form(request: Request, field_defs: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str]:
    form = await request.form()

    custom_fields: dict[str, Any] = {}
    for f in field_defs:
        key = f["key"]
        raw_val = form.get(f"cf_{key}")
        if f["field_type"] == "boolean":
            custom_fields[key] = bool(raw_val)
        else:
            custom_fields[key] = str(raw_val or "").strip()

    data = {
        "device_name": str(form.get("device_name") or ""),
        "modality_type": str(form.get("modality_type") or "OTHER"),
        "manufacturer": str(form.get("manufacturer") or ""),
        "model": str(form.get("model") or ""),
        "location": str(form.get("location") or ""),
        "ip_address": str(form.get("ip_address") or ""),
        "status": str(form.get("status") or "Active"),
        "notes": str(form.get("notes") or ""),
        "custom_fields": custom_fields,
    }

    ae_titles_list = form.getlist("ae_title")
    ae_roles = form.getlist("ae_role_label")
    ae_ips = form.getlist("ae_ip_address")
    ae_ports = form.getlist("ae_port")
    ae_notes = form.getlist("ae_notes")
    ae_titles = []
    for i, aet in enumerate(ae_titles_list):
        ae_titles.append(
            {
                "ae_title": str(aet),
                "role_label": str(ae_roles[i]) if i < len(ae_roles) else "",
                "ip_address": str(ae_ips[i]) if i < len(ae_ips) else "",
                "port": str(ae_ports[i]) if i < len(ae_ports) else "",
                "notes": str(ae_notes[i]) if i < len(ae_notes) else "",
            }
        )

    rt_dests = form.getlist("route_destination_id")
    rt_ae_idx = form.getlist("route_ae_index")
    rt_dirs = form.getlist("route_direction")
    rt_notes = form.getlist("route_notes")
    routes = []
    for i, dest_id in enumerate(rt_dests):
        if not str(dest_id).strip().isdigit():
            continue
        ae_idx_raw = str(rt_ae_idx[i]).strip() if i < len(rt_ae_idx) else ""
        routes.append(
            {
                "destination_id": int(dest_id),
                "ae_index": int(ae_idx_raw) if ae_idx_raw.isdigit() else None,
                "direction": str(rt_dirs[i]) if i < len(rt_dirs) else "Send",
                "notes": str(rt_notes[i]) if i < len(rt_notes) else "",
            }
        )

    editor = str(form.get("editor_label") or "")
    return data, ae_titles, routes, editor


@router.post("/modalities/new")
async def create_modality(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    field_defs = list_field_definitions(conn)
    data, ae_titles, routes, editor = await _parse_modality_form(request, field_defs)
    modality_id = save_modality(
        conn,
        modality_id=None,
        data=data,
        ae_titles=ae_titles,
        routes=routes,
        editor_label=get_editor_label(request, editor),
    )
    return RedirectResponse(url=f"/modalities/{modality_id}", status_code=303)


@router.get("/modalities/{modality_id}", response_class=HTMLResponse)
def modality_detail(
    modality_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    modality = get_modality(conn, modality_id)
    if not modality:
        raise HTTPException(status_code=404, detail="Modality not found")
    field_defs = list_field_definitions(conn)
    sections: dict[str, list[dict[str, Any]]] = {}
    for f in field_defs:
        sections.setdefault(f["section"] or "General", []).append(f)

    ae_warnings = {}
    for ae in modality["ae_titles"]:
        issues = validate_ae_title(ae["ae_title"])
        if issues:
            ae_warnings[ae["id"]] = issues

    recent_audit = [
        log
        for log in list_audit_logs(conn, entity_type="modality", limit=50)
        if log["entity_id"] == modality_id
    ][:10]

    return templates.TemplateResponse(
        request,
        "modality_detail.html",
        base_context(
            request,
            conn,
            active_nav="inventory",
            modality=modality,
            sections=sections,
            ae_warnings=ae_warnings,
            recent_audit=recent_audit,
        ),
    )


@router.get("/modalities/{modality_id}/edit", response_class=HTMLResponse)
def edit_modality_page(
    modality_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    modality = get_modality(conn, modality_id)
    if not modality:
        raise HTTPException(status_code=404, detail="Modality not found")
    if not modality["ae_titles"]:
        modality["ae_titles"] = [{"ae_title": "", "role_label": "Store", "ip_address": "", "port": "", "notes": ""}]
    return templates.TemplateResponse(
        request,
        "modality_form.html",
        base_context(
            request,
            conn,
            active_nav="inventory",
            modality=modality,
            field_defs=list_field_definitions(conn),
            destinations=list_destinations(conn),
            modality_types=MODALITY_TYPES,
            modality_statuses=MODALITY_STATUSES,
            route_directions=ROUTE_DIRECTIONS,
            warnings=[],
        ),
    )


@router.post("/modalities/{modality_id}/edit")
async def update_modality(
    modality_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    if not get_modality(conn, modality_id):
        raise HTTPException(status_code=404, detail="Modality not found")
    field_defs = list_field_definitions(conn)
    data, ae_titles, routes, editor = await _parse_modality_form(request, field_defs)
    save_modality(
        conn,
        modality_id=modality_id,
        data=data,
        ae_titles=ae_titles,
        routes=routes,
        editor_label=get_editor_label(request, editor),
    )
    return RedirectResponse(url=f"/modalities/{modality_id}", status_code=303)


@router.post("/modalities/{modality_id}/delete")
async def remove_modality(
    modality_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    form = await request.form()
    editor = str(form.get("editor_label") or "")
    delete_modality(conn, modality_id, get_editor_label(request, editor))
    return RedirectResponse(url="/", status_code=303)


@router.post("/api/test-tcp")
async def api_test_tcp(payload: TcpTestRequest) -> JSONResponse:
    result = await asyncio.to_thread(test_tcp_connection, payload.host, payload.port)
    return JSONResponse(result)


@router.post("/api/test-echo")
async def api_test_echo(payload: EchoTestRequest) -> JSONResponse:
    result = await asyncio.to_thread(
        test_dicom_echo,
        payload.host,
        payload.port,
        payload.called_aet,
        settings.calling_aet,
    )
    return JSONResponse(result)
