import sys
from pathlib import Path
from decimal import Decimal
sys.path.append(str(Path(__file__).resolve().parents[1]))

from modules.utils import round_money as round_money_utils
from modules.loan_module import round_money as round_money_loan

CASES = [
    "1000", 1000, 1000.0, 1000.49, 1000.50, 1000.51,
    "  2,500  ", "¥3,000", "￥4,500", "-2500.5", "-2500.51",
    "1,2,3,4", "1 000", "", None
]

def show(v):
    def try_one(fn, name):
        try:
            y = fn(v)
            print(f"{name:<18} OK   {v!r:>10} -> {y!r}")
        except Exception as e:
            print(f"{name:<18} FAIL {v!r:>10} -> {type(e).__name__}: {e}")
    try_one(round_money_utils, "utils.round_money")
    try_one(round_money_loan,  "loan.round_money")
    print("-")

if __name__ == "__main__":
    for v in CASES:
        show(v)
