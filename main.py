# --- 軽量 import（--summary で必要なものだけ） ---
from datetime import datetime, date
import argparse
import csv
import os
from pathlib import Path

# C-1（--summaryでも使う）
from modules.utils import (
    normalize_customer_id,
    normalize_method,
    fmt_date,
    get_project_paths,
    clean_header_if_quoted,
    validate_schema,
)

# --- C-7.5 非対話サマリ（軽量） ---

def _show_summary_noninteractive():
    """data配下CSVの件数だけを非対話で表示（理解日用の軽量サマリ）"""
    paths = get_project_paths()
    loans_p = Path(paths["loans_csv"])
    reps_p  = Path(paths["repayments_csv"])

    def _read_rows(p: Path):
        if p.exists() and p.stat().st_size > 0:
            with p.open("r", newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        return []

    loans = _read_rows(loans_p)
    reps  = _read_rows(reps_p)
    print(f"[summary] loans: {len(loans)} | repayments: {len(reps)}")

# === ここから下の“重い import（ドメイン層）”は try でガード ===
#    ※ --summary だけなら未存在でも問題なく動けるようにする
try:
    # 顧客情報関連
    from modules.customer_module import (
        list_customers,
        search_customer,
        get_all_customer_ids,
        get_credit_limit,
    )

    # 貸付・返済関連
    from modules.loan_module import (
        register_loan,
        display_loan_history,
        register_repayment,
        display_repayment_history,
        display_unpaid_loans,
        calculate_total_repaid_by_loan_id,
        is_loan_fully_repaid,
        get_total_repaid_amount,
        get_loan_info_by_loan_id,
        is_over_repayment,
    )

    # 残高照会
    from modules.balance_module import display_balance

    # ログ・監査
    from modules.logger import get_logger
    from modules.audit import append_audit   

    # グローバル・ロガー （二重出力しないようモジュールレベルで生成）
    logger = get_logger("k_loan_ledger")

except ModuleNotFoundError:
    # tests/test_seed_flow.py は最小構成のみをコピーするため、
    # --summary 実行時はこれらが無い想定。ダミーを用意しておく。
    def append_audit(*a, **k):
        return None

    class _DummyLogger:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass

    logger = _DummyLogger()

def _parse_today_arg(s: str | None) -> date:
    """--today の文字列を date に。未指定(None)なら今日を返す。"""
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"[ERROR] --today は YYYY-MM-DD 形式で指定してください: {s!r}")

# === 2) 既存の _parse_cli_args を置き換え === C-7.5
def _parse_cli_args():
    p = argparse.ArgumentParser()
    p.add_argument("--today", type=str, help="YYYY-MM-DD（指定がなければ今日）")
    p.add_argument("--summary", action="store_true", help="CSV件数のサマリのみ表示して終了（非対話）")
    return p.parse_args()

# 共通関数：モード突入時の技術ログ + 監査ログをセットで残す
def enter_mode(mode_name: str):
    logger.info(f"Enter mode: {mode_name}")
    append_audit("ENTER", "mode", mode_name, None)

def _prompt_date_or_today(prompt: str) -> str:
    """
    日付入力用の共通ヘルパー。
    - 空Enter: 今日の日付を YYYY-MM-DD で自動設定
    - それ以外: fmt_date で "YYYY-MM-DD" に正規化。失敗したら再入力。
    """
    while True:
        s = input(prompt).strip()
        if not s:
            today_str = datetime.today().strftime("%Y-%m-%d")
            print(f"[INFO] 日付を本日に自動設定しました: {today_str}")
            return today_str

        normalized = fmt_date(s)
        if not normalized:
            print("❌ 日付は YYYY-MM-DD 形式で入力してください（例：2025-05-05）。")
            continue
        return normalized

def loan_registration_mode(loans_file):

    # 顧客IDの存在を確認
    print("=== 顧客検索＆貸付記録モード ===")

    list_customers()  # 顧客一覧を表示

    keyword = input("検索したい顧客名またはIDの一部を入力してください: ")
    search_customer(keyword)  # 顧客名やIDの一部を検索して該当する顧客を表示する

    print("\n=== 貸付記録を登録 ===")

    # 事前に有効な顧客ID一覧を取得しておく
    valid_ids = {normalize_customer_id(x) for x in get_all_customer_ids()}
    
    # 👤 顧客ID入力（存在チェック付きループ）
    while True:
        customer_id_input = input(
            "👤顧客IDを入力してください(例：001またはCUST001): "
        ).strip()
        customer_id = normalize_customer_id(customer_id_input)

        if customer_id not in valid_ids:
            print("❌ 顧客IDが存在しません。先に顧客登録を行ってください。")
            continue
        break

    # 💰 貸付額を入力・チェック（整数・1円以上・上限以内）
    while True:
        amount_input = input("💰貸付金額を入力してください（例：10000）: ").strip()
        try:
            amount = int(amount_input)
        except ValueError:
            print("❌金額は整数で入力してください。")
            continue

        if amount <= 0:
            print("❌ 金額は1円以上で入力してください。")
            continue

        # 顧客の貸付上限金額を取得する
        credit_limit = get_credit_limit(customer_id)
        if credit_limit is None:
            print("❌ 顧客の上限金額を取得できません。処理を中断します。")
            return
        
        if amount > credit_limit:
            print(
                f"⚠ 上限金額({credit_limit}円) を超えています。別の金額を入力してください。"
            )
            continue

        # ここまで来たらOK
        break

    # 📈 利率を入力（デフォルト 10.0%、 1%以上のみ許可）
    while True:
        interest_input = input("📈利率（％）を入力してください ※未入力時は10.0%: ")
        if not interest_input:
            interest_rate = 10.0
            break
        try:
            interest_rate = float(interest_input)
        except ValueError:
            print("❌ 利率は数値で入力してください。")
            continue

        if interest_rate <= 0:
            print("❌ 利率は1%以上で入力してください。")
            continue
        break

    # 貸付日を入力（形式＋存在チェック付きで再入力ループ）
    while True:
        raw = input(
            "📅貸付日を入力(例：2025-05-05)※未入力なら今日の日付になります: "
        ).strip()

        # 空なら今日
        if raw == "":
            loan_date = datetime.today().strftime("%Y-%m-%d")
            print(f"[INFO] 貸付日は本日に自動設定しました: {loan_date}")
            break

        # まず fmt_date で "YYYY-MM-DD" に正規化（/ や . も許容）
        normalized = fmt_date(raw)
        if normalized is None:
            print("❌ 日付の形式が不正です。YYYY-MM-DD 形式で入力してください。")
            continue

        # ここで「カレンダー的に存在するか」までチェックする
        try:
            datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            print("❌ 存在しない日付です。正しい日付を入力してください。")
            continue

        loan_date = normalized
        break


    # 💳 返済方法を入力（normalize_method のまま使用） 
    repayment_method = input("💳返済方法を入力してください（例：現金／振込）: ").strip()
    repayment_method = normalize_method(repayment_method) # "CASH" 等に標準化
    if repayment_method == "UNKNOWN":
        print("⚠ 返済方法が特定できないため UNKNOWN として登録します。")

    # ⏳ 延滞猶予日数を入力（整数・0以上）
    while True:
        grace_input = input(
            "⏳延滞予定日数（日数）を入力してください（例：5）※未入力なら0日: "
        ).strip()
        if not grace_input:
            grace_period_days = 0
            break
        try:
            grace_period_days = int(grace_input)
        except ValueError:
            print("❌ 猶予日数は整数で入力してください。")
            continue

        if grace_period_days < 0:
            print("❌ 猶予日数は0以上で入力してください。")
            continue
        break

    # 🔢 延滞利率の入力（デフォルト 10.0%、0以上の数値）
    while True:
        late_fee_input = input(
            "🔢 延滞利率 (%) を入力してください（例：10.0）※未入力で10.0: "
        ).strip()
        if not late_fee_input:
            late_fee_rate_percent = 10.0
            break
        try:
            late_fee_rate_percent = round(float(late_fee_input), 1)
        except ValueError:
            print("❌ 延滞利率は数値で入力してください。")
            continue

        if late_fee_rate_percent < 0:
            print("❌ 延滞利率は0以上で入力してください。")
            continue
        break

    # C-12: 備考入力フック
    notes = input("📝 その他条件/備考があれば入力（未入力でスキップ）: ").strip()

    # ここまでバリテーション通過 → register_loan に渡す
    register_loan(
        customer_id,
        amount,
        loan_date,
        interest_rate_percent=interest_rate,
        repayment_method=repayment_method,
        grace_period_days=grace_period_days,
        late_fee_rate_percent=late_fee_rate_percent,
        file_path=loans_file,
        notes=notes,
    )

def loan_history_mode(loans_file):
    print("=== 履歴表示モード ===")
    # 顧客IDを入力
    customer_id = normalize_customer_id(
        input("👤 顧客IDを入力してください（例：CUST001 または 001）： ").strip()
    )
    display_loan_history(customer_id, filepath=loans_file)


# repayment_registration_mode の定義
def repayment_registration_mode(loans_file, repayments_file):
    print("\n=== 返済記録モード (B-11 新実装）===")

    # 初期化（なければヘッダー作成）
    def initialize_repayments_csv():
        header = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]
        with open(repayments_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
        print("[INFO] repayments.csv を初期化しました。")

    # 1) loan_id 直接入力 or 空Enterで未返済候補表示→選択
    first = input("登録する loan_id を入力（未入力で顧客IDから未返済候補を表示）: ").strip()
    if not first:
        cust_input = input("顧客IDを入力してください（例：CUST001 または 001）: ").strip()
        customer_id = normalize_customer_id(cust_input)
        try:
            # 未返済（期日内＋延滞）を一覧表示
            _ = display_unpaid_loans(
                customer_id,
                filter_mode="all",
                loan_file=loans_file,
                repayment_file=repayments_file,
                today=date.today(),
            )
        except Exception as _e:
            print(f"[WARN] 未返済候補の表示で警告: {_e}")
        loan_id = input("上の一覧から登録する loan_id を入力してください: ").strip()
    else:
        loan_id = first

    # loan_id 妥当性（存在）を loan_module 側APIで厳密確認
    info = get_loan_info_by_loan_id(loans_file, loan_id)
    if not info:
        print(f"[ERROR] loan_id {loan_id} が {os.path.basename(loans_file)} に存在しません。")
        print("       顧客IDから候補を出すには、もう一度やり直して最初の入力を空Enterしてください。")
        return
    customer_id = info.get("customer_id")

    # 契約解除済みはブロック
    if info.get("contract_status") == "CANCELLED":
        print(f"[ERROR] loan_id {loan_id} は契約解除済みのため返済登録できません。")
        return


    # 返済金額入力
    while True:
        repayment_amount = input("返済金額を入力してください（整数）: ").strip()
        if repayment_amount.isdigit() and int(repayment_amount) > 0:
            repayment_amount = int(repayment_amount)
            break
        else:
            print("[ERROR] 数字かつ1円以上を入力してください。")

    # 返済日入力（フォーマット検証＋空Enterで今日）
    repayment_date = _prompt_date_or_today(
        "返済日を入力してください（YYYY-MM-DD、未入力で今日の日付）: "
    )
    
    # 追記
    row = {
        "loan_id": loan_id,
        "customer_id": customer_id,
        "repayment_amount": repayment_amount,
        "repayment_date": repayment_date,
    }
    # repayments.csv がなければ作成してから追記
    file_exists = os.path.isfile(repayments_file)
    if not file_exists or os.stat(repayments_file).st_size == 0:
        initialize_repayments_csv()
    with open(repayments_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["loan_id", "customer_id", "repayment_amount", "repayment_date"],
        )
        writer.writerow(row)
    print(f"[INFO] repayments.csv に追記しました: {row}")

    print("✅ 返済記録の登録が完了しました。")

def cancel_contract_mode(loans_file):
    print("\n=== 契約解除登録(C-9) ===")
    loan_id = input("契約解除する loan_id を入力してください: ").strip()
    info = get_loan_info_by_loan_id(loans_file, loan_id)
    if not info:
        print(f"[ERROR] loan_id {loan_id} が見つかりません。")
        return

    # 事前プレビュー
    print(f"  loan_id: {loan_id}")
    print(f"  顧客ID : {info.get('customer_id')}")
    print(f"  貸付日 : {info.get('loan_date')}")
    print(f"  元本   : {info.get('loan_amount')}")
    print(f"  期日   : {info.get('due_date')}")
    print(f"  状態   : {info.get('contract_status','(なし→ACTIVE)')}")

    reason = input("解除理由（空でも可）: ").strip()
    ok = input("この内容で契約解除しますか？ (y/N): ").strip().lower()
    if ok != "y":
        print("[INFO] キャンセルしました。")
        return

    from modules.loan_module import cancel_contract
    if cancel_contract(loans_file, loan_id, reason=reason, operator="CLI"):
        pass  # 監査は cancel_contract 内で記録済み

def main():
    # C-7.5
    args = _parse_cli_args()
    if getattr(args, "summary", False):
        # ルート解決・CSV健全化は main() 本体の責務に乗る前に軽く実行
        paths = get_project_paths()
        # BOM/引用符の自動クレンジング（必要なら）
        clean_header_if_quoted(paths["loans_csv"])
        clean_header_if_quoted(paths["repayments_csv"])
        # 最低限のスキーマ確認（WARNのみ）
        validate_schema(paths["loans_csv"], {
            "loan_id","customer_id","loan_amount","loan_date","due_date",
            "interest_rate_percent","repayment_expected","repayment_method",
            "grace_period_days","late_fee_rate_percent","late_base_amount",
            # C-9
            "contract_status","cancelled_at","cancel_reason",
            # C-12
            "notes",
        })
        validate_schema(paths["repayments_csv"], {
            "loan_id","customer_id","repayment_amount","repayment_date",
        })
        _show_summary_noninteractive()
        return
    
    today_override = _parse_today_arg(args.today)
    paths = get_project_paths()
    loans_file = str(paths["loans_csv"])
    repayments_file = str(paths["repayments_csv"])

    # C-6.5: 起動スキーマ整合（無停止・冪等）
    try:
        from schema_migrator import check_or_migrate_schemas
        check_or_migrate_schemas()
    except Exception as e:
        logger.warning(f"Schema check failed (continue anyway): {e}")    

    # 起動ログ監査
    logger.info("App boot")
    append_audit("START", "app", "session", {"cwd": os.getcwd()}, actor="CLI")

    # ヘッダが "col" 形式なら自動で外す（初回だけでOK）
    # [C-6] 起動時のCSV健全化：引用符ヘッダがあれば除去してINFOログを残す
    if clean_header_if_quoted(loans_file):
        logger.info("clean_header_if_quoted: fixed header -> loan_v3.csv")
    if clean_header_if_quoted(repayments_file):
        logger.info("clean_header_if_quoted: fixed header -> repayments.csv")

    # 軽いスキーマ検証（足りない時は警告のみ）
    validate_schema(
        loans_file,
        {
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
            # C-9
            "contract_status","cancelled_at","cancel_reason",
            # C-12
            "notes",
        },
    )
    validate_schema(
        repayments_file,
        {"loan_id", "customer_id", "repayment_amount", "repayment_date"},
    )

    # メニューを表示して、どのモードを動かすか選ぶ
    # ユーザーの入力に応じて各モードを呼び出す
    try:
        while True:
            print("=== K's Loan Ledger ===")
            print("1: 貸付記録モード")
            print("2: 貸付履歴表示モード")
            print("3: 返済記録モード")
            print("4: 返済履歴表示モード")
            print("5: 残高照会モード")
            print("9: 未返済サマリー表示（テスト用）")
            print("10: 延滞貸付表示モード")
            print("11: 契約解除登録(C-9)")
            print("0: 終了")

            choice = input("モードを選択してください: ").strip()
            logger.info(f"Menu selected: {choice}")
            if choice == "1":
                enter_mode("loan_registration")
                loan_registration_mode(loans_file)

            elif choice == "2":
                enter_mode("loan_history")
                loan_history_mode(loans_file)

            elif choice == "3":
                enter_mode("repayment_registration")
                repayment_registration_mode(loans_file, repayments_file)  # B-11 新実装

            elif choice == "4":
                enter_mode("repayment_history")
                print("\n=== 返済履歴表示モード ===")
                customer_id = normalize_customer_id(
                    input(
                        "👤 顧客IDを入力してください（例：CUST001 または 001）: "
                    ).strip()
                )
                display_repayment_history(customer_id, filepath=repayments_file)

            elif choice == "5":
                enter_mode("balance_inquiry")
                print("\n=== 残高照会モード ===")
                customer_id = normalize_customer_id(
                    input(
                        "👤 顧客IDを入力してください（例：CUST001 または 001）: "
                    ).strip()
                )
                display_balance(customer_id)

            elif choice == "9":
                enter_mode("unpaid_summary")
                print("\n=== 未返済貸付一覧＋サマリー ===")
                customer_id = normalize_customer_id(
                    input(
                        "👤 顧客IDを入力してください（例：CUST001　または 001）: "
                    ).strip()
                )
                display_unpaid_loans(
                    customer_id,
                    filter_mode="all",
                    loan_file=loans_file,
                    repayment_file=repayments_file,
                    today=today_override,
                )

            elif choice == "10":
                enter_mode("overdue_loans")
                print("\n=== 延滞貸付一覧表示モード ===")
                customer_id = normalize_customer_id(
                    input(
                        "👤 顧客IDを入力してください（例：CUST001 または 001）: "
                    ).strip()
                )
                display_unpaid_loans(
                    customer_id,
                    filter_mode="overdue",
                    loan_file=loans_file,
                    repayment_file=repayments_file,
                    today=today_override,
                )

            elif choice == "11":
                enter_mode("cancel_contract")
                cancel_contract_mode(loans_file)


            elif choice == "0":
                print("終了します。")
                append_audit("END", "app", "session", {"status": "OK"}, actor="CLI")
                logger.info("App shutdown (user exit)")
                break

            else:
                print("❌ 無効な選択肢です。もう一度入力してください。")
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        append_audit("ERROR", "app", "session", {"error": str(e)}, actor="CLI")
        raise


if __name__ == "__main__":
    # --- C-0 quick test (一時追加したら終わったら消してOK) ---
    # from datetime import date
    # from modules.loan_module import display_unpaid_loans

    # test_customer = "CUST003"

    # print("\n[TEST-1] 閾値ちょうど（延滞にならない想定）")
    # display_unpaid_loans(
    # customer_id=test_customer,
    # loan_file=loans_file,
    # repayment_file="repayments.csv",
    # filter_mode="overdue",
    # today=date(2025, 8, 15)   # due 8/10 + 猶予5日 → 閾値 8/15
    # )

    # print("\n[TEST-2] 閾値+1日（延滞になる想定）")
    # display_unpaid_loans(
    # customer_id=test_customer,
    # loan_file=loans_file,
    # repayment_file="repayments.csv",
    # filter_mode="overdue",
    # today=date(2025, 8, 16)   # 閾値を1日超える
    # )

    main()
# ---テスト用（C-0）
# from datetime import date
# from modules.loan_module import display_unpaid_loans

# テスト用の顧客ID
# test_customer = "CUST003"

# print("=== C-0 動作確認テスト ===")
# display_unpaid_loans(
# customer_id=test_customer,
# loan_file="loan_v3.csv",
# repayment_file="repayments.csv",
# filter_mode="overdue",
# today=date(2025, 8, 27)
# )

# --- テスト用（B-13）---
# loan_id = "L20250723-001"
# result = is_loan_fully_repaid(loan_id)
# print(f"[判定結果] Loan {loan_id} fully repaid? → {result}")


# --- テスト用（B-12）---
#    test_loan_id = "L20250721-001"
#    result = calculate_total_repaid_by_loan_id("repayments.csv", test_loan_id)
#    print(f"📊 Loan ID {test_loan_id} の累計返済額は：{result:,}円")
