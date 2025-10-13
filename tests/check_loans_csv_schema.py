# tests/check_loans_csv_schema.py
from pathlib import Path
import csv
from modules.utils import normalize_method

p = Path("data/loan_v3.csv")
problems = []
allowed_methods = {"CASH", "BANK_TRANSFER", "OTHER", "UNKNOWN"}

with p.open("r", encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    headers = r.fieldnames or []
    for i, row in enumerate(r, start=2):  # 1行目ヘッダ、データは2行目〜
        # 1) 必須列の存在と空値
        required = [
            "loan_id",
            "customer_id",
            "loan_amount",
            "loan_date",
            "repayment_expected",
            "repayment_method",
            "grace_period_days",
            "late_fee_rate_percent",
            "late_base_amount",
        ]
        missing = [h for h in required if h not in row or row[h] == ""]
        # 2) 返済方法の正規化確認
        raw_method = (row.get("repayment_method") or "").strip()
        norm_method = normalize_method(raw_method)
        bad_method = norm_method not in allowed_methods

        # 3) 数値列の型チェック
        def is_int_like(x):
            try:
                int(float(x))
                return True
            except:
                return False

        def is_float_like(x):
            try:
                float(x)
                return True
            except:
                return False

        bad_types = []
        if not is_int_like(row.get("grace_period_days", "0")):
            bad_types.append("grace_period_days")
        if not is_float_like(row.get("late_fee_rate_percent", "")):
            bad_types.append("late_fee_rate_percent")
        if not is_int_like(row.get("late_base_amount", "")):
            bad_types.append("late_base_amount")

        if missing or bad_method or bad_types:
            problems.append(
                {
                    "line": i,
                    "loan_id": row.get("loan_id"),
                    "missing": missing,
                    "raw_method": raw_method,
                    "norm_method": norm_method,
                    "bad_types": bad_types,
                }
            )

print(f"[INFO] headers={headers}")
if not problems:
    print("[OK] 問題なし")
else:
    print(f"[WARN] 問題のある行: {len(problems)} 件")
    for p in problems:
        print(p)
