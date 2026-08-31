def test_create_loan_success(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-001",
            user_id=user["user_id"],
            customer_name="貸付テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-001",
            "loan_amount": "100000",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "正常系テスト",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        loan = Loan.query.filter_by(
            customer_id="CUST-LOAN-001"
        ).first()

        assert loan is not None
        assert loan.user_id == user["user_id"]
        assert loan.loan_amount == 100000
        assert loan.loan_date == "2026-08-31"
        assert loan.due_date == "2026-09-30"
        assert loan.interest_rate_percent == 10.0
        assert loan.repayment_expected == 110000
        assert loan.grace_period_days == 3
        assert loan.late_fee_rate_percent == 5.0
        assert loan.late_base_amount == 100000
        assert loan.contract_status == "ACTIVE"
        assert loan.notes == "正常系テスト"

def test_create_loan_with_nonexistent_customer(
    app,
    client,
    user,
):
    from app import Loan

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "NO-SUCH-CUSTOMER",
            "loan_amount": "100000",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "存在しない顧客IDです。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_zero_amount(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-ZERO",
            user_id=user["user_id"],
            customer_name="ゼロ円テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-ZERO",
            "loan_amount": "0",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "貸付額は1円以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_due_date_before_loan_date(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-DATE",
            user_id=user["user_id"],
            customer_name="日付テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-DATE",
            "loan_amount": "100000",
            "loan_date": "2026-09-10",
            "due_date": "2026-09-01",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "返済期日は貸付日以降の日付を入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0

def test_create_loan_with_invalid_amount(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-AMOUNT",
            user_id=user["user_id"],
            customer_name="金額形式テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )
        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-AMOUNT",
            "loan_amount": "abc",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "貸付額は数値で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_negative_interest_rate(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-INTEREST",
            user_id=user["user_id"],
            customer_name="通常利率テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )
        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-INTEREST",
            "loan_amount": "100000",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "-1",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "通常利率は0以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_negative_grace_period(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-GRACE",
            user_id=user["user_id"],
            customer_name="猶予日数テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )
        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-GRACE",
            "loan_amount": "100000",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "-1",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "延滞猶予日数は0以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_negative_late_fee_rate(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-LATE",
            user_id=user["user_id"],
            customer_name="延滞利率テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )
        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-LATE",
            "loan_amount": "100000",
            "loan_date": "2026-08-31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "-1",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "延滞利率は0以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0


def test_create_loan_with_invalid_loan_date(
    app,
    client,
    user,
):
    from app import Customer, Loan, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LOAN-DATE-FORMAT",
            user_id=user["user_id"],
            customer_name="日付形式テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )
        db.session.add(customer)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/loans/new",
        data={
            "customer_id": "CUST-LOAN-DATE-FORMAT",
            "loan_amount": "100000",
            "loan_date": "2026/08/31",
            "due_date": "2026-09-30",
            "interest_rate_percent": "10",
            "repayment_method": "一括",
            "grace_period_days": "3",
            "late_fee_rate_percent": "5",
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert "貸付日の形式が正しくありません。".encode("utf-8") in response.data

    with app.app_context():
        assert Loan.query.count() == 0