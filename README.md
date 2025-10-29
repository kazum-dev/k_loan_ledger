# K's Loan Ledger

💼 個人向けの簡易貸付管理CLIアプリ
紙の借用書をもとに、貸付・返済・残高をCSVで記録・照会できます。

---

## 🔧 使用技術
- Python（標準ライブラリのみ使用）
- CSVファイル保存
- コマンドライン操作（CLI）

---

## 📦 現在の機能（2025年5月19日時点）
- 顧客ごとの貸付記録
- 返済記録と履歴の表示
- 残高照会（貸付-返済）
- 顧客IDの補正処理

---

## ▶ 使用方法（CLI版）

1. このプロジェクトをローカルに保存
2. ターミナルで以下を実行

```bash
python main.py
```

## C-7.5 フィクスチャ生成 & 再現手順
```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/seed_demo_data.py --force
python -m unittest discover -s tests -p "test_*.py" -v
python main.py
```
Seed Summary（実行例）
```diff
== Seed Summary ==
loans: 3 rows, repayments: 1 rows
- L20250830-001 (CUST001): expected=20000, paid=0, balance=20000
- L20251024-001 (CUST001): expected=10000, paid=0, balance=10000
- L20250919-001 (CUST002): expected=16000, paid=16000, balance=0
```
# デモ期待出力（抜粋）
・延滞表示（10 → CUST001）
```csharp
[OVERDUE] L20250830-001 ... 延滞日数：30日｜延滞手数料：¥1,000｜回収額：¥21,000
🧮 件数：1件|残高合計：¥20,000
```
・未返済サマリー（9 → CUST001）
```csharp
内訳：延滞 1 件 / 期日内 1 件
🧮 件数：2件|残高合計：¥30,000
```
・残高照会（5 →　CUST001/002）
```markfile
CUST001: 貸付総額 ¥30,000 / 返済総額 ¥0 / 残高 ¥30,000
CUST002: 貸付総額 ¥16,000 / 返済総額 ¥16,000 / 残高 ¥0
```
