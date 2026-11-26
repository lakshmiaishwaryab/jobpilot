from tests.conftest import register_and_login


def test_register_login_and_me(client):
    headers = register_and_login(client, "Ana@Example.com")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"
    assert me.json()["has_resume"] is False


def test_duplicate_email_rejected(client):
    body = {"email": "x@example.com", "full_name": "X", "password": "longenough"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409


def test_wrong_password(client):
    register_and_login(client)
    r = client.post("/auth/login", data={"username": "dev@example.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "full_name": "A", "password": "short"})
    assert r.status_code == 422


def test_protected_route_requires_token(client):
    assert client.get("/applications").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/applications", headers=bad).status_code == 401


def test_save_resume(client, auth):
    r = client.put("/auth/me/resume", json={"resume_text": "Python developer " * 10}, headers=auth)
    assert r.status_code == 200
    assert r.json()["has_resume"] is True
