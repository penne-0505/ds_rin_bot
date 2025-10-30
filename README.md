# ds-rin-bot

A Discord bot project.

## Setup

1. Install dependencies: `poetry install`
2. Create `.env` file with `DISCORD_BOT_TOKEN=your_token_here`
   - (Optional) Add `DISCORD_TEMP_VC_CATEGORY_ID=your_category_id` to enable the per-user temporary voice channel feature.
3. Run: `python src/main.py`

## Slash Commands

- `/command_setup` : モーダル送信UIを設置します。
- `/vc` : 指定カテゴリーにユーザー専用のボイスチャンネルを作成し、無人になったら自動削除します。
