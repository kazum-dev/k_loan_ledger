import unittest, tempfile, os, csv, io
from contextlib import redirect_stdout
from pathlib import Path
from modules.balance_module import display_balance

LOANS_HEADER = [
    "loan_id","customer_id","loan_amount","loan_date","interest_rate_percent",
    "repayment_expected","repayment_method","grace_period_days","late_fee_rate_percent","late_base_amount"
]
REPAY_HEADER = ["loan_id","customer_id","repayment_amount","repayment_date"]

class TestBalance(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.loans = os.path.join(self.tmpdir.name, "loan_v3.csv")
        self.reps  = os.path.join(self.tmpdir.name, "repayments.csv")

        with open(self.loans, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(LOANS_HEADER)
            w.writerow(["L1","C001","10000","2025-09-27","100.0","20000","CASH","0","10.0","10000"])
            w.writerow(["L2","C001","5000","2025-10-01","100.0","10000","BANK_TRANSFER","0","10.0","5000"])

        with open(self.reps, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(REPAY_HEADER)
            w.writerow(["L1","C001","15000","2025-10-20"])
            w.writerow(["L2","C001","2000","2025-10-21"])

        # paths ダミー（balance_moduleは dict で OK）
        self.paths = {"loans_csv": Path(self.loans), "repayments_csv": Path(self.reps)}

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_display_balance_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            display_balance("C001", paths=self.paths, clamp_negative=False)
        out = buf.getvalue()
        # 予定返済合計 = 20,000 + 10,000 = 30,000
        self.assertIn("¥30,000", out)
        # 返済合計 = 15,000 + 2,000 = 17,000
        self.assertIn("¥17,000", out)
        # 残高 = 13,000
        self.assertIn("¥13,000", out)

if __name__ == "__main__":
    unittest.main()
