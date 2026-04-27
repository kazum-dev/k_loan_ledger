from flask import Flask, render_template, request, redirect, url_for
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

def generate_loan_id(loans, loan_date):
    """
    loan_date をもとに LYYYYMMDD-001 形式の loan_id を生成する
    """
    date_part = loan_date.replace("-", "")
    prefix = f"L{date_part}"

    same_day_numbers = []

    for loan in loans:
        loan_id = loan.get("loan_id", "")
        if loan_id.startswith(prefix):
            try:
                number = int(loan_id.split("-")[1])
                same_day_numbers.append(number)
            except (IndexError, ValueError):
                continue

    next_number = max(same_day_numbers, default=0) + 1
    return f"{prefix}-{next_number:03d}"

def save_loan_to_csv(file_path, loan_data):
    fieldnames = [
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
        "contract_status",
        "cancelled_at",
        "cancel_reason",
        "notes",
    ]

    with open(file_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writerow(loan_data)

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

@app.route("/loans/new", methods=["GET", "POST"])
def loan_new():
    if request.method == "POST":
        loans = load_loans("data/loan_v3.csv")
        customers = load_customers("data/customers.csv")

        errors = []

        form_data = {
            "customer_id": request.form.get("customer_id", "").strip(),
            "loan_amount": request.form.get("loan_amount", "").strip(),
            "loan_date": request.form.get("loan_date", "").strip(),
            "due_date": request.form.get("due_date", "").strip(),
            "interest_rate_percent": request.form.get("interest_rate_percent", "").strip(),
            "repayment_method": request.form.get("repayment_method", "UNKNOWN").strip(),
            "grace_period_days": request.form.get("grace_period_days", "").strip(),
            "late_fee_rate_percent": request.form.get("late_fee_rate_percent", "").strip(),
            "notes": request.form.get("notes", "").strip(),
        }

        customer_ids = [customer.get("customer_id", "").strip() for customer in customers]

        if not form_data["customer_id"]:
            errors.append("顧客IDを入力してください。")
        elif form_data["customer_id"] not in customer_ids:
            errors.append("存在しない顧客IDです。")

        if not form_data["loan_amount"]:
            errors.append("貸付額を入力してください。")
        else:
            try:
                loan_amount = int(form_data["loan_amount"])
                if loan_amount <= 0:
                    errors.append("貸付額は1円以上で入力してください。")
            except ValueError:
                loan_amount = 0
                errors.append("貸付額は数値で入力してください。")

        try:
            interest_rate_percent = float(form_data["interest_rate_percent"])
            if interest_rate_percent < 0:
                errors.append("通常利率は0以上で入力してください。")
        except ValueError:
            interest_rate_percent = 0
            errors.append("通常利率は数値で入力してください。")

        try:
            grace_period_days = int(form_data["grace_period_days"])
            if grace_period_days < 0:
                errors.append("延滞猶予日数は0以上で入力してください。")
        except ValueError:
            grace_period_days = 0
            errors.append("延滞猶予日数は数値で入力してください。")

        try:
            late_fee_rate_percent = float(form_data["late_fee_rate_percent"])
            if late_fee_rate_percent < 0:
                errors.append("延滞利率は0以上で入力してください。")
        except ValueError:
            late_fee_rate_percent = 0
            errors.append("延滞利率は数値で入力してください。")

        loan_date_obj = None
        due_date_obj = None

        if not form_data["loan_date"]:
            errors.append("貸付日を入力してください。")
        else:
            try:
                loan_date_obj = datetime.strptime(form_data["loan_date"], "%Y-%m-%d").date()
            except ValueError:
                errors.append("貸付日の形式が正しくありません。")

        if not form_data["due_date"]:
            errors.append("返済期日を入力してください。")
        else:
            try:
                due_date_obj = datetime.strptime(form_data["due_date"], "%Y-%m-%d").date()
            except ValueError:
                errors.append("返済期日の形式が正しくありません。")

        if loan_date_obj and due_date_obj:
            if loan_date_obj > due_date_obj:
                errors.append("返済期日は貸付日以降の日付を入力してください。")

        if errors:
            return render_template(
                "loan_form.html",
                errors=errors,
                form_data=form_data
            )

        repayment_expected = int(loan_amount * (1 + interest_rate_percent / 100))
        loan_id = generate_loan_id(loans, form_data["loan_date"])

        loan_data = {
            "loan_id": loan_id,
            "customer_id": form_data["customer_id"],
            "loan_amount": loan_amount,
            "loan_date": form_data["loan_date"],
            "due_date": form_data["due_date"],
            "interest_rate_percent": interest_rate_percent,
            "repayment_expected": repayment_expected,
            "repayment_method": form_data["repayment_method"],
            "grace_period_days": grace_period_days,
            "late_fee_rate_percent": late_fee_rate_percent,
            "late_base_amount": loan_amount,
            "contract_status": "ACTIVE",
            "cancelled_at": "",
            "cancel_reason": "",
            "notes": form_data["notes"],
        }

        save_loan_to_csv("data/loan_v3.csv", loan_data)

        return redirect(url_for("loan_list"))

    return render_template(
        "loan_form.html",
        form_data={}
    )

if __name__ == "__main__":
    app.run(debug=True)