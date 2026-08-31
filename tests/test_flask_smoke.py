def test_login_page_get(client):
    response = client.get("/login")

    assert response.status_code == 200

def test_protected_page_redirects_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

def test_login_success(client, user):
    response = client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    response = client.get("/")

    assert response.status_code == 200

def test_login_wrong_password(client, user):
    response = client.post(
        "/login",
        data={
            "username": user["username"],
            "password": "wrong_password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

def test_logout_blocks_protected_page_again(client, user):
    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")