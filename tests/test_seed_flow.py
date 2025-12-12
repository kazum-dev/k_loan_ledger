# tests/test_seed_flow.py
from __future__ import annotations
import subprocess, sys, shutil, csv
from pathlib import Path

def run_ok(cmd: list[str], cwd: Path | None = None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)

def test_seed_then_summary(tmp_path: Path):
    proj = tmp_path
    # 必要ファイルをコピー
    for p in ["seed_demo_data.py", "main.py", "modules/utils.py", "modules/__init__.py"]:
        dst = proj / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)

    py = sys.executable
    # 1) seed --force （ルート指定でdata配下に生成）
    out = run_ok([py, str(proj / "seed_demo_data.py"), "--force", "--root", str(proj)])
    assert "== Seed Summary ==" in out.stdout

    # 2) main --summary（件数が表示される）
    out2 = run_ok([py, str(proj / "main.py"), "--summary"], cwd=proj)
    assert "[summary] loans:" in out2.stdout
    assert "repayments:" in out2.stdout


    # 3) CSVの存在とヘッダ簡易確認
    loans_csv = proj / "data" / "loan_v3.csv"
    reps_csv  = proj / "data" / "repayments.csv"
    assert loans_csv.exists() and reps_csv.exists()
    with loans_csv.open("r", newline="", encoding="utf-8-sig") as f:
        hdr = next(csv.reader(f))
    assert "loan_id" in hdr and "repayment_expected" in hdr
