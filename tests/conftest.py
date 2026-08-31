from werkzeug.security import generate_password_hash
import importlib
import sys

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_loan_ledger.db"
    test_database_url = f"sqlite:///{test_db_path.as_posix()}"

    monkeypatch.setenv("TEST_DATABASE_URL", test_database_url)

    if "app" in sys.modules:
        del sys.modules["app"]

    app_module = importlib.import_module("app")

    flask_app = app_module.app
    db = app_module.db

    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    database_uri = flask_app.config["SQLALCHEMY_DATABASE_URI"]

    assert database_uri.startswith("sqlite:///")
    assert "test_loan_ledger.db" in database_uri

    with flask_app.app_context():
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def user(app):
    from app import User, db, now_str

    test_user = User(
        username="test_user",
        password_hash=generate_password_hash("test_password"),
        role="USER",
        is_active=True,
        created_at=now_str(),
        updated_at=now_str(),
    )

    with app.app_context():
        db.session.add(test_user)
        db.session.commit()

        user_id = test_user.user_id

    return {
        "user_id": user_id,
        "username": "test_user",
        "password": "test_password",
    }

@pytest.fixture
def user_a(app):
    from app import User, db, now_str

    test_user = User(
        username="user_a",
        password_hash=generate_password_hash("password_a"),
        role="USER",
        is_active=True,
        created_at=now_str(),
        updated_at=now_str(),
    )

    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
        user_id = test_user.user_id

    return {
        "user_id": user_id,
        "username": "user_a",
        "password": "password_a",
    }

@pytest.fixture
def user_b(app):
    from app import User, db, now_str

    test_user = User(
        username="user_b",
        password_hash=generate_password_hash("password_b"),
        role="USER",
        is_active=True,
        created_at=now_str(),
        updated_at=now_str(),
    )

    with app.app_context():
        db.session.add(test_user)
        db.session.commit()
        user_id = test_user.user_id

    return {
        "user_id": user_id,
        "username": "user_b",
        "password": "password_b",
    }

@pytest.fixture
def client(app):
    return app.test_client()