import os, csv
from tempfile import TemporaryDirectory
import modules.utils as u

def _write(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames); w.writeheader(); w.writerows(rows)

def test_c45_migration_rewrites_all(monkeypatch):
    with TemporaryDirectory() as tmp:
        data = os.path.join(tmp,"data"); os.makedirs(data, exist_ok=True)
        loans = os.path.join(data,"loan_v3.csv")

        def fake_paths(_=None):
            return {"root": tmp, "modules": os.path.join(tmp,"modules"),
                    "data": data, "loans_csv": loans,
                    "repayments_csv": os.path.join(data,"repayments.csv")}

        # ① utils 側を差し替え
        monkeypatch.setattr(u, "get_project_paths", fake_paths, raising=False)

        fn = ["loan_id","customer_id","loan_amount","loan_date","due_date",
              "interest_rate_percent","repayment_expected","repayment_method",
              "grace_period_days","late_fee_rate_percent","late_base_amount"]
        rows = [
            dict(loan_id="L1", customer_id="C1", loan_amount="1000.9", loan_date="2025-01-01",
                 due_date="2025-02-01", interest_rate_percent="10.0", repayment_expected="1101",
                 repayment_method="CASH", grace_period_days="0", late_fee_rate_percent="10.0",
                 late_base_amount="999"),
            dict(loan_id="L2", customer_id="C2", loan_amount="2000", loan_date="2025-01-01",
                 due_date="2025-02-01", interest_rate_percent="10.0", repayment_expected="2200",
                 repayment_method="UNKNOWN", grace_period_days="0", late_fee_rate_percent="10.0",
                 late_base_amount="2001"),
        ]
        _write(loans, fn, rows)

        import scripts.migrate_c45_fix_late_base as mig

        # ② migration モジュール内のローカル名も差し替え（これがポイント）
        monkeypatch.setattr(mig, "get_project_paths", fake_paths, raising=False)

        # 念のため存在チェック
        assert os.path.exists(loans)

        r = mig.run()
        assert r["updated"] == 2

        with open(loans, newline="", encoding="utf-8") as f:
            got = list(csv.DictReader(f))
        assert [int(float(x["late_base_amount"])) for x in got] == [1000, 2000]
