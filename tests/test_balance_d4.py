import csv
import io
from pathlib import Path
from contextlib import redirect_stdout

from modules.balance_module import display_balance

def test_balance_ignores_late_fee(tmp_path, monkeypatch):
    loans = tmp_path / "loan_v3.csv"
    reps  = tmp_path / "repayments.csv"

    loans.write_text(
        "loan_id,customer_id,loan_amount,loan_date,interest_rate_percent,"
        "repayment_expected,repayment_method,grace_period_days,"
        "late_fee_rate_percent,late_base_amount,contract_status\n"
        "L1,C001,10000,2025-01-01,100,20000,CASH,0,10,10000,ACTIVE\n",
        encoding="utf-8"
    )

    with reps.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["loan_id","customer_id","repayment_amount","repayment_date","payment_type"])
        w.writerow(["L1","C001","5000","2025-01-10","REPAYMENT"])
        w.writerow(["L1","C001","3000","2025-01-15","LATE_FEE"])

    monkeypatch.setattr(
        "modules.balance_module.get_project_paths",
        lambda: {"loans_csv": loans, "repayments_csv": reps},
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        display_balance("C001")

    out = buf.getvalue()
    assert "¥20,000" in out      # expected
    assert "¥5,000" in out       # REPAYMENTのみ
    assert "¥15,000" in out      # 残高
