# tests/c1_utils_smoke.py
# C-1（utils.py）入力→出力スモークテスト

from pathlib import Path
from modules.utils import (
    normalize_customer_id,
    normalize_method,
    round_money,
    fmt_currency,
    fmt_date,
    clean_header_if_quoted,
    validate_schema,
    get_project_paths,
)

print("=== 0) パス確認 get_project_paths ===")
paths = get_project_paths()
for k, v in paths.items():
    print(f"{k}: {v}")
print("data/ は存在する？ ->", paths["data"].exists())
print()

print("=== 1) normalize_customer_id ===")
for x in ["", None, "abc99", "001", "CUST12"]:
    print(repr(x), "->", normalize_customer_id(x))
print()

print("=== 2) normalize_method ===")
for x in ["現金", "振込", "bank-transfer", "", None]:
    print(repr(x), "->", normalize_method(x))
print()

print("=== 3) round_money ===")
for x in [123.9, -1.2, "99.9"]:
    print(repr(x), "->", round_money(x))
print()

print("=== 4) fmt_currency ===")
for x in [0, 11000, 11633.33]:
    print(repr(x), "->", fmt_currency(x))
print()

print("=== 5) fmt_date ===")
for x in ["2025/09/01", "2025.09.01", "", None]:
    print(repr(x), "->", fmt_date(x))
print()

print("=== 6) clean_header_if_quoted（実ファイルで検証） ===")
data_dir = paths["data"]
quoted_csv = data_dir / "quoted_headers_demo.csv"
# ヘッダだけ "で囲われたCSVを作成
quoted_csv.write_text('"loan_id","amount"\n"001","1000"\n', encoding="utf-8")
print("作成:", quoted_csv)
print("実行:", clean_header_if_quoted(quoted_csv))
print("ヘッダ行（after）:", quoted_csv.read_text(encoding="utf-8").splitlines()[0])
print()

print("=== 7) validate_schema（不足列が出せるか） ===")
schema_bad = data_dir / "schema_bad_demo.csv"
schema_bad.write_text("loan,amt\n001,1000\n", encoding="utf-8-sig")  # BOM付きで作成
required = {"loan_id", "amount"}
ok = validate_schema(schema_bad, required)
print(
    "validate_schema result:",
    ok,
    "(False になり、足りない列名が上で print されていればOK)",
)
print()

print("=== 8) get_project_paths 実在確認 ===")
print("loans_csv ->", paths["loans_csv"], "exists?", paths["loans_csv"].exists())
print(
    "repayments_csv ->",
    paths["repayments_csv"],
    "exists?",
    paths["repayments_csv"].exists(),
)
print()

print("--- 完了：上の入出力を見て、挙動イメージを掴もう ---")
