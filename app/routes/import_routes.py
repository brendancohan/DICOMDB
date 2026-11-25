import sqlite3

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.deps import base_context, get_db, require_user, templates
from app.docx_importer import extract_docx_data
from app.models import (
    MODALITY_STATUSES,
    MODALITY_TYPES,
    ROUTE_DIRECTIONS,
    list_destinations,
    list_field_definitions,
)

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/import", response_class=HTMLResponse)
def import_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "import_docx.html",
        base_context(request, conn, active_nav="import", extracted=None, error=""),
    )


@router.post("/import/parse", response_class=HTMLResponse)
async def import_parse(
    request: Request,
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    if not file.filename or not file.filename.lower().endswith(".docx"):
        return templates.TemplateResponse(
            request,
            "import_docx.html",
            base_context(
                request,
                conn,
                active_nav="import",
                extracted=None,
                error="Please upload a valid .docx Word document.",
            ),
            status_code=400,
        )

    content = await file.read()
    try:
        extracted = extract_docx_data(content, filename=file.filename)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "import_docx.html",
            base_context(
                request,
                conn,
                active_nav="import",
                extracted=None,
                error=f"Could not parse .docx file: {exc}",
            ),
            status_code=400,
        )

    sugg = extracted["suggestions"]
    ports = sugg["ports"]
    ae_titles = [
        {"ae_title": aet, "role_label": "", "ip_address": "", "port": ports[0] if ports else "", "notes": ""}
        for aet in sugg["ae_titles"]
    ]
    if not ae_titles:
        ae_titles = [{"ae_title": "", "role_label": "Store", "ip_address": "", "port": ports[0] if ports else "", "notes": ""}]

    modality_prefill = {
        "id": None,
        "device_name": sugg["device_name"],
        "modality_type": sugg["modality_type"],
        "manufacturer": "",
        "model": "",
        "location": "",
        "ip_address": sugg["ip_address"],
        "status": "Active",
        "notes": f"Imported from {file.filename}",
        "custom_fields": {},
        "ae_titles": ae_titles,
        "routes": [],
    }

    return templates.TemplateResponse(
        request,
        "import_docx.html",
        base_context(
            request,
            conn,
            active_nav="import",
            extracted=extracted,
            error="",
            modality=modality_prefill,
            field_defs=list_field_definitions(conn),
            destinations=list_destinations(conn),
            modality_types=MODALITY_TYPES,
            modality_statuses=MODALITY_STATUSES,
            route_directions=ROUTE_DIRECTIONS,
        ),
    )
