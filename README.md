# 授業用ノートサービス（プロトタイプ）

最小のFlaskアプリケーション。生徒は登録してノートを作成/編集/削除できます。

セットアップ:

```bash
# 授業用ノートサービス（世界史向け・プロトタイプ）

軽量なFlaskアプリ。世界史の授業用ノートを素早く作成・整理できます。

セットアップ

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

起動時に `notes.db` が存在しない場合は `schema.sql` に従って初期化されます。既存の `notes.db` がある場合はバックアップが作成されます。

主要機能

- ユーザー登録 / ログイン（Flask-Login）
自動運用（共有リンクの期限切れ自動取り消し）

1) 毎日期限切れ共有リンクを無効化するには、作成した `scripts/cleanup_expired_shares.py` を systemd タイマーや cron で実行します。例（systemd）:

```bash
# コピーして有効化の例
cp deploy/cleanup_expired_shares.service.example /etc/systemd/system/cleanup_expired_shares.service
cp deploy/cleanup_expired_shares.timer.example /etc/systemd/system/cleanup_expired_shares.timer
systemctl daemon-reload
systemctl enable --now cleanup_expired_shares.timer
```

または cron 例:

```cron
0 3 * * * /home/omoto/デスクトップ/tst/venv/bin/python3 /home/omoto/デスクトップ/tst/scripts/cleanup_expired_shares.py /home/omoto/デスクトップ/tst/notes.db >> /var/log/tst_cleanup.log 2>&1
```

2) Gitでのコミット例:

```bash
git add .
git commit -m "Add world-history features, sharing, cleanup scripts and deploy examples"
git push origin main
```

- ノート作成 / 編集 / 削除
- 世界史メタデータ：期（period）/地域（region）/タグ
- 複数のノート雛形（年表、出来事カード、主要人物）
- キーワード・期・地域・タグでの検索／フィルタ
- 簡易Markdown風プレビューと自動保存（編集時に数秒でサーバーに保存）
- ノートのエクスポート（Markdown）とMarkdownファイルからのインポート

ファイル

- `app.py` - アプリ本体（ルート、DB処理、テンプレート処理）
- `schema.sql` - SQLiteスキーマ
- `templates/` - HTMLテンプレート
- `static/` - CSS / JavaScript（`note.js` が自動保存とプレビューを提供）

注意

- 本番運用には WSGI サーバーやセキュリティ対策（CSRF保護など）が必要です。
- 今後の拡張案：正確なMarkdownレンダリング（`markdown`ライブラリ）、安全なマイグレーション、ノートの共有機能。

本番デプロイ（簡易）

このリポジトリは軽量なプロトタイプとして動きます。本番環境で動かす場合の簡易例:

1) `gunicorn` を使う（`requirements.txt` に追加済み）

```bash
gunicorn -b 0.0.0.0:8000 app:app
```

2) Heroku 等にデプロイする場合は、ルートに `Procfile` を追加します（既に用意済み）:

```
web: gunicorn -b 0.0.0.0:$PORT app:app
```

注意: 本番では `DEBUG=False` にし、環境変数 `FLASK_SECRET` を強力な値に設定してください。
