# K’s Loan Ledger — CSVベースの貸付管理CLI

ローカルCSVで 貸付 / 返済 / 延滞 を管理する、学習兼ポートフォリオ用のミニCLIツール。

- OS: Windows 11 / PowerShell

- Python: 3.13.3

- テスト: pytest（22 passed）



\## TL;DR（最短クイックスタート）



```powershell

# 1) 取得

git clone <YOUR\_REPO\_URL>

cd <YOUR\_REPO\_DIR>



# 2) 仮想環境

python -m venv .venv

. .\\.venv\\Scripts\\Activate.ps1



# 3) 依存

pip install -r requirements.txt



# 4) （任意）デモデータ投入

# ある場合のみ: python .\\scripts\\seed\_demo\_data.py



# 5) 実行

python .\\main.py

```



備考: 初回で requirements.txt が無い場合は



pip install pytest → pip freeze > requirements.txt で生成できます。



\## 背景（開発意図・位置づけ）

- 紙の借用書の運用をコード化し、未返済/延滞/回収額 を明確化。

- 学習用ポートフォリオだが、実務で使える 再現性・軽さ・オフライン を重視。



\## 機能ハイライト

- 貸付登録：loan\_id 自動付与、due\_date ほか主要項目の記録

- 返済登録：分割返済対応、過剰返済ガード（B-11.1）

- 一覧/サマリー：未返済サマリー、延滞のみ抽出

- 延滞計算：grace\_period\_days / late\_fee\_rate\_percent 等の設定に基づく

- 残高照会：貸付・返済からの計算サマリー

- テスト：スモーク＋ユニットで振る舞いを担保（tests/ 参照）



\## メニュー（python main.py 実行時）



```text

1: 貸付記録モード

2: 貸付履歴表示モード

3: 返済記録モード

4: 返済履歴表示モード

5: 残高照会モード

9: 未返済サマリー表示（テスト用）

10: 延滞貸付表示モード

0: 終了

```



\## ファイル構成（抜粋）

```text

<repo>/

&nbsp; main.py

&nbsp; modules/

&nbsp;   loan\_module.py

&nbsp;   ...（他のモジュール）

&nbsp; scripts/

&nbsp;   seed\_demo\_data.py

&nbsp; data/

&nbsp;   loans.csv

&nbsp;   repayments.csv

&nbsp; tests/

&nbsp;   fixtures/

&nbsp;   audit\_test.py

&nbsp;   c1\_loan\_smoke.py

&nbsp;   c1\_utils\_smoke.py

&nbsp;   check\_loans\_csv\_schema.py

&nbsp;   list\_test.py

&nbsp;   repay\_audit\_test.py

&nbsp;   smoke\_c4.py

&nbsp;   test\_balance.py

&nbsp;   test\_c4.py

&nbsp;   test\_c5.py

&nbsp;   test\_enum\_round.py

&nbsp;   test\_late\_fee.py

&nbsp;   test\_overpayment.py

&nbsp;   test\_seed\_flow.py

&nbsp;   ...（他）

&nbsp; requirements.txt

```



\## セットアップ（詳細）



```powershell

python -m venv .venv

. .\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

```



実行ポリシーで怒られたら一時的に：



```powershell

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

. .\\.venv\\Scripts\\Activate.ps1

```



\## 使い方（CLI版）

基本



```powershell

python .\\main.py

```

よく使う操作

- 未返済サマリー（テスト用）：メニューで \[9]

- 延滞のみ表示：メニューで \[10]

- 返済登録：メニューで \[3] → loan\_id / 返済額 / 日付 を入力

- 残高照会：メニューで \[5]

将来的にサブコマンド直叩き（例：python main.py add\_loan ...）を実装したら追記予定。



\## テスト（pytest）

```powershell

pytest -q

# 詳細/絞り込み

pytest -q --maxfail=1 -k <keyword>

```

- 期待結果：22 passed

- 主な観点：

&nbsp;   - CSVスキーマ整合（check\_loans\_csv\_schema.py）

&nbsp;   - 延滞手数料（test\_late\_fee.py）

&nbsp;   - 過剰返済ガード（test\_overpayment.py）

&nbsp;   - 残高計算（test\_balance.py）

&nbsp;   - シード/スモーク（test\_seed\_flow.py, smoke\_c4.py ほか）



\## スクリーンショット / 出力例



\### 画面イメージ

- メニュー画面  

&nbsp; !\[Menu](docs/images/menu.png)

- 未返済サマリー（メニュー \[9]）  

&nbsp; !\[Unpaid Summary](docs/images/unpaid\_summary.png)

- 延滞一覧（メニュー \[10]）  

&nbsp; !\[Overdue List](docs/images/overdue\_list.png)



\### テキスト出力例

```text

\[UNPAID] loan\_id=LN-001, principal=10000, due=2025-11-15, status=OVERDUE(+3d), late\_fee=300

\[UNPAID] loan\_id=LN-002, principal=8000,  due=2025-11-20, status=DUE(–2d),   late\_fee=0

```



```text

\[REPAYMENT ADDED] loan\_id=LN-001, amount=5000, date=2025-11-05

\[REPAYMENT TOTAL] paid=5000 / expected=11000 → remaining=6000

```



\### 返済登録後の計算例



```text

\[REPAYMENT ADDED] loan\_id=LN-001, amount=5000, date=2025-11-05

\[REPAYMENT TOTAL] paid=5000 / expected=11000 → remaining=6000

```



画像版スクショは docs/images/ などに配置して README から参照。



データと注意点

- 保存：data/\*.csv（UTF-8）

- バックアップ推奨：data/ は .gitignore で除外し、.gitkeep でディレクトリ維持

- 同時編集注意：Excel等で同時開きは不可（排他制御なし）


