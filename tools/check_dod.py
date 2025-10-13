from decimal import Decimal, ROUND_HALF_UP
import csv, sys

csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/loan_v3.csv"
ENUM = {"CASH", "BANK_TRANSFER", "UNKNOWN"}


def recalc(loan_amount, rate_percent):
    p = Decimal(str(loan_amount))
    r = Decimal(str(rate_percent)) / Decimal("100")
    return int((p * (Decimal("1") + r)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


bad_enum = []
bad_expected = []

with open(csv_path, encoding="utf-8", newline="") as f:
    rdr = csv.DictReader(f)
    for row in rdr:
        lid = row.get("loan_id", "")
        method = row.get("repayment_method", "")
        if method not in ENUM:
            bad_enum.append((lid, method))
        try:
            exp = int(row["repayment_expected"])
            calc = recalc(row["loan_amount"], row["interest_rate_percent"])
            if exp != calc:
                bad_expected.append((lid, exp, calc))
        except Exception as e:
            bad_expected.append((lid, row.get("repayment_expected"), f"ERR:{e}"))

ok = (not bad_enum) and (not bad_expected)
print("DoD CHECK:", "PASS ✅" if ok else "FAIL ❌")
if bad_enum:
    print(" Non-ENUM methods:")
    for item in bad_enum:
        print("  ", item)
if bad_expected:
    print(" Rounding mismatches:")
    for item in bad_expected:
        print("  ", item)

sys.exit(0 if ok else 1)
