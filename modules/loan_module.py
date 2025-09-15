import csv
import os
import pandas as pd
from datetime import date, datetime, timedelta
from modules.utils import get_project_paths
from decimal import Decimal, ROUND_HALF_UP, getcontext
from enum import Enum
from modules.utils import normalize_method  # 既存の正規化（文字列）を再利用
getcontext().prec = 28 

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

# 返済方法 ENUM（内部表現を固定）
class RepaymentMethod(Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    UNKOWN = "UNKNOWN"

def _normalize_method_to_enum(value: str | None) -> RepaymentMethod:
    """
    utils.normalize_method (→ "CASH"/"BANK_TRANSFER"/"UNKNOWN" を返す前提)
    を受けて Enum にマッピング。None/空は UNKNOWN。
    """
    try:
        s = normalize_method(value or "")
    except Exception:
        s = "UNKNOWN"
    mapping = {
        "CASH": RepaymentMethod.CASH,
        "BANK_TRANSFER": RepaymentMethod.BANK_TRANSFER,
        "UNKNOWN": RepaymentMethod.UNKOWN,
    }
    return mapping.get(s, RepaymentMethod.UNKOWN)

def round_money(amount: Decimal | int | float, *, unit: int = 1) -> int:
    """
    日本円の四捨五入。unitで10円/100円丸めにも対応（規定1円）。
    """
    if unit not in(1, 10, 100, 1000):
        raise ValueError("unit must be 1/10/100/1000")
    d = Decimal(str(amount)) / Decimal(unit)
    y = d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(y * unit)

def calc_repayment_expected(amount: int | float | Decimal,
                            interest_rate_percent: float | Decimal,
                            *, round_unit: int = 1) -> int:
    """
    予定返済額 = round_money( amount * (1+ 利率/100) )
    """
    base = Decimal(str(amount))
    rate = Decimal(str(interest_rate_percent)) / Decimal("100")
    raw = base * (Decimal("1") + rate)
    return round_money(raw, unit=round_unit)

# main.py から新規貸付データを受け取り CSV に保存する関数
# late_fee_rate_percent は延滞利率（％）
# デフォルトは10.0
def register_loan(
    customer_id,
    amount,
    loan_date,
    due_date=None,
    interest_rate_percent=10.0,
    repayment_method="未設定",
    grace_period_days=0,
    late_fee_rate_percent=10,
    file_path=None,     # ← ここを None に
):
    # === 追加: パス自動解決 ===
    if not file_path:
        paths = get_project_paths()
        file_path = str(paths["loans_csv"])
    
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

    # 予定返済額 (Decimalベースで四捨五入。将来は round_unit=10/100 にも対応可)
    repayment_expected = calc_repayment_expected(amount, interest_rate_percent, round_unit=1)
    print(f"[DEBUG] 自動計算された予定返済額: {repayment_expected}")

    # 延滞対象元金を初期設定（amount をコピー）
    late_base_amount = amount
    print(f"[DEBUG] late_base_amount の設定: {late_base_amount}")

    # ユニークな loan_id を生成
    loan_id = generate_loan_id(file_path, loan_date)

    # 返済方法をENUM化に正規化（内部統一）
    method_enum = _normalize_method_to_enum(repayment_method)

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
            print("[DEBUG] 保存内容：", [loan_id, customer_id, amount, loan_date, due_date, interest_rate_percent, repayment_expected, method_enum.value, grace_period_days, late_fee_rate_percent, late_base_amount])
            writer.writerow([
                loan_id, customer_id, amount, loan_date, due_date, 
                interest_rate_percent, repayment_expected, 
                method_enum.value,
                grace_period_days, late_fee_rate_percent, late_base_amount
            ])
        
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

    #CSVに返済データを追記(旧)
    #try:
        #with open("repayments.csv", mode="a", newline="", encoding="utf-8") as file:
            #writer = csv.writer(file)
            # 顧客ID・返済額・返済日を保存
            #writer.writerow([loan_id, customer_id, amount, repayment_date])

        # 保存成功メッセージ
        #print(f"✅ {customer_id} の返済記録を保存しました。")

    #except Exception as e:
        # CSV書き込みエラー時のメッセージ
        #print(f"❌ CSV書き込み中にエラーが発生しました: {e}")

    # CSVに返済データを追記（ヘッダー保証 + 列名を新仕様に統一）
    try:
        header = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]
        file_exists = os.path.exists("repayments.csv")
        need_header = (not file_exists) or (os.stat("repayments.csv").st_size == 0)

        with open("repayments.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=header)
            if need_header:
                writer.writeheader()
            writer.writerow({
                "loan_id": loan_id,
                "customer_id": customer_id,
                "repayment_amount": amount,
                "repayment_date": repayment_date
            })
        print(f"✅ {customer_id} の返済記録を保存しました。")
    except Exception as e:
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
    with open(file_path, newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['loan_id'] == loan_id:
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
                # 返済日
                date_str = datetime.strptime(row['repayment_date'], '%Y-%m-%d').strftime('%Y年%m月%d日')
                # 金額
                amount_str = f"{int(row['repayment_amount']):,}円"

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

# 未返済の貸付を表示　B-14　新
def display_unpaid_loans(
        customer_id, 
        loan_file='loan_v3.csv', 
        repayment_file='repayments.csv',
        *,
        filter_mode='all',  # "all" /  "overdue"
        today=None,
):
    """
    未返済ローンを一括表示する。
    - filter_mode="all"     : 返済期日を問わず未返済すべて（旧モード9）
    - filter_mode="overdue" : 返済期日を過ぎた未返済のみ（旧モード10）
    """
    try:
        _today = today or date.today()

        # 1) 顧客の全貸付
        with open(loan_file, newline='', encoding='utf-8') as lf:
            loan_reader = csv.DictReader(lf)
            loans = [row for row in loan_reader if row.get('customer_id') == customer_id]

        # 2) 未返済のみ抽出（loan_idベース）
        unpaid = []
        for loan in loans:
            loan_id = loan.get('loan_id')
            if not loan_id:
                continue
            if not is_loan_fully_repaid(loan_id, loan_file, repayment_file):
                unpaid.append(loan)

        # 3) overdueフィルタ
        def _is_overdue(row):
            ds = row.get('due_date', '')
            if not ds:
                return False
            try:
                grace_days = int(row.get('grace_period_days', 0))
            except ValueError:
                grace_days = 0
            # ✅ 猶予込みで延滞判定
            return calc_overdue_days(_today, ds, grace_days) > 0
        
        if filter_mode == 'overdue':
            unpaid = [ln for ln in unpaid if _is_overdue(ln)]
        elif filter_mode != 'all':
            print(f"[WARN] 未知のfilter_mode: {filter_mode} → 'all'扱い")

        # 4) 並び順：期日昇順→loan_id（期日なし/不正は末尾）
        def _due_key(ln):
            ds = ln.get('due_date', '')
            try:
                return (0, datetime.strptime(ds, '%Y-%m-%d').date(), ln.get('loan_id', ''))
            except ValueError:
                return (1, date.max, ln.get('loan_id', ''))
            
        unpaid.sort(key=_due_key)

        # 3) 表示
        if not unpaid:
            if filter_mode == 'overdue':
                print("✅ 現在延滞中の未返済はありません。")
            else:
                print("✅ 全ての貸付は返済済みです。")
            return []
        
        header = f"\n■ 顧客ID: {customer_id} の{'延滞中の未返済' if filter_mode=='overdue' else '未返済'}貸付一覧"
        print(header)
        print("  [STATUS]  loan_id      ｜貸付日        ｜金額        ｜期日           ｜予定        ｜返済済      ｜残高")

        rows_out = []
        for loan in unpaid:
            loan_id = loan['loan_id']
            loan_date_jp = datetime.strptime(loan['loan_date'], '%Y-%m-%d').strftime('%Y年%m月%d日')
            amount = int(loan['loan_amount'])
            amount_str = f"{amount:,}円"

            due_str = loan.get('due_date', '')
            status = 'UNPAID'
            days_late = 0
            late_fee = 0
            recovery_amount = None

            # 予定返済額・累計返済・残
            try:
                expected = int(loan.get('repayment_expected', '0'))
            except ValueError:
                expected = 0
            total_repaid = calculate_total_repaid_by_loan_id(repayment_file, loan_id)
            remaining = max(0, expected - total_repaid)

            if due_str:
                try:
                    # 期日バース
                    _ = datetime.strptime(due_str, '%Y-%m-%d')  # フォーマット検証用
                    due_jp = datetime.strptime(due_str, '%Y-%m-%d').date().strftime('%Y年%m月%d日')

                    # CSVから延滞用パラメータ
                    try:
                        late_base_amount = int(float(loan.get('late_base_amount', amount)))
                    except ValueError:
                        late_base_amount = amount
                    try:
                        late_rate_percent = float(loan.get('late_fee_rate_percent', 10.0))
                    except ValueError:
                        late_rate_percent = 10.0
                    grace_days = int(loan.get('grace_period_days', 0))

                    # ✅ 統一計算：残・延滞日数・延滞手数料・回収額（残＋手数料）
                    info = compute_recovery_amount(
                        repayment_expected=expected,
                        total_repaid=total_repaid,
                        today=_today,
                        due_date_str=due_str,
                        grace_period_days=grace_days,
                        late_fee_rate_percent=late_rate_percent,
                        late_base_amount=late_base_amount,
                    )

                    days_late= info["overdue_days"]
                    late_fee = info["late_fee"]
                    remaining = info["remaining"]
                    recovery_amount = info["recovery_total"]
                    status = 'OVERDUE' if days_late > 0 else 'UNPAID'

                except ValueError:
                    status = 'DATE_ERR'
                    due_jp = due_str

            else:
                due_jp = due_str


            #if due_str:
                #try:
                    #due = datetime.strptime(due_str, '%Y-%m-%d').date()
                   #due_jp = due.strftime('%Y年%m月%d日')
                    #if due < _today:
                        #status = 'OVERDUE'

                        # --- B-15：CSVの設定で延滞計算 ---
                        #try:
                            #late_base_amount = int(float(loan.get('late_base_amount', amount)))
                        #except ValueError:
                            #late_base_amount = amount
                        #try:
                            #late_rate_percent = float(loan.get('late_fee_rate_percent', 10.0))
                        #except ValueError:
                            #late_rate_percent = 10.0

                        #days_late, late_fee = calculate_late_fee(
                            #late_base_amount, 
                            #due,
                            #late_fee_rate_percent=late_rate_percent
                        #)
                        #recovery_amount = expected + late_fee # 🧾 回収額
                #except ValueError:
                    #status = 'DATE_ERR'
                    #due_jp = due_str # 壊れている場合は原文
            #else:
                #due_jp = due_str


            sep = "｜"
            # 延滞行のみ、追加情報を右側に連結
            extra = ""
            if status == 'OVERDUE':
                extra = (
                    f"{sep}延滞日数：{days_late}日"
                    f"{sep}延滞手数料：¥{late_fee:,}"
                    f"{sep}🧾回収額：¥{recovery_amount:,}"
                )
            else:
                extra = ""

            line = (
                f"[{status:<7}] "
                f"{loan_id:<14}{sep}"
                f"{loan_date_jp:<12}{sep}"
                f"{amount_str:>10}{sep}"
                f"期日：{due_jp:<12}{sep}"
                f"予定：¥{expected:,}{sep}"
                f"返済済：¥{total_repaid:,}{sep}"
                f"残：¥{remaining:,}"
                f"{extra}"
            )
            print(line)

            rows_out.append({
                "loan_id": loan_id,
                "loan_date": loan["loan_date"],
                "loan_amount": amount,
                "due_date": due_str,
                "status": status,
                "repayment_expected": expected,
                "total_repaid": total_repaid,
                "remaining":  remaining,
                "days_late": days_late,
                "late_fee": late_fee,
            })

        # サマリー
        total_unpaid = len(rows_out)
        total_remaining = sum(r["remaining"] for r in rows_out)

        # 内訳（モード9のみ表示）
        if filter_mode == "all":
            overdue_count = sum(1 for r in rows_out if r["status"] == "OVERDUE")
            in_time_count = total_unpaid - overdue_count
            print(f"\n内訳：延滞 {overdue_count} 件 / 期日内 {in_time_count} 件")

        print(f"\n🧮 件数：{total_unpaid}件|残高合計：¥{total_remaining:,}")

        return rows_out

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return []

# 未返済の貸付を抽出して表示する関数 バックアップ（旧バージョン）
def display_unpaid_loans_old(customer_id, loan_file='loan.csv', repayment_file='repayments.csv'):
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
def calculate_late_fee(principal, due_date, *, late_fee_rate_percent: float = 10.0):
    """
    月利(late_fee_rate_percent %）を (月利/30) の日割りで計算。
    - principal: 延滞対象元金(CSV の late_base_amount を想定)
    - due_date: 返済期日 (date)
    - late_fee_rate_percent: 月利 (%)　デフォルト10.0
    return: (days_late, late_fee)
    """
    today = date.today()
    if due_date < today:
        days_late = (today - due_date).days
        daily_late_rate = (float(late_fee_rate_percent) / 100.0) / 30.0
        late_fee = round(int(principal) * daily_late_rate * days_late)
        return days_late, late_fee
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
    repayments.csv のヘッダー表記ゆれを吸収しつつ、loan_id ごとの累計返済額を合算。
    """
    total = 0
    try:
        # ファイルを開く
        with open(repayments_file, mode='r', encoding='utf-8-sig', newline='') as file:
            r= csv.reader(file)
            header = next(r, None)
            if not header:
                print("[ERROR] repayments.csv が空です。")
                return 0
            # BOM/引用符/空白を除去
            header = [h.lstrip("\ufeff").strip().strip('"') for h in header]
            header = _normalize_repayments_headers(header)  # ★表記ゆれ吸収

            # 必須列がなければ0で返す
            if "loan_id" not in header or "repayment_amount" not in header:
                print("[ERROR] repayments.csv のヘッダーに必須列が見つかりません。")
                return 0

            idx_loan = header.index("loan_id")
            idx_amt = header.index("repayment_amount")

            for row in r:
                if len(row) <= max(idx_loan, idx_amt):
                    continue
                if row[idx_loan] == loan_id:
                    try:
                        total += int(float(row[idx_amt]))
                    except (ValueError, TypeError):
                        continue
    except FileNotFoundError:
        print(f"[ERROR] ファイルが見つかりません: {repayments_file}")
        return 0
    except Exception as e:
        print(f"[ERROR] 想定外のエラーが発生しました: {e}")
        return 0
    return total

def get_repayment_expected(loan_id: str, loan_file: str = "loan_v3.csv") -> float:
    """
    指定された loan_id に対して予定返済額を取得する。
    """
    df = pd.read_csv(loan_file)
    row = df[df["loan_id"] == loan_id]
    if row.empty:
        raise ValueError(f"[ERROR] loan_id '{loan_id}' がloan_v3.csv に存在しません。")    
    return float(row.iloc[0]["repayment_expected"])

def is_loan_fully_repaid(loan_id: str, loan_file: str = "loan_v3.csv", repayments_file: str = "repayments.csv") -> bool:
    """
    完了された loan_id の返済が完了しているかどうかを判定する。
    完了 → True、未完了 → False
    """
    expected = get_repayment_expected(loan_id, loan_file) # 予定返済額を取得
    total_repaid = calculate_total_repaid_by_loan_id(repayments_file, loan_id)

    return total_repaid >= expected

# C-0 （today＋猶予の延滞統一 & 回収額一本化）
def _parse_date_yyyy_mm_dd(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()

def calc_overdue_days(today: date, due_date_str: str, grace_period_days: int) -> int:
    d_due = _parse_date_yyyy_mm_dd(due_date_str)
    threshold = d_due + timedelta(days=int(grace_period_days or 0))
    return max(0, (today - threshold).days)

def calc_late_fee(
        late_base_amount: float,
        late_fee_rate_percent: float,
        overdue_days: int,
        month_days: int = 30
) -> float:
    if overdue_days <= 0 or late_base_amount <= 0 or late_fee_rate_percent <= 0:
        return 0.0
    return float(late_base_amount) * (float(late_fee_rate_percent) / 100.0) * (overdue_days / month_days)

def _to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default
    
def compute_remaining_amount(repayment_expected: float, total_repaid: float) -> float:
    return max(0.0, float(repayment_expected) - float(total_repaid))

def compute_recovery_amount(
    *,
    repayment_expected: float,
    total_repaid: float,
    today: date,
    due_date_str: str,
    grace_period_days: int, 
    late_fee_rate_percent: float,
    late_base_amount: float | None = None
) -> dict:
    remain = compute_remaining_amount(repayment_expected, total_repaid)
    base = late_base_amount if late_base_amount is not None else repayment_expected
    odays = calc_overdue_days(today, due_date_str, grace_period_days) # 期日 + 猶予日数 を閾値にして延滞日数を返す（マイナスは0で切り上げ）
    lfee = calc_late_fee(base, late_fee_rate_percent, odays)
    return{
        "remaining": round(remain, 2),
        "late_fee": round(lfee, 2),
        "recovery_total": round(remain + lfee, 2),
        "overdue_days": odays,
    }

def _normalize_repayments_headers(header_row: list[str]) -> list[str]:
    mapping = {
        "repayed_amount": "repayment_amount",
        "repay_amount": "repayment_amount",
        "loanid": "loan_id",
        "date": "repayment_date",
        "payer": "customer_id",

    }
    return [mapping.get(h.strip(), h.strip()) for h in header_row]
