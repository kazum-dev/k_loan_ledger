# C-3.5 Test Checklist (事前準備用)

## Dry-run
- [ ] `--dry-run` で実行し、サマリに変換件数が出る
- [ ] `--dry-run --fail-on-warn` で警告がある場合、終了コードが非0になる
- [ ] 監査（data/audit_log.csv）に run_id, options が出力される

## Backup
- [ ] `--no-backup` 未指定でバックアップが作成される（data/loan_v3_YYYYMMDDHHMMSS.bak.csv）
- [ ] `--backup-dir` 指定で保存先を変更できる
- [ ] 失敗時は上書きに進まない

## Method normalize
- [ ] `現金` → `CASH`、`振込` → `BANK_TRANSFER`、その他 → `UNKNOWN`
- [ ] ENUM以外が来たら `UNKNOWN` に落とす

## Expected recalc
- [ ] Decimal + ROUND_HALF_UP で 1円単位
- [ ] 差分がある行のみ更新

## Logs/Audit
- [ ] logs/app.log に INFO で対象/変換/エラー/バックアップ
- [ ] audit に before/after と reason が残る
