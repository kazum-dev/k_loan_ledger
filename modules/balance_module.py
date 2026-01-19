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

from modules.loan_module import get_unpaid_loans_rows, calculate_total_repaid_by_loan_id


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
def display_balance(customer_id: str,paths: Dict[str, Path] | None = None,today=None,clamp_negative: bool = True,) -> None:
    """
    残高を表示する(メニュー5から利用)
    - モード9/10と同じ判定軸（loan_idベース / CANCELLED除外 / REPAYMENTのみ）で残高を算出する
    """
    paths = paths or get_project_paths()
    logger = get_logger("k_loan_ledger")

    _preflight(paths, logger)

    loans_file = str(Path(paths["loans_csv"]))
    reps_file  = str(Path(paths["repayments_csv"]))

    unpaid_loans = get_unpaid_loans_rows(
        customer_id,
        loan_file=loans_file,
        repayment_file=reps_file,
        filter_mode="all",
        today=today,
    )

    total_expected = 0
    total_repaid = 0
    total_remaining = 0

    for loan in unpaid_loans:
        loan_id = loan.get("loan_id")
        if not loan_id:
            continue

        try:
            expected = int(float(loan.get("repayment_expected") or 0))
        except (ValueError, TypeError):
            expected = 0

        repaid = calculate_total_repaid_by_loan_id(reps_file, loan_id)
        raw_remaining = expected - repaid       
        remaining = max(0, raw_remaining) if clamp_negative else raw_remaining

        total_expected += expected
        total_repaid += repaid
        total_remaining += remaining

    print("\n=== 残高照会モード ===")
    print(f"顧客ID：{customer_id}")
    print(f"💰 未返済分の予定返済額合計：{fmt_currency(total_expected)}")
    print(f"💸 未返済分の返済済合計（REPAYMENT累計）：{fmt_currency(total_repaid)}")
    print(f"🧾 残高（未返済額合計）：{fmt_currency(total_remaining)}")
