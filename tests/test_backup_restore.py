import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient


def test_backup_page_and_download(authed_client: TestClient) -> None:
    page = authed_client.get("/backup")
    assert page.status_code == 200
    assert "Database Backup" in page.text

    dl = authed_client.get("/backup/download")
    assert dl.status_code == 200
    assert dl.content[:16] == b"SQLite format 3\x00"


def test_restore_rejects_invalid_files(authed_client: TestClient, tmp_path: Path) -> None:
    bad_text = authed_client.post(
        "/backup/restore",
        files={"file": ("not_a_db.db", b"not sqlite data at all", "application/octet-stream")},
    )
    assert bad_text.status_code == 400
    assert "not a valid SQLite database" in bad_text.text

    unrelated_db = tmp_path / "unrelated.db"
    conn = sqlite3.connect(str(unrelated_db))
    conn.execute("CREATE TABLE foo (id INTEGER)")
    conn.close()

    bad_schema = authed_client.post(
        "/backup/restore",
        files={"file": ("unrelated.db", unrelated_db.read_bytes(), "application/octet-stream")},
    )
    assert bad_schema.status_code == 400
    assert "missing required DicomDB tables" in bad_schema.text


def test_backup_and_restore_roundtrip(authed_client: TestClient) -> None:
    # Create a modality and download a backup
    created = authed_client.post(
        "/modalities/new",
        data={
            "device_name": "Backup Test CT",
            "modality_type": "CT",
            "status": "Active",
            "ae_title": ["BK_CT"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    detail_url = created.headers["location"]

    backup_bytes = authed_client.get("/backup/download").content

    # Delete the modality
    authed_client.post(f"{detail_url}/delete", follow_redirects=False)
    assert "Backup Test CT" not in authed_client.get("/").text

    # Restore from backup
    restored = authed_client.post(
        "/backup/restore",
        files={"file": ("backup.db", backup_bytes, "application/octet-stream")},
        data={"editor_label": "SYS"},
    )
    assert restored.status_code == 200
    assert "Database restored successfully" in restored.text
    assert "pre_restore_" in restored.text

    # Modality is back and restore is in audit log
    assert "Backup Test CT" in authed_client.get("/").text
    audit = authed_client.get("/audit")
    assert "restore" in audit.text
