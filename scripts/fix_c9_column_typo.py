from __future__ import annotations
import csv
from pathlib import Path

def fix(path: str):
    p = Path(path)
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("[INFO] empty file. nothing to do."); return
    header = [h.lstrip("\ufeff").strip().strip('"') for h in rows[0]]
    body = rows[1:]
    changed = False
    for i, h in enumerate(header):
        if h == "canceled_at":               # ← single-L を
            header[i] = "cancelled_at"       # ← double-L に
            changed = True
    if not changed:
        print("[INFO] header already OK. no changes.")
        return
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)
    print("[OK] renamed header: canceled_at -> cancelled_at")

if __name__ == "__main__":
    fix("data/loan_v3.csv")
