import csv
import os
import pandas as pd
import json 
import warnings
import sys
from datetime import date, datetime, timedelta
from modules.utils import get_project_paths, normalize_method # 既存の正規化（文字列）を再利用
from decimal import Decimal, ROUND_HALF_UP, getcontext
from enum import Enum
getcontext().prec = 28 
VERBOSE_AUDIT = True  # 本番で抑えたいときは False


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
    UNKNOWN = "UNKNOWN"
    UNKOWN = "UNKNOWN" # backward-compat alias(一時的に残す)

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
        "UNKNOWN": RepaymentMethod.UNKNOWN,
    }
    return mapping.get(s, RepaymentMethod.UNKNOWN)

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
        paths = _get_project_paths_patched()
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

    # 予定返済額（整数化を明示）
    principal = int(float(amount))
    repayment_expected = calc_repayment_expected(principal, interest_rate_percent, round_unit=1)

    print(f"[DEBUG] 自動計算された予定返済額: {repayment_expected}")

    # C-4.5 延滞対象元金は常に元金（整数化済の principal）に固定
    late_base_amount = principal
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
            print("[DEBUG] 保存内容：", [loan_id, customer_id, principal, loan_date, due_date, interest_rate_percent, repayment_expected, method_enum.value, grace_period_days, late_fee_rate_percent, late_base_amount])
            writer.writerow([
                loan_id, customer_id, principal, loan_date, due_date, 
                interest_rate_percent, repayment_expected, 
                method_enum.value,
                grace_period_days, late_fee_rate_percent, late_base_amount
            ])
        
        # 保存成功メッセージ
        print("✅貸付記録が保存されました。")

        # ★C-4 監査フック（成功時のみ）
        try:
            append_audit(
                event="REGISTER_LOAN",
                loan_id=loan_id,
                amount=principal,
                meta={
                    "customer_id": customer_id,
                    "loan_date": loan_date,
                    "due_date": due_date,
                    "interest_rate_percent": interest_rate_percent,
                    "repayment_expected": repayment_expected,
                    "repayment_method": method_enum.value,
                    "grace_period_days": grace_period_days,
                    "late_fee_rate_percent": late_fee_rate_percent,
                    "late_base_amount": late_base_amount,
                    "policy": "C-4.5 fixed late_bee_base_amount == loan_amount",
                },
                actor="user"
            )
        except Exception as _e:
            # エラーが起きた場合はメッセージを表示
            print(f"[WARN] append_audit で警告: {_e}")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    return loan_id

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

    try:
        paths = _get_project_paths_patched()
        loans_csv_path = str(paths["loans_csv"])
    except Exception:
        # パス解決に失敗したら規定ファイル名をフォールバック
        loans_csv_path = "loan_v3.csv"

    repayments_csv_path = "repayments.csv"

    if not is_over_repayment(loans_csv_path, repayments_csv_path, loan_id, amount):
        print("❌ 返済額が予定返済額を超えるため、この返済は記録しません。")
        return

    try:
        header = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]
        file_exists = os.path.exists(repayments_csv_path)
        need_header = (not file_exists) or (os.stat(repayments_csv_path).st_size == 0)

        with open(repayments_csv_path, mode="a", newline="", encoding="utf-8") as file:
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

        # ★C-4 監査フック（成功時のみ）
        try:
            append_audit(
                event="REGISTER_REPAYMENT",
                loan_id=loan_id,
                amount=amount,
                meta={
                    "customer_id": customer_id,
                    "paid_date": repayment_date
                },
                actor="user"
            )
        except Exception as _e:
            print(f"[WARN] append_audit で警告: {_e}")
    
    except Exception as e:
        print(f"❌ CSV書き込み中にエラーが発生しました: {e}")

def register_repayment_api(*, loan_id: str, customer_id: str, amount: int, repayment_date: str | None = None) -> bool:
    if not repayment_date:
        repayment_date = str(datetime.today().date())

    # --- ローンCSVの場所を賢く推定 ---
    def _contains_loan_id(csv_path: str, _loan_id: str) -> bool:
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("loan_id") == _loan_id:
                        return True
        except Exception:
            pass
        return False

    loans_csv_path = None

    # 1) adapter 側の get_project_paths（monkeypatch 済みならそれ）を試す
    try:
        paths = _get_project_paths_patched()
        p = str(paths["loans_csv"])
        if os.path.exists(p) and _contains_loan_id(p, loan_id):
            loans_csv_path = p
    except Exception:
        pass

    # 2) AUDIT_PATH と同じフォルダの loan_v3.csv を優先
    if loans_csv_path is None:
        audit_dir = os.path.dirname(_resolve_audit_path())
        cand = os.path.join(audit_dir, "loan_v3.csv") if audit_dir else "loan_v3.csv"
        if os.path.exists(cand) and _contains_loan_id(cand, loan_id):
            loans_csv_path = cand

    # 3) まだ決まらなければ従来の候補でフォールバック
    if loans_csv_path is None:
        try:
            paths = _get_project_paths_patched()
            loans_csv_path = str(paths["loans_csv"])
        except Exception:
            loans_csv_path = "loan_v3.csv"

    repayments_csv_path = "repayments.csv"

    if not is_over_repayment(loans_csv_path, repayments_csv_path, loan_id, amount):
        return False

    header = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]
    file_exists = os.path.exists(repayments_csv_path)
    need_header = (not file_exists) or (os.stat(repayments_csv_path).st_size == 0)

    with open(repayments_csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if need_header:
            w.writeheader()
        w.writerow({
            "loan_id": loan_id,
            "customer_id": customer_id,
            "repayment_amount": amount,
            "repayment_date": repayment_date
        })

    append_audit(
        event="REGISTER_REPAYMENT", loan_id=loan_id, amount=amount,
        meta={"customer_id": customer_id, "paid_date": repayment_date}, actor="user"
    )
    return True

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
    try:
        with open(file_path, newline='', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('loan_id') == loan_id:
                    try:
                        total += int(row['repayment_amount'])
                    except (ValueError, TypeError, KeyError):
                        continue
    except FileNotFoundError:
        # 返済ファイルがまだ無ければ累計は 0
        return 0
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
        print("❌ 指定された loan_id が見つからないため、この返済は記録しません。")
        if VERBOSE_AUDIT:  # ← 追加フラグ
            print(f"[DEV] loans_file={loans_file} loan_id={loan_id} が見つかりません。")
        return False
    
    # 予定返済額 repayment_expected を辞書から取得
    try:
        repayment_expected = int(loan_info["repayment_expected"])
    except (KeyError, ValueError):
        print("❌ 予定返済額の参照に失敗したため、この返済は記録しません。")
        if VERBOSE_AUDIT:
            print(f"[DEV] loan_id={loan_id} の repayment_expected を読めません。row={loan_info!r}")
        return False

    # loan_idに対する返済の合計額を取得
    total_repaid = get_total_repaid_amount(repayments_file, loan_id)

    # 合計返済額 + 入力額 > 予定返済額 か判定
    if total_repaid + repayment_amount > repayment_expected:
        remaining = max(0, repayment_expected - total_repaid)
        print("❌ 返済額が予定額を超えるため、この返済は記録しません。")
        print(f"   残り登録可能額：¥{remaining:,}（予定：¥{repayment_expected:,}／累計：¥{total_repaid:,}）")
        if VERBOSE_AUDIT:
            print(f"[DEV] loan_id={loan_id} 入力：¥{repayment_amount:,} → 累計+入力=¥{(total_repaid+repayment_amount):,} > 予定")
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

# 延滞日数と延滞手数料を計算する関数
def calculate_late_fee(
        principal, 
        due_date, 
        *, 
        late_fee_rate_percent: float = 10.0,
        **kwargs
    ):


    """
    DEPRECATED: 互換ラッパー。戻り値は (days_late, late_fee_int) を維持。
    旧コードの呼び出しを壊さず、新ロジックへ譲渡します。

    追加で受け付ける任意引数（互換目的）：
    - paid_date: 'YYYY-MM-DD' (あればこれを基準日にする)
    - grace_period_days: int = 0 (旧仕様は猶予なし。ここで0を規定にして互換を維持)
    - month_days: int = 30 (1ヶ月の日数とみなす)
    - late_base_amount: float = principal (延滞手数料の計算ベース)
    """
    warnings.warn(
        "calculate_late_fee is deprecated. Use compute_recovery_amount / calc_late_fee.",
        DeprecationWarning, stacklevel=2
    )

    # due_date は　date か　'YYYY-MM-DD' を受ける
    if isinstance(due_date, str):
        due = _parse_date_yyyy_mm_dd(due_date)
    else:
        due = due_date

    # 支払い基準日（任意）:あればそれを today とする
    paid_date = kwargs.get("paid_date")
    if paid_date:
        try:
            basis_day = _parse_date_yyyy_mm_dd(paid_date)
        except Exception:
            basis_day = date.today()
    else:
        basis_day = date.today()

    # 旧API互換の規定値（挙動を変えないため grace は 0 が規定）
    grace = int(kwargs.get("grace_period_days",0))
    month_days = int(kwargs.get("month_days", 30))
    base_amount = float(kwargs.get("late_base_amount", principal))

    # 延滞日数（猶予は規定0。　将来、設定値に寄せたいときはここで default_grace を読む）
    overdue_days = calc_overdue_days(basis_day, due.isoformat(), grace)

    # 新ロジックで手数料を算出
    fee = calc_late_fee(
        late_base_amount=base_amount,
        late_fee_rate_percent=float(late_fee_rate_percent),
        overdue_days=overdue_days,
        month_days=month_days
    )
    return overdue_days, int(round(fee))
    

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

    # 円に統一（四捨五入）
    remaining_int = round_money(remain, unit=1)
    late_fee_int = round_money(lfee, unit=1)
    recovery_total_int = remaining_int + late_fee_int

    return{
        "remaining": remaining_int,
        "late_fee": late_fee_int,
        "recovery_total": recovery_total_int,
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

# C-4 猶予付き延滞判定（effective_due）

DATE_FMT = "%Y-%m-%d"

def _parse_date(s: str) -> date:
    return datetime.strptime(s, DATE_FMT).date()

def _to_int(x, fallback=0) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return fallback
    
def compute_effective_due(due_date_str: str, grace_days: int) -> date:
    """due_date + grace_period_days を返す。grace_daysは欠損/不正なら0扱い。"""
    due = _parse_date(due_date_str)
    gd = _to_int(grace_days, 0)
    if gd < 0:  # マイナスは0に矯正（仕様上、猶予は負にしない）
        gd = 0
    return due + timedelta(days=gd)

def is_overdue_with_grace(today: date, 
                          due_date_str: str,
                          grace_period_days: int) -> bool:
    return today > compute_effective_due(due_date_str, grace_period_days)

# C-4 監査ログ append_audit()
AUDIT_PATH = "data/audit_log.csv"
AUDIT_HEADERS = ["ts", "event", "loan_id", "amount", "meta", "actor"]

def append_audit(event: str,  
                 loan_id: str,
                 amount: float | int | None = None,
                 meta: dict | None = None,
                 actor: str = "system") -> None:
    """
    監査イベントをCSVに追記。
    adapter (loan_module) 側で AUDIT_PATH が上書きされていればそちらを優先。
    """
    audit_path = _resolve_audit_path()  # ★ ここがポイント

    # ディレクトリがある場合のみ作成（ファイル名のみの場合は skip）
    dirn = os.path.dirname(audit_path)
    if dirn:
        os.makedirs(dirn, exist_ok=True)

    file_exists = os.path.exists(audit_path)
    need_header = (not file_exists) or (os.stat(audit_path).st_size == 0)

    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event, 
        "loan_id": str(loan_id) if loan_id is not None else "", 
        "amount": amount if amount is not None else "",
        "meta": json.dumps(meta, ensure_ascii=False) if meta else "",
        "actor": actor,
    }
    with open(audit_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_HEADERS)
        if need_header:
            w.writeheader()
        w.writerow(row)


def _get_project_paths_patched():
    """
    tests ではトップレベルの adapter モジュール `loan_module`
    に対して monkeypatch されるので、そちらにオーバーライドが
    あれば優先して使う。
    """
    try:
        mod = sys.modules.get('loan_module')
        if mod and hasattr(mod, 'get_project_paths'):
            return mod.get_project_paths()
    except Exception:
        pass
    return get_project_paths()


def _resolve_audit_path() -> str:
    """
    adapter 側で AUDIT_PATH が上書きされていればそれを使う。
    そうでなければ元の AUDIT_PATH を使う。
    """
    try:
        mod = sys.modules.get('loan_module')
        if mod:
            p = getattr(mod, 'AUDIT_PATH', None)
            if p:
                return p
    except Exception:
        pass
    return AUDIT_PATH


