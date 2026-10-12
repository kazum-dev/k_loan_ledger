def test_failed_login_log_does_not_contain_credentials(
    app,
    client,
    caplog,
):
    username = "secret_test_username"
    password = "secret_test_password"

    with caplog.at_level("WARNING"):
        response = client.post(
            "/login",
            data={
                "username": username,
                "password": password,
            },
        )

    assert response.status_code == 200

    log_text = caplog.text

    assert "Login failed" in log_text
    assert username not in log_text
    assert password not in log_text


def test_successful_login_log_does_not_contain_password(
    app,
    client,
    user,
    caplog,
):
    with caplog.at_level("INFO"):
        response = client.post(
            "/login",
            data={
                "username": user["username"],
                "password": user["password"],
            },
            follow_redirects=False,
        )

    assert response.status_code == 302

    log_text = caplog.text

    assert "Login succeeded" in log_text
    assert f"user_id={user['user_id']}" in log_text
    assert user["password"] not in log_text