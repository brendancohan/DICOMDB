from fastapi.testclient import TestClient


def test_audit_log_and_exports(authed_client: TestClient) -> None:
    authed_client.post(
        "/modalities/new",
        data={
            "device_name": "Export CT",
            "modality_type": "CT",
            "status": "Active",
            "ae_title": ["EXP_CT"],
            "editor_label": "MK",
        },
        follow_redirects=False,
    )

    audit = authed_client.get("/audit")
    assert audit.status_code == 200
    assert "Export CT" in audit.text
    assert "MK" in audit.text

    csv_resp = authed_client.get("/export/csv")
    assert csv_resp.status_code == 200
    assert "Export CT" in csv_resp.text

    xlsx_resp = authed_client.get("/export/xlsx")
    assert xlsx_resp.status_code == 200
    assert xlsx_resp.content[:2] == b"PK"

    downtime = authed_client.get("/export/downtime")
    assert downtime.status_code == 200
    assert "Export CT" in downtime.text
