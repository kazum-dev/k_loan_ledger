# tests/test_c4.py
import csv
import json
from datetime import date
import os
import builtins
import types

import pytest

import sys
import modules.loan_module as m
sys.modules["loan_module"] = m

import modules.audit as audit


# ---------- A1: compute_effective_due が負のgraceを0に矯正 ----------
def test_compute_effective_due_clamps_negative_grace():
    d = m.compute_effective_due("2025-10-12", -5)  # マイナスは0に矯正
    assert d.isoformat() == "2025-10-12"


# ---------- A2: A/B/Cケースで is_overdue_with_grace の真偽 ----------
@pytest.mark.parametrize(
    "today_s, due_s, grace, expected",
    [
        # A: 期日+猶予 ちょうどの日は延滞ではない（ > 判定なのでFalse）
        ("2025-10-15", "2025-10-12", 3, False),
        # B: 期日+猶予 を1日超えたら延滞
        ("2025-10-16", "2025-10-12", 3, True),
        # C: 猶予が負でも0として扱う → 2025-10-13 は延滞
        ("2025-10-13", "2025-10-12", -2, True),
    ],
)
def test_is_overdue_with_grace_cases(today_s, due_s, grace, expected):
    today = date.fromisoformat(today_s)
    assert m.is_overdue_with_grace(today, due_s, grace) is expected


# ---------- B1/B2/B3: 監査ログ（ヘッダ/成功時のみ/metaの内容） ----------
def test_audit_log_headers_and_success_only(tmp_path, monkeypatch):
    # 監査ログの出力先をテスト用に差し替え
    audit_path = tmp_path / "audit_log.csv"
    monkeypatch.setattr(audit, "AUDIT_PATH", str(audit_path))

    # 貸付CSV（loan_v3）もテスト用に
    loans_csv = tmp_path / "loan_v3.csv"

    monkeypatch.setattr(
    m,
    "get_project_paths",
    lambda: {"loans_csv": str(loans_csv), "repayments_csv": str(tmp_path / "repayments.csv")},
    )


    # 1) register_loan（成功）→ 監査1行（REGISTER_LOAN）
    m.register_loan(
        customer_id="CUST001",
        amount=1000,
        loan_date="2025-10-01",
        due_date="2025-10-31",
        file_path=str(loans_csv),
    )
    assert audit_path.exists()

    with audit_path.open(encoding="utf-8") as f:
        r = list(csv.DictReader(f))
    #assert [*r[0].keys()] == m.AUDIT_HEADERS  # ヘッダ一致（B1）
    assert [*r[0].keys()] == audit.AUDIT_HEADERS


    assert r[-1]["action"] == "REGISTER_LOAN"  # 成功時のみ追記（B2）
    meta = json.loads(r[-1]["details"])
    assert (
        meta["loan_date"] == "2025-10-01" and meta["due_date"] == "2025-10-31"
    )  # metaチェック（B3）

    # 2) loan_id取得（ファイルから読む）
    with loans_csv.open(encoding="utf-8") as f:
        loans = list(csv.DictReader(f))
    loan_id = loans[-1]["loan_id"]
    assert loan_id.startswith("L20251001-")

    # 3) register_repayment_api（成功）→ 監査追記（REGISTER_REPAYMENT）
    #    予定返済は 1000 の10%上= 1100 なので 500 はOK
    monkeypatch.setenv("TZ", "UTC")  # ただの安定化（任意）
    assert m.register_repayment_api(loan_id=loan_id, customer_id="CUST001", amount=500)

    with audit_path.open(encoding="utf-8") as f:
        r2 = list(csv.DictReader(f))
    assert r2[-1]["action"] == "REGISTER_REPAYMENT"
    meta2 = json.loads(r2[-1]["details"])
    assert meta2["customer_id"] == "CUST001"


# ---------- E2: 監査フック：失敗分岐（過剰返済）は追記されない ----------
def test_register_repayment_overpay_blocks_and_no_audit(tmp_path, monkeypatch):
    # 監査ログ差し替え
    audit_path = tmp_path / "audit.csv"
    monkeypatch.setattr(audit, "AUDIT_PATH", str(audit_path))

    # 貸付CSV
    loans_csv = tmp_path / "loan_v3.csv"
    m.register_loan(
        "CUST001", 1000, "2025-10-01", "2025-10-31", file_path=str(loans_csv)
    )

    # 直近のloan_id
    with loans_csv.open(encoding="utf-8") as f:
        loan_id = list(csv.DictReader(f))[-1]["loan_id"]

    # get_project_paths をモンキーパッチ（API/関数が参照するため）
    monkeypatch.setattr(m, "get_project_paths", lambda: {"loans_csv": str(loans_csv)})

    # いったん監査行数を取得
    if audit_path.exists():
        with audit_path.open(encoding="utf-8") as f:
            before = len(list(csv.DictReader(f)))
    else:
        before = 0

    # 予定返済(1100)を超える 2000 → False & 監査追記なし
    ok = m.register_repayment_api(loan_id=loan_id, customer_id="CUST001", amount=2000)
    assert ok is False

    if audit_path.exists():
        with audit_path.open(encoding="utf-8") as f:
            after = len(list(csv.DictReader(f)))
    else:
        after = 0

    assert after == before  # 失敗時は監査ログに追記されない（B2/E2）


# ---------- E3: inputモックで返済登録の自動テスト ----------
def test_register_repayment_interactive_flow(tmp_path, monkeypatch, capsys):
    # 作業ディレクトリをテスト用に
    monkeypatch.chdir(tmp_path)

    # 監査ログ差し替え & 貸付CSVセットアップ
    audit_path = tmp_path / "audit.csv"
    monkeypatch.setattr(audit, "AUDIT_PATH", str(audit_path))
    loans_csv = tmp_path / "loan_v3.csv"
    m.register_loan(
        "CUST001", 1000, "2025-10-01", "2025-10-31", file_path=str(loans_csv)
    )

    # loan_id
    with loans_csv.open(encoding="utf-8") as f:
        loan_id = list(csv.DictReader(f))[-1]["loan_id"]

    # get_project_paths を貸付CSVに向ける
    monkeypatch.setattr(m, "get_project_paths", lambda: {"loans_csv": str(loans_csv)})

    # 入力モック（loan_id, customer_id(3桁→CUST付与), 金額, 返済日空で=本日）
    inputs = iter([loan_id, "001", "500", ""])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    # 実行
    m.register_repayment()

    # 副作用：repayments.csv が作られている
    rep = tmp_path / "repayments.csv"
    assert rep.exists()
    with rep.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[-1]["customer_id"] == "CUST001"
    assert rows[-1]["repayment_amount"] == "500"
