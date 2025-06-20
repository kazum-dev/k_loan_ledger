from modules.customer_module import list_customers, search_customer, get_all_customer_ids, get_credit_limit
from modules.loan_module import register_loan, display_loan_history, register_repayment, display_repayment_history, display_unpaid_loans, calculate_late_fee, extract_overdue_loans
from modules.balance_module import display_balance
from datetime import datetime

def loan_registration_mode():
    print("=== 顧客検索＆貸付記録モード ===")

    list_customers()
    keyword = input("検索したい顧客名またはIDの一部を入力してください: ")
    search_customer(keyword)

    print("\n=== 貸付記録を登録 ===")
    customer_id_input = input("👤顧客IDを入力してください(例：001またはCUST001): ").strip()

    #🔧 入力補正
    if not customer_id_input.startswith("CUST"):
        customer_id_input = "CUST" + customer_id_input.zfill(3)

    customer_id = customer_id_input
    valid_ids = get_all_customer_ids()

    if customer_id not in valid_ids:
        print("❌ 顧客IDが存在しません。先に顧客登録を行ってください。")
        return

    amount_input = input("💰貸付記録を入力してください（例：10000）: ")

    try:
        amount = int(amount_input)
        if amount <= 0:
            print("❌金額は1円以上で入力してください。")
            return
        
        credit_limit = get_credit_limit(customer_id)
        if credit_limit is None:
            print("❌ 顧客の上限金額を取得できません。")
            return
        
        
        if amount > credit_limit:
            print(f"⚠ 上限額({credit_limit}円) を超えています。貸付記録を保存できません。")
            return
        
    except ValueError:
        print("❌ 金額は整数で入力してください。")
        return

    interest_input = input("📈利率（％）を入力してください ※未入力時は10.0%: ").strip()
    try:
        interest_rate = float(interest_input) if interest_input else 10.0
        if interest_rate <= 0:
            print("❌ 利率は1%以上で入力してください。")
            return
    except ValueError:
        print("❌ 利率は数値で入力してください。")
        return
    
    loan_date = input("📅貸付日を入力(例：2025-05-05)※未入力なら今日の日付になります: ")
    if not loan_date:
        loan_date = datetime.today().strftime("%Y-%m-%d")

    repayment_method = input("💳返済方法を入力してください（例：現金／振込）: ").strip()
    if not repayment_method:
        repayment_method = "未設定"

    register_loan(customer_id, amount, loan_date, interest_rate_percent=interest_rate, repayment_method=repayment_method)
    

def loan_history_mode():
    print("=== 履歴表示モード ===")
    customer_id = input("👤 顧客IDを入力してください（例：CUST001 または 001）： ").strip().upper()

    #🔧 補正処理を追加
    if not customer_id.startswith("CUST"):
        customer_id = "CUST" + customer_id.zfill(3)

    display_loan_history(customer_id)

def main():
    while True:
        print("=== K's Loan Ledger ===")
        print("1: 貸付記録モード")
        print("2: 貸付履歴表示モード")
        print("3: 返済記録モード")
        print("4: 返済履歴表示モード")
        print("5: 残高照会モード")
        print("9: 未返済サマリー表示（テスト用）")
        print("10: 延滞貸付表示モード")
        print("0: 終了")

        choice = input("モードを選択してください: ").strip()

        if choice =="1":
            loan_registration_mode()
        elif choice == "2":
            loan_history_mode()
        elif choice == "3":
            register_repayment()
        elif choice =='4':
            print("\n=== 返済履歴表示モード ===")
            customer_id = input("👤 顧客IDを入力してください（例：CUST001 または 001）: ").strip().upper()
            if not customer_id.startswith("CUST"):
                customer_id = "CUST" + customer_id.zfill(3)
            display_repayment_history(customer_id)
        elif choice == "5":
            print("\n=== 残高照会モード ===")
            customer_id = input("👤 顧客IDを入力してください（例：CUST001 または 001）: ").strip().upper()
            if not customer_id.startswith("CUST"):
                customer_id = "CUST" + customer_id.zfill(3)
            display_balance(customer_id)
        elif choice == "9":
            print("\n=== 未返済貸付一覧＋サマリー ===")
            customer_id = input("👤 顧客IDを入力してください（例：CUST001　または 001）: ").strip().upper()
            if not customer_id.startswith("CUST"):
                customer_id = "CUST" + customer_id.zfill(3)
            display_unpaid_loans(customer_id)
        elif choice == "10":
            print("\n=== 延滞貸付一覧表示モード ===")
            customer_id = input("👤 顧客IDを入力してください（例：CUST001 または 001）: ").strip().upper()
            if not customer_id.startswith("CUST"):
                customer_id = "CUST" + customer_id.zfill(3)
            extract_overdue_loans(customer_id)

        elif choice == "0":
            print("終了します。")
            break
        
        else:
            print("❌ 無効な選択肢です。もう一度入力してください。")

if __name__ == "__main__":
    main()