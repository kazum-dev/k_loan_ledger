# schmea_migrator.py
from __future__ import annotations
import csv
import shutil
import time
from pathlib import Path
from typing import Dict, List, Tuple

# 既存ロガー／パス取得を利用
from modules.logger import get_logger
from modules.utils import get_project_paths

logger = get_logger("schema_migrator")

TARGET_SCHEMAS: Dict[str, List[str]] = {
    "loan_v3.csv": [
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
    ],
    "repayments": [
        "loan_id",
        "customer_id",
        "repayment_amount",
        "repayment_date",
    ],
}

# 旧→新の自動リネーム（遭遇確率が高そうな別名を保険で）
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
        "amount": "reapynment_amount",
        "paid_at": "repayment_date",
        "reapymentAt": "repayment_date",
    },
}

# 新規追加のカラムのデフォルト
DEFAULTS: Dict[str, Dict[str, str]] = {
    "loan_v3.csv": {
        "grace_period_days": "0",
        "late_fee_rate_percent": "0",
        "late_base_amount": "", 
    },
    "repayments": {},
}

ENABLE_BACKUP = True  # *.back.YYYYMMDD_HHMMSS を data/ 配下に作成


# ========== 内部ユーティリティ ==========
def timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _backup_file(src: Path) -> None:
    if not ENABLE_BACKUP or not src.exists():
        return
    dst = src.with_suffix(src.suffix + f".bak.{_timestamp()}")
    shutil.copy2(src, dst)
    logger.info(f"Backup: {src.name} -> {dst.name}")


def _read_header(csv_path: Path) -> List[str]:
    # BOM対策 utf-8-sig
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            header = []
    # 余計な引用符や空白をトリム
    return [h.strip().strip('"').strip("'") for h in header]


def _write_header_and_passthrough_body(
    src: Path,
    dst: Path,
    new_header: List[str],
    rename_map: Dict[str, str],
    default: Dict[str, str],
) -> None:
    # 読み込みは utf-8、書き出しは utf-8 に正規化
    with src.open("r", newline="", encoding="utf-8-sig") as rf, dst.open(
        "w", newline="", encoding="utf-8"
    ) as wf:
        reader = csv.DictReader(rf)
        # 旧名→新名へキーを寄せる
        mormalized_rows = []
        for row in reader:
            rorm = {}
            for k, v in row.items():
                k2 = rename_map.get(k, k)
                rorm[k2] = v
            normalized_rows.append(norm)

        writer = csv.DictWriter(wf, fieldnames=new_header, extrasaction="ignore")
        writer.writeheader()
        
        for nr in normalized_rows:
            out = {}
            for col in new_header:
                val = nr.get(col, "")
                out[col] = val if (val is not None and val != "") else defaults.get(col, "")
            writer.writerow(out)


def _migrate_one(
        csv_path: Path, target_header: List[str], rename_map: Dict[str, str], defaults: Dict[str, str]
) -> Tuple[bool, str]:
    if not csv_path.exists():
        return False, f"SKIP (not found): {csv_path.name}"
    
    current = _read_header(csv_path)
    if not current:
        # 空ファイル → ヘッダ初期化だけ行う
        _backup_file(csv_path)
        tmp = csv_path.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as wf:
            csv.writer(wf).writerow(target_header)
        tmp.replace(csv_path)
        return True, f"INIT header written: {csv_path.name}"
    
    logical_current = [rename_map.get(c, c) for c in current]

    missing = [c for c in target_header if c not in logical_current]
    extras = [c for c in logical_current if c not in target_header]
    order_diff = logical_current != target_header

    need = bool(missing or extras or order_diff or (logical_current != current))
    if not need:
        return False, f"OK (already up-to-date): {csv_path.name}"
    
    _backup_file(csv_path)
    tmp = csv_path.with_suffix(".tmp")
    # 余剰列はいったん末尾に退避
    new_header = target_header + extras
    _write_header_and_passthrough_body(
        src=csv_path, dst=tmp, new_header=new_header, rename_map=rename_map, defaults=defaults
    )
    tmp.replace(csv_path)

    detail = []
    if missing:
        detail.append(f"+{missing}")
    if extras:
        detail.append(f"extras->{extras}")
    if order_diff:
        detail.append("reordered")
    if logical_current != current:
        detail.append("renamed")
    return True, f"FIXED {csv_path.name}: " + ", ".join(detail)


# ========== 公開エントリポイント ==========
def check_or_migrate_schemas() -> None:
    """
    アプリ起動時に必ず呼ぶ。欠落/旧名/順序ズレを無停止で自己修復。
    """ 
    paths = get_project_paths()
    data_dir = paths["data"]
    loan_csv = paths["loans_csv"]
    rep_csv = paths["repayments_csv"]

    loan_schema = TARGET_SCHEMAS["loan_v3"]
    rep_schema = TARGET_SCHEMAS["repayments"]
    loan_rename = RENAME_MAPS.get("loan_v3", {})
    rep_rename = RENAME_MAPS.get("repayments", {})
    loan_defaults = DEFAULTS.get("loan_v3", {})
    rep_defaults = DEFAULTS.get("repayments", {})

    # ディレクトリがなければ生成だけして終了（初回起動想定）
    data_dir.mkdir(parents=True, exist_ok=True)

    ch1, m1 = _migrate_one(loan_csv, loan_schema, loan_rename, loan_defaults)
    logger.info(m1)
    ch2, m2 = _migrate_one(rep_csv, rep_schema, rep_rename, rep_defaults)
    logger.info(m2)

    if not (ch1 or ch2):
        logger.info("schema check: no changes. All good")


if __name__== "__main__":
    check_or_migrate_schemas()
