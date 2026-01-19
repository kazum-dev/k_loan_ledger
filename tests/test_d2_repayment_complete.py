import csv
from modules.loan_module import register_repayment_complete

LOANS_HEADER = [
    "loan_id",
    "customer_id",
    "loan_amount",
    "loan_date",
    "due_date",
    "interest_rate_percent",
    "repayment_expected",
    "repayment_method",
    "grace_period_days",
    "late_fee_rate_percent",
    "late_base_amount",
    "contract_status",
    "cancelled_at",
    "cancel_reason",
    "notes",
]


def write_loans(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOANS_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_repayments(path, rows):
    header = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_repayments(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def base_loan(**kw):
    base = {k: "" for k in LOANS_HEADER}
    base.update(
        {
            "loan_id": "L001",
            "customer_id": "CUST001",
            "repayment_expected": "1000",
            "contract_status": "ACTIVE",
        }
    )
    base.update(kw)
    return base


def test_success(tmp_path):
    loans = tmp_path / "loan_v3.csv"
    reps = tmp_path / "repayments.csv"

    write_loans(loans, [base_loan()])

    row = register_repayment_complete(
        loans_file=str(loans),
        repayments_file=str(reps),
        loan_id="L001",
        amount=500,
        repayment_date="2025-12-22",
        actor="TEST",
    )

    assert row is not None

    got = read_repayments(reps)
    assert len(got) == 1
    assert got[0]["loan_id"] == "L001"
    assert got[0]["repayment_amount"] == "500"


def test_loan_id_not_found(tmp_path):
    loans = tmp_path / "loan_v3.csv"
    reps = tmp_path / "repayments.csv"

    write_loans(loans, [])

    row = register_repayment_complete(
        loans_file=str(loans),
        repayments_file=str(reps),
        loan_id="NOPE",
        amount=100,
        repayment_date="2025-12-22",
        actor="TEST",
    )
    assert row is None


def test_overpayment_blocked(tmp_path):
    loans = tmp_path / "loan_v3.csv"
    reps = tmp_path / "repayments.csv"

    write_loans(loans, [base_loan(repayment_expected="1000")])

    write_repayments(
        reps,
        [
            {
                "loan_id": "L001",
                "customer_id": "CUST001",
                "repayment_amount": "900",
                "repayment_date": "2025-12-20",
            }
        ],
    )

    row = register_repayment_complete(
        loans_file=str(loans),
        repayments_file=str(reps),
        loan_id="L001",
        amount=200,
        repayment_date="2025-12-22",
        actor="TEST",
    )
    assert row is None

def test_d21_exact_remaining_allowed(tmp_path):
    from modules.loan_module import register_repayment_complete

    loans = tmp_path / "loan_v3.csv"
    reps  = tmp_path / "repayments.csv"

    loans.write_text(
        "loan_id,customer_id,loan_amount,loan_date,due_date,"
        "interest_rate_percent,repayment_expected,repayment_method,"
        "grace_period_days,late_fee_rate_percent,late_base_amount,contract_status\n"
        "L1,C001,10000,2025-01-01,2025-01-10,100,20000,CASH,0,10,10000,ACTIVE\n",
        encoding="utf-8"
    )

    reps.write_text(
        "loan_id,customer_id,repayment_amount,repayment_date,payment_type\n"
        "L1,C001,15000,2025-01-05,REPAYMENT\n",
        encoding="utf-8"
    )

    result = register_repayment_complete(
        loans_file=str(loans),
        repayments_file=str(reps),
        loan_id="L1",
        amount=5000,   # 残りちょうど
        repayment_date="2025-01-20",
    )

    assert result is not None
    assert result["repayment_part"] == 5000
