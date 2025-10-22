# sys.path に project root を追加
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from modules.utils import get_project_paths, validate_schema

REQUIRED = {
    "loan_id",
    "customer_id",
    "loan_amount",
    "loan_date",
    "due_date",
    "interest_rate_percent",
    "repayment_expected",
    "repayment_method",
    "grace_period_days",
    "late_fee_rate_percent",
    "late_base_amount",
}

def main():
    p = get_project_paths()
    csv_path = Path(p["loans_csv"])
    ok = validate_schema(csv_path, REQUIRED)
    print("validate_schema:", ok)

if __name__ == "__main__":
    main()
