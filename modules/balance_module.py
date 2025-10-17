from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, Iterable, Tuple, List

from modules.utils import (
    get_project_paths,
    clean_header_if_quoted,
    fmt_currency,
)
from modules.logger import get_logger

# --- C-6: balance側でも明示的にスキーマ検証してログに出す ---

REQUIRED_LOANS = {
    "loan_id",
    "customer_id",
    "loan_amount",
    "loan_date",
    "interest_rate_percent",
    "repayment_expected",
    "repayment_method",
    "grace_period_days",
    "late_fee_rate_percent",
    "late_base_amount",
}

REQUIRED_REPAY = {
    "loan_id",
    "customer_id",
    "repayment_amount", # 新カラム名（旧: amount は後方互換で読み取りのみ対応）
    "repayment_date",
}

def _read_header(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        first = f.readline()
        if not first:
            return []
        return [c.strip().strip('"') for c in first.rstrip("\n\r").split(",")]
    
def _schema_diff(header: Iterable[str], required: Iterable[str]) -> Tuple[List[str], List[str]]:
    hset = set(header)
    rset = set(required)
    missing = sorted(list(rset - hset))
    extra = sorted(list(hset -rset))
    return (missing, extra)

def _preflight(paths: Dict[str, Path], logger) -> None:
    """ヘッダ修正→スキーマ検証→結果をINFO/WARNでログ出力"""
    loans = Path(paths["loans_csv"])
    reps = Path(paths["repayments_csv"])

    # 1) ヘッダの引用符を除去（変更があればINFOログ）
    for p in (loans, reps):
        changed = clean_header_if_quoted(p)
        if changed:
            logger.info(f"clean_header_if_quoted: fixed header -> {p.name}")

    # 2) スキーマ検証（balance側でも必ず実施してログへ）
    if loans.exists():
        h = _read_header(loans)
        miss, extra = _schema_diff(h, REQUIRED_LOANS)
        if not miss:
            logger.info("validate_schema: OK (loans)")
        else:
            logger.warning(f"validate_schema: WARN (loans) missing={miss} extra={extra}")
    else:
        logger.warning("validate_schema: WARN (loans) file not found")

    if reps.exists():
        h = _read_header(reps)
        miss, extra = _schema_diff(h, REQUIRED_REPAY)
        if not miss:
            logger.info("validate_schema: OK (repayments)")
        else:
            logger.warning(f"validate_schema: WARN (repayments) missing={miss} extra={extra}")
    else:
        logger.warning("validate_schema: WARN (repayments) file not found")


# --- 金額バース（カンマ/空白/全角空白/空欄/少数を吸収）---

def _parse_money(x) -> int:
    if x is None:
        return 0
    s = str(x).replace(",", "").replace(" ", "").replace("\u3000", "")
    if s == "" or s.lower() == "nan":
        return 0
    try:
        # "11000" / "11000.0" / "1 100"　などを許容
        return int(float(s))
    except Exception:
        return 0
    
def _normalize_row(d: dict) -> dict:
    """キー・値の前後空白と外側クォートを軽く正規化"""
    def n(v):
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            s = s[1:-1].strip()
        return s
    return {n(k): n(v) for k, v in (d or {}).items()}

# --- 公開API ---

def display_balance(customer_id: str, paths: Dict[str, Path] | None = None, clamp_negative: bool = False) -> None:
    """
    残高を表示する(メニュー5から利用)
    - 引数paths省略時は get_project_paths() の data 配下を使用 (C-6要件)
    - 事前にヘッダ補正＆スキーマ検証を行い、結果を data/app.log に INFO/WARN 出力
    - 表示の金額は fmt_currency() で "¥#,###" 統一
    """
    paths = paths or get_project_paths()
    logger = get_logger("k_loan_ledger")

    _preflight(paths, logger)

    loans_file = Path(paths["loans_csv"])
    reps_file = Path(paths["repayments_csv"])

    # --- 集計：顧客別 期待値返済額 と 返済額 ---
    loan_totals = defaultdict(int)
    repay_totals = defaultdict(int)

    if loans_file.exists():
        with loans_file.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                row = _normalize_row(row)
                if row.get("customer_id") != customer_id:
                    continue
                expected = _parse_money(row.get("repayment_expected") or row.get("loan_amount"))
                loan_totals[customer_id] += expected

    if reps_file.exists():
        with reps_file.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                row = _normalize_row(row)
                if row.get("customer_id") != customer_id:
                    continue
                # 新: repayment_amount / 旧: amount の双方に対応
                amount = _parse_money(row.get("repayment_amount") or row.get("amount"))
                repay_totals[customer_id] += amount

    excepted_total = loan_totals.get(customer_id, 0)
    repaid_total = repay_totals.get(customer_id, 0)
    balance = excepted_total -repaid_total
    if clamp_negative:
        balance = max(0, balance)

    # --- 表示（フォーマット統一）---
    print("\n=== 残高照会モード ===")
    print(f"顧客ID：{customer_id}")
    print(f"💰 貸付総額（予定返済額合計）：{fmt_currency(excepted_total)}")
    print(f"💸 返済総額：{fmt_currency(repaid_total)}")
    print(f"🧾 残高（未返済額）：{fmt_currency(balance)}")