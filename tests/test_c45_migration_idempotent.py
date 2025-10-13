import os
from tempfile import TemporaryDirectory
import modules.utils as u

def test_c45_migration_idempotent(monkeypatch):
    with TemporaryDirectory() as tmp:
        data = os.path.join(tmp,"data"); os.makedirs(data, exist_ok=True)
        loans = os.path.join(data,"loan_v3.csv")

        monkeypatch.setattr(u, "get_project_paths", lambda _=None: {
            "root": tmp, "modules": os.path.join(tmp,"modules"),
            "data": data, "loans_csv": loans,
            "repayments_csv": os.path.join(data,"repayments.csv")
        }, raising=False)

        with open(loans, "w", encoding="utf-8") as f:
            f.write("loan_id,customer_id,loan_amount,loan_date,due_date,interest_rate_percent,repayment_expected,repayment_method,grace_period_days,late_fee_rate_percent,late_base_amount\n")
            f.write("L1,C1,1000,2025-01-01,2025-02-01,10.0,1100,CASH,0,10.0,999\n")

        import scripts.migrate_c45_fix_late_base as mig
        r1 = mig.run(); assert r1["updated"] == 1
        r2 = mig.run(); assert r2["updated"] == 0
