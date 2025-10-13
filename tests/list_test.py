from datetime import date
from modules.loan_module import register_loan, display_unpaid_loans

# 期限内
register_loan(
    "CUSTA",
    5000,
    "2025-09-29",
    "2025-10-10",
    10.0,
    "CASH",
    3,
    10.0,
    file_path="loan_v3_test.csv",
)
# 延滞（猶予5日でも超えてる）
register_loan(
    "CUSTA",
    7000,
    "2025-09-10",
    "2025-09-20",
    10.0,
    "CASH",
    5,
    10.0,
    file_path="loan_v3_test.csv",
)

display_unpaid_loans(
    "CUSTA",
    loan_file="loan_v3_test.csv",
    repayment_file="repayments.csv",
    filter_mode="all",
    today=date(2025, 10, 1),
)
display_unpaid_loans(
    "CUSTA",
    loan_file="loan_v3_test.csv",
    repayment_file="repayments.csv",
    filter_mode="overdue",
    today=date(2025, 10, 1),
)
