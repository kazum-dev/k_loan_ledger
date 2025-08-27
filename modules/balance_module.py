import os
import csv
from collections import defaultdict

# このファイル（modules/）の1つ上のディレクトリに CSV がある想定（main.py と同階層）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

LOANS_FILE_DEFAULT = os.path.join(PROJECT_DIR, "loan_v3.csv")
REPAYMENTS_FILE_DEFAULT = os.path.join(PROJECT_DIR, "repayments.csv")


def _normalize_dict(d: dict) -> dict:
    """キーと値の前後空白やクォート（' / "）を除去して正規化。"""
    def _norm(s: str) -> str:
        return (s or "").strip().strip("'\"")
    return {_norm(k): _norm(v) for k, v in (d or {}).items()}


def load_balances(loans_file: str = LOANS_FILE_DEFAULT,
                  repayments_file: str = REPAYMENTS_FILE_DEFAULT):
    """
    顧客別：
      - 貸付側：repayment_expected の合計（無ければ loan_amount を保険）
      - 返済側：repayment_amount の合計（旧 amount も後方互換）
    を返す。
    """
    loan_totals = defaultdict(int)
    repayment_totals = defaultdict(int)

    # --- 貸付（予定返済額） ---
    try:
        with open(loans_file, "r", encoding="utf-8") as lf:
            reader = csv.DictReader(lf)
            for row in reader:
                row = _normalize_dict(row)
                customer_id = row.get("customer_id", "")
                exp_str = row.get("repayment_expected") or row.get("loan_amount") or "0"
                try:
                    expected = int(float(exp_str))
                except (ValueError, TypeError):
                    expected = 0
                loan_totals[customer_id] += expected
    except FileNotFoundError:
        pass  # 無ければ0扱い

    # --- 返済（返済額） ---
    try:
        with open(repayments_file, "r", encoding="utf-8") as rf:
            reader = csv.DictReader(rf)
            for row in reader:
                row = _normalize_dict(row)
                customer_id = row.get("customer_id", "")
                # 新 'repayment_amount'（旧 'amount' も後方互換）
                amt_str = row.get("repayment_amount") or row.get("amount") or "0"
                amt_str = amt_str.replace(",", "")
                try:
                    amount = int(float(amt_str))
                except (ValueError, TypeError):
                    amount = 0
                repayment_totals[customer_id] += amount
    except FileNotFoundError:
        pass  # 無ければ0扱い

    return loan_totals, repayment_totals


def display_balance(customer_id: str,
                    loans_file: str = LOANS_FILE_DEFAULT,
                    repayments_file: str = REPAYMENTS_FILE_DEFAULT,
                    clamp_negative: bool = False):
    """
    残高を表示する。clamp_negative=True でマイナス表示を0に丸め可能。
    """
    loan_totals, repayment_totals = load_balances(loans_file, repayments_file)

    loan = loan_totals.get(customer_id, 0)
    repayment = repayment_totals.get(customer_id, 0)
    balance = loan - repayment
    if clamp_negative:
        balance = max(0, balance)

    print("\n=== 残高照会モード ===")
    print(f"顧客ID：{customer_id}")
    print(f"💰 貸付総額（予定返済額合計）：{loan:,}円")
    print(f"💸 返済総額：{repayment:,}円")
    print(f"🧾 残高（未返済額）：{balance:,}円")
