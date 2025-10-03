from modules.loan_module import register_loan
register_loan(
    customer_id="CUST999",
    amount=1000,
    loan_date="2025-09-29",
    due_date="2025-09-20",          # わざと過去期日
    interest_rate_percent=10.0,
    repayment_method="CASH",
    grace_period_days=5,
    late_fee_rate_percent=10.0,
    file_path="loan_v3_test.csv"
)
print("OK")
