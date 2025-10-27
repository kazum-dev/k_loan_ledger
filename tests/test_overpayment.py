import unittest, tempfile, os, csv
from modules.loan_module import is_over_repayment

LOANS_HEADER = [
    "loan_id","customer_id","loan_amount","loan_date","due_date",
    "interest_rate_percent","repayment_expected","repayment_method",
    "grace_period_days","late_fee_rate_percent","late_base_amount"
]
REPAY_HEADER = ["loan_id","customer_id","repayment_amount","repayment_date"]

class TestOverpayment(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.loans = os.path.join(self.tmpdir.name, "loan_v3.csv")
        self.reps  = os.path.join(self.tmpdir.name, "repayments.csv")

        with open(self.loans, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(LOANS_HEADER)
            # 予定返済 20,000 のローン
            w.writerow(["L20250927-001","C001","10000","2025-09-27","2025-10-27","100.0","20000","CASH","0","10.0","10000"])

        with open(self.reps, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(REPAY_HEADER)
            # 累計 15,000 返済済み
            w.writerow(["L20250927-001","C001","15000","2025-10-20"])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_reject_when_exceeds_remaining(self):
        # 残り5,000のところに 6,000 を入れようとすると False
        ok = is_over_repayment(self.loans, self.reps, "L20250927-001", 6000)
        self.assertFalse(ok)

    def test_accept_when_within_remaining(self):
        ok = is_over_repayment(self.loans, self.reps, "L20250927-001", 5000)
        self.assertTrue(ok)

if __name__ == "__main__":
    unittest.main()
