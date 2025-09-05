# tests/c1_prep_make_sample_repayment.py
from pathlib import Path
import csv
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
loans = ROOT / "data" / "loan_v3.csv"
repays = ROOT / "data" / "repayments.csv"

assert loans.exists(), f"loan_v3.csv が見つかりません: {loans}"

# loan_v3.csv の先頭1件から loan_id / customer_id を拾う
with open(loans, "r", encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    first = next(r, None)
    if not first:
        raise SystemExit("loan_v3.csv が空です。")
    loan_id = first["loan_id"]
    customer_id = first.get("customer_id", "CUST000")

# repayments.csv に 1,000円の返済を1行追記（ヘッダ保証）
need_header = not repays.exists() or repays.stat().st_size == 0
with open(repays, "a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["loan_id","customer_id","repayment_amount","repayment_date"])
    if need_header:
        w.writeheader()
    w.writerow({
        "loan_id": loan_id,
        "customer_id": customer_id,
        "repayment_amount": 1000,
        "repayment_date": str(date(2025,9,5))
    })

print(f"[OK] サンプル返済を追加: loan_id={loan_id}, customer_id={customer_id}, amount=1000")
print(f"repayments.csv -> {repays}")
