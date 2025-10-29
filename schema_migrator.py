# schema_migrator.py
from __future__ import annotations
import csv
import shutil
import time
from pathlib import Path
from typing import Dict, List, Tuple

from modules.logger import get_logger
from modules.utils import get_project_paths

logger = get_logger("schema_migrator")

# ==== 正スキーマ（あなたの現行ヘッダで確定）========================
TARGET_SCHEMAS: Dict[str, List[str]] = {
    "loan_v3": [
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
    ],
    "repayments": [
        "loan_id",
        "customer_id",
        "repayment_amount",
        "repayment_date",
    ],
}

# 旧→新の自動リネーム（遭遇しがちな別名を保険で）
RENAME_MAPS: Dict[str, Dict[str, str]] = {
    "loan_v3": {
        "interest_percent": "interest_rate_percent",
        "repaymentMethod": "repayment_method",
        "repayment_expected_amount": "repayment_expected",
        "grace_days": "grace_period_days",
        "late_fee_percent": "late_fee_rate_percent",
        "late_amount_base": "late_base_amount",
        "amount": "loan_amount",
    },
    "repayments": {
        "amount": "repayment_amount",
        "paid_at": "repayment_date",
        "repaymentAt": "repayment_date",
    },
}

# 欠落列のデフォルト
DEFAULTS: Dict[str, Dict[str, str]] = {
    "loan_v3": {
        "grace_period_days": "0",
        "late_fee_rate_percent": "0",
        "late_base_amount": "",
    },
    "repayments": {},
}

ENABLE_BACKUP = True  # *.bak.YYYYMMDD_HHMMSS を作る


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _backup(src: Path) -> None:
    if not ENABLE_BACKUP or not src.exists():
        return
    dst = src.with_suffix(src.suffix + f".bak.{_ts()}")
    shutil.copy2(src, dst)
    logger.info(f"Backup: {src.name} -> {dst.name}")


def _read_header(p: Path) -> List[str]:
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            hdr = next(reader)
        except StopIteration:
            hdr = []
    return [h.strip().strip('"').strip("'") for h in hdr]


def _write_with_new_header(
    src: Path,
    dst: Path,
    new_header: List[str],
    rename_map: Dict[str, str],
    defaults: Dict[str, str],
) -> None:
    with src.open("r", newline="", encoding="utf-8-sig") as rf, dst.open(
        "w", newline="", encoding="utf-8"
    ) as wf:
        reader = csv.DictReader(rf)
        norm_rows = []
        for row in reader:
            n = {}
            for k, v in row.items():
                n[rename_map.get(k, k)] = v
            norm_rows.append(n)

        writer = csv.DictWriter(wf, fieldnames=new_header, extrasaction="ignore")
        writer.writeheader()
        for r in norm_rows:
            out = {}
            for col in new_header:
                val = r.get(col, "")
                out[col] = val if (val is not None and val != "") else defaults.get(col, "")
            writer.writerow(out)


def _migrate_one(
    csv_path: Path,
    target_header: List[str],
    rename_map: Dict[str, str],
    defaults: Dict[str, str],
) -> Tuple[bool, str]:
    if not csv_path.exists():
        return False, f"SKIP (not found): {csv_path.name}"

    current = _read_header(csv_path)
    if not current:
        _backup(csv_path)
        tmp = csv_path.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as wf:
            csv.writer(wf).writerow(target_header)
        tmp.replace(csv_path)
        return True, f"INIT header written: {csv_path.name}"

    logical = [rename_map.get(c, c) for c in current]
    missing = [c for c in target_header if c not in logical]
    extras = [c for c in logical if c not in target_header]
    order_diff = logical != target_header
    need = bool(missing or extras or order_diff or (logical != current))
    if not need:
        return False, f"OK (already up-to-date): {csv_path.name}"

    _backup(csv_path)
    tmp = csv_path.with_suffix(".tmp")
    new_header = target_header + extras  # 余剰を残したい方針。削除したいなら target_header のみに。
    _write_with_new_header(csv_path, tmp, new_header, rename_map, defaults)
    tmp.replace(csv_path)

    detail = []
    if missing:
        detail.append(f"+{missing}")
    if extras:
        detail.append(f"extras->{extras}")
    if order_diff:
        detail.append("reordered")
    if logical != current:
        detail.append("renamed")
    return True, f"FIXED {csv_path.name}: " + ", ".join(detail)


def check_or_migrate_schemas() -> None:
    paths = get_project_paths()
    data_dir = paths["data"]
    loan_csv = paths["loans_csv"]
    rep_csv = paths["repayments_csv"]
    data_dir.mkdir(parents=True, exist_ok=True)

    # ---- キー存在ガード（今回のKeyError対策）----
    if "loan_v3" not in TARGET_SCHEMAS or "repayments" not in TARGET_SCHEMAS:
        raise KeyError("TARGET_SCHEMAS must contain 'loan_v3' and 'repayments'")

    loan_schema = TARGET_SCHEMAS["loan_v3"]
    rep_schema = TARGET_SCHEMAS["repayments"]
    if not loan_schema or not rep_schema:
        logger.warning("TARGET_SCHEMAS entries are empty. Please fill correct headers.")
        return

    changed1, m1 = _migrate_one(
        loan_csv, loan_schema, RENAME_MAPS.get("loan_v3", {}), DEFAULTS.get("loan_v3", {})
    )
    logger.info(m1)
    changed2, m2 = _migrate_one(
        rep_csv, rep_schema, RENAME_MAPS.get("repayments", {}), DEFAULTS.get("repayments", {})
    )
    logger.info(m2)

    if not (changed1 or changed2):
        logger.info("Schema check: no changes. All good.")


if __name__ == "__main__":
    check_or_migrate_schemas()
