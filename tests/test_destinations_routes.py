from fastapi.testclient import TestClient


def test_destinations_and_reverse_lookup(authed_client: TestClient) -> None:
    d_resp = authed_client.post(
        "/destinations",
        data={
            "name": "Main PACS",
            "dest_type": "PACS",
            "ae_title": "MAIN_PACS",
            "ip_address": "10.20.0.10",
            "port": "104",
        },
        follow_redirects=False,
    )
    assert d_resp.status_code == 303

    m_resp = authed_client.post(
        "/modalities/new",
        data={
            "device_name": "US Room 2",
            "modality_type": "US",
            "status": "Active",
            "ae_title": ["US2_AE"],
            "ae_role_label": ["Store"],
            "route_destination_id": ["1"],
            "route_ae_index": ["0"],
            "route_direction": ["Send"],
            "route_notes": ["Primary archive"],
        },
        follow_redirects=False,
    )
    assert m_resp.status_code == 303

    dest_detail = authed_client.get("/destinations/1")
    assert dest_detail.status_code == 200
    assert "US Room 2" in dest_detail.text
    assert "US2_AE" in dest_detail.text
