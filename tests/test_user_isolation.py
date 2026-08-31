def test_customer_visibility_is_separated_by_user(
    app,
    client,
    user_a,
    user_b,
):
    from app import Customer, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-A-001",
            user_id=user_a["user_id"],
            customer_name="ユーザーAの顧客",
            credit_limit=100000,
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user_a["username"],
            "password": user_a["password"],
        },
    )

    response = client.get("/customers")

    assert response.status_code == 200
    assert "ユーザーAの顧客".encode("utf-8") in response.data

    client.post("/logout")

    client.post(
        "/login",
        data={
            "username": user_b["username"],
            "password": user_b["password"],
        },
    )

    response = client.get("/customers")

    assert response.status_code == 200
    assert "ユーザーAの顧客".encode("utf-8") not in response.data

def test_loan_visibility_is_separated_by_user(
    app,
    client,
    user_a,
    user_b,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-A-002",
            user_id=user_a["user_id"],
            customer_name="ユーザーAの貸付顧客",
            credit_limit=200000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-001",
            user_id=user_a["user_id"],
            customer_id="CUST-A-002",
            loan_amount=50000,
            loan_date="2026-08-01",
            due_date="2026-09-01",
            interest_rate_percent=10.0,
            repayment_expected=55000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=5.0,
            late_base_amount=55000,
            contract_status="ACTIVE",
            cancelled_at=None,
            cancel_reason=None,
            notes="user_a loan",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user_a["username"],
            "password": user_a["password"],
        },
    )

    response = client.get("/loans")

    assert response.status_code == 200
    assert b"L20260831-001" in response.data

    client.post("/logout")

    client.post(
        "/login",
        data={
            "username": user_b["username"],
            "password": user_b["password"],
        },
    )

    response = client.get("/loans")

    assert response.status_code == 200
    assert b"L20260831-001" not in response.data

def test_repayment_visibility_is_separated_by_user(
    app,
    client,
    user_a,
    user_b,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-A-003",
            user_id=user_a["user_id"],
            customer_name="ユーザーAの返済顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-002",
            user_id=user_a["user_id"],
            customer_id="CUST-A-003",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-01",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=5.0,
            late_base_amount=110000,
            contract_status="ACTIVE",
            cancelled_at=None,
            cancel_reason=None,
            notes="user_a repayment test",
            created_at=now_str(),
        )

        repayment = Repayment(
            user_id=user_a["user_id"],
            loan_id="L20260831-002",
            customer_id="CUST-A-003",
            repayment_amount=30000,
            repayment_date="2026-08-15",
            payment_type="REPAYMENT",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.add(repayment)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user_a["username"],
            "password": user_a["password"],
        },
    )

    response = client.get("/repayments")

    assert response.status_code == 200
    assert b"L20260831-002" in response.data

    client.post("/logout")

    client.post(
        "/login",
        data={
            "username": user_b["username"],
            "password": user_b["password"],
        },
    )

    response = client.get("/repayments")

    assert response.status_code == 200
    assert b"L20260831-002" not in response.data