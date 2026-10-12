import re


def extract_csrf_token(response):
    html = response.get_data(as_text=True)

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        html,
    )

    assert match is not None

    return match.group(1)


def test_login_without_csrf_token_is_rejected(
    app,
    client,
    user,
):
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_login_with_csrf_token_succeeds(
    app,
    client,
    user,
):
    app.config["WTF_CSRF_ENABLED"] = True

    login_page = client.get("/login")

    assert login_page.status_code == 200

    csrf_token = extract_csrf_token(login_page)

    response = client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302