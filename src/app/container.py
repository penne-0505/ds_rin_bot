from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tinydb import TinyDB

from app.config import AppConfig
from app.database import Database
from bot import BotClient, register_commands
from bot.nickname_sync import ChannelNicknameRuleRepository, NicknameSyncService
from bot.temp_vc import TempVCChannelStore, TempVCCategoryStore, TempVoiceChannelManager


LOGGER = logging.getLogger(__name__)


DATA_DIR_NAME = "data"
TEMP_VC_DB_NAME = "temp_vc.json"


@dataclass(slots=True)
class DiscordApplication:
    """Discord クライアントとトークンを保持し、実行処理を提供する。"""

    client: BotClient
    token: str
    database: Database

    async def run(self) -> None:
        """クライアントを起動する。"""

        try:
            async with self.client:
                await self.client.start(self.token)
        finally:
            await self.database.close()


def _initialise_data_directory(root: Path | None = None) -> Path:
    base = root or Path(DATA_DIR_NAME)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _build_temp_vc_manager(data_dir: Path) -> TempVoiceChannelManager:
    database = TinyDB(data_dir / TEMP_VC_DB_NAME)
    category_store = TempVCCategoryStore(database)
    channel_store = TempVCChannelStore(database)
    return TempVoiceChannelManager(
        category_store=category_store,
        channel_store=channel_store,
    )


async def build_discord_app(config: AppConfig) -> DiscordApplication:
    """アプリケーションの依存関係を構築し、DiscordApplication を返す。"""

    data_dir = _initialise_data_directory()
    temp_vc_manager = _build_temp_vc_manager(data_dir)
    database = Database(dsn=config.database.url)
    await database.connect()

    nickname_rule_repository = ChannelNicknameRuleRepository(database)
    nickname_sync_service = NicknameSyncService(nickname_rule_repository)

    try:
        client = BotClient(
            temp_vc_manager=temp_vc_manager,
            nickname_sync_service=nickname_sync_service,
        )
        await register_commands(
            client,
            nickname_sync_service=nickname_sync_service,
            nickname_rule_repository=nickname_rule_repository,
        )
        LOGGER.info("Discord クライアントの初期化が完了し、コマンドを登録しました。")
    except Exception:
        await database.close()
        raise

    return DiscordApplication(client=client, token=config.discord.token, database=database)


__all__ = ["DiscordApplication", "build_discord_app"]
