import csv
import os
from datetime import date, datetime, timedelta

# 日付ごとにユニークな loan_id を生成する関数
def generate_loan_id(file_path, loan_date=None):
    # 貸付日が未指定なら今日の日付を設定
    if loan_date is None:
        loan_date = datetime.today().strftime("%Y-%m-%d")

    # 日付を　yyymmdd に変換（例：20250707）
    date_part = loan_date.replace("-", "")

    # ローンID の説頭辞を作成（例：L20250707-）
    prefix = f"L{date_part}-"

    # カウンタを初期化
    counter = 1

    # CSVファイルが存在する場合、同じ日の貸付件数をカウントする
    if os.path.exists(file_path):
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 貸付日の一致を確認
                if row.get("loan_date") == loan_date:
                    counter += 1

    # ローンIDを生成（例：L20250707-003）
    return f"{prefix}{str(counter).zfill(3)}"

# main.py から新規貸付データを受け取り CSV に保存する関数
# late_fee_rate_percent は延滞利率（％）
# デフォルトは10.0
def register_loan(customer_id, amount, loan_date, due_date=None, interest_rate_percent=10.0, repayment_method="未設定", grace_period_days=0, late_fee_rate_percent=10, file_path="loan_v3.csv"):
    
    # 利率と延滞利率を受信したことを表示
    print(f"[DEBUG] 利率受信: {interest_rate_percent}")
    print(f"[DEBUG] 延滞利率受信:{late_fee_rate_percent}%")

    """
    貸付情報をCSVに追記します。
    初回の場合はヘッダーも自動で追加します。
    """

    # CSV　のヘッダを定義
    header = [
        "loan_id",                  # 貸付ID
        "customer_id",              # 顧客ID
        "loan_amount",              # 借りた金額
        "loan_date",                # 貸付日
        "due_date",                 # 返済期日
        "interest_rate_percent",    # 通常利率（%）
        "repayment_expected",       # 予定返済額
        "repayment_method",         # 返済方法
        "grace_period_days",        # 延滞猶予日数
        "late_fee_rate_percent",    # 延滞利率（%）
        "late_base_amount"          # 延滞対象元金
    ]

    # 返済期日が未入力なら 貸付日（loan_date） の30日後をデフォルト設定
    if due_date is None or due_date == "": 
        due_date =  (datetime.strptime(loan_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d") 

    # 予定返済額（repayment_expected）を自動計算（整数に丸める）
    repayment_expected = int(amount * (1 + interest_rate_percent / 100))
    print(f"[DEBUG] 自動計算された予定返済額: {repayment_expected}")

    # 延滞対象元金を初期設定（amount をコピー）
    late_base_amount = amount
    print(f"[DEBUG] late_base_amount の設定: {late_base_amount}")

    # ユニークな loan_id を生成
    loan_id = generate_loan_id(file_path, loan_date)

    try:
        # ファイルが存在しない or 空なら header を w モードで書く
        if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:    
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(header)

        # データ行を a モードで　CSV　に追記する
        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # 保存する内容をデバック出力
            print("[DEBUG] 保存内容：", [loan_id, customer_id, amount, loan_date, due_date, interest_rate_percent, repayment_expected, repayment_method, grace_period_days, late_fee_rate_percent, late_base_amount])
            writer.writerow([loan_id, customer_id, amount, loan_date, due_date, interest_rate_percent, repayment_expected, repayment_method ,grace_period_days, late_fee_rate_percent, late_base_amount])
        
        # 保存成功メッセージ
        print("✅貸付記録が保存されました。")
    except Exception as e:
        # エラーが起きた場合はメッセージを表示
        print(f"❌エラーが発生しました: {e}")

# 顧客IDごとの貸付履歴を表示する関数
def display_loan_history(customer_id, filepath):
    try:
        # CSVファイルを開き、DictReaderで読み込む
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # customer_id が一致する行を抽出
            history = [row for row in reader if row['customer_id'] == customer_id]

        # 該当データがあれば表示
        if history:
            print(f"\n■ 顧客ID: {customer_id}の貸付履歴")
            for row in history:
                # 日付を YYY年MM月DD日　の形式に変換
                date_str = datetime.strptime(row['loan_date'], '%Y-%m-%d').strftime('%Y年%m月%d日') 

                # 金額をカンマ区切りに整形
                amount_str = f"{int(row['loan_amount']):,}円"

                # 期日を取得（存在しない場合は空文字）
                due_date = row.get('due_date', '')

                # 一軒ずつ履歴を出力
                print(f"{date_str}｜{amount_str}｜返済期日：{due_date}")

        else:
            # 該当履歴がなかった場合のメッセージ
            print("該当する貸付履歴はありません。")

    except FileNotFoundError:
        # ファイルが存在しない場合のエラーメッセージ
        print("エラー：ファイルが見つかりません。ファイルパスを確認してください。")
    except Exception as e:
        # その他の予期せぬエラー
        print(f"予期せぬエラーが発生しました:{e}")

# 顧客からの返済を登録する関数
def register_repayment():
    loan_id = input("返済する loan_id を入力してください（例：L20250709-001）: ").strip()

    #顧客IDの入力と補正
    customer_id = input("顧客IDを入力してください（例：001 または CUST001）： ").strip()

    # 入力された顧客IDを正規化（3桁なら CUST を付与）
    if customer_id.isdigit() and len(customer_id) == 3:
        customer_id = f"CUST{customer_id}"
    elif not customer_id.startswith("CUST"):
        # フォーマットが不正な場合はエラー表示して終了
        print("❌ 顧客の形式が不正です。３桁の数字または CUSTxxx 形式で入力してください。")
        return

    #返済額を入力させる
    try:
        amount = int(input("返済額を入力してください（例：5000）: ").strip())
        # 金額が正の整数であるか確認
        if amount <= 0:
            raise ValueError
    except ValueError:
        # 不正な金額入力時のエラー表示
        print("❌金額は正の整数で入力してください。")
        return
    
    #返済日の入力（未入力の場合は今日の日付）
    repayment_date = input("📅 返済日を入力してください（未入力で本日の日付を使用）：").strip()
    if not repayment_date:
        repayment_date = str(datetime.today().date())

    #CSVに返済データを追記
    try:
        with open("repayments.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # 顧客ID・返済額・返済日を保存
            writer.writerow([loan_id, customer_id, amount, repayment_date])

        # 保存成功メッセージ
        print(f"✅ {customer_id} の返済記録を保存しました。")

    except Exception as e:
        # CSV書き込みエラー時のメッセージ
        print(f"❌ CSV書き込み中にエラーが発生しました: {e}")

# B-11.1 loan_idで貸付情報を検索
def get_loan_info_by_loan_id(file_path, loan_id):
    with open(file_path, newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['loan_id'] == loan_id:
                return row
    return None

# B-11.1 repayments.csvから返済合計を取得
def get_total_repaid_amount(file_path, loan_id):
    total = 0
    with open(file_path, newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['loan_id'] == loan_id:
                print(f"DEBUG: 加算中 -> {row['repayment_amount']}")
                total += int(row['repayment_amount'])
    return total

# ▼ B-11.2 過剰返済チェックの共通関数
def is_over_repayment(loans_file, repayments_file, loan_id, repayment_amount):
    """
    予定返済額を超えてないかチェックする。
    超えていたらFalseを返し、同時にエラーメッセージを出力する。
    超えていたらFalseを返し、同時にエラーメッセージを出力する。
    """

    # 該当のloan_idの貸付情報を取得
    loan_info = get_loan_info_by_loan_id(loans_file, loan_id)
    if loan_info is None:
        print("❌ 指定された loan_id が loan_v3.csv に見つかりません")
        return False
    
    # 予定返済額 repayment_expected を辞書から取得
    try:
        repayment_expected = int(loan_info["repayment_expected"])
    except (KeyError, ValueError):
        print("❌ repayment_expected の読み込みに失敗しました。")
        return False

    # loan_idに対する返済の合計額を取得
    total_repaid = get_total_repaid_amount(repayments_file, loan_id)

    # 合計返済額 + 入力額 > 予定返済額 か判定
    if total_repaid + repayment_amount > repayment_expected:
        print(f"❌ 返済額が予定額を超えています。現在の累計返済額：{total_repaid}円 / 予定：{repayment_expected}円")
        return False

    return True 

# 顧客IDごとの返済履歴を表示する関数
def display_repayment_history(customer_id, filepath='repayments.csv'):
    try:
        # 返済履歴のCSVファイルを開く
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # customer_id が一致する行を抽出する
            history = [row for row in reader if row['customer_id'] == customer_id]

        if history:
            # 該当する履歴があった場合
            print(f"\n■ 顧客ID: {customer_id} の返済履歴")
            for row in history:
                # 日付を YYY年MM月DD日 形式に変換
                date_str = datetime.strptime(row['repayment_date'], '%Y-%m-%d').strftime('%Y年%m月%d日')

                # 金額をカンマ区切りに整形
                amount_str = f"{int(row['amount']):,}円"

                # 履歴を表示
                print(f"{date_str}｜{amount_str}")
        else:
            # 該当履歴がない場合のメッセージ
            print("該当する返済履歴はありません。")

    except FileNotFoundError:
        # CSVファイルが存在しない場合のエラーメッセージ
        print("エラー：repayments.csv が見つかりません。")

    except Exception as e:
        # その他の予期せぬエラー
        print(f"予期せぬエラーが発生しました: {e}")

# 未返済の貸付を抽出して表示する関数
def display_unpaid_loans(customer_id, loan_file='loan.csv', repayment_file='repayments.csv'):
    try:
        # 貸付データを読み込む
        with open(loan_file, newline='', encoding='utf-8') as lf:
            loan_reader = csv.DictReader(lf)
            # 顧客IDが一致するデータを抽出
            loans = [row for row in loan_reader if row['customer_id'] == customer_id]
        
        # 返済データを読み込む
        with open(repayment_file, newline='', encoding='utf-8') as rf:
            repayment_reader = csv.DictReader(rf)
            # 顧客IDが一致する返済データを抽出
            repayments = [row for row in repayment_reader if row['customer_id'] == customer_id]

        # 未返済の貸付を格納するリスト
        unpaid_loans = []

        # 貸付データと返済データを突き合わせる
        for loan in loans:
            match_found = False
            for repayment in repayments:
                # 同額＆同日なら返済済とみなす
                if(
                    loan['loan_amount'] == repayment['amount'] and
                    loan['loan_date'] == repayment['repayment_date']
                ):
                    match_found = True
                    break
            if not match_found:
                # 一致しなかったものを返済とみなす
                unpaid_loans.append(loan)
            
        if unpaid_loans:
            # 未返済データがあった場合
            print(f"\n■ 顧客ID: {customer_id} の未返済貸付一覧")
            today = datetime.today().date()

            for loan in unpaid_loans:
                # 日付を表示用に変換
                loan_date = datetime.strptime(loan['loan_date'], '%Y-%m-%d').strftime('%Y年%m月%d日')
                # 金額をカンマ区切りに整形
                amount_str = f"{int(loan['loan_amount']):,}円"
                # 返済期日を取得（存在しない場合は空文字）
                due_date_str = loan.get('due_date', '')
                status = ""

                # ✅ 延滞チェック
                if due_date_str:
                    try:
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                        if due_date < today:
                            # 延滞中の場合
                            status = "⚠延滞中"
                            principal = int(loan["loan_amount"])
                            # 延滞日数と手数料を計算
                            days_late, late_fee = calculate_late_fee(principal, due_date)
                            status += f"｜延滞日数：{days_late}日｜延滞手数料：¥{late_fee:,}"
                    except ValueError:
                        # 期日のフォーマットが不正な場合
                        status = "⚠期日形式エラー"

                # 1件の貸付情報を表示
                print(f"{loan_date}｜{amount_str}｜返済期日：{due_date_str}{status}")

            # 未返済の件数と合計金額を表示
            total_unpaid =  len(unpaid_loans)
            total_amount = sum(int(loan['loan_amount']) for loan in unpaid_loans)
            print(f"\n🧮 未返済件数：{total_unpaid}件｜合計：¥{total_amount:,}")

        else:
            # 未返済がない場合のメッセージ
            print("✅ 全ての貸付は返済済みです。")

    except Exception as e:
        # 想定外のエラーが発生した場合
        print(f"❌ エラーが発生しました: {e}")

from datetime import date

# 延滞日数と延滞手数料を計算する関数
def calculate_late_fee(principal, due_date):
    """
    月利10%を基準とし、(日割り0.0033)で延滞手数料を計算する
    """

    # 今日の日付を取得
    today = date.today()

    # 期日を過ぎていれば延滞とみなす
    if due_date < today:
        # 延滞日数を計算
        days_late = (today - due_date).days

        # 日割り利率（例：月利10% ÷ 30日）
        daily_late_rate = 0.10 / 30

        # 延滞手数料を計算
        late_fee = round(principal * daily_late_rate * days_late)

        # 延滞日数と手数料を返す
        return days_late, late_fee
    
    # 延滞していない場合は0を返す
    return 0, 0

# 延滞中の貸付を抽出して表示する関数
def extract_overdue_loans(customer_id, loan_file='loan.csv', repayment_file='repayments.csv'):
    try:
        # 貸付データを読み込む
        with open(loan_file, newline='', encoding='utf-8') as lf:
            loan_reader = csv.DictReader(lf)
            # 顧客IDが一致する貸付データを抽出
            loans = [row for row in loan_reader if row['customer_id'] == customer_id]

        # 返済データを読み込む
        with open(repayment_file, newline='', encoding='utf-8') as rf:
            repayment_reader = csv.DictReader(rf) 
            # 顧客IDが一致する返済データを抽出
            repayments = [row for row in repayment_reader if row['customer_id'] == customer_id]

        # 今日の日付を取得
        today = datetime.today().date()

        # 延滞中の貸付を格納するリスト
        overdue_loans = []

        # 貸付データをループ
        for loan in loans:
            match_found = False

            # 返済データと突き合わせ
            for repayment in repayments:
                # 同日なら返済済みとみなす
                if(
                    loan['loan_amount'] == repayment['amount'] and
                    loan['loan_date'] == repayment['repayment_date']
                ):
                    match_found = True
                    break

            # 返済済みならスキップ
            if match_found:
                 continue
            
            # 延滞判定
            due_date_str = loan.get('due_date', '')
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    if due_date < today:
                        # 延滞中なら overdue_loans に追加
                        overdue_loans.append(loan)
                except ValueError:
                    # 日付フォーマットの場合はスキップ
                    continue

        if overdue_loans:
            # 延滞中の貸付があった場合
            print(f"\n🚨 顧客ID: {customer_id} の延滞中の貸付一覧")
            for loan in overdue_loans:
                # 日付を YYY年MM月DD日 の形式に変換
                loan_date = datetime.strptime(loan['loan_date'], '%Y-%m-%d').strftime('%Y年%m月%d日')

                # 金額をカンマ区切りに整形
                amount_str = f"{int(loan['loan_amount']):,}円"

                # 返済期日を取得
                due_date_str = loan['due_date']
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()

                # 返済日数と延滞手数料を計算
                principal = int(loan["loan_amount"])
                days_late, late_fee = calculate_late_fee(principal, due_date)

                # 延滞情報を表示
                print(f"{loan_date}｜{amount_str}｜返済期日：{due_date_str}｜延滞：{days_late}日｜手数料：¥{late_fee:,}")
        else:
            # 延滞がない場合のメッセージ
            print("✅ 現在延滞中の貸付はありません。")

    except Exception as e:
        # 想定外のエラーが発生した場合
        print(f"❌ エラーが発生しました: {e}")

def calculate_total_repaid_by_loan_id(repayments_file, loan_id):
    """
    指定された loan_id に対応する累計返済情報を計算して返す変数。
    """
    import csv

    total = 0
    try:
        with open(repayments_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('loan_id') == loan_id:
                    try:
                        amount = int(row.get('repayment_amount', '0'))
                        total += amount
                    except (ValueError, TypeError):
                        continue # 金額が不正な場合はスキップ
    except FileNotFoundError:
        print(f"[ERROR] ファイルが見つかりません: {repayments_file}")
        return 0
    except Exception as e:
        print(f"[ERROR] 想定外のエラーが発生しました: {e}")
        return 0
    
    return total