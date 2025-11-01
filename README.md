# ds-rin-bot

Discord 向けの多機能ボットです。

## セットアップ手順

1. 依存関係をインストールします: `poetry install`
2. `DISCORD_BOT_TOKEN` 環境変数に Discord Bot トークンを設定します（`.env` ファイルやシェルの環境変数を利用できます）。
3. Bot を起動します: `python src/main.py`

## スラッシュコマンド

- `/command_setup` : モーダル送信UIを設置します。
- `/vc` : 指定カテゴリーにユーザー専用のボイスチャンネルを作成し、無人になったら自動削除します。
- `/vc_category` : 一時VCの作成先カテゴリを設定します。

## ブリッジメッセージ記録

チャンネルブリッジ機能は、送信元・送信先のメッセージIDや DiceBear プロフィール情報を `data/bridge_messages.json` に保存します。定期的なクリーンアップやルート設定変更時の再同期手順については [docs/bridge_message_store.md](docs/bridge_message_store.md) を参照してください。

## チャンネルブリッジ設定

- 本番運用では `BRIDGE_ROUTES_ENABLED=true` を設定し、`BRIDGE_ROUTES` 環境変数に JSON 配列でルートを渡します。
- 例: `set -x BRIDGE_ROUTES '[{"src":{"guild":123,"channel":456},"dst":{"guild":789,"channel":101112}}]'`
- `BRIDGE_ROUTES_REQUIRE_RECIPROCAL=true` を併用すると、双方向ルートが揃っていない場合に起動を中断します。
- `BRIDGE_ROUTES_STRICT=true` を指定すると重複や形式不備を検出した時点で起動エラーになります。
- `BRIDGE_ROUTES_ENABLED` を `true` 以外にするとローカルデバッグ用の `data/channel_routes.json` がフォールバックとして使用されます。

より詳しい設定手順は [docs/bridge_configuration.md](docs/bridge_configuration.md) にまとめています。
