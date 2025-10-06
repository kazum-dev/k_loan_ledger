# -*- coding: utf-8 -*-
"""
C-4.5 migration: late_base_amount を常に loan_amount(整数) に固定
- backup -> read -> replace -> write
- audit に MIGRATION_C45 を1行追記
"""

# --- ensure project root on sys.path (for 'modules', 'loan_module') ---
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ----------------------------------------------------------------------

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from modules.utils import get_project_paths        # ← modules を使う
from loan_module import append_audit               # ← 監査だけ使えばOK

def _int_from_any(x) -> int:
    try:
        return int(Decimal(str(x)))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"loan_amount を整数化できません: {x!r}")

def run() -> dict:
    paths = get_project_paths()
    loans_csv = str(paths["loans_csv"])

    if not os.path.exists(loans_csv):
        raise FileNotFoundError(f"CSV not found: {loans_csv}")

    # 1) backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = loans_csv.replace(".csv", f"_backup_{ts}.csv")
    with open(loans_csv, "rb") as rf, open(backup, "wb") as wf:
        wf.write(rf.read())

    # 2) read
    with open(loans_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    total = len(rows)
    changed = 0

    # 3) ensure header
    if "late_base_amount" not in fieldnames:
        fieldnames.append("late_base_amount")

    # 4) rewrite rows
    for r in rows:
        principal = _int_from_any(r.get("loan_amount", 0))
        cur = r.get("late_base_amount")
        try:
            cur_int = _int_from_any(cur)
        except Exception:
            cur_int = None
        if cur_int != principal:
            r["late_base_amount"] = str(principal)
            changed += 1
        else:
            r["late_base_amount"] = str(cur_int)

    # 5) write back
    with open(loans_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # 6) audit（個人情報なし）
    meta = {
        "file": os.path.basename(loans_csv),
        "backup": os.path.basename(backup),
        "total_rows": total,
        "updated_rows": changed,
        "policy": "C-4.5 fixed to principal",
    }
    append_audit(
        event="MIGRATION_C45",
        loan_id="-",
        amount=changed,
        meta=meta,
        actor=os.environ.get("USERNAME") or os.environ.get("USER") or "user",
    )

    print(f"[MIGRATION_C45] total={total} updated={changed} backup={backup}")
    return {"total": total, "updated": changed, "backup": backup}

if __name__ == "__main__":
    run()
