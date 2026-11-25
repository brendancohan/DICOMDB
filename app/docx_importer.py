import io
import re
from pathlib import Path
from typing import Any

from docx import Document

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PORT_RE = re.compile(r"(?:port|:\s*)(\d{2,5})\b", re.IGNORECASE)
_AET_KEYWORD_RE = re.compile(
    r"(?:AE\s*Title|AET|Called\s*AE|Calling\s*AE|Station\s*AE)\s*[:=\-]?\s*([A-Za-z0-9_\-]{3,16})",
    re.IGNORECASE,
)
_MODALITY_TYPES = ("CT", "MR", "US", "DX", "CR", "MG", "XA", "NM", "PT", "RF")
_MODALITY_RE = re.compile(r"\b(" + "|".join(_MODALITY_TYPES) + r")\b")


def extract_docx_data(file_bytes: bytes, filename: str = "") -> dict[str, Any]:
    """Extract paragraphs, tables, and heuristic DICOM field suggestions from a .docx file."""
    doc = Document(io.BytesIO(file_bytes))

    paragraphs: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            paragraphs.append(text)

    tables: list[list[list[str]]] = []
    table_lines: list[str] = []
    for table in doc.tables:
        rows_data: list[list[str]] = []
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            if any(cells):
                rows_data.append(cells)
                table_lines.append(" | ".join(cells))
        if rows_data:
            tables.append(rows_data)

    full_text = "\n".join(paragraphs + table_lines)

    ips = list(dict.fromkeys(_IP_RE.findall(full_text)))
    ports = [
        int(p)
        for p in dict.fromkeys(_PORT_RE.findall(full_text))
        if 1 <= int(p) <= 65535
    ]
    ae_candidates = list(dict.fromkeys(_AET_KEYWORD_RE.findall(full_text)))

    modality_match = _MODALITY_RE.search(full_text) or _MODALITY_RE.search(filename)
    suggested_type = modality_match.group(1) if modality_match else "OTHER"

    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip() if filename else ""
    suggested_name = stem or (paragraphs[0][:80] if paragraphs else "")

    return {
        "filename": filename,
        "paragraphs": paragraphs,
        "tables": tables,
        "suggestions": {
            "device_name": suggested_name,
            "modality_type": suggested_type,
            "ip_address": ips[0] if ips else "",
            "ip_addresses": ips,
            "ports": ports,
            "ae_titles": ae_candidates,
        },
    }
