# ds-rin-bot

Discord 向けの多機能ボットです。

## セットアップ手順

1. 依存関係をインストールします: `poetry install`
2. `.env` やシェルの環境変数で以下を設定します。
   - `DISCORD_BOT_TOKEN` : Discord Bot トークン
   - `DATABASE_URL` : PostgreSQL への接続文字列 (例: `postgresql://user:pass@localhost:5432/ds_rin_bot`)
3. Bot を起動します: `python src/main.py`

## スラッシュコマンド

- `/command_setup` : モーダル送信UIを設置します。
- `/vc` : 指定カテゴリーにユーザー専用のボイスチャンネルを作成し、無人になったら自動削除します。
- `/vc_category` : 一時VCの作成先カテゴリを設定します。
- `/nickname_sync_setup` : ニックネーム同期対象のチャンネルと付与ロールを選択します。

## ニックネーム同期チャンネル

`/nickname_sync_setup` をサーバー管理者（`Manage Guild` 権限以上）が実行すると、対象のテキスト/アナウンスチャンネルと付与するロールを指定できます。

- Bot には「メッセージの管理」「ロールの管理」権限が必要です。
- 設定は PostgreSQL の `channel_nickname_rules` テーブルに保存され、メッセージ投稿時にニックネームへ本文を同期し、指定ロールを自動付与します。
- 設定後にチャンネル/ロールが削除された場合は WARN ログが出力されるため、再設定を実施してください。
- DB 接続に失敗した場合は起動が中断されるので、`DATABASE_URL` と接続先の疎通をご確認ください。

## チャンネルブリッジ機能の移動について

以前 `src/bot/bridge` 以下に含まれていたチャンネルブリッジ機能は、独立して動作するテンプレートとして `temp/bridge_base/` 配下へ再構成しました。ブリッジ機能を利用したい場合は、`temp/bridge_base/README.md` の手順に従って起動してください。

## ブリッジメッセージ記録

ブリッジ機能は `temp/bridge_base/data/bridge_messages.json` にメッセージメタデータを保存します。メンテナンス方法は [temp/bridge_base/docs/bridge_message_store.md](temp/bridge_base/docs/bridge_message_store.md) を参照してください。

## チャンネルブリッジ設定

ブリッジ専用テンプレートでは以下のルールでルート定義を読み込みます。

- 本番運用では `BRIDGE_ROUTES_ENABLED=true` を設定し、`BRIDGE_ROUTES` 環境変数に JSON 配列でルートを渡します。
- 例: `set -x BRIDGE_ROUTES '[{"src":{"guild":123,"channel":456},"dst":{"guild":789,"channel":101112}}]'`
- `BRIDGE_ROUTES_REQUIRE_RECIPROCAL=true` を併用すると、双方向ルートが揃っていない場合に起動を中断します。
- `BRIDGE_ROUTES_STRICT=true` を指定すると重複や形式不備を検出した時点で起動エラーになります。
- `BRIDGE_ROUTES_ENABLED` を `true` 以外にすると `temp/bridge_base/data/channel_routes.json` がフォールバックとして使用されます。

詳細は [temp/bridge_base/docs/bridge_configuration.md](temp/bridge_base/docs/bridge_configuration.md) を参照してください。
