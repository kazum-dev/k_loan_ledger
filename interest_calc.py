print("hello,K") #動作確認

from datetime import datetime

#各関数の定義
def get_valid_days():
    while True:
        try:
            days = int(input("貸付日数を入力してください:"))
            if days <= 0:
                print("貸付日数は一日以上で入力してください。")
            else:
                return days
        except ValueError:
            print("有効な日数を入力してください。")


#貸付金額をユーザーから入力（数字に変換）
def get_valid_amount():
    while True:
        try:
            amount = int(input("貸付金額を入力してください（円）: "))
            if amount <= 0:
                print("貸付金額は1円以上で入力してください。")
            else:
                return amount #有効な数字なので返す
        except ValueError:
            print("有効な金額を入力してください")

#利率（％）を入力してもらい、数字に変換
#利率入力関数
def get_valid_interest_rate():
    while True:
        try:
            rate = float(input("利率（％）を入力してください: "))
            if rate < 0 or rate > 1000:
                print("利率は0以上、1000以下で入力してください。")
            else:
                return rate
        except ValueError:
            print("有効な利率を入力してください。")

#利息計算の関数を定義
def calculate_interest(amount, rate, days):
    interest = amount * (rate / 100) * (days / 30)
    total = amount + interest
    return interest, total

def calculate_late_fee(total,due_date_str, late_fee_rate):
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        today = datetime.today()
        late_days = (today - due_date).days

        if late_days <= 0:
            return 0 #延滞していなければ手数料ゼロ
        else:
            #月利（%）を日割りにして日数分計算
            late_fee =total * (late_fee_rate / 100) * (late_days / 30)
            return late_fee
    except ValueError:
        print("日付の形式が正しくありません。例：2025-04-25")
        return 0 

def display_results(interest, total, late_fee, final_total):
    print("\n📄　計算結果")
    print(f"利息：　¥{interest:,.2f}")
    print(f"返済総額：　¥{total:,.2f}")
    print(f"延滞手数料：　¥{late_fee:,.2f}")
    print(f"最終返済総額：　¥{final_total:,.2f}")

def main():
    print("💰　K's Loan Ledger　利息・延滞手数料計算ツール")
    print("※　利率は年利（％）、返済期日は　YYYY-MM-DD　形式で入力してください。\n")

    amount = get_valid_amount()
    rate = get_valid_interest_rate()
    days = get_valid_days()

    interest, total = calculate_interest(amount,rate,days)

    due_date_str = input("返済期日を入力してください（例：2025-04-25）: ")
    late_fee_rate = float(input("延滞手数料（月利％）を入力してください: "))
    late_fee = calculate_late_fee(total, due_date_str,late_fee_rate) 

    final_total = total + late_fee

    #結果をまとめて表示
    display_results(interest,total, late_fee, final_total)

if __name__ == "__main__":
    main()