from fastapi.testclient import TestClient


def test_unauthenticated_redirects_to_login(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_and_logout(client: TestClient) -> None:
    bad = client.post("/login", data={"username": "pacsadmin", "password": "wrong"})
    assert bad.status_code == 401

    good = client.post(
        "/login",
        data={"username": "pacsadmin", "password": "changeme"},
        follow_redirects=False,
    )
    assert good.status_code == 303
    assert good.headers["location"] == "/"

    home = client.get("/")
    assert home.status_code == 200
    assert "Modality Inventory" in home.text

    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/login"
