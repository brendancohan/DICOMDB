import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app.deps import base_context, get_db, require_user, templates
from app.exports import export_csv, export_xlsx
from app.models import list_destinations, list_field_definitions, list_modalities

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/export/csv")
def download_csv(conn: sqlite3.Connection = Depends(get_db)) -> Response:
    modalities = list_modalities(conn)
    field_defs = list_field_definitions(conn)
    csv_data = export_csv(modalities, field_defs)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="dicomdb_inventory.csv"'},
    )


@router.get("/export/xlsx")
def download_xlsx(conn: sqlite3.Connection = Depends(get_db)) -> Response:
    modalities = list_modalities(conn)
    destinations = list_destinations(conn)
    field_defs = list_field_definitions(conn)
    xlsx_bytes = export_xlsx(modalities, destinations, field_defs)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="dicomdb_inventory.xlsx"'},
    )


@router.get("/export/downtime", response_class=HTMLResponse)
def downtime_binder(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    modalities = list_modalities(conn, status="Active")
    destinations = list_destinations(conn)
    field_defs = list_field_definitions(conn)
    return templates.TemplateResponse(
        request,
        "downtime_print.html",
        base_context(
            request,
            conn,
            active_nav="inventory",
            modalities=modalities,
            destinations=destinations,
            field_defs=field_defs,
        ),
    )
