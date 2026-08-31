def test_create_customer_success(
    app,
    client,
    user,
):
    from app import Customer, db

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-TEST-001",
            "customer_name": "テスト顧客",
            "credit_limit": "100000",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        customer = db.session.get(
            Customer,
            "CUST-TEST-001",
        )

        assert customer is not None
        assert customer.customer_name == "テスト顧客"
        assert customer.credit_limit == 100000
        assert customer.user_id == user["user_id"]

def test_create_customer_missing_name(
    app,
    client,
    user,
):
    from app import Customer

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-TEST-002",
            "customer_name": "",
            "credit_limit": "100000",
        },
    )

    assert response.status_code == 200
    assert "顧客名を入力してください。".encode("utf-8") in response.data

    with app.app_context():
        customer = Customer.query.filter_by(
            customer_id="CUST-TEST-002"
        ).first()

        assert customer is None


def test_create_customer_invalid_credit_limit(
    app,
    client,
    user,
):
    from app import Customer

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-TEST-003",
            "customer_name": "非数値テスト",
            "credit_limit": "abc",
        },
    )

    assert response.status_code == 200
    assert "貸付上限額は数値で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        customer = Customer.query.filter_by(
            customer_id="CUST-TEST-003"
        ).first()

        assert customer is None


def test_create_customer_zero_credit_limit(
    app,
    client,
    user,
):
    from app import Customer

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-TEST-004",
            "customer_name": "ゼロ円テスト",
            "credit_limit": "0",
        },
    )

    assert response.status_code == 200
    assert "貸付上限額は1円以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        customer = Customer.query.filter_by(
            customer_id="CUST-TEST-004"
        ).first()

        assert customer is None


def test_create_customer_negative_credit_limit(
    app,
    client,
    user,
):
    from app import Customer

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-TEST-005",
            "customer_name": "負数テスト",
            "credit_limit": "-1",
        },
    )

    assert response.status_code == 200
    assert "貸付上限額は1円以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        customer = Customer.query.filter_by(
            customer_id="CUST-TEST-005"
        ).first()

        assert customer is None

def test_create_customer_duplicate_customer_id(
    app,
    client,
    user,
):
    from app import Customer, db, now_str

    with app.app_context():
        existing_customer = Customer(
            customer_id="CUST-DUP-001",
            user_id=user["user_id"],
            customer_name="既存顧客",
            credit_limit=100000,
            created_at=now_str(),
        )

        db.session.add(existing_customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/customers/new",
        data={
            "customer_id": "CUST-DUP-001",
            "customer_name": "重複顧客",
            "credit_limit": "200000",
        },
    )

    assert response.status_code == 200
    assert "この顧客IDは使用できません。".encode("utf-8") in response.data

    with app.app_context():
        customers = Customer.query.filter_by(
            customer_id="CUST-DUP-001"
        ).all()

        assert len(customers) == 1
        assert customers[0].customer_name == "既存顧客"