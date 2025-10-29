from __future__ import annotations

import argparse
import csv
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

# 既存ユーティリティを優先利用
from modules.utils import (
    get_project_paths,          # loan_csv / repayments_csvを解決
    clean_header_if_quoted,     # 起動時のヘッダの自動クレンジングに合わせておく
    validate_schema,            # 最低限のスキーマ検証
)

# ==== スキーマ（現行の loan_v3.csv / repayments.csv に一致） ====

LOAN_HEADERS = [
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
]

REPAY_HEADERS = ["loan_id", "customer_id", "repayment_amount", "repayment_date"]

REPAY_HEADER_ALIASES = {
    # 手動入力ゆれ吸収
    "repay_amount": "repayment_amount",
    "repayed_amount": "repayment_amount",
    "date": "repayment_date",
    "payer": "customer_id",
}

# ==== I/O ユーティリティ ====

def _backup_if_exists(path: Path):
    # ファイルが存在する時だけバックアップ（ディレクトリは無視）
    if not path.is_file():
        return
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    # 例: loan_v3.csv.bak.20251029... を同じフォルダに作成
    candidate = path.with_name(f"{path.name}.bak.{ts}")
    i = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak.{ts}.{i}")
        i += 1
    shutil.copy2(str(path), str(candidate))

def _write_csv(path: Path, headers: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in headers})

def _append_csv(path: Path, headers: list[str], rows: list[dict]):
    path.parcent.mkdir(parents=True, exist_ok=True)
    newfile = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if newfile:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in headers})

def _sum_paid_for_loan(repay_csv: Path, loan_id: str) -> int:
    if not repay_csv.exists() or repay_csv.stat().st_size == 0:
        return 0
    total = 0
    with repay_csv.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if not header:
            return 0
        # 別名吸収
        norm = []
        for h in header:
            key = h.lstrip("\ufeff").strip().strip('"')
            norm.append(REPAY_HEADER_ALIASES.get(key, key))
        try:
            idx_loan = norm.index("loan_id")
            idx_amt  = norm.index("repayment_amount")
        except ValueError:
            return 0
        for row in rdr:
            if len(row) <= max(idx_loan, idx_amt):
                continue
            if row[idx_loan] == loan_id:
                try:
                    total += int(float(row[idx_amt]))
                except Exception:
                    pass    
    return total    

# ==== デフォルト投入データ（再現性重視の代表ケース）====

def _default_loans() -> list[dict]:
    today = date.today()
    loans = [
        # 1) 延滞中（期日=今日-30, 猶予0）
        {
            "loan_id": f"L{(today - timedelta(days=60)).strftime('%Y%m%d')}-001",
            "customer_id": "CUST001",
            "loan_amount": 10000,
            "loan_date": (today - timedelta(days=60)).isoformat(),
            "due_date": (today - timedelta(days=30)).isoformat(),
            "interest_rate_percent": 100.0,
            "repayment_expected": 20000,
            "repayment_method": "CASH",
            "grace_period_days": 0,
            "late_fee_rate_percent": 10.0,
            "late_base_amount": 10000,
        },
        # 2) 期日内（期日=今日+10, 猶予0）
        {
            "loan_id": f"L{(today - timedelta(days=5)).strftime('%Y%m%d')}-001",
            "customer_id": "CUST001",
            "loan_amount": 5000,
            "loan_date": (today - timedelta(days=5)).isoformat(),
            "due_date": (today + timedelta(days=10)).isoformat(),
            "interest_rate_percent": 100.0,
            "repayment_expected": 10000,
            "repayment_method": "BANK_TRANSFER",
            "grace_period_days": 0,
            "late_fee_rate_percent": 10.0,
            "late_base_amount": 5000,
        },
        # 3) 完済（CUST002）← ここが大事：customer_id を必ず含める
        {
            "loan_id": f"L{(today - timedelta(days=40)).strftime('%Y%m%d')}-001",
            "customer_id": "CUST002",
            "loan_amount": 8000,
            "loan_date": (today - timedelta(days=40)).isoformat(),
            "due_date": (today - timedelta(days=5)).isoformat(),
            "interest_rate_percent": 100.0,
            "repayment_expected": 16000,
            "repayment_method": "CASH",
            "grace_period_days": 0,
            "late_fee_rate_percent": 10.0,
            "late_base_amount": 8000,
        },
    ]

    # 必須キー検証（欠落があれば即指摘して終了）
    required = set(LOAN_HEADERS)
    for i, rec in enumerate(loans):
        missing = [k for k in required if k not in rec]
        if missing:
            raise SystemExit(f"[seed] default_loans[{i}] missing keys: {missing}")
    return loans

def _default_repayments(loans: list[dict]) -> list[dict]:
    """完済レコード（L_closed のみ全額返済）"""
    today = date.today()

    # CUST002 のレコードを安全に探索（キー欠落に強い）
    l_closed = next((x for x in loans if (x.get("customer_id") == "CUST002")), None)
    if not l_closed:
        # 代表ケースが壊れている場合は明確に指摘して終了
        raise SystemExit(
            "[seed] internal error: closed-loan(CUST002) not found. "
            "Check _default_loans() for 'customer_id' and other keys."
        )

    # 必須キーのフォールバック（タイプミス対策）
    expected = int(float(l_closed.get("repayment_expected", 0)))
    cust_id = l_closed.get("customer_id", "CUST002")
    lid = l_closed.get("loan_id")

    if not lid or expected <= 0:
        raise SystemExit(
            "[seed] internal error: invalid closed-loan record. "
            f"loan_id={lid!r}, repayment_expected={expected}"
        )

    return [
        {
            "loan_id": lid,
            "customer_id": cust_id,
            "repayment_amount": expected,
            "repayment_date": (today - timedelta(days=3)).isoformat(),
        },
        # 過剰返済境界の追加テストを行う場合はここに追記行を足してください
    ]

# ==== サマリ ====

def _summarize(loans_csv: Path, repay_csv: Path):
    with loans_csv.open("r", newline="", encoding="utf-8") as f:
        loans = list(csv.DictReader(f))
    with repay_csv.open("r", newline="", encoding="utf-8-sig") as f:
        repays = list(csv.DictReader(f)) if f.readable() and repay_csv.stat().st_size > 0 else []
    print("== Seed Summary ==")
    print(f"loans: {len(loans)} rows, repayments: {len(repays)} rows")
    for L in loans:
        lid = L.get("loan_id", "")
        exp = int(float(L.get("repayment_expected", 0) or 0))
        paid = _sum_paid_for_loan(repay_csv, lid)
        bal  = max(0, exp -paid)
        print(F"- {lid} ({L.get('customer_id','')}): expected={exp}, paid={paid}, balance={bal}")

# ==== メイン ====

def main():
    ap = argparse.ArgumentParser(description="Seed demo data for k_loan_ledger")
    ap.add_argument("--force", action="store_true", help="既存CSVをバックアップし初期化して投入")
    ap.add_argument("--append", action="store_true", help="既存CSVへ追記")
    ap.add_argument("--root", type=str, default=None, help="プロジェクトルート指定（任意）")
    args = ap.parse_args()

    if args.force and args.append:
        print("ERROR: --force と --append は同時使用不可です。")
        raise SystemExit(2)
    
    paths = get_project_paths(args.root)
    loans_csv = Path(paths["loans_csv"])
    repay_csv = Path(paths["repayments_csv"])

    loans = _default_loans()
    repays = _default_repayments(loans)

    if args.force:
        _backup_if_exists(loans_csv)
        _backup_if_exists(repay_csv)
        _write_csv(loans_csv, LOAN_HEADERS, loans)
        _write_csv(repay_csv, REPAY_HEADERS, repays)
    elif args.append:
        # ヘッダ不整合を避けるため既存ヘッダが "col" 形式なら剥がす
        clean_header_if_quoted(loans_csv)
        clean_header_if_quoted(repay_csv)
        _append_csv(loans_csv, LOAN_HEADERS, loans)
        _append_csv(repay_csv, REPAY_HEADERS, repays)
    else:
        # どちらも未指定：既存があれば安全のためエラー
        if loans_csv.exists() or repay_csv.exists():
            print("ERROR: 既存CSVが見つかりました。--force または --append を指定してください。")
            raise SystemExit(1)
        _write_csv(loans_csv, LOAN_HEADERS, loans)
        _write_csv(repay_csv, REPAY_HEADERS, repays)

    # 軽いスキーマ検証（不足があってもここでは通知のみ）
    validate_schema(loans_csv, set(LOAN_HEADERS))
    validate_schema(repay_csv, set(REPAY_HEADERS))

    _summarize(loans_csv, repay_csv)

if __name__ == "__main__":
    main()

