from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from tinydb import TinyDB

from app.config import AppConfig
from bot import BotClient, register_commands
from bot.bridge import (
    BridgeMessageStore,
    BridgeProfileStore,
    ChannelBridgeManager,
    load_channel_routes,
)
from bot.temp_vc import TempVCChannelStore, TempVCCategoryStore, TempVoiceChannelManager


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DiscordApplication:
    """Discord クライアントとトークンを保持し、実行処理を提供する。"""

    client: BotClient
    token: str

    async def run(self) -> None:
        """クライアントを起動する。"""

        async with self.client:
            await self.client.start(self.token)


async def build_discord_app(config: AppConfig) -> DiscordApplication:
    """アプリケーションの依存関係を構築し、DiscordApplication を返す。"""

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    temp_vc_db = TinyDB(data_dir / "temp_vc.json")
    temp_vc_category_store = TempVCCategoryStore(temp_vc_db)
    temp_vc_channel_store = TempVCChannelStore(temp_vc_db)
    temp_vc_manager = TempVoiceChannelManager(
        category_store=temp_vc_category_store,
        channel_store=temp_vc_channel_store,
    )

    bridge_profiles_db = TinyDB(data_dir / "bridge_profiles.json")
    profile_store = BridgeProfileStore(bridge_profiles_db)
    bridge_messages_db = TinyDB(data_dir / "bridge_messages.json")
    message_store = BridgeMessageStore(bridge_messages_db)
    routes = load_channel_routes(
        data_dir / "channel_routes.json",
        env_enabled=config.bridge_routes_env.enabled,
        env_payload=config.bridge_routes_env.routes_json,
        require_reciprocal=config.bridge_routes_env.require_reciprocal,
        strict=config.bridge_routes_env.strict,
    )

    client = BotClient(temp_vc_manager=temp_vc_manager)
    client.bridge_manager = ChannelBridgeManager(
        client=client,
        profile_store=profile_store,
        message_store=message_store,
        routes=routes,
    )

    await register_commands(client)
    LOGGER.info("Discord クライアントの初期化が完了し、コマンドを登録しました。")
    return DiscordApplication(client=client, token=config.discord.token)


__all__ = ["DiscordApplication", "build_discord_app"]
