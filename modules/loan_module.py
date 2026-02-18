import csv
import os
# pandas 依存をなくす（C-５用途はCSV直読みで十分）

import warnings
import sys
from datetime import date, datetime, timedelta
from modules.utils import (
    get_project_paths,
    normalize_method,)  
# 既存の正規化（文字列）を再利用
from decimal import Decimal, ROUND_HALF_UP, getcontext
from enum import Enum
from pathlib import Path
from modules.audit import append_audit as _write_audit, AUDIT_PATH as _AUDIT_PATH
from modules.audit import append_audit

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
        with open(file_path, newline="", encoding="utf-8") as f:
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
    UNKOWN = "UNKNOWN"  # backward-compat alias(一時的に残す)


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
    if unit not in (1, 10, 100, 1000):
        raise ValueError("unit must be 1/10/100/1000")
    d = Decimal(str(amount)) / Decimal(unit)
    y = d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(y * unit)


def calc_repayment_expected(
    amount: int | float | Decimal,
    interest_rate_percent: float | Decimal,
    *,
    round_unit: int = 1,
) -> int:
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
    file_path=None,  # ← ここを None に
    notes: str = "", # C-12 備考欄　デフォルト空文字
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
        "loan_id",  # 貸付ID
        "customer_id",  # 顧客ID
        "loan_amount",  # 借りた金額
        "loan_date",  # 貸付日
        "due_date",  # 返済期日
        "interest_rate_percent",  # 通常利率（%）
        "repayment_expected",  # 予定返済額
        "repayment_method",  # 返済方法
        "grace_period_days",  # 延滞猶予日数
        "late_fee_rate_percent",  # 延滞利率（%）
        "late_base_amount",  # 延滞対象元金
        # C-9 追加
        "contract_status",
        "cancelled_at",
        "cancel_reason",
        # C-12 追加
        "notes",
    ]

    # 返済期日が未入力なら 貸付日（loan_date） の30日後をデフォルト設定
    if due_date is None or due_date == "":
        due_date = (
            datetime.strptime(loan_date, "%Y-%m-%d") + timedelta(days=30)
        ).strftime("%Y-%m-%d")

    # 予定返済額 (Decimalベースで四捨五入。将来は round_unit=10/100 にも対応可)
    repayment_expected = calc_repayment_expected(
        amount, interest_rate_percent, round_unit=1
    )
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
            with open(file_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(header)

        # データ行を a モードで　CSV　に追記する
        with open(file_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # 保存する内容をデバック出力
            print(
                "[DEBUG] 保存内容：",
                [
                    loan_id,
                    customer_id,
                    amount,
                    loan_date,
                    due_date,
                    interest_rate_percent,
                    repayment_expected,
                    method_enum.value,
                    grace_period_days,
                    late_fee_rate_percent,
                    late_base_amount,
                ],
            )
            writer.writerow(
                [
                    loan_id,
                    customer_id,
                    amount,
                    loan_date,
                    due_date,
                    interest_rate_percent,
                    repayment_expected,
                    method_enum.value,
                    grace_period_days,
                    late_fee_rate_percent,
                    late_base_amount,
                    # C-9 の初期値
                    "ACTIVE",
                    "",
                    "",
                    # C-12 notes
                    notes,
                ]
            )

        # 保存成功メッセージ
        #print("✅貸付記録が保存されました。")
        print("✅ SUCCESS: 貸付記録を保存しました。")

        # ★C-4 監査フック（成功時のみ）
        try:
            _audit_event(
                "REGISTER_LOAN",
                loan_id=loan_id,
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
                    "amount": amount,
                },
                actor="CLI",
            )
        except Exception as _e:
            print(f"⚠️ WARN: 監査ログの記録に失敗しました: {_e}。")
    
    except Exception as e:        
        print(f"❌ ERROR: 処理に失敗しました: {e}。")


# 顧客IDごとの貸付履歴を表示する関数
def display_loan_history(customer_id, filepath):
    try:
        # CSVファイルを開き、DictReaderで読み込む
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            # customer_id が一致する行を抽出
            history = [row for row in reader if row["customer_id"] == customer_id]

        # 該当データがあれば表示
        if history:
            print(f"\n■ 顧客ID: {customer_id}の貸付履歴")
            for row in history:
                # 日付を YYY年MM月DD日　の形式に変換
                date_str = datetime.strptime(row["loan_date"], "%Y-%m-%d").strftime(
                    "%Y年%m月%d日"
                )

                # 金額をカンマ区切りに整形
                amount_str = f"{int(row['loan_amount']):,}円"

                # 期日を取得（存在しない場合は空文字）
                due_date = row.get("due_date", "")

                # 一軒ずつ履歴を出力
                tag = ""
                try:
                    if row.get("contract_status") == "CANCELLED":
                        tag = " [CANCELLED]"
                except Exception:
                    pass
                print(f"{date_str}｜{amount_str}｜返済期日：{due_date}{tag}")

                # C-12: 備考があれば表示
                notes = (row.get("notes") or "").strip()
                if notes:
                    print(f"    その他条件：{notes}")


        else:
            print("✅ SUCCESS: 該当する貸付履歴はありません。")

    except FileNotFoundError:
        print("❌ ERROR: ファイルが見つかりません。ファイルパスを確認してください。")
    except Exception as e:
        print(f"❌ ERROR: 予期せぬエラーが発生しました: {e}。")


# 顧客からの返済を登録する関数
def register_repayment():
    loan_id = input(
        "返済する loan_id を入力してください（例：L20250709-001）: "
    ).strip()

    # 顧客IDの入力と補正
    customer_id = input("顧客IDを入力してください（例：001 または CUST001）： ").strip()
    if customer_id.isdigit() and len(customer_id) == 3:
        customer_id = f"CUST{customer_id}"
    elif not customer_id.startswith("CUST"):
        print("❌ ERROR: 顧客IDが不正です。3桁の数字またはCUSTxxx形式で入力してください。")
        return

    # 返済額を入力させる
    try:
        amount = int(input("返済額を入力してください（例：5000）: ").strip())
        # 金額が正の整数であるか確認
        if amount <= 0:
            raise ValueError
    except ValueError:
        print("❌ ERROR: 金額は1円以上の整数で入力してください。")
        return

    # 返済日の入力（未入力の場合は今日の日付）
    repayment_date = input(
        "📅 返済日を入力してください（未入力で本日の日付を使用）："
    ).strip()
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
        # is_over_repayment() 側で詳細メッセージと残額案内を出すため、ここでは重複表示しない
        return
    
    try:
        file_exists = os.path.exists(repayments_csv_path)
        need_header = (not file_exists) or (os.stat(repayments_csv_path).st_size == 0)

        with open(repayments_csv_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=REPAYMENTS_HEADER)

            if need_header:
                writer.writeheader()

            writer.writerow(
                {
                    "loan_id": loan_id,
                    "customer_id": customer_id,
                    "repayment_amount": amount,
                    "repayment_date": repayment_date,
                    "payment_type": "REPAYMENT",  # ← 旧モードでも必ず明示
                }
            )

        print(f"✅ SUCCESS: 返済記録を保存しました（顧客ID: {customer_id}）。")

        # ★C-4 監査フック（成功時のみ）
        try:
            _audit_event(
                "REGISTER_REPAYMENT",
                loan_id=loan_id,
                amount=amount,
                meta={"customer_id": customer_id, "paid_date": repayment_date},
                actor="user",
            )
        except Exception as _e:
            print(f"⚠️ WARN: 監査ログの記録に失敗しました: {_e}。")
    
    except Exception as e:
        print(f"❌ ERROR: 返済記録の保存に失敗しました: {e}。")
        return

def register_repayment_api(
    *, loan_id: str, customer_id: str, amount: int, repayment_date: str | None = None
) -> bool:
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

    # --- repayments.csv の場所を決める（テスト汚染を避ける）---
    repayments_csv_path = None
    # a) loans_csv と同じフォルダを最優先
    if loans_csv_path:
        repayments_csv_path = os.path.join(os.path.dirname(loans_csv_path) or "", "repayments.csv") 
    # b) 次点で　AUDIT_PATH　と同じフォルダ
    if not repayments_csv_path:
        audit_dir = os.path.dirname(_resolve_audit_path())
        if audit_dir:
            repayments_csv_path = os.path.join(audit_dir, "repayments.csv")
    # c) 最後にカレント
    if not repayments_csv_path:
        repayments_csv_path = "repayments.csv"


    if not is_over_repayment(loans_csv_path, repayments_csv_path, loan_id, amount):
        return False
    
    # ここで repayments のスキーマ/ヘッダーを必ず保証（5列）
    _ensure_repayments_csv_initialized(repayments_csv_path)

    with open(repayments_csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REPAYMENTS_HEADER)
        w.writerow(
            {
                "loan_id": loan_id,
                "customer_id": customer_id,
                "repayment_amount": str(amount),
                "repayment_date": repayment_date,
                "payment_type": "REPAYMENT", # ★ D-2.1:必ず明示
            }
        )

    _audit_event(
        "REGISTER_REPAYMENT",
        loan_id=loan_id,
        amount=amount,
        meta={"customer_id": customer_id, "paid_date": repayment_date},
        actor="user",
    )
    return True


# B-11.1 loan_idで貸付情報を検索
def get_loan_info_by_loan_id(file_path, loan_id):
    with open(file_path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["loan_id"] == loan_id:
                return row
    return None

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
        print("❌ ERROR: 指定されたloan_idは見つかりません。")
        if VERBOSE_AUDIT:  # ← 追加フラグ
            print(f"[DEV] loans_file={loans_file} loan_id={loan_id} が見つかりません。")
        return False

    # 予定返済額 repayment_expected を辞書から取得
    try:
        repayment_expected = int(loan_info["repayment_expected"])
    except (KeyError, ValueError):
        print("❌ ERROR: 予定返済額の参照に失敗したため、この返済は記録しません。")
        if VERBOSE_AUDIT:
            print(
                f"[DEV] loan_id={loan_id} の repayment_expected を読めません。row={loan_info!r}"
            )
        return False

    # loan_idに対する返済の合計額を取得
    total_repaid = calculate_total_repaid_by_loan_id(repayments_file, loan_id) 

    # 合計返済額 + 入力額 > 予定返済額 か判定
    if total_repaid + repayment_amount > repayment_expected:
        remaining = max(0, repayment_expected - total_repaid)
        print("❌ ERROR: 入力額が予定返済額を超えるため、この返済は記録しません。")
        print(
            f"   残り登録可能額：¥{remaining:,}（予定：¥{repayment_expected:,}／累計：¥{total_repaid:,}）"
        )
        if VERBOSE_AUDIT:
            print(
                f"[DEV] loan_id={loan_id} 入力：¥{repayment_amount:,} → 累計+入力=¥{(total_repaid+repayment_amount):,} > 予定"
            )
        return False

    return True

# D-2

REPAYMENTS_HEADER = ["loan_id", "customer_id", "repayment_amount", "repayment_date", "payment_type"]

def _ensure_repayments_csv_initialized(repayments_csv_path: str) -> None:
    file_exists = os.path.exists(repayments_csv_path)
    need_header = (not file_exists) or (os.stat(repayments_csv_path).st_size == 0)
    if need_header:
        with open(repayments_csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=REPAYMENTS_HEADER)
            w.writeheader()

# D-2.1
def register_repayment_complete(
    *,
    loans_file: str,
    repayments_file: str,
    loan_id: str,
    amount: int,                 # 入力は「合計額」(元本 + 延滞手数料をまとめて受け取る)
    repayment_date: str,
    actor: str = "CLI",
) -> dict | None:
    """
    返済登録（D-2.1）
    - ユーザー入力は「合計支払額 amount」のみ
    - 返済日基準で「その時点の残元本」と「その時点までに発生した延滞の列が想定スキーマ（payment_type等）になっていることを保証する手数料残」を算出
    - amount を ①元本返済(REPAYMENT) ②延滞手数料(LATE_FEE) に自動配分し、repayments.csv に2行で記録
    - 「残元本 + 延滞手数料残」を上限とし、超過入力は過剰回収になるためブロック
    - 監査ログ(audit)も同時に残す
    """

    # 1) repayments.csv の列が想定スキーマ（payment_type等）になっていることを保証する
    _ensure_repayments_schema(repayments_file)

    # 2) 返済日（文字列）を date に変換
    repay_day = _parse_date_yyyy_mm_dd(repayment_date)

    # 3) loans_file から loan_id の貸付行を1件取得する（存在確認）
    info = None
    with open(loans_file, "r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("loan_id") == loan_id:
                info = row
                break
    if info is None:
        # loan が存在しないなら、repayments に実在しないデータを作るので即中断
        print("❌ ERROR: 指定されたloan_idは見つかりません。")
        return None

    # 3.1) 契約解除済み(CANCELLED)ローンは返済登録を禁止（仕様として安全）
    if (info.get("contract_status") or "ACTIVE").upper() == "CANCELLED":
        print("❌ ERROR: このloan_idは契約解除済みのため返済登録できません。")
        return None

    # 4) 元本返済(REPAYMENT)の累計を repayments.csv から集計し、
    #    予定返済額(repayment_expected)との差分＝「残元本」を出す
    total_repaid = calculate_total_repaid_by_loan_id(repayments_file, loan_id)
    expected = int(float(info.get("repayment_expected", 0) or 0))
    remaining_now = max(0, expected - total_repaid)

    # 5) 返済期日基準で「その時点までに発生している延滞手数料(累計)」を計算する
    due_str = info.get("due_date", "")
    grace = int(info.get("grace_period_days", 0) or 0)
    late_rate = float(info.get("late_fee_rate_percent", 10.0) or 10.0)
    try:
        late_base = int(float(info.get("late_base_amount", expected)))
    except Exception:
        late_base = expected

    late_fee_accrued_now = 0
    if due_str:
        calc = compute_recovery_amount(
            repayment_expected=expected,
            total_repaid=total_repaid,
            today=repay_day,
            due_date_str=due_str,
            grace_period_days=grace,
            late_fee_rate_percent=late_rate,
            late_base_amount=late_base,
        )
        late_fee_accrued_now = int(calc["late_fee"])

    # 5.1) 既に支払われた延滞手数料(LATE_FEE)累計を repayments.csv から集計し、
    #      発生分との差分＝「延滞手数料残」を出す
    late_fee_paid_total = calculate_total_late_fee_paid_by_loan_id(repayments_file, loan_id)
    late_fee_remaining_now = max(0, late_fee_accrued_now - late_fee_paid_total)

    # 6) 入力合計が「残 + 延滞手数料残」を超えたらブロック
    total_due_now = remaining_now + late_fee_remaining_now
    if amount <= 0:
        print("❌ ERROR: 返済金額は1円以上の整数で入力してください。")
        return None
    if amount > total_due_now:
        print("❌ ERROR: 入力額が『残高＋延滞手数料残』を超えるため、この返済は記録しません。")
        print(f"   入力：¥{amount:,} / 残：¥{remaining_now:,} / 延滞手数料残：¥{late_fee_remaining_now:,} / 合計上限：¥{total_due_now:,}")
        return None

    # 7) 合計額 amount を自動配分する：
    #    まず残元本に充当(REPAYMENT)し、余りがあれば延滞手数料に充当(LATE_FEE)
    #    → 2行分割で「何に対する支払いか」を後から必ず復元できる
    repayment_part = min(remaining_now, amount)
    leftover = amount - repayment_part
    fee_part = min(late_fee_remaining_now, leftover)

    # 8) repayments_file が相対パスで "repayments.csv" の場合は data/repayments.csv に寄せる
    try:
        p = Path(repayments_file)
        is_relative_repayments_csv = (p.name.lower() == "repayments.csv" and not p.is_absolute())
    except Exception:
        is_relative_repayments_csv = False

    if is_relative_repayments_csv:
        paths = _get_project_paths_patched()
        repayments_file = str(paths["repayments_csv"])

    print(f"[DEBUG] repayments_csv_path = {repayments_file}")

    # 8.1) repayments.csv へ追記（最大2行）
    #      - 元本返済(REPAYMENT)行（repayment_part）
    #      - 延滞手数料(LATE_FEE)行（fee_part）
    #      それぞれ audit_log にも同内容を残す（監査性/説明責任）

    written_rows = []
    with open(repayments_file, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REPAYMENTS_HEADER)

        if repayment_part > 0:
            row1 = {
                "loan_id": loan_id,
                "customer_id": info.get("customer_id"),
                "repayment_amount": str(repayment_part),
                "repayment_date": repayment_date,
                "payment_type": "REPAYMENT",
            }
            w.writerow(row1)
            written_rows.append(row1)

            append_audit(
                action="REGISTER_REPAYMENT",
                entity="loan",
                entity_id=loan_id,
                details={
                    "customer_id": info.get("customer_id"),
                    "amount": repayment_part,
                    "paid_date": repayment_date,
                    "payment_type": "REPAYMENT",
                },
                actor=actor,
            )

        if fee_part > 0:
            row2 = {
                "loan_id": loan_id,
                "customer_id": info.get("customer_id"),
                "repayment_amount": str(fee_part),
                "repayment_date": repayment_date,
                "payment_type": "LATE_FEE",
            }
            w.writerow(row2)
            written_rows.append(row2)

            append_audit(
                action="REGISTER_REPAYMENT",
                entity="loan",
                entity_id=loan_id,
                details={
                    "customer_id": info.get("customer_id"),
                    "amount": fee_part,
                    "paid_date": repayment_date,
                    "payment_type": "LATE_FEE",
                },
                actor=actor,
            )

    # 9) 呼び出し側（CLI）に「何が起きたか」を返すため summary を返却する
    return {
        "loan_id": loan_id,
        "customer_id": info.get("customer_id"),
        "input_total": amount,
        "repayment_part": repayment_part,
        "late_fee_part": fee_part,
        "remaining_before": remaining_now,
        "late_fee_remaining_before": late_fee_remaining_now,
        "written_rows": written_rows,
        "repayments_file": repayments_file,
    }

# 顧客IDごとの返済履歴を表示する関数
def display_repayment_history(customer_id, filepath="repayments.csv"):
    try:
        # 返済履歴のCSVファイルを開く
        with open(filepath, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            # customer_id が一致する行を抽出する
            history = [row for row in reader if row["customer_id"] == customer_id]

        if history:
            # 該当する履歴があった場合
            print(f"\n■ 顧客ID: {customer_id} の返済履歴")
            for row in history:
                # 返済日
                date_str = datetime.strptime(
                    row["repayment_date"], "%Y-%m-%d"
                ).strftime("%Y年%m月%d日")
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
    loan_file="loan_v3.csv",
    repayment_file="repayments.csv",
    *,
    filter_mode="all",  # "all" /  "overdue"
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
        with open(loan_file, newline="", encoding="utf-8") as lf:
            loan_reader = csv.DictReader(lf)
            loans = [
                row for row in loan_reader if row.get("customer_id") == customer_id
            ]
        # CANCELLED は一覧から除外（回収対象ではないため）
        loans = [row for row in loans if row.get("contract_status", "ACTIVE") != "CANCELLED"]


        # 2) 未返済のみ抽出（loan_idベース）
        unpaid = []
        for loan in loans:
            loan_id = loan.get("loan_id")
            if not loan_id:
                continue
            if not is_loan_fully_repaid(loan_id, loan_file, repayment_file):
                unpaid.append(loan)

        # 3) overdueフィルタ（インライン化してスコープ問題を回避）
        if filter_mode == "overdue":
            filtered = []
            for ln in unpaid:
                ds = ln.get("due_date", "")
                if not ds:
                    continue
                try:
                    grace_days = int(ln.get("grace_period_days", 0))
                except ValueError:
                    grace_days = 0
                # ✅ 猶予込み延滞判定
                if calc_overdue_days(_today, ds, grace_days) > 0:
                    filtered.append(ln)
            unpaid = filtered
        elif filter_mode != "all":
            print(f"⚠️ WARN: filter_modeが不正です: {filter_mode}（'all'として処理します）。")

        # 4) 並び順：期日昇順→loan_id（期日なし/不正は末尾）
        def _due_key(ln):
            ds = ln.get("due_date", "")
            try:
                return (
                    0,
                    datetime.strptime(ds, "%Y-%m-%d").date(),
                    ln.get("loan_id", ""),
                )
            except ValueError:
                return (1, date.max, ln.get("loan_id", ""))

        unpaid.sort(key=_due_key)

        # 3) 表示
        if not unpaid:
            if filter_mode == "overdue":
                print("✅ SUCCESS: 現在、延滞中の未返済はありません。")
            else:
                print("✅ 全ての貸付は返済済みです。")
            return []

        header = f"\n■ 顧客ID: {customer_id} の{'延滞中の未返済' if filter_mode=='overdue' else '未返済'}貸付一覧"
        print(header)
        print(
            "  [STATUS]  loan_id      ｜貸付日        ｜金額        ｜期日           ｜予定        ｜返済済      ｜残高"
        )

        rows_out = []
        for loan in unpaid:
            loan_id = loan["loan_id"]

            loan_date_jp = datetime.strptime(loan["loan_date"], "%Y-%m-%d").strftime(
                "%Y年%m月%d日"
            )
            amount = int(loan["loan_amount"])
            amount_str = f"{amount:,}円"

            due_str = loan.get("due_date", "")

            status = "UNPAID"
            overdue_days = 0
            late_fee = 0
            # 期日がない/不正でも破綻しないよう規定は 「残高=回収額」
            recovery_amount = None  # 後で remaining + late_fee に必ず埋める

            # 予定返済額・累計返済・残
            try:
                expected = int(loan.get("repayment_expected", "0"))
            except ValueError:
                expected = 0
            total_repaid = calculate_total_repaid_by_loan_id(repayment_file, loan_id)
            remaining = max(0, expected - total_repaid)

            if due_str:
                try:
                    # 期日バース
                    _ = datetime.strptime(due_str, "%Y-%m-%d")  # フォーマット検証用
                    due_jp = (
                        datetime.strptime(due_str, "%Y-%m-%d")
                        .date()
                        .strftime("%Y年%m月%d日")
                    )

                    # CSVから延滞用パラメータ
                    try:
                        late_base_amount = int(
                            float(loan.get("late_base_amount", amount))
                        )
                    except ValueError:
                        late_base_amount = amount
                    try:
                        late_rate_percent = float(
                            loan.get("late_fee_rate_percent", 10.0)
                        )
                    except ValueError:
                        late_rate_percent = 10.0
                    grace_days = int(loan.get("grace_period_days", 0))

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

                    late_fee_paid_total = calculate_total_late_fee_paid_by_loan_id(repayment_file, loan_id)
                    
                    overdue_days = info["overdue_days"]

                    # 返済日(=today)基準で発生している延滞手数料（総額）
                    late_fee_accrued_now = info["late_fee"]

                    # すでに支払われた延滞手数料（LATE_FEEの合計）を差し引く
                    late_fee_remaining_now = max(0, late_fee_accrued_now - late_fee_paid_total)

                    # 画面に出す late_fee は 「残」
                    late_fee = late_fee_remaining_now

                    # 残元本(利息込み)は従来通り
                    remaining = info["remaining"]

                    # 回収額も「残 + 延滞手数料」
                    recovery_amount = remaining + late_fee_remaining_now

                    status = "OVERDUE" if overdue_days > 0 else "UNPAID"

                except ValueError:
                    status = "DATE_ERR"
                    due_jp = due_str

            else:
                due_jp = due_str

            sep = "｜"
            # 延滞行のみ、追加情報を右側に連結
            
            # 回収額は常に定義（未延滞・期日不正でも remaining + late_fee）
            if recovery_amount is None:
                recovery_amount = remaining + (late_fee or 0)
            extra = (
                f"{sep}延滞日数：{overdue_days}日"
                f"{sep}延滞手数料残：¥{late_fee_remaining_now:,}"
                f"{sep}(支払済：¥{late_fee_paid_total:,})"
                f"{sep}回収額：¥{recovery_amount:,}"
                if status == "OVERDUE"
                else ""
            )

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
            
            # C-5 正字で返却
            try:
                grace_val = int(loan.get("grace_period_days",0))
            except ValueError:
                grace_val =0
            rows_out.append(
                {
                    "loan_id": loan_id,
                    "loan_date": loan["loan_date"],
                    "loan_amount": amount,
                    "due_date": due_str,
                    "status": status,
                    "repayment_expected": expected,
                    "remaining": remaining,
                    "grace_period_days": grace_val,
                    "overdue_days": overdue_days,
                    "late_fee": late_fee,
                    "recovery_total": recovery_amount,
                }
            )

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
        print(f"❌ ERROR: 処理に失敗しました: {e}。")
        return []

# D-2.2   
def get_unpaid_loans_rows(
    customer_id: str,
    loan_file: str,
    repayment_file: str,
    *,
    filter_mode: str = "all",  # "all" / "overdue"
    today=None,
):
    """
    表示なしで「未返済loan行（loan_v3のrow）」だけ返す。
    display_unpaid_loans() と同じ抽出条件（CANCELLED除外 / loan_idベース）で統一する。
    """
    _today = today or date.today()

    with open(loan_file, newline="", encoding="utf-8") as lf:
        loan_reader = csv.DictReader(lf)
        loans = [row for row in loan_reader if row.get("customer_id") == customer_id]

    # CANCELLED除外（回収対象外）
    loans = [row for row in loans if row.get("contract_status", "ACTIVE") != "CANCELLED"]

    unpaid = []
    for loan in loans:
        loan_id = loan.get("loan_id")
        if not loan_id:
            continue
        if not is_loan_fully_repaid(loan_id, loan_file, repayment_file):
            unpaid.append(loan)

    if filter_mode == "overdue":
        filtered = []
        for ln in unpaid:
            ds = ln.get("due_date", "")
            if not ds:
                continue
            try:
                grace_days = int(ln.get("grace_period_days", 0))
            except ValueError:
                grace_days = 0

            if calc_overdue_days(_today, ds, grace_days) > 0:
                filtered.append(ln)
        unpaid = filtered

    return unpaid


# 延滞日数と延滞手数料を計算する関数
def calculate_late_fee(
    principal, due_date, *, late_fee_rate_percent: float = 10.0, **kwargs
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
        DeprecationWarning,
        stacklevel=2,
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
    grace = int(kwargs.get("grace_period_days", 0))
    month_days = int(kwargs.get("month_days", 30))
    base_amount = float(kwargs.get("late_base_amount", principal))

    # 延滞日数（猶予は規定0。　将来、設定値に寄せたいときはここで default_grace を読む）
    overdue_days = calc_overdue_days(basis_day, due.isoformat(), grace)

    # 新ロジックで手数料を算出
    fee = calc_late_fee(
        late_base_amount=base_amount,
        late_fee_rate_percent=float(late_fee_rate_percent),
        overdue_days=overdue_days,
        month_days=month_days,
    )
    return overdue_days, int(round(fee))

# D-2.1 新
def calculate_total_repaid_by_loan_id(repayments_file: str, loan_id: str) -> int:
    """
    D-2.1:
    - payment_type が "REPAYMENT" の行だけを返済累計に含める
    - 旧仕様（payment_type が無い/空）の行は REPAYMENT 扱いとして含める（後方互換）
    """
    total = 0

    for row in _iter_repayments_rows(repayments_file) or []:
        if (row.get("loan_id") or "") != loan_id:
            continue

        pt = (row.get("payment_type") or "").strip().upper()

        # 後方互換：列が無い/空 → REPAYMENT扱い
        if pt not in ("", "REPAYMENT"):
            continue

        try:
            amt = int(float(row.get("repayment_amount") or 0))
        except (ValueError, TypeError):
            amt = 0

        total += amt

    return total


def get_total_repaid_amount(repayments_file: str, loan_id: str) -> int:
    """
    Backward-compatible alias.
    main.py や旧コードが参照するため残す。
    """
    return calculate_total_repaid_by_loan_id(repayments_file, loan_id)


def calculate_total_late_fee_paid_by_loan_id(repayments_file: str, loan_id: str) -> int:
    total = 0
    for row in _iter_repayments_rows(repayments_file) or []:
        if row["loan_id"] != loan_id:
            continue
        if (row.get("payment_type") or "").strip().upper() != "LATE_FEE":
            continue
        try:
            total += int(float(row["repayment_amount"]))
        except Exception:
            continue
    return total
        

def get_repayment_expected(loan_id: str, loan_file: str = "loan_v3.csv") -> float:
    """指定 loan_id の予定返済額を CSV から取得（pandas不要）"""
    try:
        with open(loan_file, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("loan_id") == loan_id:
                    try:
                        return float(row.get("repayment_expected", 0))
                    except (TypeError, ValueError):
                        return 0.0
    except FileNotFoundError:
        pass
    raise ValueError(f"❌ ERROR: 指定されたloan_idは見つかりません。")

def is_loan_fully_repaid(
    loan_id: str,
    loan_file: str = "loan_v3.csv",
    repayments_file: str = "repayments.csv",
) -> bool:
    """
    完了された loan_id の返済が完了しているかどうかを判定する。
    完了 → True、未完了 → False
    """
    expected = get_repayment_expected(loan_id, loan_file)  # 予定返済額を取得
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
    month_days: int = 30,
) -> float:
    if overdue_days <= 0 or late_base_amount <= 0 or late_fee_rate_percent <= 0:
        return 0.0
    return (
        float(late_base_amount)
        * (float(late_fee_rate_percent) / 100.0)
        * (overdue_days / month_days)
    )


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
    late_base_amount: float | None = None,
) -> dict:
    remain = compute_remaining_amount(repayment_expected, total_repaid)
    base = late_base_amount if late_base_amount is not None else repayment_expected
    odays = calc_overdue_days(
        today, due_date_str, grace_period_days
    )  # 期日 + 猶予日数 を閾値にして延滞日数を返す（マイナスは0で切り上げ）
    lfee = calc_late_fee(base, late_fee_rate_percent, odays)

    # 円に統一（四捨五入）
    remaining_int = round_money(remain, unit=1)
    late_fee_int = round_money(lfee, unit=1)
    recovery_total_int = remaining_int + late_fee_int

    return {
        "remaining": remaining_int,
        "late_fee": late_fee_int,
        "recovery_total": recovery_total_int,
        "overdue_days": odays,
    }


def _normalize_repayments_headers(headers: list[str]) -> list[str]:
    alias = {
        # loan_id
        "loanid": "loan_id",
        "loan_id": "loan_id",

        # customer_id
        "payer": "customer_id",
        "customer": "customer_id",
        "customer_id": "customer_id",

        # repayment_amount
        "repay_amount": "repayment_amount",
        "repayed_amount": "repayment_amount",
        "repayment_amount": "repayment_amount",

        # repayment_date
        "date": "repayment_date",
        "repayment_date": "repayment_date",
    }
    return [alias.get(h.strip().lower(), h.strip().lower()) for h in headers]


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


def is_overdue_with_grace(
    today: date, due_date_str: str, grace_period_days: int
) -> bool:
    return today > compute_effective_due(due_date_str, grace_period_days)

def _get_project_paths_patched():
    """
    tests ではトップレベルの adapter モジュール `loan_module`
    に対して monkeypatch されるので、そちらにオーバーライドが
    あれば優先して使う。
    """
    try:
        mod = sys.modules.get("loan_module")
        if mod and hasattr(mod, "get_project_paths"):
            return mod.get_project_paths()
    except Exception:
        pass
    return get_project_paths()

def _resolve_audit_path() -> str:
    """
    audit_log の実体パスを返す。modules.audit から輸入した _AUDIT_PATH を優先。
    それが無ければ data/audit_log.csv をフォールバック。
    """
    try:
        # modules.audit から import した AUDIT_PATH を優先
        if _AUDIT_PATH:
            return str(_AUDIT_PATH)
    except Exception:
        pass
    # フォールバック: このファイルの上位 ../data/audit_log.csv
    base = Path(__file__).resolve().parent.parent
    return str((base / "data" / "audit_log.csv").resolve())



def _audit_event(event: str, *, loan_id: str, amount: float | int | None = None,
                 meta: dict | None = None, actor: str = "system") -> None:
    """
    既存コードの（event/loan_id/meta…）呼び出しを、modules.audit.append_audit
    の (action/entity/entity_id/details/actor) 形式へブリッジする薄いラッパ。
    """
    details = {}
    if meta:
        details.update(meta)
    if amount is not None:
        details["amount"] = amount

    _write_audit(
        action=event,            # 例: "CANCEL_CONTRACT" / "REGISTER_LOAN"
        entity="loan",
        entity_id=loan_id,
        details=details,
        actor=actor,
    )

# === C-9: 契約解除（最小表現） ===
C9_COL_STATUS = "contract_status"
C9_COL_CANCELLED_AT = "cancelled_at"     
C9_COL_CANCEL_REASON = "cancel_reason"
C9_STATUS_CANCELLED  = "CANCELLED"
C9_STATUS_ACTIVE     = "ACTIVE"  
COL_LOAN_ID = "loan_id"

def _ensure_c9_columns_or_raise(header: list[str]) -> None:
    need = {C9_COL_STATUS, C9_COL_CANCELLED_AT, C9_COL_CANCEL_REASON}
    if not need.issubset(set(header)):
        missing = sorted(list(need - set(header)))
        raise RuntimeError(f"[C-9] loan_v3.csv に必須列がありません。先にマイグレーションを実行してください: {missing}")

def _ensure_c9_columns(header, rows):
    """
    loan_v3.csvにC-9列が無い場合に、ヘッダ＆全行へ安全に追加する。
    返り値: (header, rows)  いずれも新しいリストを返す
    """
    need = {C9_COL_STATUS, C9_COL_CANCELLED_AT, C9_COL_CANCEL_REASON}
    hset = set(header)
    if need.issubset(hset):
        return header, rows
    new_header = header[:]
    missing = [c for c in (C9_COL_STATUS, C9_COL_CANCELLED_AT, C9_COL_CANCEL_REASON) if c not in hset]
    new_header.extend(missing)
    # 既存各行にデフォルトを埋める
    idx = {name: i for i, name in enumerate(new_header)}
    out_rows = []
    for r in rows:
        rr = r[:] + [""] * (len(new_header) - len(r))
        if C9_COL_STATUS in missing and not rr[idx[C9_COL_STATUS]]:
            rr[idx[C9_COL_STATUS]] = C9_STATUS_ACTIVE
        if C9_COL_CANCELLED_AT in missing and not rr[idx[C9_COL_CANCELLED_AT]]:
            rr[idx[C9_COL_CANCELLED_AT]] = ""
        if C9_COL_CANCEL_REASON in missing and not rr[idx[C9_COL_CANCEL_REASON]]:
            rr[idx[C9_COL_CANCEL_REASON]] = ""
        out_rows.append(rr)
    return new_header, out_rows

def cancel_contract(loan_file: str, loan_id: str, *, reason: str = "", operator: str = "CLI") -> bool:
    """
    契約をCANCELLEDにして cancelled_at と cancel_reason を埋める。
    返り値: True=成功 / False=見つからない・既にCANCELLED・（必要なら）完済など
    例外は基本的に起こさない（IOエラー等は上位に伝播）。
    """

    # 1) CSV 読み出し
    import csv
    import datetime

    # データディレクトリを loan_file から推定
    try:
        paths = _get_project_paths_patched()
        # loan_v3.csv のディレクトリを基準にする
        DATA_DIR = Path(paths.get("loans_csv", loan_file)).resolve().parent
    except Exception:
        # 念のためフォールバック
        DATA_DIR = Path("data").resolve()

    with open(loan_file, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    if not rows:
        return False

    # 2) ヘッダ正規化（外側クォート/BOM除去）
    header = [h.lstrip("\ufeff").strip().strip('"').strip("'") for h in rows[0]]
    body = rows[1:]

    # C-9列を必ず保証
    header, body = _ensure_c9_columns(header, body)

    # 必須列が揃っているか（schema_migratorで既に整っている想定だが、念のため）
    needed = {COL_LOAN_ID, C9_COL_STATUS, C9_COL_CANCELLED_AT, C9_COL_CANCEL_REASON}
    missing = [c for c in needed if c not in header]
    if missing:
        # 必須列がないならここで False（本来はマイグレータを先に流す）
        return False

    idx = {name: i for i, name in enumerate(header)}

    # 3) 対象行を探索
    found_i = None
    for i, row in enumerate(body):
        # 行長をヘッダ長にパディング（不足セルを空文字で埋める）
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
            body[i] = row  # パディング反映

        if row[idx[COL_LOAN_ID]] == loan_id:
            found_i = i
            break

    if found_i is None:
        # loan_id が見つからない
        return False

    row = body[found_i]

    # 4) 既にCANCELLEDか？
    prev_status = row[idx[C9_COL_STATUS]].strip() if row[idx[C9_COL_STATUS]] else ""
    if prev_status.upper() == "CANCELLED":
        print("❌ ERROR: すでに契約解除済みです。")
        try:
            _audit_event(
                "CANCEL_CONTRACT_SKIPPED",
                loan_id=row[idx[COL_LOAN_ID]],
                meta={"reason": "already cancelled", "previous_status": prev_status},
                actor="user",
            )
        except Exception as _e:
            print(f"⚠️ WARN: 監査ログの記録に失敗しました: {_e}。")
        return False

    # 5) 完済済みはキャンセル不可
    try:
        expected = int(row[idx["repayment_expected"]])
    except Exception:
        expected = 0

    repaid_sum = 0
    try:
        with open(DATA_DIR / "repayments.csv", newline="", encoding="utf-8-sig") as rf: # type: ignore
            import csv
            r = csv.DictReader(rf)
            for rec in r:
                if rec.get("loan_id") == loan_id:
                    try:
                        repaid_sum += int(rec.get("repayment_amount", 0))
                    except Exception:
                        pass
    except FileNotFoundError:
        repaid_sum = 0

    if expected > 0 and repaid_sum >= expected:
        print("❌ ERROR: 完済済みのため、契約解除できません。")
        print(f"   予定返済額: ¥{expected:,} / 返済合計: ¥{repaid_sum:,}")
        return False

    # 6) 状態を更新
    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row[idx[C9_COL_STATUS]] = "CANCELLED"
    row[idx[C9_COL_CANCELLED_AT]] = now_iso
    row[idx[C9_COL_CANCEL_REASON]] = reason or ""

    body[found_i] = row

    # 7) 書き戻し（上書き）
    with open(loan_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)

    # 8) 監査ログ
    _audit_event(
        "CANCEL_CONTRACT",
        loan_id=loan_id,
        meta={
            "previous_status": prev_status or "ACTIVE",
            "new_status": "CANCELLED",
            "cancelled_at": now_iso,
            "cancel_reason": reason or "",
            "loan_id": loan_id,
        },
        actor=operator,
    )
    return True

# D-2.1
def _ensure_repayments_schema(repayments_file: str) -> None:
    if (not os.path.exists(repayments_file)) or (os.stat(repayments_file).st_size == 0):
        with open(repayments_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(REPAYMENTS_HEADER)
        return

    with open(repayments_file, "r", newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        header = next(r, None)
    
    if not header:
        with open(repayments_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(REPAYMENTS_HEADER)
        return
    
    header_norm = [h.lstrip("\ufeff").strip().strip('"') for h in header]
    header_norm = _normalize_repayments_headers(header_norm) 

    if "payment_type" in header_norm:
        return
    
    idx = {name: i for i, name in enumerate(header_norm)}

    def _get(row, key, default=""):
        i = idx.get(key)
        if i is None or i >= len(row):
            return default
        return row[i]
    
    new_rows = []
    with open(repayments_file, "r", newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        _ = next(r, None)
        for row in r:
            new_rows.append(
                [
                    _get(row, "loan_id"),
                    _get(row, "customer_id"),
                    _get(row, "repayment_amount"),
                    _get(row, "repayment_date"),
                    "REPAYMENT",
                ]
            )

    with open(repayments_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REPAYMENTS_HEADER)
        w.writerows(new_rows)

# D-2.1
def _iter_repayments_rows(repayments_file: str):
    try:
        with open(repayments_file, "r", newline="", encoding="utf-8-sig") as f:
            r = csv.reader(f)
            header = next(r, None)
            if not header:
                return
            header = [h.lstrip("\ufeff").strip().strip('"') for h in header]
            header = _normalize_repayments_headers(header)

            idx = {name: i for i, name in enumerate(header)}

            def getv(row, key, default=""):
                i = idx.get(key)
                if i is None or i >= len(row):
                    return default
                return row[i]
            
            has_type = "payment_type" in idx

            for row in r:
                loan_id = getv(row, "loan_id")
                custoemer_id = getv(row, "customer_id")
                payment_type = getv(row, "payment_type") if has_type else "REPAYMENT"
                amt = getv(row, "repayment_amount")
                rdate = getv(row, "repayment_date")
                yield {
                    "loan_id": loan_id,
                    "customer_id": custoemer_id,
                    "payment_type": (payment_type or "REPAYMENT").strip(),
                    "repayment_amount": amt,
                    "repayment_date": rdate,
                }
    except FileNotFoundError:
        return        