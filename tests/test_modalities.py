from fastapi.testclient import TestClient


def test_modality_crud_with_multiple_ae_titles(authed_client: TestClient) -> None:
    resp = authed_client.post(
        "/modalities/new",
        data={
            "device_name": "CT Scanner 1",
            "modality_type": "CT",
            "manufacturer": "GE",
            "model": "Revolution",
            "location": "Main Radiology",
            "ip_address": "10.10.1.50",
            "status": "Active",
            "notes": "Primary ED CT",
            "ae_title": ["CT1_STORE", "CT1_MWL"],
            "ae_role_label": ["Store", "MWL"],
            "ae_ip_address": ["", "10.10.1.51"],
            "ae_port": ["104", "105"],
            "ae_notes": ["", "Worklist"],
            "editor_label": "JDS",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    detail_url = resp.headers["location"]

    detail = authed_client.get(detail_url)
    assert detail.status_code == 200
    assert "CT Scanner 1" in detail.text
    assert "CT1_STORE" in detail.text
    assert "CT1_MWL" in detail.text

    search = authed_client.get("/?q=CT1_MWL")
    assert search.status_code == 200
    assert "CT Scanner 1" in search.text

    del_resp = authed_client.post(f"{detail_url}/delete", follow_redirects=False)
    assert del_resp.status_code == 303
    assert "CT Scanner 1" not in authed_client.get("/").text
