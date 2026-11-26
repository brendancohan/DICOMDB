import re
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


def test_clone_modality(authed_client: TestClient) -> None:
    created = authed_client.post(
        "/modalities/new",
        data={
            "device_name": "US Room 4",
            "modality_type": "US",
            "manufacturer": "Philips",
            "model": "EPIQ 7",
            "location": "Ultrasound",
            "ip_address": "10.10.4.4",
            "status": "Active",
            "ae_title": ["US4_STORE"],
            "ae_role_label": ["Store"],
            "ae_port": ["104"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    detail_url = created.headers["location"]

    clone_page = authed_client.get(f"{detail_url}/clone")
    assert clone_page.status_code == 200
    assert "US Room 4 (Copy)" in clone_page.text
    assert "Philips" in clone_page.text
    assert "EPIQ 7" in clone_page.text
    assert "US4_STORE" not in clone_page.text


def test_calling_aet_setting_and_echo_override(authed_client: TestClient, monkeypatch) -> None:
    bad = authed_client.post(
        "/backup/settings",
        data={"calling_aet": "THIS_AET_IS_WAY_TOO_LONG"},
    )
    assert bad.status_code == 400
    assert "Invalid Calling AE Title" in bad.text

    good = authed_client.post(
        "/backup/settings",
        data={"calling_aet": "PACS_ADMIN_AE"},
    )
    assert good.status_code == 200
    assert "PACS_ADMIN_AE" in good.text

    captured = {}

    def fake_echo(host, port, called_aet, calling_aet="DICOMDB", timeout=5.0):
        captured["calling_aet"] = calling_aet
        return {"ok": True, "status": "0x0000", "latency_ms": 1.0, "message": "OK"}

    monkeypatch.setattr("app.routes.modality_routes.test_dicom_echo", fake_echo)

    # Uses DB default when omitted
    r1 = authed_client.post(
        "/api/test-echo",
        json={"host": "10.0.0.1", "port": 104, "called_aet": "CT1"},
    )
    assert r1.status_code == 200
    assert captured["calling_aet"] == "PACS_ADMIN_AE"

    # Uses per-test override when provided
    r2 = authed_client.post(
        "/api/test-echo",
        json={"host": "10.0.0.1", "port": 104, "called_aet": "CT1", "calling_aet": "CUSTOM_AE"},
    )
    assert r2.status_code == 200
    assert captured["calling_aet"] == "CUSTOM_AE"


def test_change_password_and_safety_download(authed_client: TestClient) -> None:
    bad_pw = authed_client.post(
        "/backup/password",
        data={
            "current_password": "wrong",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert bad_pw.status_code == 400
    assert "incorrect" in bad_pw.text

    ok_pw = authed_client.post(
        "/backup/password",
        data={
            "current_password": "changeme",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert ok_pw.status_code == 200
    assert "updated" in ok_pw.text

    authed_client.post("/logout", follow_redirects=False)
    login_new = authed_client.post(
        "/login",
        data={"username": "pacsadmin", "password": "newpass123"},
        follow_redirects=False,
    )
    assert login_new.status_code == 303

    # Trigger a restore to create a safety snapshot, then download it
    backup_bytes = authed_client.get("/backup/download").content
    restored = authed_client.post(
        "/backup/restore",
        files={"file": ("b.db", backup_bytes, "application/octet-stream")},
    )
    assert restored.status_code == 200
    m = re.search(r"(pre_restore_\d{8}_\d{6}\.db)", restored.text)
    assert m is not None
    safety_name = m.group(1)

    dl = authed_client.get(f"/backup/safety/{safety_name}")
    assert dl.status_code == 200
    assert dl.content[:16] == b"SQLite format 3\x00"

    bad_name = authed_client.get("/backup/safety/..%2F..%2Fetc%2Fpasswd")
    assert bad_name.status_code in (400, 404)
