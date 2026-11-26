from fastapi.testclient import TestClient

from app.dicom_utils import validate_ae_title


def test_validate_ae_title() -> None:
    assert validate_ae_title("CT1_STORE") == []
    assert any("16 characters" in e for e in validate_ae_title("THIS_AE_TITLE_IS_TOO_LONG"))
    assert any("backslash" in e for e in validate_ae_title("BAD\\AET"))


def test_conflicts_page_detects_duplicates(authed_client: TestClient) -> None:
    for name in ("Device A", "Device B"):
        authed_client.post(
            "/modalities/new",
            data={
                "device_name": name,
                "modality_type": "DX",
                "ip_address": "10.30.1.10",
                "status": "Active",
                "ae_title": ["DUP_AET"],
                "ae_port": ["104"],
            },
            follow_redirects=False,
        )

    conflicts = authed_client.get("/conflicts")
    assert conflicts.status_code == 200
    assert "DUP_AET" in conflicts.text
    assert "10.30.1.10:104" in conflicts.text
