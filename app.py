from flask import Flask, render_template
import csv
from datetime import datetime, date, timedelta

app = Flask(__name__)

def count_csv_rows(file_path):
    count = 0
    with open(file_path, "r", encoding= "utf-8") as file:
        reader = csv.reader(file)
        next(reader)
        for row in  reader:
            count += 1
    return count

def load_loans(file_path):
    loans = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            loans.append(row)
    return loans    

def load_repayments(file_path):
    repayments = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            repayments.append(row)
    return repayments

def load_customers(file_path):
    customers = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            customers.append(row)
    return customers

def calculate_total_repaid_map(repayments):
    """
    loan_idごとの返済累計を辞書で返す
    - payment_type == "REPAYMENT" のみ集計
    - LATE_FEE は含めない
    """
    repaid_map = {}

    for row in repayments:
        loan_id = row.get("loan_id", "").strip()
        payment_type = row.get("payment_type", "").strip().upper()

        if payment_type != "REPAYMENT":
            continue

        try:
            amount = int(float(row.get("repayment_amount", 0)))
        except ValueError:
            amount = 0

        if loan_id not in repaid_map:
            repaid_map[loan_id] = 0

        repaid_map[loan_id] += amount

    return repaid_map

def calc_overdue_days(today, due_date_str, grace_period_days):
    """
    due_date + grace_period_days を過ぎていれば延滞日数を返す
    過ぎていなければ 0
    """
    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    threshold_date = due_date + timedelta(days=grace_period_days)
    return max(0, (today - threshold_date).days)

def build_unpaid_loan_rows(loans, repayments):
    """
    未返済一覧用の表示データを作る
    """
    today = date.today()
    repaid_map = calculate_total_repaid_map(repayments)
    unpaid_rows = []

    for loan in loans:
        contract_status = (loan.get("contract_status") or "").strip().upper()

        # CANCELLED は除外
        if contract_status == "CANCELLED":
            continue

        loan_id = loan.get("loan_id", "").strip()
        customer_id = loan.get("customer_id", "").strip()

        try:
            loan_amount = int(float(loan.get("loan_amount", 0)))
        except ValueError:
            loan_amount = 0

        due_date = loan.get("due_date", "").strip()

        try:
            repayment_expected = int(float(loan.get("repayment_expected", 0)))
        except ValueError:
            repayment_expected = 0

        try:
            grace_period_days = int(float(loan.get("grace_period_days", 0)))
        except ValueError:
            grace_period_days = 0

        total_repaid = repaid_map.get(loan_id, 0)
        remaining = repayment_expected - total_repaid

        # 完済なら除外
        if repayment_expected <= total_repaid:
            continue

        status = "UNPAID"
        overdue_days = 0

        # due_date があるときだけ延滞判定
        if due_date:
            try:
                overdue_days = calc_overdue_days(today, due_date, grace_period_days)
                if overdue_days > 0:
                    status = "OVERDUE"
            except ValueError:
                # 日付不正時は今回は最低限、未返済扱いで残す
                status = "UNPAID"

        unpaid_rows.append(
            {
                "loan_id": loan_id,
                "customer_id": customer_id,
                "loan_amount": loan_amount,
                "due_date": due_date,
                "repayment_expected": repayment_expected,
                "total_repaid": total_repaid,
                "remaining": remaining,
                "status": status,
                "overdue_days": overdue_days,
            }
        )

    unpaid_rows.sort(key=lambda row: (row["due_date"], row["loan_id"]))
    return unpaid_rows

@app.route("/")
def home():
    customer_count = count_csv_rows("data/customers.csv")
    loan_count = count_csv_rows("data/loan_v3.csv")
    repayment_count = count_csv_rows("data/repayments.csv")
    
    return render_template(
        "index.html",
        customer_count=customer_count,
        loan_count=loan_count,
        repayment_count=repayment_count
    )

@app.route("/loans")
def loan_list():
    loans = load_loans("data/loan_v3.csv")
    return render_template("loan_list.html", loans=loans)

@app.route("/repayments")
def repayment_list():
    repayments = load_repayments("data/repayments.csv")
    return render_template("repayment_list.html", repayments=repayments)

@app.route("/customers")
def customer_list():
    customers = load_customers("data/customers.csv")
    return render_template("customer_list.html", customers=customers)

@app.route("/loan-status")
def loan_status():
    loans = load_loans("data/loan_v3.csv")
    repayments = load_repayments("data/repayments.csv")
    unpaid_loans = build_unpaid_loan_rows(loans, repayments)

    return render_template(
        "loan_status.html",
        unpaid_loans=unpaid_loans
    )

if __name__ == "__main__":
    app.run(debug=True)