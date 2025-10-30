# ds-rin-bot

A Discord bot project.

## Setup

1. Install dependencies: `poetry install`
2. Provide the Discord bot token via environment variable `DISCORD_BOT_TOKEN` (e.g. set it in the shell or create a `.env` file).
3. Run: `python src/main.py`

## Slash Commands

- `/command_setup` : モーダル送信UIを設置します。
- `/vc` : 指定カテゴリーにユーザー専用のボイスチャンネルを作成し、無人になったら自動削除します。
- `/vc_category` : 一時VCの作成先カテゴリを設定します。

## ブリッジメッセージ記録

チャンネルブリッジ機能は、送信元・送信先のメッセージIDや DiceBear プロフィール情報を `data/bridge_messages.json` に保存します。定期的なクリーンアップやルート設定変更時の再同期手順については [docs/bridge_message_store.md](docs/bridge_message_store.md) を参照してください。
