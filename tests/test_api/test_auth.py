"""Authentication endpoint tests."""


def test_register_user(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "password123",
        "display_name": "New User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["display_name"] == "New User"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_first_user_is_admin(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "first@example.com",
        "password": "password123",
    })
    assert response.status_code == 201
    assert response.json()["role"] == "admin"


def test_register_duplicate_email(client):
    client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "password123",
    })
    response = client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "password456",
    })
    assert response.status_code == 409


def test_login_correct_credentials(client):
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "mypassword",
    })
    response = client.post("/api/v1/auth/login", data={
        "username": "login@example.com",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "password": "correct",
    })
    response = client.post("/api/v1/auth/login", data={
        "username": "wrong@example.com",
        "password": "incorrect",
    })
    assert response.status_code == 401


def test_me_with_token(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_me_without_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
