def test_create_repayment_success(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-001",
            user_id=user["user_id"],
            customer_name="返済テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-001",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-001",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-001",
            "repayment_amount": "30000",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        repayment = Repayment.query.filter_by(
            loan_id="L20260831-REPAY-001"
        ).first()

        assert repayment is not None
        assert repayment.user_id == user["user_id"]
        assert repayment.customer_id == "CUST-REPAY-001"
        assert repayment.repayment_amount == 30000
        assert repayment.repayment_date == "2026-08-31"
        assert repayment.payment_type == "REPAYMENT"

def test_create_repayment_with_nonexistent_loan(
    app,
    client,
    user,
):
    from app import Repayment

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "NO-SUCH-LOAN",
            "repayment_amount": "10000",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "存在しない loan_id です。".encode("utf-8") in response.data

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_repayment_with_zero_amount(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-ZERO",
            user_id=user["user_id"],
            customer_name="ゼロ円返済テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-ZERO",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-ZERO",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-ZERO",
            "repayment_amount": "0",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "返済金額は1円以上で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_repayment_over_normal_remaining(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-OVER",
            user_id=user["user_id"],
            customer_name="過払いテスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-OVER",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-OVER",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-OVER",
            "repayment_amount": "120000",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert (
        "通常返済額が通常残高を超えています。通常残高は 110000 円です。"
        .encode("utf-8")
        in response.data
    )

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_repayment_for_cancelled_loan(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-CANCEL",
            user_id=user["user_id"],
            customer_name="取消済み返済テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-CANCEL",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-CANCEL",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="CANCELLED",
            cancelled_at="2026-08-20 12:00:00",
            cancel_reason="テスト取消",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-CANCEL",
            "repayment_amount": "10000",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "取消済みの貸付には返済登録できません。".encode("utf-8") in response.data

    with app.app_context():
        assert Repayment.query.count() == 0

def test_create_repayment_with_invalid_amount(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-INVALID",
            user_id=user["user_id"],
            customer_name="返済額形式テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-INVALID",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-INVALID",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-INVALID",
            "repayment_amount": "abc",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "返済金額は数値で入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_repayment_before_loan_date(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-DATE",
            user_id=user["user_id"],
            customer_name="返済日テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-DATE",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-DATE",
            loan_amount=100000,
            loan_date="2026-08-10",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-DATE",
            "repayment_amount": "10000",
            "repayment_date": "2026-08-01",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "返済日は貸付日以降の日付を入力してください。".encode("utf-8") in response.data

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_repayment_after_normal_repayment_completed(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-REPAY-COMPLETE",
            user_id=user["user_id"],
            customer_name="完済テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-REPAY-COMPLETE",
            user_id=user["user_id"],
            customer_id="CUST-REPAY-COMPLETE",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=3,
            late_fee_rate_percent=5.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        completed_repayment = Repayment(
            user_id=user["user_id"],
            loan_id="L20260831-REPAY-COMPLETE",
            customer_id="CUST-REPAY-COMPLETE",
            repayment_amount=110000,
            repayment_date="2026-08-20",
            payment_type="REPAYMENT",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.add(completed_repayment)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-REPAY-COMPLETE",
            "repayment_amount": "1000",
            "repayment_date": "2026-08-31",
            "payment_type": "REPAYMENT",
        },
    )

    assert response.status_code == 200
    assert "この貸付は通常返済がすでに完了しています。".encode("utf-8") in response.data

    with app.app_context():
        repayments = Repayment.query.filter_by(
            loan_id="L20260831-REPAY-COMPLETE"
        ).all()

        assert len(repayments) == 1
        assert repayments[0].repayment_amount == 110000

def test_create_late_fee_repayment_success(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LATE-001",
            user_id=user["user_id"],
            customer_name="延滞手数料テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-LATE-001",
            user_id=user["user_id"],
            customer_id="CUST-LATE-001",
            loan_amount=100000,
            loan_date="2026-07-01",
            due_date="2026-07-31",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=6.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-LATE-001",
            "repayment_amount": "3000",
            "repayment_date": "2026-08-31",
            "payment_type": "LATE_FEE",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        repayment = Repayment.query.filter_by(
            loan_id="L20260831-LATE-001",
            payment_type="LATE_FEE",
        ).first()

        assert repayment is not None
        assert repayment.user_id == user["user_id"]
        assert repayment.customer_id == "CUST-LATE-001"
        assert repayment.repayment_amount == 3000
        assert repayment.payment_type == "LATE_FEE"


def test_create_late_fee_repayment_when_not_overdue(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LATE-NOT-OVERDUE",
            user_id=user["user_id"],
            customer_name="未延滞テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-LATE-NOT-OVERDUE",
            user_id=user["user_id"],
            customer_id="CUST-LATE-NOT-OVERDUE",
            loan_amount=100000,
            loan_date="2026-08-01",
            due_date="2026-09-30",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=6.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-LATE-NOT-OVERDUE",
            "repayment_amount": "1000",
            "repayment_date": "2026-08-31",
            "payment_type": "LATE_FEE",
        },
    )

    assert response.status_code == 200
    assert (
        "この貸付には現在、延滞手数料が発生していません。"
        .encode("utf-8")
        in response.data
    )

    with app.app_context():
        assert Repayment.query.count() == 0


def test_create_late_fee_repayment_over_remaining(
    app,
    client,
    user,
):
    from app import Customer, Loan, Repayment, db, now_str

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LATE-OVER",
            user_id=user["user_id"],
            customer_name="延滞手数料過払いテスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-LATE-OVER",
            user_id=user["user_id"],
            customer_id="CUST-LATE-OVER",
            loan_amount=100000,
            loan_date="2026-07-01",
            due_date="2026-07-31",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=6.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-LATE-OVER",
            "repayment_amount": "10000",
            "repayment_date": "2026-08-31",
            "payment_type": "LATE_FEE",
        },
    )

    assert response.status_code == 200
    assert (
        "延滞手数料返済額が延滞手数料残額を超えています。"
        .encode("utf-8")
        in response.data
    )

    with app.app_context():
        assert Repayment.query.count() == 0

def test_create_late_fee_repayment_after_late_fee_paid(
    app,
    client,
    user,
    monkeypatch,
):
    import app as app_module
    from app import Customer, Loan, Repayment, db, now_str

    class FixedDate(app_module.date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 31)

    monkeypatch.setattr(app_module, "date", FixedDate)

    with app.app_context():
        customer = Customer(
            customer_id="CUST-LATE-PAID",
            user_id=user["user_id"],
            customer_name="延滞手数料完済テスト顧客",
            credit_limit=300000,
            created_at=now_str(),
        )

        loan = Loan(
            loan_id="L20260831-LATE-PAID",
            user_id=user["user_id"],
            customer_id="CUST-LATE-PAID",
            loan_amount=100000,
            loan_date="2026-07-01",
            due_date="2026-07-31",
            interest_rate_percent=10.0,
            repayment_expected=110000,
            repayment_method="一括",
            grace_period_days=0,
            late_fee_rate_percent=6.0,
            late_base_amount=100000,
            contract_status="ACTIVE",
            cancelled_at="",
            cancel_reason="",
            notes="",
            created_at=now_str(),
        )

        paid_late_fee = Repayment(
            user_id=user["user_id"],
            loan_id="L20260831-LATE-PAID",
            customer_id="CUST-LATE-PAID",
            repayment_amount=6200,
            repayment_date="2026-08-31",
            payment_type="LATE_FEE",
            created_at=now_str(),
        )

        db.session.add(customer)
        db.session.add(loan)
        db.session.add(paid_late_fee)
        db.session.commit()

    client.post(
        "/login",
        data={
            "username": user["username"],
            "password": user["password"],
        },
    )

    response = client.post(
        "/repayments/new",
        data={
            "loan_id": "L20260831-LATE-PAID",
            "repayment_amount": "100",
            "repayment_date": "2026-08-31",
            "payment_type": "LATE_FEE",
        },
    )

    assert response.status_code == 200
    assert (
        "この貸付の延滞手数料はすでに支払い済みです。"
        .encode("utf-8")
        in response.data
    )

    with app.app_context():
        repayments = Repayment.query.filter_by(
            loan_id="L20260831-LATE-PAID",
            payment_type="LATE_FEE",
        ).all()

        assert len(repayments) == 1