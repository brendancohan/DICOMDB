import io

from docx import Document
from fastapi.testclient import TestClient

from app.docx_importer import extract_docx_data


def _sample_docx_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph("CT Room 3 Configuration")
    doc.add_paragraph("AE Title: CT3_STORE")
    doc.add_paragraph("IP: 10.50.2.15 Port: 104")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_docx_data() -> None:
    data = extract_docx_data(_sample_docx_bytes(), filename="CT_Room_3.docx")
    assert data["suggestions"]["modality_type"] == "CT"
    assert "10.50.2.15" in data["suggestions"]["ip_addresses"]
    assert 104 in data["suggestions"]["ports"]
    assert "CT3_STORE" in data["suggestions"]["ae_titles"]


def test_import_parse_route(authed_client: TestClient) -> None:
    resp = authed_client.post(
        "/import/parse",
        files={"file": ("CT_Room_3.docx", _sample_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200
    assert "CT3_STORE" in resp.text
    assert "10.50.2.15" in resp.text
