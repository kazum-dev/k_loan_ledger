from datetime import date
from modules.loan_module import (
    compute_effective_due,
    is_overdue_with_grace,
    calc_overdue_days,
    calc_late_fee,
    calculate_late_fee,
)

print("effective_due:", compute_effective_due("2025-09-25", 5))  # → 2025-09-30
print(
    "overdue A :", is_overdue_with_grace(date(2025, 9, 29), "2025-09-25", 5)
)  # → False
print(
    "overdue B :", is_overdue_with_grace(date(2025, 9, 29), "2025-09-20", 3)
)  # → True

od = calc_overdue_days(date.today(), "2025-09-20", 0)
fee_new = int(round(calc_late_fee(10000, 10.0, od)))
dl, fee_old = calculate_late_fee(10000, "2025-09-20", late_fee_rate_percent=10.0)

print("days(new,old):", od, dl)  # 一致するはず
print("fee (new,old):", fee_new, fee_old)  # ほぼ一致するはず
