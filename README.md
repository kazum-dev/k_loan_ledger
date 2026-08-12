# K's Loan Ledger

K's Loan Ledger は、顧客ごとの貸付・返済状況を管理するためのWebアプリケーションです。

顧客情報、貸付記録、返済記録を一元管理し、未返済額や延滞状況、契約状態などを確認できます。

Python / Flask を使用して開発し、ローカル環境では SQLite、本番環境では Neon PostgreSQL を使用しています。

---

## 主な機能

### ログイン認証

* ユーザー名・パスワードによるログイン
* パスワードのハッシュ化
* セッションによるログイン状態管理
* ログアウト
* 未ログイン時のアクセス制御

### ユーザー別データ管理

* 顧客・貸付・返済データをログインユーザーごとに管理
* 他ユーザーのデータを一覧・集計対象から分離

### 顧客管理

* 顧客登録
* 顧客一覧表示
* 顧客IDによる管理
* 与信限度額の設定

### 貸付管理

* 貸付登録
* 貸付一覧表示
* 貸付IDの自動生成
* 貸付金額
* 貸付日
* 返済期日
* 利率
* 返済予定額
* 返済方法
* 猶予日数
* 延滞手数料率
* 備考
* 契約状態

### 返済管理

* 返済登録
* 返済一覧表示
* 通常返済
* 延滞手数料支払い
* 過剰返済の防止
* 完済済み貸付への通常返済防止
* 契約解除済み貸付への返済防止

### 未返済・延滞管理

貸付データと返済データをもとに、現在の返済状況を自動計算します。

主な表示内容：

* 貸付金額
* 予定返済額
* 返済累計
* 未返済残額
* 延滞日数
* 延滞手数料
* 延滞手数料支払済額
* 延滞手数料残額
* 現在回収額

貸付状態は主に以下へ分類されます。

* 期日内未返済
* 延滞
* 延滞手数料のみ未払い

### 契約解除管理

* 契約解除登録
* 解除理由の記録
* 解除日の記録
* 契約状態一覧
* 契約解除済み一覧
* 契約解除済み貸付への返済防止

### ダッシュボード

Chart.js を使用して貸付・返済状況を可視化します。

主な表示内容：

* 総貸付額
* 総返済額
* 未返済残高
* 延滞件数
* 貸付・返済・未返済額
* 契約状態内訳
* 月別返済額

---

## 技術構成

### Backend

* Python
* Flask
* Flask-SQLAlchemy
* SQLAlchemy
* Gunicorn

### Database

**ローカル環境**

* SQLite

**本番環境**

* PostgreSQL
* Neon

### Frontend

* HTML
* Jinja2
* Chart.js

### Deployment / Development

* Git
* GitHub
* Render
* Visual Studio Code

---

## システム構成

本番環境は以下の構成で動作します。

```text
GitHub
   ↓
Render
   ↓
Flask + Gunicorn
   ↓
Flask-SQLAlchemy / SQLAlchemy
   ↓
Neon PostgreSQL
```

GitHub の `main` ブランチと Render を連携し、アプリケーションをデプロイしています。

---

## データベース構成

主に以下のテーブルを使用します。

### users

ユーザー情報を管理します。

主な項目：

* user_id
* username
* password_hash
* role
* is_active
* created_at
* updated_at

### customers

顧客情報を管理します。

主な項目：

* customer_id
* user_id
* customer_name
* credit_limit
* created_at

### loans

貸付情報を管理します。

主な項目：

* loan_id
* user_id
* customer_id
* loan_amount
* loan_date
* due_date
* interest_rate_percent
* repayment_expected
* repayment_method
* grace_period_days
* late_fee_rate_percent
* late_base_amount
* contract_status
* cancelled_at
* cancel_reason
* notes
* created_at

### repayments

返済情報を管理します。

主な項目：

* repayment_id
* user_id
* loan_id
* customer_id
* repayment_amount
* repayment_date
* payment_type
* created_at

---

## ローカル環境と本番環境

K's Loan Ledger では環境に応じて使用するデータベースを切り替えます。

### ローカル

`DATABASE_URL` が設定されていない場合は SQLite を使用します。

```text
data/loan_ledger.db
```

### 本番

`DATABASE_URL` が設定されている場合は、その接続先の PostgreSQL を使用します。

本番環境では Neon PostgreSQL を使用しています。

これにより、ローカル開発では SQLite を使用しながら、本番環境では PostgreSQL を利用できます。

---

## ローカル起動方法

### 1. リポジトリを取得

```powershell
git clone <repository-url>
cd k_loan_ledger
```

### 2. 仮想環境を作成

Windows PowerShell の例：

```powershell
python -m venv .venv
```

### 3. 仮想環境を有効化

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. 必要なパッケージをインストール

```powershell
python -m pip install -r requirements.txt
```

### 5. 必要な環境変数を設定

ローカルで初期ユーザーを作成する場合は、初期ユーザー用の環境変数を設定します。

例：

```powershell
$env:INITIAL_USERNAME="your_username"
$env:INITIAL_PASSWORD="your_password"
$env:INITIAL_ROLE="ADMIN"
```

必要に応じて `SECRET_KEY` も設定します。

```powershell
$env:SECRET_KEY="your_secret_key"
```

実際の秘密情報はリポジトリへコミットしないでください。

### 6. データベースを初期化

```powershell
python init_db.py
```

SQLite のテーブルが作成され、初期ユーザー用の環境変数が設定されている場合はユーザーも作成されます。

### 7. アプリケーションを起動

```powershell
python app.py
```

起動後、ブラウザからローカルアプリへアクセスします。

```text
http://127.0.0.1:5000
```

---

## 環境変数

K's Loan Ledger では主に以下の環境変数を使用します。

| 環境変数               | 用途                    |
| ------------------ | --------------------- |
| `DATABASE_URL`     | PostgreSQL接続先。本番環境で使用 |
| `SECRET_KEY`       | Flaskのセッション管理に使用      |
| `INITIAL_USERNAME` | 初期ユーザー名               |
| `INITIAL_PASSWORD` | 初期ユーザーのパスワード          |
| `INITIAL_ROLE`     | 初期ユーザーの権限             |

`INITIAL_ROLE` は以下を使用できます。

```text
USER
ADMIN
```

パスワード、SECRET_KEY、DATABASE_URLなどの秘密情報そのものはREADMEやソースコードへ記載しません。

---

## 本番環境

本番環境では Render から Gunicorn を使用して Flask アプリケーションを起動します。

```text
gunicorn app:app
```

データベースには Neon PostgreSQL を使用します。

本番環境では Render 側に必要な環境変数を設定し、秘密情報をGitHubリポジトリへ保存しない構成としています。

---

## エラーハンドリング・入力チェック

本番運用前の整理として、主要なDB更新処理では更新失敗時にロールバックを行う構成としています。

また、登録フォームでは主に以下を確認します。

* 必須入力
* 数値形式
* 0・負数
* 日付形式
* 存在しないID
* 重複ID
* 返済可能額を超える返済
* 貸付日より前の返済日
* 契約解除済み貸付への返済
* 不正な延滞手数料支払い

404 / 500 エラー発生時には、内部エラーの詳細を利用者へ直接表示しないようにしています。

---

## セキュリティ上の注意

以下の情報はGitHubリポジトリへコミットしないようにします。

* データベースのパスワード
* `DATABASE_URL`
* `SECRET_KEY`
* 初期ユーザーのパスワード
* `.env` ファイル
* その他の認証情報

パスワードは平文では保存せず、ハッシュ化してデータベースへ保存します。

---

## 現在のステータス

K's Loan Ledger は、ローカル環境での開発から本番デプロイまでの基本工程を完了しています。

本番環境では以下の構成で動作確認を行っています。

```text
GitHub
→ Render
→ Flask / Gunicorn
→ Neon PostgreSQL
```

ログイン、顧客登録、貸付登録、返済登録、未返済・延滞管理、契約状態管理、ダッシュボード表示までの主要機能を実装しています。

---

## 今後の改善

今後の改善候補として、以下を検討しています。

* CSS導入・UI改善
* 共通テンプレート化
* レスポンシブ対応
* フォームUI改善
* 専用エラーページ
* ログ管理
* 自動テスト強化
* SQLAlchemy関連コードの整理
* データベースマイグレーション導入
* セキュリティ強化
* ユーザー管理機能
* バックアップ方針の整備
* 本番環境の監視
* 独自ドメイン対応

---

## Disclaimer

本アプリケーションは、Python / Flask / SQLAlchemy / PostgreSQL などを使用したWebアプリケーション開発の学習・ポートフォリオを目的として制作しています。