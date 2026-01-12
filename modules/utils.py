# modules/utils.py
from __future__ import annotations

import csv
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, Union

# ======================
# 正規化
# ======================

_CUST_PATTERN = re.compile(r"^(?:CUST)?0*([0-9]{1,})$", re.IGNORECASE)


def normalize_customer_id(s: Union[str, int, None]) -> str:
    """
    入力例: "1", "001", "CUST1", "CUST001", 1 -> "CUST001"
    数字が含まれない場合は "CUST000" を返す。
    """
    if s is None:
        return "CUST000"
    text = str(s).strip()
    m = _CUST_PATTERN.match(text)
    if not m:
        digits = re.sub(r"\D", "", text)
        if digits == "":
            return "CUST000"
        n = int(digits)
    else:
        n = int(m.group(1))
    return f"CUST{n:03d}"


_METHOD_MAP = {
    # 英語
    "cash": "CASH",
    "bank_transfer": "BANK_TRANSFER",
    "bank": "BANK_TRANSFER",
    "transfer": "BANK_TRANSFER",
    "other": "OTHER",
    "unknown": "UNKNOWN",
    # 日本語
    "現金": "CASH",
    "振込": "BANK_TRANSFER",
    "銀行振込": "BANK_TRANSFER",
    "その他": "OTHER",
    "未設定": "UNKNOWN",
    "不明": "UNKNOWN",
}


def normalize_method(s: Optional[str]) -> str:
    """
    支払い方法を標準化: CASH / BANK_TRANSFER / OTHER / UNKNOWN
    """
    if not s:
        return "UNKNOWN"
    key = str(s).strip()
    if key in _METHOD_MAP:  # 日本語を含む完全一致
        return _METHOD_MAP[key]
    key2 = key.lower().replace(" ", "_").replace("-", "_")
    return _METHOD_MAP.get(key2, "UNKNOWN")


# ======================
# 金額・日付の整形
# ======================


def round_money(x: Union[int, float, str, None]) -> int:
    """
    円未満切り捨て。負数も floor(-1.2 -> -2) 。
    """
    try:
        val = float(x)
    except (TypeError, ValueError):
        return 0
    return int(math.floor(val))


def fmt_currency(n: Union[int, float, str, None]) -> str:
    """
    "¥12,345" 形式。内部でround_money を通す。
    """
    yen = round_money(n)
    return f"¥{yen:,}"


def fmt_date(d: Union[str, date, datetime, None]) -> Optional[str]:
    """
    入力：datetime/date/文字列("YYYY-MM-DD" or "YYYY/MM/DD" 等)
    返却："YYYY-MM-DD" or None
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    s = str(d).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    s2 = re.sub(r"[./]", "-", s)
    try:
        return datetime.strptime(s2, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None
    
# ======================
# 入力ヘルパー（D-3）
# ======================

def prompt_int(
        prompt: str,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        default: int | None = None,
) -> int:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            n = int(raw)
        except ValueError:
            print("❌ 金額/日数は整数で入力してください。")
            continue

        if min_value is not None and n < min_value:
            print(f"❌ {min_value}以上で入力してください。")
            continue
        if max_value is not None and n > max_value:
            print(f"⚠ 上限({max_value})を超えています。別の値を入力してください。")
            continue
        return n
    
def prompt_float(
        prompt: str,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        default: float | None = None,
        round_to: int | None = None,
) -> float:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            val = float(default)
            return round(val, round_to) if round_to is not None else val
        
        try:
            x = float(raw)
        except ValueError:
            print("❌ 数値で入力してください。")
            continue

        if min_value is not None and x < min_value:
            print(f"❌ {min_value}以上で入力してください。")
            continue
        if max_value is not None and x > max_value:
            print(f"⚠ {max_value}以下で入力してください。")
            continue

        return round(x, round_to) if round_to is not None else x
    
def prompt_date_or_today(prompt: str, *, today: date | None = None) -> str:
    """
    - 空Enter: today (未指定なら今日) を YYYY-MM-DD で返す
    - 入力あり: fmt_date で正規化し、存在日付チェックも通す
    """
    base = today or date.today()
    while True:
        s = input(prompt).strip()
        if not s:
            today_str = base.isoformat()
            print(f"[INFO] 日付を本日に自動設定しました: {today_str}")
            return today_str
        
        normalized = fmt_date(s)
        if not normalized:
            print("❌ 日付は YYYY-MM-DD 形式で入力してください（例：2025-05-05）。")
            continue

        try:
            datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            print("❌ 存在しない日付です。正しい日付を入力してください。")
            continue

        return normalized
    
def prompt_customer_id(
        prompt: str,
        *,
        valid_ids: Set[str] | None = None,
) -> str:
    while True:
        raw = input(prompt).strip()
        cust = normalize_customer_id(raw)

        if cust == "CUST000":
            print("❌ 顧客IDが不正です（数字を含めて入力してください）。")
            continue

        if valid_ids is not None and cust not in valid_ids:
            print("❌ 顧客IDが存在しません。先に顧客登録を行ってください。")
            continue

        return cust
    
def prompt_method(prompt: str) -> str:
    raw = input(prompt).strip()
    method = normalize_method(raw)
    if method == "UNKNOWN":
        print("⚠ 返済方法が特定できないため UNKNOWN として登録します。")
    return method
        


# =======================
# CSV ヘッダ補正 ＆ スキーマ検証
# =======================


def clean_header_if_quoted(path: Union[str, Path]) -> bool:
    """
    先頭行(ヘッダ)の各カラムが "xxx" で囲まれている場合だけ外して上書き。
    データ行は変更しない。変更したら True。
    """
    p = Path(path)
    if not p.exists():
        return False

    # 1) 読み込みは r（読み取り専用）
    with p.open("r", newline="", encoding="utf-8") as f:
        first_line = f.readline()
        rest = f.read()

    raw_cols = [c.strip() for c in first_line.rstrip("\n\r").split(",")]

    def _strip_quotes(s: str) -> Tuple[str, bool]:
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1], True
        return s, False

    stripped, changed_any = [], False
    for c in raw_cols:
        s, ch = _strip_quotes(c)
        stripped.append(s)
        changed_any = changed_any or ch

    if not changed_any:
        return False

    # 2) 書き戻しは w（上書き）
    with p.open("w", newline="", encoding="utf-8") as f:
        f.write(",".join(stripped) + "\n")
        f.write(rest)

    return True


def validate_schema(path: Union[str, Path], required_cols: Set[str]) -> bool:
    """
    CSV の1行目(ヘッダ)が required_cols を包含しているか確認。
    BOM(\ufeff)や "col" 形式の引用符にも体制を持たせる。
    True=OK / False=不足あり（不足は print で通知）。
    """
    p = Path(path)
    if not p.exists():
        print(f"[validate_schema] file not found: {p}")
        return False

    # BOM を除去するため utf-8-sig で読む
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        first_line = ""
        while first_line == "":
            first_line = f.readline()
            if not first_line:
                print(f"[validate_schema] empty file: {p}")
                return False

    # カンマ分割 → 余分な空白/引用符/BOMの残りを除去
    raw_cols = [c.strip() for c in first_line.rstrip("\n\r").split(",")]

    def _normalize_col(name: str) -> str:
        # 先頭末尾の二重引用符を外す
        if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
            name = name[1:-1]
        # 万一残っているBOMを除去
        return name.lstrip("\ufeff").strip()

    header_set = {_normalize_col(h) for h in raw_cols}
    missing = sorted(list(required_cols - header_set))
    if missing:
        print(f"[validate_schema] missing columns in {p.name}:{missing}")
        return False
    return True


# =======================
# パス取得（loan_v3.csv 優先検出）
# =======================


def get_project_paths(root_hint: Optional[Union[str, Path]] = None) -> Dict[str, Path]:
    """
    代表的なパスを返す。data 直下に CSV がある想定。
    既存の loan_v3.csv があればそれを最優先で採用。
    無ければ loans.csv をデフォルト名として返す。
    """

    def _discover_root() -> Path:
        if root_hint:
            return Path(root_hint).resolve()
        here = Path.cwd().resolve()
        for base in [here, *here.parents]:
            if (base / "modules").is_dir():
                return base
        return here

    root = _discover_root()
    modules_dir = root / "modules"
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    candidate_loans = [
        data_dir / "loan_v3.csv",  # 既存命名
        data_dir / "loans.csv",  # 新規標準
    ]
    loans_csv = next((p for p in candidate_loans if p.exists()), candidate_loans[0])

    repayments_csv = data_dir / "repayments.csv"

    return {
        "root": root,
        "modules": modules_dir,
        "data": data_dir,
        "loans_csv": loans_csv,
        "repayments_csv": repayments_csv,
    }


# ======================
#  簡易セルフテスト
# 　=====================


def _selfcheck() -> None:
    assert normalize_customer_id("1") == "CUST001"
    assert normalize_customer_id("CUST12") == "CUST012"
    assert normalize_customer_id("abc99") == "CUST099"
    assert normalize_method("現金") == "CASH"
    assert normalize_method("bank-transfer") == "BANK_TRANSFER"
    assert normalize_method(None) == "UNKNOWN"
    assert round_money(-1.2) == -2
    assert fmt_currency(1234567.89) == "¥1,234,567"
    assert fmt_date("2025/09/01") == "2025-09-01"


if __name__ == "__main__":
    _selfcheck()
    print("[utils] selfcheck OK")
