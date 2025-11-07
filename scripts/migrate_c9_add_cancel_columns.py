# scripts/migrate_c9_add_cancel_columns.py
from __future__ import annotations
import argparse, csv, shutil
from pathlib import Path

NEW_COLS = ["contract_status", "canceled_at", "cancel_reason"]

def migrate(path_in: str, path_out: str|None=None) -> None:
    p_in = Path(path_in)
    if not p_in.exists():
        raise SystemExit(f"[ERROR] not found: {p_in}")
    p_out = Path(path_out) if path_out else p_in

    # 読み込み
    with p_in.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        # 空ファイルはそのまま列ヘッダだけ作る
        with p_out.open("w", newline="", encoding="itf-8") as f:
            w = csv.writer(f)
            w.writerow(NEW_COLS) # 最低限
        print("[INFO] empty file → header initialized with C-9 columns only")
        return
    
    header = [h.lstrip("\ufeff").strip().strip('"') for h in rows[0]]
    body = rows[1:]

    # 既存に不足する列を末尾に追加
    missing = [c for c in NEW_COLS if c not in header]
    if not missing:
        if p_out != p_in:
            shutil.copyfile(p_in, p_out)
        print("[INFO] already migrated. no changes.")
        return
    
    new_header = header + missing

    # 既存行にデフォルト値を付与
    idx = {name:i for i,name in enumerate(new_header)}
    def _pad(row):
        r = row + [""]*(len(new_header)-len(row))
        if "contract_status" in missing:
            r[idx["contract_status"]] = "ACTIVE"
        if "cancelled_at" in missing:
            r[idx["cancelled_at"]] = ""
        if "cancel_reason" in missing:
            r[idx["cancel_reason"]] = ""
        return r
    
    new_body = [_pad(r) for r in body]

    # 書き戻し
    with p_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(new_header)
        w.writerows(new_body)

    print(f"[OK] migrated -> {p_out} (+{','.join(missing)})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", default=None)
    args = ap.parse_args()
    migrate(args.in_path, args.out_path)