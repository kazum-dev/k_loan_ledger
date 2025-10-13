# tests/c1_loan_smoke.py
# C-1（loan_module）入力→出力スモークテスト

from datetime import date
from pathlib import Path
import csv

from modules.utils import get_project_paths, fmt_currency
from modules.loan_module import (
    compute_recovery_amount,  # 9
    calc_overdue_days,  # 10
    calc_late_fee,  # 11
    calculate_total_repaid_by_loan_id,  # 12
    is_over_repayment,  # 13
)

print("=== A) 前提パス検出 ===")
paths = get_project_paths()
print("loans_csv:", paths["loans_csv"])
print("repayments_csv:", paths["repayments_csv"])
print()

print("=== B) 10) calc_overdue_days（期日+猶予→延滞日数） ===")
# 例：期日 9/01、猶予3日、今日 9/10 → 延滞6日（9/05〜9/10の手前でカウント想定）
from datetime import date

print(
    "case1:",
    calc_overdue_days(
        today=date(2025, 9, 10), due_date_str="2025-09-01", grace_period_days=3
    ),
)

print(
    "case2（当日以内）:",
    calc_overdue_days(
        today=date(2025, 9, 10), due_date_str="2025-09-01", grace_period_days=9
    ),
)

print()

print("=== C) 11) calc_late_fee（30日按分） ===")
# 月利10%を30日按分、ベース=11,000、延滞9日
print("late_fee(ex 11,000 @10%/mo, 9days):", calc_late_fee(11000, 10, 9))
# ベース金額, 月利%, 延滞日数 の順を仮定
print()

print("=== D) 9) compute_recovery_amount（各パラメータの効き方） ===")
from datetime import date

print(
    "base(expectedベース):",
    compute_recovery_amount(
        repayment_expected=11000,
        total_repaid=2000,
        today=date(2025, 9, 10),
        due_date_str="2025-09-01",
        grace_period_days=3,
        late_fee_rate_percent=10.0,  # 月利%
        # late_base_amount を省略 → expectedベース
    ),
)

print(
    "principalベース比較:",
    compute_recovery_amount(
        repayment_expected=11000,
        total_repaid=2000,
        today=date(2025, 9, 10),
        due_date_str="2025-09-01",
        grace_period_days=3,
        late_fee_rate_percent=10.0,
        late_base_amount=10000.0,  # ← 元本ベースで日割り
    ),
)

print(
    "当日内（延滞0のはず）:",
    compute_recovery_amount(
        repayment_expected=11000,
        total_repaid=2000,
        today=date(2025, 9, 10),
        due_date_str="2025-09-01",
        grace_period_days=9,  # ← 猶予で延滞0に
        late_fee_rate_percent=10.0,
    ),
)
print()

print("=== E) 12) calculate_total_repaid_by_loan_id（ヘッダ揺れ/BOM耐性） ===")
repay_csv = paths["repayments_csv"]
first_id = None
if Path(repay_csv).exists():
    with open(repay_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # loan_id（大文字小文字やBOM混入は関数側で吸収する前提）
            if (
                row.get("loan_id")
                or row.get("LOAN_ID")
                or next(iter(row.keys()), "").lower().startswith("loan")
            ):
                # できるだけ素直に拾う
                first_id = (
                    row.get("loan_id")
                    or row.get("LOAN_ID")
                    or row.get(
                        next(k for k in row.keys() if k.lower().startswith("loan"))
                    )
                )
                break

    if first_id:
        total = calculate_total_repaid_by_loan_id(repay_csv, first_id)  # ← 引数順修正
        print(f"found loan_id={first_id} -> total_repaid={fmt_currency(total)}")
    else:
        print("repayments.csv から loan_id が見つからなかったのでスキップ")
else:
    print("repayments.csv が存在しないためスキップ")
print()

print("=== F) 13) is_over_repayment（予定超過ブロック判定） ===")
print(
    "overpay? demo ->",
    is_over_repayment(
        paths["loans_csv"], paths["repayments_csv"], "L20250801-001", 5000
    ),
)
print()

print("--- 完了：9〜13の“効き方”を目で確認しよう ---")
