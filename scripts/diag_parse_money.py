import sys
from pathlib import Path
from decimal import Decimal
sys.path.append(str(Path(__file__).resolve().parents[1]))

from modules.utils import _parse_money

CASES_OK = ["1000", "1,000", "¥1,000", "￥1,000", "1_000", "+1000", "-2,500.50", "  3000  "]
CASES_NG = ["1,2,3,4", "1 000", "1,000.123", "", None]

def try_parse(v):
    try:
        x = _parse_money(v)
        print(f"OK  : {v!r} -> {x!r} (type={type(x).__name__})")
    except Exception as e:
        print(f"FAIL: {v!r} -> {type(e).__name__}: {e}")

def main():
    print("== ACCEPTED ==")
    for v in CASES_OK:
        try_parse(v)
    print("\n== REJECTED ==")
    for v in CASES_NG:
        try_parse(v)

if __name__ == "__main__":
    main()
