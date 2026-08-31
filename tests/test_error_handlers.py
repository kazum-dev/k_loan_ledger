def test_404_handler_after_login(
    client,
    user,
):
    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404

def test_500_handler_returns_custom_message(
    app,
    client,
    user,
):
    @app.route("/test-500")
    def test_500():
        raise RuntimeError("intentional test error")

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    original_testing = app.config["TESTING"]
    original_propagate = app.config.get("PROPAGATE_EXCEPTIONS")

    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    try:
        response = client.get("/test-500")
    finally:
        app.config["TESTING"] = original_testing
        app.config["PROPAGATE_EXCEPTIONS"] = original_propagate

    assert response.status_code == 500
    assert (
        "サーバー内部でエラーが発生しました。時間をおいて再度お試しください。"
        .encode("utf-8")
        in response.data
    )