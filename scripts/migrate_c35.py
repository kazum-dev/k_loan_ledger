#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C-3.5 Migration Script
- Normalize repayment_method to ENUM
- Recalculate repayment_expected with Decimal ROUND_HALF_UP
- Backup original CSV
- Dry-run support
"""

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime, timezone
import sys
import json

# 追加（ファイル先頭の imports 付近に）
from pathlib import Path
from datetime import datetime, timezone
import csv as _csv  # 既存の csv と衝突しないよう別名でもOK

def append_local_migration_audit(run_id: str, loan_id: str, field: str, before, after, reason: str, options: str, operator: str):
    """
    Always write C-3.5 audit to data/migration_audit.csv (project-local)
    regardless of project-specific audit module behavior.
    """
    out = Path("data") / "migration_audit.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = ["run_id","timestamp","loan_id","field","before","after","reason","options","operator"]
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    write_header = not out.exists()
    with out.open("a", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow([run_id, ts, loan_id, field, before, after, reason, options, operator])

# Optional imports for project logger/audit; fallback to stdout if not found
try:
    from modules.logger import get_logger  # type: ignore
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    def get_logger():
        return logging.getLogger("migrate_c35")

try:
    from modules.audit import append_audit  # type: ignore
except Exception:
    def append_audit(*args, **kwargs):
        # Fallback: no-op
        pass

logger = get_logger()

@dataclass
class Counters:
    total: int = 0
    method_changed: int = 0
    expected_changed: int = 0
    warnings: int = 0
    errors: int = 0

def load_mapping(mapping_path: Path):
    if not mapping_path.exists():
        logger.warning(f"Mapping file not found: {mapping_path} (will use defaults)")
        # Minimal default mapping
        return {
            "現金": "CASH",
            "げんきん": "CASH",
            "振込": "BANK_TRANSFER",
            "ふりこみ": "BANK_TRANSFER",
            "CASH": "CASH",
            "BANK_TRANSFER": "BANK_TRANSFER",
            "UNKNOWN": "UNKNOWN",
            "": "UNKNOWN",
            "空": "UNKNOWN",
            "未設定": "UNKNOWN",
            "不明": "UNKNOWN",
        }
    with mapping_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def normalize_method(value: str, mapping: dict) -> str:
    if value is None:
        return "UNKNOWN"
    v = str(value).strip()
    if v in mapping:
        return mapping[v]
    # Heuristic: ASCII words to UPPER; otherwise UNKNOWN
    return v.upper() if v.isascii() and v.upper() in {"CASH", "BANK_TRANSFER", "UNKNOWN"} else "UNKNOWN"

def recalc_expected(principal: str, rate_percent: str) -> int:
    p = Decimal(str(principal))
    r = (Decimal(str(rate_percent)) / Decimal("100"))
    expected = p * (Decimal("1") + r)
    return int(expected.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def backup_csv(csv_path: Path, backup_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d%H%M%S")
    backup_path = backup_dir / f"{csv_path.stem}_{ts}.bak{csv_path.suffix}"
    backup_path.write_bytes(csv_path.read_bytes())
    return backup_path

def append_audit_row(run_id: str, loan_id: str, field: str, before, after, reason: str, options: str, operator: str):
    try:
        append_audit(run_id=run_id, loan_id=loan_id, field=field, before=before, after=after, reason=reason, options=options, operator=operator)
    except TypeError:
        # Fallback: write to CSV in data/audit_log.csv
        out = Path("data") / "audit_log.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        header = ["run_id","timestamp","loan_id","field","before","after","reason","options","operator"]
        ts = datetime.now(timezone.utc).astimezone().isoformat()
        new_line = [run_id, ts, loan_id, field, str(before), str(after), reason, options, operator]
        write_header = not out.exists()
        with out.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow(new_line)

def migrate(csv_path: Path, dry_run: bool, no_backup: bool, backup_dir: Path, fail_on_warn: bool, operator: str, mapping_path: Path) -> int:
    counters = Counters()
    run_id = datetime.now(timezone.utc).astimezone().strftime("C35RUN-%Y%m%d-%H%M%S")
    options = f"dry_run={dry_run}, no_backup={no_backup}, backup_dir={backup_dir}"

    if not csv_path.exists():
        logger.error(f"CSV not found: {csv_path}")
        return 2

    mapping = load_mapping(mapping_path)

    # Read CSV
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    required = {"loan_id","loan_amount","interest_rate_percent","repayment_expected","repayment_method"}
    missing = required - set(fieldnames)
    if missing:
        logger.error(f"Missing required columns: {missing}")
        return 2

    # Backup
    backup_path = None
    if not dry_run and not no_backup:
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_csv(csv_path, backup_dir)

    # Process rows
    for row in rows:
        counters.total += 1
        loan_id = row.get("loan_id","")

        # Method normalize
        before_m = row["repayment_method"]
        after_m = normalize_method(before_m, mapping)

        if after_m not in {"CASH","BANK_TRANSFER","UNKNOWN"}:
            # Shouldn't happen, but guard
            counters.warnings += 1
            after_m = "UNKNOWN"

        if after_m != before_m:
            counters.method_changed += 1
            append_audit_row(run_id, loan_id, "repayment_method", before_m, after_m, 
                             "method_normalized", options, operator)
            append_audit_row(run_id, loan_id, "repayment_method", before_m, after_m, 
                             "method_normalized", options, operator)
            append_local_migration_audit(run_id, loan_id, "repayment_method", before_m, after_m, 
                                         "method_normalized", options, operator)
            row["repayment_method"] = after_m

        # Expected recalc
        
        new_expected = recalc_expected(row["loan_amount"], row["interest_rate_percent"])

        before_e = row["repayment_expected"]
        try:
            before_e_int = int(before_e)
        except Exception:
            counters.warnings += 1
            before_e_int = new_expected

        if new_expected != before_e_int:
            counters.expected_changed += 1
            append_audit_row(run_id, loan_id, "repayment_expected", before_e, new_expected, 
                             "expected_recalculated", options, operator)
            append_local_migration_audit(run_id, loan_id, "repayment_expected", before_e, new_expected, 
                                         "expected_recalculated", options, operator)
            row["repayment_expected"] = str(new_expected)
        
    # Write CSV
    if not dry_run:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    logger.info(f"[C-3.5] total={counters.total} method_changed={counters.method_changed} expected_changed={counters.expected_changed} warnings={counters.warnings} errors={counters.errors} backup={backup_path}")
    if fail_on_warn and (counters.warnings > 0 or counters.errors > 0):
        return 3
    return 0

def main():
    p = argparse.ArgumentParser(description="C-3.5 Migration")
    p.add_argument("--csv", default="data/loan_v3.csv")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--backup-dir", default="data/")
    p.add_argument("--fail-on-warn", action="store_true")
    p.add_argument("--operator", default="CLI_USER")
    p.add_argument("--mapping", default="data/c35_method_mapping.json")
    args = p.parse_args()

    csv_path = Path(args.csv)
    backup_dir = Path(args.backup_dir)
    mapping_path = Path(args.mapping)

    code = migrate(csv_path, args.dry_run, args.no_backup, backup_dir, args.fail_on_warn, args.operator, mapping_path)
    sys.exit(code)

if __name__ == "__main__":
    main()
