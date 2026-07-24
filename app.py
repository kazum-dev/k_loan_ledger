# app.py
import os
from datetime import datetime, date, timedelta
from pathlib import Path

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "loan_ledger.db"

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-secret-key-change-before-production",
)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )
    username = db.Column(
        db.String(50),
        nullable=False,
        unique=True,
    )
    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )
    role = db.Column(
        db.String(20),
        nullable=False,
        default="USER",
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    created_at = db.Column(
        db.String,
        nullable=False,
    )
    updated_at = db.Column(
        db.String,
        nullable=False,
    )

    customers = db.relationship(
        "Customer",
        backref="user",
        lazy=True,
    )
    loans = db.relationship(
        "Loan",
        backref="user",
        lazy=True,
    )
    repayments = db.relationship(
        "Repayment",
        backref="user",
        lazy=True,
    )

class Customer(db.Model):
    __tablename__ = "customers"

    customer_id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    customer_name = db.Column(db.String, nullable=False)
    credit_limit = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String, nullable=False)

    loans = db.relationship("Loan", backref="customer", lazy=True)
    repayments = db.relationship("Repayment", backref="customer", lazy=True)


class Loan(db.Model):
    __tablename__ = "loans"

    loan_id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    customer_id = db.Column(db.String, db.ForeignKey("customers.customer_id"), nullable=False)

    loan_amount = db.Column(db.Integer, nullable=False)
    loan_date = db.Column(db.String, nullable=False)
    due_date = db.Column(db.String, nullable=False)
    interest_rate_percent = db.Column(db.Float, nullable=False)
    repayment_expected = db.Column(db.Integer, nullable=False)
    repayment_method = db.Column(db.String, nullable=False)
    grace_period_days = db.Column(db.Integer, nullable=False)
    late_fee_rate_percent = db.Column(db.Float, nullable=False)
    late_base_amount = db.Column(db.Integer, nullable=False)

    contract_status = db.Column(db.String, nullable=False)
    cancelled_at = db.Column(db.String)
    cancel_reason = db.Column(db.String)
    notes = db.Column(db.String)
    created_at = db.Column(db.String, nullable=False)

    repayments = db.relationship("Repayment", backref="loan", lazy=True)


class Repayment(db.Model):
    __tablename__ = "repayments"

    repayment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    loan_id = db.Column(db.String, db.ForeignKey("loans.loan_id"), nullable=False)
    customer_id = db.Column(db.String, db.ForeignKey("customers.customer_id"), nullable=False)

    repayment_amount = db.Column(db.Integer, nullable=False)
    repayment_date = db.Column(db.String, nullable=False)
    payment_type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.String, nullable=False)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
@app.before_request
def load_logged_in_user():
    """
    sessionのuser_idから現在のログインユーザーを取得する。
    """
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
        return

    user = db.session.get(User, user_id)

    if user is None or not user.is_active:
        session.clear()
        g.user = None
        return

    g.user = user

@app.before_request
def require_login():
    """
    loginとstatic以外のページをログイン必須にする。
    """
    public_endpoints = {
        "login",
        "static",
    }

    if request.endpoint in public_endpoints:
        return

    if g.user is None:
        return redirect(url_for("login"))

def load_loans(file_path=None):
    loans = (
        Loan.query
        .filter_by(user_id=g.user.user_id)
        .order_by(
            Loan.loan_date,
            Loan.loan_id,
        )
        .all()
    )

    return [
        {
            "loan_id": loan.loan_id,
            "customer_id": loan.customer_id,
            "loan_amount": loan.loan_amount,
            "loan_date": loan.loan_date,
            "due_date": loan.due_date,
            "interest_rate_percent": loan.interest_rate_percent,
            "repayment_expected": loan.repayment_expected,
            "repayment_method": loan.repayment_method,
            "grace_period_days": loan.grace_period_days,
            "late_fee_rate_percent": loan.late_fee_rate_percent,
            "late_base_amount": loan.late_base_amount,
            "contract_status": loan.contract_status,
            "cancelled_at": loan.cancelled_at or "",
            "cancel_reason": loan.cancel_reason or "",
            "notes": loan.notes or "",
        }
        for loan in loans
    ]

def load_repayments(file_path=None):
    repayments = (
        Repayment.query
        .filter_by(user_id=g.user.user_id)
        .order_by(
            Repayment.repayment_date,
            Repayment.repayment_id,
        )
        .all()
    )

    return [
        {
            "loan_id": repayment.loan_id,
            "customer_id": repayment.customer_id,
            "repayment_amount": repayment.repayment_amount,
            "repayment_date": repayment.repayment_date,
            "payment_type": repayment.payment_type,
        }
        for repayment in repayments
    ]

def load_customers(file_path=None):
    customers = (
        Customer.query
        .filter_by(user_id=g.user.user_id)
        .order_by(Customer.customer_id)
        .all()
    )

    return [
        {
            "customer_id": customer.customer_id,
            "customer_name": customer.customer_name,
            "credit_limit": customer.credit_limit,
        }
        for customer in customers
    ]

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

def calculate_late_fee_paid_map(repayments):
    """
    loan_idごとの延滞手数料支払済額を辞書で返す
    - payment_type == "LATE_FEE" のみ集計
    """
    late_fee_paid_map = {}

    for row in repayments:
        loan_id = row.get("loan_id", "").strip()
        payment_type = row.get("payment_type", "").strip().upper()

        if payment_type != "LATE_FEE":
            continue

        try:
            amount = int(float(row.get("repayment_amount", 0)))
        except ValueError:
            amount = 0

        late_fee_paid_map[loan_id] = late_fee_paid_map.get(loan_id, 0) + amount

    return late_fee_paid_map

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
    late_fee_paid_map = calculate_late_fee_paid_map(repayments)
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
        late_fee_paid = late_fee_paid_map.get(loan_id, 0)
        remaining = max(0, repayment_expected - total_repaid)

        try:
            late_fee_rate_percent = float(
                loan.get("late_fee_rate_percent", 0)
            )
        except ValueError:
            late_fee_rate_percent = 0

        try:
            late_base_amount = int(
                float(loan.get("late_base_amount", 0))
            )
        except ValueError:
            late_base_amount = 0

        status = "UNPAID"
        overdue_days = 0

        late_fee_amount = 0
        late_fee_remaining = 0
        current_collect_amount = remaining

        # due_date があるときだけ延滞判定
        if due_date:
            try:
                overdue_days = calc_overdue_days(
                    today,
                    due_date,
                    grace_period_days
                )

                if overdue_days > 0:
                    late_fee_amount = int(
                        late_base_amount
                        * (late_fee_rate_percent / 100)
                        * (overdue_days / 30)
                    )

                    late_fee_remaining = max(
                        0,
                        late_fee_amount - late_fee_paid
                    )

                current_collect_amount = remaining + late_fee_remaining

                if remaining > 0 and overdue_days > 0:
                    status = "OVERDUE"
                elif remaining > 0:
                    status = "UNPAID"
                elif remaining <= 0 and late_fee_remaining > 0:
                    status = "LATE_FEE_ONLY"

            except ValueError:
                status = "UNPAID"

        # 通常残高と延滞手数料残額がどちらも0なら除外
        if remaining <= 0 and late_fee_remaining <= 0:
            continue

        unpaid_rows.append(
            {
                "loan_id": loan_id,
                "customer_id": customer_id,
                "loan_amount": loan_amount,
                "loan_date": loan.get("loan_date", "").strip(),
                "due_date": due_date,
                "repayment_expected": repayment_expected,
                "total_repaid": total_repaid,
                "remaining": remaining,
                "status": status,
                "status_label": {
                    "UNPAID": "期日内未返済",
                    "OVERDUE": "延滞中",
                    "LATE_FEE_ONLY": "延滞手数料のみ未払い",
                }.get(status, status),
                "overdue_days": overdue_days,
                "late_fee_paid": late_fee_paid,
                "late_fee_amount": late_fee_amount,
                "late_fee_remaining": late_fee_remaining,
                "current_collect_amount": current_collect_amount,
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
    loan = Loan(
        loan_id=loan_data["loan_id"],
        user_id=g.user.user_id,
        customer_id=loan_data["customer_id"],
        loan_amount=int(loan_data["loan_amount"]),
        loan_date=loan_data["loan_date"],
        due_date=loan_data["due_date"],
        interest_rate_percent=float(
            loan_data["interest_rate_percent"]
        ),
        repayment_expected=int(
            loan_data["repayment_expected"]
        ),
        repayment_method=loan_data["repayment_method"],
        grace_period_days=int(
            loan_data["grace_period_days"]
        ),
        late_fee_rate_percent=float(
            loan_data["late_fee_rate_percent"]
        ),
        late_base_amount=int(
            loan_data["late_base_amount"]
        ),
        contract_status=loan_data["contract_status"],
        cancelled_at=loan_data.get("cancelled_at") or None,
        cancel_reason=loan_data.get("cancel_reason") or None,
        notes=loan_data.get("notes") or None,
        created_at=now_str(),
    )

    db.session.add(loan)
    db.session.commit()

def save_repayment_to_csv(file_path, repayment_data):
    repayment = Repayment(
        user_id=g.user.user_id,
        loan_id=repayment_data["loan_id"],
        customer_id=repayment_data["customer_id"],
        repayment_amount=int(
            repayment_data["repayment_amount"]
        ),
        repayment_date=repayment_data["repayment_date"],
        payment_type=repayment_data["payment_type"],
        created_at=now_str(),
    )

    db.session.add(repayment)
    db.session.commit()

def save_customer_to_csv(file_path, customer_data):
    customer = Customer(
        customer_id=customer_data["customer_id"],
        user_id=g.user.user_id,
        customer_name=customer_data["customer_name"],
        credit_limit=int(customer_data["credit_limit"]),
        created_at=now_str(),
    )

    db.session.add(customer)
    db.session.commit()

def update_loan_cancel_status(
    file_path,
    target_loan_id,
    cancel_reason,
):
    loan = Loan.query.filter_by(
        loan_id=target_loan_id,
        user_id=g.user.user_id,
    ).first()

    if loan is None:
        return False

    loan.contract_status = "CANCELLED"
    loan.cancelled_at = date.today().strftime("%Y-%m-%d")
    loan.cancel_reason = cancel_reason

    db.session.commit()
    return True

def get_contract_status_label(contract_status):
    """
    contract_status を日本語表示に変換する
    """
    status = (contract_status or "").strip().upper()

    labels = {
        "ACTIVE": "有効",
        "CANCELLED": "契約解除済み",
    }

    return labels.get(status, "不明")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    username = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(
            username=username
        ).first()

        authentication_failed = (
            user is None
            or not user.is_active
            or not check_password_hash(
                user.password_hash,
                password,
            )
        )

        if authentication_failed:
            error = (
                "ユーザー名またはパスワードが"
                "正しくありません。"
            )
        else:
            session.clear()
            session["user_id"] = user.user_id

            return redirect(url_for("home"))

    return render_template(
        "login.html",
        error=error,
        username=username,
    )

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    customer_count = Customer.query.filter_by(
        user_id=g.user.user_id
    ).count()

    loan_count = Loan.query.filter_by(
        user_id=g.user.user_id
    ).count()

    repayment_count = Repayment.query.filter_by(
        user_id=g.user.user_id
    ).count()

    return render_template(
        "index.html",
        customer_count=customer_count,
        loan_count=loan_count,
        repayment_count=repayment_count,
    )

@app.route("/dashboard")
def dashboard():
    loans = load_loans()
    repayments = load_repayments()

    # 総貸付額
    total_loan_amount = sum(
        loan["loan_amount"]
        for loan in loans
    )

    # 総返済額
    # 通常返済（REPAYMENT）のみ集計
    total_repaid = sum(
        repayment["repayment_amount"]
        for repayment in repayments
        if repayment["payment_type"].strip().upper() == "REPAYMENT"
    )

    # 未返済情報を作成
    unpaid_loans = build_unpaid_loan_rows(
        loans,
        repayments,
    )

    # 未返済残高
    total_remaining = sum(
        loan["remaining"]
        for loan in unpaid_loans
    )

    # 延滞件数
    overdue_count = sum(
        1
        for loan in unpaid_loans
        if loan["status"] == "OVERDUE"
    )

    dashboard_data = {
        "total_loan_amount": total_loan_amount,
        "total_repaid": total_repaid,
        "total_remaining": total_remaining,
        "overdue_count": overdue_count,
    }

    return render_template(
        "dashboard.html",
        dashboard_data=dashboard_data,
    )

@app.route("/loans")
def loan_list():
    loans = load_loans("data/loan_v3.csv")
    return render_template("loan_list.html", loans=loans)

@app.route("/repayments")
def repayment_list():
    repayments = load_repayments("data/repayments.csv")
    return render_template("repayment_list.html", repayments=repayments)

@app.route("/repayments/new", methods=["GET", "POST"])
def repayment_new():

    if request.method == "POST":

        loans = load_loans("data/loan_v3.csv")

        repayments = load_repayments("data/repayments.csv")
        repaid_map = calculate_total_repaid_map(repayments)
        late_fee_paid_map = calculate_late_fee_paid_map(repayments)

        errors = []

        form_data = {
            "loan_id": request.form.get("loan_id", "").strip(),
            "repayment_amount": request.form.get("repayment_amount", "").strip(),
            "repayment_date": request.form.get("repayment_date", "").strip(),
            "payment_type": request.form.get("payment_type", "REPAYMENT").strip().upper(),
        }

        # 返済種別チェック
        valid_payment_types = ["REPAYMENT", "LATE_FEE"]

        if form_data["payment_type"] not in valid_payment_types:
            errors.append("返済種別が正しくありません。")

        target_loan = None

        for loan in loans:
            if loan.get("loan_id", "").strip() == form_data["loan_id"]:
                target_loan = loan
                break

        # 取消済み貸付への返済禁止チェック
        if target_loan:
            contract_status = target_loan.get("contract_status", "").strip().upper()

            if contract_status == "CANCELLED":
                errors.append("取消済みの貸付には返済登録できません。")

        # loan_id 一覧取得
        loan_ids = [
            loan.get("loan_id", "").strip()
            for loan in loans
        ]

        # loan_id チェック
        if not form_data["loan_id"]:
            errors.append("loan_id を入力してください。")

        elif form_data["loan_id"] not in loan_ids:
            errors.append("存在しない loan_id です。")

        # 返済金額チェック
        if not form_data["repayment_amount"]:
            errors.append("返済金額を入力してください。")

        else:
            try:
                repayment_amount = int(form_data["repayment_amount"])

                if repayment_amount <= 0:
                    errors.append("返済金額は1円以上で入力してください。")

            except ValueError:
                repayment_amount = 0
                errors.append("返済金額は数値で入力してください。")

        # 返済種別ごとの登録可否チェック
        if target_loan and not errors:
            try:
                repayment_expected = int(float(target_loan.get("repayment_expected", 0)))
            except ValueError:
                repayment_expected = 0

            total_repaid = repaid_map.get(form_data["loan_id"], 0)
            normal_remaining = max(0, repayment_expected - total_repaid)

            try:
                grace_period_days = int(float(target_loan.get("grace_period_days", 0)))
            except ValueError:
                grace_period_days = 0

            try:
                late_fee_rate_percent = float(target_loan.get("late_fee_rate_percent", 0))
            except ValueError:
                late_fee_rate_percent = 0

            try:
                late_base_amount = int(float(target_loan.get("late_base_amount", 0)))
            except ValueError:
                late_base_amount = 0

            due_date = target_loan.get("due_date", "").strip()
            overdue_days = 0
            late_fee_amount = 0

            if due_date:
                try:
                    overdue_days = calc_overdue_days(
                        date.today(),
                        due_date,
                        grace_period_days
                    )

                    if overdue_days > 0:
                        late_fee_amount = int(
                            late_base_amount
                            * (late_fee_rate_percent / 100)
                            * (overdue_days / 30)
                        )

                except ValueError:
                    overdue_days = 0
                    late_fee_amount = 0

            late_fee_paid = late_fee_paid_map.get(form_data["loan_id"], 0)
            late_fee_remaining = max(0, late_fee_amount - late_fee_paid)

            if form_data["payment_type"] == "REPAYMENT":
                if normal_remaining <= 0:
                    errors.append("この貸付は通常返済がすでに完了しています。")

                elif repayment_amount > normal_remaining:
                    errors.append(
                        f"通常返済額が通常残高を超えています。通常残高は {normal_remaining} 円です。"
                    )

            elif form_data["payment_type"] == "LATE_FEE":
                if overdue_days <= 0:
                    errors.append("この貸付には現在、延滞手数料が発生していません。")

                elif late_fee_amount <= 0:
                    errors.append("この貸付には現在、延滞手数料が発生していません。")

                elif late_fee_remaining <= 0:
                    errors.append("この貸付の延滞手数料はすでに支払い済みです。")

                elif repayment_amount > late_fee_remaining:
                    errors.append(
                        f"延滞手数料返済額が延滞手数料残額を超えています。延滞手数料残額は {late_fee_remaining} 円です。"
                    )

        # 返済日チェック
        if not form_data["repayment_date"]:

            today_str = date.today().strftime("%Y-%m-%d")

            form_data["repayment_date"] = today_str

        else:
            try:
                datetime.strptime(
                    form_data["repayment_date"],
                    "%Y-%m-%d"
                )

            except ValueError:
                errors.append("返済日の形式が正しくありません。")

        # エラーがある場合
        if errors:

            return render_template(
                "repayment_form.html",
                errors=errors,
                form_data=form_data
            )

        # customer_id を取得
        customer_id = ""

        for loan in loans:

            if loan.get("loan_id", "").strip() == form_data["loan_id"]:

                customer_id = loan.get("customer_id", "").strip()
                break

        repayment_data = {
            "loan_id": form_data["loan_id"],
            "customer_id": customer_id,
            "repayment_amount": repayment_amount,
            "repayment_date": form_data["repayment_date"],
            "payment_type": form_data["payment_type"],
        }

        save_repayment_to_csv(
            "data/repayments.csv",
            repayment_data
        )

        return redirect(url_for("repayment_list"))

    return render_template(
        "repayment_form.html",
        form_data={},
        errors=[]
    )

@app.route("/customers")
def customer_list():
    customers = load_customers("data/customers.csv")
    return render_template("customer_list.html", customers=customers)

@app.route("/customers/new", methods=["GET", "POST"])
def new_customer():
    errors = []
    form_data = {
        "customer_id": "",
        "customer_name": "",
        "credit_limit": "",
    }

    if request.method == "POST":
        customer_id = request.form.get("customer_id", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        credit_limit = request.form.get("credit_limit", "").strip()

        form_data = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "credit_limit": credit_limit,
        }

        if customer_id == "":
            errors.append("顧客IDを入力してください。")

        if customer_name == "":
            errors.append("顧客名を入力してください。")

        if credit_limit == "":
            errors.append("貸付上限額を入力してください。")
        else:
            try:
                credit_limit_int = int(credit_limit)
                if credit_limit_int <= 0:
                    errors.append("貸付上限額は1円以上で入力してください。")
            except ValueError:
                errors.append("貸付上限額は数値で入力してください。")

        existing_customer = Customer.query.filter_by(
            customer_id=customer_id
        ).first()

        if existing_customer is not None:
            errors.append("この顧客IDは使用できません。")

        if not errors:
            customer_data = {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "credit_limit": credit_limit_int,
            }

            save_customer_to_csv("data/customers.csv", customer_data)
            return redirect("/customers")

    return render_template(
        "customer_form.html",
        errors=errors,
        form_data=form_data
    )

@app.route("/loan-status")
def loan_status():
    loans = load_loans("data/loan_v3.csv")
    repayments = load_repayments("data/repayments.csv")

    unpaid_loans = build_unpaid_loan_rows(loans, repayments)

    overdue_count = sum(
        1 for loan in unpaid_loans
        if loan["status"] == "OVERDUE"
    )

    unpaid_count = sum(
        1 for loan in unpaid_loans
        if loan["status"] == "UNPAID"
    )

    late_fee_only_count = sum(
        1 for loan in unpaid_loans
        if loan["status"] == "LATE_FEE_ONLY"
    )

    total_loan_amount = sum(
        loan["loan_amount"] for loan in unpaid_loans
    )

    total_repayment_expected = sum(
        loan["repayment_expected"] for loan in unpaid_loans
    )

    total_repaid = sum(
        loan["total_repaid"] for loan in unpaid_loans
    )

    total_remaining = sum(
        loan["remaining"] for loan in unpaid_loans
    )

    total_late_fee_remaining = sum(
        loan["late_fee_remaining"] for loan in unpaid_loans
    )

    total_current_collect_amount = sum(
        loan["current_collect_amount"] for loan in unpaid_loans
    )

    return render_template(
        "loan_status.html",
        unpaid_loans=unpaid_loans,
        overdue_count=overdue_count,
        unpaid_count=unpaid_count,
        late_fee_only_count=late_fee_only_count,
        total_loan_amount=total_loan_amount,
        total_repayment_expected=total_repayment_expected,
        total_repaid=total_repaid,
        total_remaining=total_remaining,
        total_late_fee_remaining=total_late_fee_remaining,
        total_current_collect_amount=total_current_collect_amount,
    )

@app.route("/overdue-loans")
def overdue_loans():
    loans = load_loans("data/loan_v3.csv")
    repayments = load_repayments("data/repayments.csv")

    unpaid_loans = build_unpaid_loan_rows(loans, repayments)

    overdue_loans = [
        loan for loan in unpaid_loans
        if loan["status"] in ["OVERDUE", "LATE_FEE_ONLY"]
    ]

    return render_template(
        "overdue_loans.html",
        overdue_loans=overdue_loans
    )

@app.route("/loans/cancel", methods=["GET", "POST"])
def loan_cancel():
    errors = []
    form_data = {
        "loan_id": "",
        "cancel_reason": "",
    }

    if request.method == "POST":
        loans = load_loans("data/loan_v3.csv")

        form_data = {
            "loan_id": request.form.get("loan_id", "").strip(),
            "cancel_reason": request.form.get("cancel_reason", "").strip(),
        }

        target_loan = None

        for loan in loans:
            if loan.get("loan_id", "").strip() == form_data["loan_id"]:
                target_loan = loan
                break

        if not form_data["loan_id"]:
            errors.append("貸付IDを入力してください。")

        elif target_loan is None:
            errors.append("存在しない貸付IDです。")

        elif target_loan.get("contract_status", "").strip().upper() == "CANCELLED":
            errors.append("この貸付はすでに契約解除済みです。")

        if not form_data["cancel_reason"]:
            errors.append("契約解除理由を入力してください。")

        if errors:
            return render_template(
                "loan_cancel_form.html",
                errors=errors,
                form_data=form_data
            )

        update_loan_cancel_status(
            "data/loan_v3.csv",
            form_data["loan_id"],
            form_data["cancel_reason"]
        )

        return redirect(url_for("loan_contracts"))

    return render_template(
        "loan_cancel_form.html",
        errors=errors,
        form_data=form_data
    )

@app.route("/loan-contracts")
def loan_contracts():
    loans = load_loans("data/loan_v3.csv")

    active_count = 0
    cancelled_count = 0

    cancelled_loans = []

    for loan in loans:
        status = (
            loan.get("contract_status", "")
            .strip()
            .upper()
        )

        loan["contract_status_label"] = (
            get_contract_status_label(status)
        )

        if status == "ACTIVE":
            active_count += 1

        elif status == "CANCELLED":
            cancelled_count += 1
            cancelled_loans.append(loan)

    return render_template(
        "loan_contracts.html",
        loans=loans,
        cancelled_loans=cancelled_loans,
        active_count=active_count,
        cancelled_count=cancelled_count,
        total_count=len(loans),
    )

@app.route("/loans/new", methods=["GET", "POST"])
def loan_new():
    if request.method == "POST":
        loans = load_loans("data/loan_v3.csv")

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

        customer = None

        if not form_data["customer_id"]:
            errors.append("顧客IDを入力してください。")
        else:
            customer = Customer.query.filter_by(
                customer_id=form_data["customer_id"],
                user_id=g.user.user_id,
        ).first()

        if customer is None:
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
    with app.app_context():
        db.create_all()
        print("SQLAlchemyでテーブルを作成しました。")

    app.run(debug=True)