import unittest
from datetime import date, timedelta
from modules.loan_module import calc_overdue_days, calc_late_fee, compute_recovery_amount

class TestLateFee(unittest.TestCase):
    def test_overdue_days_with_grace(self):
        # 期日 10/10、猶予3日 → 10/13を越えたら延滞
        today = date(2025, 10, 15)
        self.assertEqual(calc_overdue_days(today, "2025-10-10", 3), 2)

    def test_calc_late_fee_month_fraction(self):
        # 月10%を30日で日割り、基礎額 10,000、延滞 30日 → 10,000 * 10% * (30/30) = 1,000
        fee = calc_late_fee(late_base_amount=10000, late_fee_rate_percent=10, overdue_days=30, month_days=30)
        self.assertEqual(round(fee), 1000)

    def test_compute_recovery_amount_pipeline(self):
        # 予定2万・既返済1.5万・延滞30日・月10%・基礎=予定
        info = compute_recovery_amount(
            repayment_expected=20000,
            total_repaid=15000,
            today=date(2025, 10, 27),
            due_date_str="2025-09-27",
            grace_period_days=0,
            late_fee_rate_percent=10.0,
            late_base_amount=None,   # 既定は予定返済額
        )
        # remaining=5000, late_fee≈20000*10%*(30/30)=2000 → int丸め後
        self.assertEqual(info["overdue_days"], 30)
        self.assertEqual(info["remaining"], 5000)
        self.assertEqual(info["late_fee"], 2000)
        self.assertEqual(info["recovery_total"], 7000)

if __name__ == "__main__":
    unittest.main()
