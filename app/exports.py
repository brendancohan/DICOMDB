import csv
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def _format_ae_titles(ae_titles: list[dict[str, Any]]) -> str:
    parts = []
    for ae in ae_titles:
        label = f" ({ae['role_label']})" if ae.get("role_label") else ""
        endpoint = ""
        if ae.get("ip_address") or ae.get("port"):
            ip = ae.get("ip_address") or ""
            port = f":{ae['port']}" if ae.get("port") else ""
            endpoint = f" [{ip}{port}]"
        parts.append(f"{ae['ae_title']}{label}{endpoint}")
    return "; ".join(parts)


def _format_routes(routes: list[dict[str, Any]]) -> str:
    parts = []
    for r in routes:
        dest = r.get("destination_name") or ""
        direction = r.get("direction") or "Send"
        parts.append(f"{direction} -> {dest}")
    return "; ".join(parts)


def export_csv(modalities: list[dict[str, Any]], field_defs: list[dict[str, Any]]) -> str:
    """Export modalities, AE titles, routes, and active custom fields to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    custom_headers = [f["label"] for f in field_defs]
    writer.writerow(
        [
            "ID",
            "Device Name",
            "Modality Type",
            "Manufacturer",
            "Model",
            "Location",
            "Primary IP",
            "Status",
            "AE Titles",
            "Routes",
            "Notes",
            *custom_headers,
            "Updated At",
        ]
    )

    for m in modalities:
        cf = m.get("custom_fields") or {}
        custom_vals = [cf.get(f["key"], "") for f in field_defs]
        writer.writerow(
            [
                m["id"],
                m["device_name"],
                m["modality_type"],
                m["manufacturer"],
                m["model"],
                m["location"],
                m["ip_address"],
                m["status"],
                _format_ae_titles(m.get("ae_titles", [])),
                _format_routes(m.get("routes", [])),
                m["notes"],
                *custom_vals,
                m["updated_at"],
            ]
        )

    return output.getvalue()


def _style_header(ws: Any) -> None:
    fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
    ws.freeze_panes = "A2"


def _autofit(ws: Any) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)


def export_xlsx(
    modalities: list[dict[str, Any]],
    destinations: list[dict[str, Any]],
    field_defs: list[dict[str, Any]],
) -> bytes:
    """Export a multi-sheet Excel workbook (Modalities, AE Titles, Routes, Destinations)."""
    wb = Workbook()

    # Sheet 1: Modalities
    ws_mod = wb.active
    ws_mod.title = "Modalities"
    custom_headers = [f["label"] for f in field_defs]
    ws_mod.append(
        [
            "ID",
            "Device Name",
            "Type",
            "Manufacturer",
            "Model",
            "Location",
            "Primary IP",
            "Status",
            "AE Titles",
            "Notes",
            *custom_headers,
            "Updated At",
        ]
    )
    for m in modalities:
        cf = m.get("custom_fields") or {}
        ws_mod.append(
            [
                m["id"],
                m["device_name"],
                m["modality_type"],
                m["manufacturer"],
                m["model"],
                m["location"],
                m["ip_address"],
                m["status"],
                _format_ae_titles(m.get("ae_titles", [])),
                m["notes"],
                *[cf.get(f["key"], "") for f in field_defs],
                m["updated_at"],
            ]
        )
    _style_header(ws_mod)
    _autofit(ws_mod)

    # Sheet 2: AE Titles
    ws_ae = wb.create_sheet("AE Titles")
    ws_ae.append(["Modality ID", "Device Name", "AE Title", "Role", "IP Override", "Port", "Notes"])
    for m in modalities:
        for ae in m.get("ae_titles", []):
            ws_ae.append(
                [
                    m["id"],
                    m["device_name"],
                    ae["ae_title"],
                    ae.get("role_label", ""),
                    ae.get("ip_address", ""),
                    ae.get("port") or "",
                    ae.get("notes", ""),
                ]
            )
    _style_header(ws_ae)
    _autofit(ws_ae)

    # Sheet 3: Routes
    ws_rt = wb.create_sheet("Routes")
    ws_rt.append(["Modality ID", "Device Name", "Source AE Title", "Direction", "Destination", "Notes"])
    for m in modalities:
        for rt in m.get("routes", []):
            ws_rt.append(
                [
                    m["id"],
                    m["device_name"],
                    rt.get("ae_title") or "",
                    rt.get("direction", "Send"),
                    rt.get("destination_name", ""),
                    rt.get("notes", ""),
                ]
            )
    _style_header(ws_rt)
    _autofit(ws_rt)

    # Sheet 4: Destinations
    ws_dst = wb.create_sheet("Destinations")
    ws_dst.append(["ID", "Name", "Type", "AE Title", "IP Address", "Port", "Notes"])
    for d in destinations:
        ws_dst.append(
            [
                d["id"],
                d["name"],
                d["dest_type"],
                d["ae_title"],
                d["ip_address"],
                d["port"] or "",
                d["notes"],
            ]
        )
    _style_header(ws_dst)
    _autofit(ws_dst)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
