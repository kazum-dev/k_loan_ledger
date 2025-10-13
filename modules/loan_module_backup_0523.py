import csv
import os
from datetime import datetime, timedelta


def register_loan(customer_id, amount, loan_date, due_date=None, file_path="loan.csv"):
    """
    貸付情報をCSVに追記します。
    初回の場合はヘッダーも自動で追加します。
    """
    header = ["customer_id", "loan_amount", "loan_date", "due_date"]

    if due_date is None or due_date == "":
        due_date = (
            datetime.strptime(loan_date, "%Y-%m-%d") + timedelta(days=30)
        ).strftime("%Y-%m-%d")

    try:
        # ファイルが存在しない、または空ならヘッダー追加
        if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:
            with open(file_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(header)

        with open(file_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([customer_id, amount, loan_date, due_date])

        print("✅貸付記録が保存されました。")
    except Exception as e:
        print(f"❌エラーが発生しました: {e}")


def display_loan_history(customer_id, filepath="loan.csv"):
    try:
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            history = [row for row in reader if row["customer_id"] == customer_id]

        if history:
            print(f"\n■ 顧客ID: {customer_id}の貸付履歴")
            for row in history:
                date_str = datetime.strptime(row["loan_date"], "%Y-%m-%d").strftime(
                    "%Y年%m月%d日"
                )
                amount_str = f"{int(row['loan_amount']):,}円"
                due_date = row.get("due_date", "")
                print(f"{date_str}｜{amount_str}｜返済期日：{due_date}")

        else:
            print("該当する貸付履歴はありません。")

    except FileNotFoundError:
        print("エラー：ファイルが見つかりません。ファイルパスを確認してください。")
    except Exception as e:
        print(f"予期せぬエラーが発生しました:{e}")


def register_repayment():
    # 顧客IDの入力と補正
    customer_id = input("顧客IDを入力してください（例：001 または CUST001）： ").strip()
    if customer_id.isdigit() and len(customer_id) == 3:
        customer_id = f"CUST{customer_id}"
    elif not customer_id.startswith("CUST"):
        print(
            "❌ 顧客の形式が不正です。３桁の数字または CUSTxxx 形式で入力してください。"
        )
        return

    # 金額の入力
    try:
        amount = int(input("返済額を入力してください（例：5000）: ").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        print("❌金額は正の整数で入力してください。")
        return

    # 返済日の入力（未入力時は今日）
    repayment_date = input(
        "📅 返済日を入力してください（未入力で本日の日付を使用）："
    ).strip()
    if not repayment_date:
        repayment_date = str(datetime.today().date())

    # CSVに追記
    try:
        with open("repayments.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([customer_id, amount, repayment_date])
        print(f"✅ {customer_id} の返済記録を保存しました。")
    except Exception as e:
        print(f"❌ CSV書き込み中にエラーが発生しました: {e}")


def display_repayment_history(customer_id, filepath="repayments.csv"):
    try:
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            history = [row for row in reader if row["customer_id"] == customer_id]

        if history:
            print(f"\n■ 顧客ID: {customer_id} の返済履歴")
            for row in history:
                date_str = datetime.strptime(
                    row["repayment_date"], "%Y-%m-%d"
                ).strftime("%Y年%m月%d日")
                amount_str = f"{int(row['amount']):,}円"
                print(f"{date_str}｜{amount_str}")
        else:
            print("該当する返済履歴はありません。")

    except FileNotFoundError:
        print("エラー：repayments.csv が見つかりません。")
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")


def display_unpaid_loans(
    customer_id, loan_file="loan.csv", repayment_file="repayments.csv"
):
    try:
        with open(loan_file, newline="", encoding="utf-8") as lf:
            loan_reader = csv.DictReader(lf)
            loans = [row for row in loan_reader if row["customer_id"] == customer_id]

        with open(repayment_file, newline="", encoding="utf-8") as rf:
            repayment_reader = csv.DictReader(rf)
            repayments = [
                row for row in repayment_reader if row["customer_id"] == customer_id
            ]

        unpaid_loans = []
        for loan in loans:
            match_found = False
            for repayment in repayments:
                if (
                    loan["loan_amount"] == repayment["amount"]
                    and loan["loan_date"] == repayment["repayment_date"]
                ):
                    match_found = True
                    break
            if not match_found:
                unpaid_loans.append(loan)

        if unpaid_loans:
            print(f"\n■ 顧客ID: {customer_id} の未返済貸付一覧")
            for loan in unpaid_loans:
                loan_date = datetime.strptime(loan["loan_date"], "%Y-%m-%d").strftime(
                    "%Y年%m月%d日"
                )
                amount_str = f"{int(loan['loan_amount']):,}円"
                due_date = loan.get("due_date", "")
                print(f"{loan_date}｜{amount_str}｜返済期日：{due_date}")
        else:
            print("✅ 全ての貸付は返済済みです。")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
