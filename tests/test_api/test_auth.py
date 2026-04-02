"""Authentication endpoint tests."""


def test_register_user(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "username": "newuser",
        "password": "Pass123!",
        "display_name": "New User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["username"] == "newuser"
    assert data["display_name"] == "New User"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_first_user_is_admin(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "first@example.com",
        "username": "firstuser",
        "password": "First123!",
    })
    assert response.status_code == 201
    assert response.json()["role"] == "admin"


def test_register_duplicate_email(client):
    client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "username": "dupuser1",
        "password": "Dup12345!",
    })
    response = client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "username": "dupuser2",
        "password": "Dup45678!",
    })
    assert response.status_code == 409


def test_login_correct_credentials(client):
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "username": "loginuser",
        "password": "Login123!",
    })
    response = client.post("/api/v1/auth/login", data={
        "username": "login@example.com",
        "password": "Login123!",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "username": "wronguser",
        "password": "Wrong123!",
    })
    response = client.post("/api/v1/auth/login", data={
        "username": "wrong@example.com",
        "password": "Wrong456!",
    })
    assert response.status_code == 401


def test_me_with_token(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_me_without_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_register_weak_password_rejected(client):
    """Password without uppercase, digit, or special char is rejected."""
    response = client.post("/api/v1/auth/register", json={
        "email": "weak@example.com",
        "username": "weakuser",
        "password": "password123",
    })
    assert response.status_code == 422


def test_login_account_lockout(client):
    """After too many failed attempts, account is locked."""
    client.post("/api/v1/auth/register", json={
        "email": "lockout@example.com",
        "username": "lockoutuser",
        "password": "Lockout1!",
    })
    # 5 failed attempts should trigger lockout
    for _ in range(5):
        client.post("/api/v1/auth/login", data={
            "username": "lockout@example.com",
            "password": "WrongPass1!",
        })
    response = client.post("/api/v1/auth/login", data={
        "username": "lockout@example.com",
        "password": "WrongPass2!",
    })
    assert response.status_code == 429
    assert "locked" in response.json()["detail"].lower()
