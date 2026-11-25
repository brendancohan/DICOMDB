from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import ensure_default_password
from app.config import Settings
from app.database import get_connection, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = str(tmp_path / "test_dicomdb.db")
    test_settings = Settings(
        host="127.0.0.1",
        port=8000,
        db_path=db_file,
        secret_key="test-secret-key",
        username="pacsadmin",
        default_password="changeme",
        calling_aet="DICOMDB",
    )
    monkeypatch.setattr("app.config.settings", test_settings)
    monkeypatch.setattr("app.auth.settings", test_settings)
    monkeypatch.setattr("app.deps.settings", test_settings)
    monkeypatch.setattr("app.main.settings", test_settings)
    monkeypatch.setattr("app.routes.modality_routes.settings", test_settings)

    init_db(db_file)
    conn = get_connection(db_file)
    ensure_default_password(conn)
    conn.close()

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def authed_client(client: TestClient) -> TestClient:
    resp = client.post(
        "/login",
        data={"username": "pacsadmin", "password": "changeme"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client
