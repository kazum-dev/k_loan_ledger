from unittest.mock import patch
from modules.loan_module import register_repayment

# 対話入力をモックして実行
with patch(
    "builtins.input",
    side_effect=[
        "L20250929-004",  # loan_id（直前の貸付IDを使う）
        "CUST999",  # customer_id
        "200",  # 返済額
        "2025-09-30",  # 返済日
    ],
):
    register_repayment()
print("OK")
