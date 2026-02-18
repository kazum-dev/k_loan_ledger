# --- 軽量 import（--summary で必要なものだけ） ---
from datetime import datetime, date
import argparse
import csv
import os
import sys
from pathlib import Path

# C-1（--summaryでも使う）
from modules.utils import (
    normalize_customer_id,
    normalize_method,
    fmt_date,
    get_project_paths,
    clean_header_if_quoted,
    prompt_method,
    validate_schema,
    prompt_int,
    prompt_float,
    prompt_date_or_today,
    prompt_customer_id
)

def _count_csv_rows(path: Path) -> int:
    """ヘッダー除く行数（ファイル無ければ0）"""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        # 1行目ヘッダーを除外
        n = -1
        for _ in f:
            n += 1
        return max(0, n)

def _quick_summary(argv: list[str]) -> bool:
    if "--summary" not in argv:
        return False

    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    loans = data_dir / "loan_v3.csv"
    reps  = data_dir / "repayments.csv"

    print(f"[summary] loans: {_count_csv_rows(loans)} | repayments: {_count_csv_rows(reps)}")
    raise SystemExit(0)

_quick_summary(sys.argv[1:])

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

except ModuleNotFoundError as e:
    #print(f"[ERROR] import 失敗: {e}")
    print(f"❌ ERROR: importに失敗しました: {e}。")
    raise
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
        raise SystemExit(f"❌ ERROR: --todayはYYYY-MM-DD形式で指定してください: {s!r}。")

# === 2) 既存の _parse_cli_args を置き換え === C-7.5
def _parse_cli_args():
    p = argparse.ArgumentParser()
    p.add_argument("--today", type=str, help="YYYY-MM-DD（指定がなければ今日）")
    return p.parse_args()

# 共通関数：モード突入時の技術ログ + 監査ログをセットで残す
def enter_mode(mode_name: str):
    logger.info(f"Enter mode: {mode_name}")
    append_audit("ENTER", "mode", mode_name, None)

def loan_registration_mode(loans_file):

    # 顧客IDの存在を確認
    print("=== 顧客検索＆貸付記録モード ===")

    list_customers()  # 顧客一覧を表示

    keyword = input("検索したい顧客名またはIDの一部を入力してください: ")
    search_customer(keyword)  # 顧客名やIDの一部を検索して該当する顧客を表示する

    print("\n=== 貸付記録を登録 ===")

    # 事前に有効な顧客IDを取得しておく
    valid_ids = {normalize_customer_id(x) for x in get_all_customer_ids()}

    # 👤 顧客ID入力（存在チェック付き）
    customer_id = prompt_customer_id(
        "👤顧客IDを入力してください(例：001またはCUST001): ",
        valid_ids=valid_ids,
    )

    # 上限取得
    credit_limit = get_credit_limit(customer_id)
    if credit_limit is None:
        print("❌ ERROR: 顧客の上限金額を取得できません。処理を中断します。")
        return
    
    # 💰 貸付額（整数・1円以上・上限以内）
    amount = prompt_int(
        "💰 貸付金額を入力してください（例：10000）: ",
        min_value=1,
        max_value=credit_limit,
    )

    # 📈 利率（デフォ10.0 / 0.1以上）
    interest_rate = prompt_float(
        "📈利率（％）を入力してください ※未入力時は10.0%: ",
        min_value=0.1,
        default=10.0,
    )

    # 📅 貸付日（未入力なら今日）
    loan_date = prompt_date_or_today(
        "📅貸付日を入力(例：2025-05-05)※未入力なら今日の日付になります: "
    )

    # 💳 返済方法（標準化）
    repayment_method = prompt_method("💳返済方法を入力してください（例：現金／振込）: ")

    # 猶予日数（デフォ0 / 0以上）
    grace_period_days = prompt_int(
        "⏳延滞猶予日数（日数）を入力してください（例：5） ※未入力なら0日: ",
        min_value=0,
        default=0,
    )

    # 🔢 延滞利率（デフォ10.0 / 0以上 / 小数1桁丸め）
    late_fee_rate_percent = prompt_float(
        "🔢 延滞利率（％）を入力してください（例：10.0）※未入力で10.0: ",
        min_value=0.0,
        default=10.0,
        round_to=1,
    )

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



def repayment_registration_mode(loans_file, repayments_file):
    print("\n=== 返済記録モード (B-11 新実装）===")

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
            print(f"⚠️ WARN: 未返済候補の表示に失敗しました: {_e}。")
        loan_id = input("上の一覧から登録する loan_id を入力してください: ").strip()
    else:
        loan_id = first

    # 返済金額入力
    repayment_amount = prompt_int("返済金額を入力してください（整数）: ", min_value=1)

    repayment_date = prompt_date_or_today(
        "返済日を入力してください（YYYY-MM-DD、未入力で今日の日付）: "
    )
    
    from modules.loan_module import register_repayment_complete

    # 追記
    summary = register_repayment_complete(
        loans_file=loans_file,
        repayments_file=repayments_file,
        loan_id=loan_id,
        amount=repayment_amount,
        repayment_date=repayment_date,
        actor="user",
    )

    if not summary:
        print("❌ ERROR: 返済登録に失敗しました（入力額超過/loan_id不正など）。")
        return

    print("✅ SUCCESS: 返済記録の登録が完了しました。")
    print(f"✅ SUCCESS: 書込先: {summary.get('repayments_file')}。")
    print(f"✅ SUCCESS: 入力合計: ¥{summary['input_total']:,} "f"(REPAYMENT: ¥{summary['repayment_part']:,} / LATE_FEE: ¥{summary['late_fee_part']:,})。")

    # 実際に書いた行を全部表示
    for r in summary["written_rows"]:
        print(f"✅ SUCCESS: 追記行: {r}。")

def cancel_contract_mode(loans_file):
    print("\n=== 契約解除登録(C-9) ===")
    loan_id = input("契約解除する loan_id を入力してください: ").strip()
    info = get_loan_info_by_loan_id(loans_file, loan_id)
    if not loan_id: print("❌ ERROR: loan_idを入力してください。"); return
    if not info:
        print(f"❌ ERROR: 指定されたloan_idは見つかりません: {loan_id}。")
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
        print("⚠️ WARN: キャンセルしました。")
        return

    from modules.loan_module import cancel_contract
    if cancel_contract(loans_file, loan_id, reason=reason, operator="CLI"):
        pass  # 監査は cancel_contract 内で記録済み

def main():
    # C-7.5
    args = _parse_cli_args()

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
                customer_id = prompt_customer_id("👤 顧客IDを入力してください（例：CUST001 または 001）: ")
                display_repayment_history(customer_id, filepath=repayments_file)

            elif choice == "5":
                enter_mode("balance_inquiry")
                print("\n=== 残高照会モード ===")
                customer_id = prompt_customer_id("👤 顧客IDを入力してください（例：CUST001 または 001）: ")
                display_balance(customer_id)

            elif choice == "9":
                enter_mode("unpaid_summary")
                print("\n=== 未返済貸付一覧＋サマリー ===")
                customer_id = prompt_customer_id("👤 顧客IDを入力してください（例：CUST001 または 001）: ")
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
                customer_id = prompt_customer_id("👤 顧客IDを入力してください（例：CUST001 または 001）: ")
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
                print("✅ SUCCESS: 終了します。")
                append_audit("END", "app", "session", {"status": "OK"}, actor="CLI")
                logger.info("App shutdown (user exit)")
                break

            else:
                print("❌ ERROR: 無効な選択肢です。もう一度入力してください。")

    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        append_audit("ERROR", "app", "session", {"error": str(e)}, actor="CLI")
        raise

if __name__ == "__main__":
    main()