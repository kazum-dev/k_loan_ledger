import csv
from collections import defaultdict

def load_balances(loan_file='loan.csv', repayment_file='repayments.csv'):
    loan_totals = defaultdict(int)
    repayment_totals = defaultdict(int)

    #貸付データの読み込み
    with open(loan_file, 'r', encoding='utf-8') as lf:
        reader = csv.DictReader(lf)
        for row in reader:
            customer_id = row['customer_id']
            amount = int(row['loan_amount'])
            loan_totals[customer_id] += amount

    #返済データの読み込み
    with open(repayment_file, 'r', encoding='utf-8') as rf:
        reader = csv.DictReader(rf)
        for row in reader:
            customer_id = row['customer_id']
            #amount = int(row['amount'])
            # 返済額は新仕様 'repayment_amount'。後方互換で'amount'も許容
            amt_str = row.get('repayment_amount') or row.get('amount') or "0"
            amount = int(float(amt_str))
            repayment_totals[customer_id] += amount

    return loan_totals, repayment_totals

def display_balance(customer_id):
    loan_totals, repayment_totals = load_balances()
    loan = loan_totals.get(customer_id, 0)
    repayment = repayment_totals.get(customer_id, 0)
    balance =loan - repayment

    print("\n=== 残高照会モード ===")
    print(f"顧客ID：{customer_id}")
    print(f"💰 貸付総額：{loan:,}円")
    print(f"💸 返済総額：{repayment:,}円")
    print(f"🧾 残高（未返済額）：{balance:,}円")

