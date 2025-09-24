# C-3.5 事前準備 実装仕様 下書き（2025-09-22）

## 目的
- 既存CSV（loan_v3.csv）を ENUM/丸め規則に統一し、表記ゆれと金額誤差を根絶する。

## 対象
- 入力: data/loan_v3.csv（UTF-8, ヘッダー固定）
- 出力: 上書き保存（--dry-run 時は上書きなし）
- バックアップ: data/loan_v3_YYYYMMDDHHMMSS.bak.csv（--no-backup 指定がない限り常に作成）

## ルール
### repayment_method 正規化
- 許可値（ENUM）: CASH | BANK_TRANSFER | UNKNOWN
- マッピング: data/c35_method_mapping.json を参照
- 不正値 → UNKNOWN（監査に before/after と reason=method_normalized を記録）

### repayment_expected 再計算
- Decimal で計算: expected = loan_amount * (1 + interest_rate_percent/100)
- 丸め: 1円単位 ROUND_HALF_UP
- 既存値と差分がある場合のみ上書き（監査に reason=expected_recalculated を記録）

## CLI 仕様（scripts/migrate_c35.py）
- --csv PATH（既定: data/loan_v3.csv）
- --dry-run（更新なし、サマリ出力と監査のみ）
- --no-backup（バックアップ省略・非推奨）
- --backup-dir PATH（既定: data/）
- --fail-on-warn（警告発生で終了コード≠0）
- --operator NAME（監査用: 既定 CLI_USER）

## ログ/監査
- logs/app.log に INFO でサマリ（対象/変換/スキップ/エラー件数、バックアップパス）
- data/audit_log.csv に以下のカラムで追記：
  - run_id,timestamp,loan_id,field,before,after,reason,options,operator

## 影響範囲メモ
- 未返済残：repayment_expected 改定で差額の可能性
- 過剰返済チェック：expected 減少で over-payment が発生しうる
- 延滞計算：late_base_amount は維持だが、回収総額の算出ロジックに expected を使う場合は要確認

## DoD
- loan_v3.csv の repayment_method が全件 ENUM のみ
- repayment_expected が Decimal + ROUND_HALF_UP + 1円単位で統一
- 変換サマリ（対象/変換/エラー/バックアップパス）が確認できる
