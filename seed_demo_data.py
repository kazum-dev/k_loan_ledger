from __future__ import annotations
import argparse, csv, shutil
from datetime import date, timedelta
from pathlib import Path

from modules.utils import (
    get_project_paths,
    clean_header_if_quoted,
    validate_schema,
)

LOAN_HEADERS = [
    "loan_id","customer_id","loan_amount","loan_date","due_date",
    "interest_rate_percent","repayment_expected","repayment_method",
    "grace_period_days","late_fee_rate_percent","late_base_amount",
]
REPAY_HEADERS = ["loan_id","customer_id","repayment_amount","repayment_date"]

REPAY_HEADER_ALIASES = {
    "repay_amount":"repayment_amount",
    "repayed_amount":"repayment_amount",
    "date":"repayment_date",
    "payer":"customer_id",
}

def _backup_if_exists(path: Path):
    if not path.is_file():
        return
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")
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
    path.parent.mkdir(parents=True, exist_ok=True)   # ← 修正済（parcent→parent）
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
    with repay_csv.open("r", newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if not header:
            return 0
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

def _default_loans() -> list[dict]:
    today = date.today()
    loans = [
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
    required = set(LOAN_HEADERS)
    for i, rec in enumerate(loans):
        missing = [k for k in required if k not in rec]
        if missing:
            raise SystemExit(f"[seed] default_loans[{i}] missing keys: {missing}")
    return loans

def _default_repayments(loans: list[dict]) -> list[dict]:
    today = date.today()
    l_closed = next((x for x in loans if (x.get("customer_id") == "CUST002")), None)
    if not l_closed:
        raise SystemExit("[seed] internal error: closed-loan(CUST002) not found.")
    expected = int(float(l_closed.get("repayment_expected", 0)))
    cust_id = l_closed.get("customer_id", "CUST002")
    lid = l_closed.get("loan_id")
    if not lid or expected <= 0:
        raise SystemExit("[seed] internal error: invalid closed-loan record.")
    return [{
        "loan_id": lid,
        "customer_id": cust_id,
        "repayment_amount": expected,
        "repayment_date": (today - timedelta(days=3)).isoformat(),
    }]

def _summarize(loans_csv: Path, repay_csv: Path):
    with loans_csv.open("r", newline="", encoding="utf-8") as f:
        loans = list(csv.DictReader(f))
    repays = []
    if repay_csv.exists() and repay_csv.stat().st_size > 0:
        with repay_csv.open("r", newline="", encoding="utf-8-sig") as f:
            repays = list(csv.DictReader(f))
    print("== Seed Summary ==")
    print(f"loans: {len(loans)} rows, repayments: {len(repays)} rows")
    for L in loans:
        lid = L.get("loan_id", "")
        exp = int(float(L.get("repayment_expected", 0) or 0))
        paid = _sum_paid_for_loan(repay_csv, lid)
        bal  = max(0, exp - paid)
        print(f"- {lid} ({L.get('customer_id','')}): expected={exp}, paid={paid}, balance={bal}")

def main():
    ap = argparse.ArgumentParser(description="Seed demo data for k_loan_ledger")
    ap.add_argument("--force", action="store_true", help="既存CSVをバックアップし初期化して投入")
    ap.add_argument("--append", action="store_true", help="既存CSVへ追記")
    ap.add_argument("--root", type=str, default=None, help="プロジェクトルート指定（任意）")
    args = ap.parse_args()

    if args.force and args.append:
        print("ERROR: --force と --append は同時使用不可です。"); raise SystemExit(2)

    paths = get_project_paths(args.root)
    loans_csv = Path(paths["loans_csv"])
    repay_csv = Path(paths["repayments_csv"])

    loans = _default_loans()
    repays = _default_repayments(loans)

    if args.force:
        _backup_if_exists(loans_csv); _backup_if_exists(repay_csv)
        _write_csv(loans_csv, LOAN_HEADERS, loans)
        _write_csv(repay_csv, REPAY_HEADERS, repays)
    elif args.append:
        clean_header_if_quoted(loans_csv); clean_header_if_quoted(repay_csv)
        _append_csv(loans_csv, LOAN_HEADERS, loans)
        _append_csv(repay_csv, REPAY_HEADERS, repays)
    else:
        if loans_csv.exists() or repay_csv.exists():
            print("ERROR: 既存CSVが見つかりました。--force または --append を指定してください。")
            raise SystemExit(1)
        _write_csv(loans_csv, LOAN_HEADERS, loans)
        _write_csv(repay_csv, REPAY_HEADERS, repays)

    validate_schema(loans_csv, set(LOAN_HEADERS))
    validate_schema(repay_csv, set(REPAY_HEADERS))
    _summarize(loans_csv, repay_csv)

if __name__ == "__main__":
    main()
