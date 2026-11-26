from fastapi.testclient import TestClient


def test_dynamic_custom_fields_appear_in_form_and_table(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/fields",
        data={
            "label": "Software Version",
            "field_type": "text",
            "section": "Hardware",
            "show_in_table": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    form_page = authed_client.get("/modalities/new")
    assert "Software Version" in form_page.text
    assert "cf_software_version" in form_page.text

    created = authed_client.post(
        "/modalities/new",
        data={
            "device_name": "MRI 1",
            "modality_type": "MR",
            "status": "Active",
            "cf_software_version": "VA30A",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    inv = authed_client.get("/?q=VA30A")
    assert inv.status_code == 200
    assert "MRI 1" in inv.text
    assert "VA30A" in inv.text
