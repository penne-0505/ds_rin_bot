from __future__ import annotations

import asyncio
import logging

from app import build_discord_app, load_config


LOGGER = logging.getLogger(__name__)


async def run_bot() -> None:
    """Load configuration, build the Discord application and run the client."""

    try:
        config = load_config()
    except Exception:  # pragma: no cover - configuration errors should be rare
        LOGGER.exception("設定ファイルの読み込みに失敗しました。")
        return

    app = await build_discord_app(config)
    await app.run()


def main() -> None:
    """Entry point for launching the Discord bot."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())


if __name__ == "__main__":
    LOGGER.info("Discord Bot を起動します。")
    main()
