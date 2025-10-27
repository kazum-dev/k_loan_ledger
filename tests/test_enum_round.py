import unittest
from modules.loan_module import _normalize_method_to_enum, RepaymentMethod, round_money as yen_round

class TestEnumRound(unittest.TestCase):
    def test_method_mapping(self):
        self.assertEqual(_normalize_method_to_enum("現金"), RepaymentMethod.CASH)
        self.assertEqual(_normalize_method_to_enum("bank-transfer"), RepaymentMethod.BANK_TRANSFER)
        self.assertEqual(_normalize_method_to_enum(None), RepaymentMethod.UNKNOWN)
        self.assertEqual(_normalize_method_to_enum("???"), RepaymentMethod.UNKNOWN)

    def test_yen_round_units(self):
        # 1円丸め（四捨五入）
        self.assertEqual(yen_round(1.5, unit=1), 2)
        self.assertEqual(yen_round(1.4, unit=1), 1)
        # 10円丸め
        self.assertEqual(yen_round(14, unit=10), 10)
        self.assertEqual(yen_round(15, unit=10), 20)
        # 100円丸め
        self.assertEqual(yen_round(149, unit=100), 100)
        self.assertEqual(yen_round(150, unit=100), 200)

if __name__ == "__main__":
    unittest.main()
