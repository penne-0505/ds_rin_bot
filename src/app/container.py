from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from tinydb import TinyDB

from app.config import AppConfig
from bot import BotClient, register_commands
from bot.bridge import (
    BridgeMessageStore,
    BridgeProfileStore,
    ChannelBridgeManager,
    ChannelRoute,
    load_channel_routes,
)
from bot.temp_vc import TempVCChannelStore, TempVCCategoryStore, TempVoiceChannelManager


LOGGER = logging.getLogger(__name__)


DATA_DIR_NAME = "data"
TEMP_VC_DB_NAME = "temp_vc.json"
BRIDGE_PROFILES_DB_NAME = "bridge_profiles.json"
BRIDGE_MESSAGES_DB_NAME = "bridge_messages.json"
CHANNEL_ROUTES_FILE_NAME = "channel_routes.json"


@dataclass(slots=True)
class DiscordApplication:
    """Discord クライアントとトークンを保持し、実行処理を提供する。"""

    client: BotClient
    token: str

    async def run(self) -> None:
        """クライアントを起動する。"""

        async with self.client:
            await self.client.start(self.token)


@dataclass(slots=True)
class _BridgeDependencies:
    profile_store: BridgeProfileStore
    message_store: BridgeMessageStore
    routes: Sequence[ChannelRoute]


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


def _load_bridge_dependencies(
    data_dir: Path, config: AppConfig
) -> _BridgeDependencies:
    profile_store = BridgeProfileStore(TinyDB(data_dir / BRIDGE_PROFILES_DB_NAME))
    message_store = BridgeMessageStore(TinyDB(data_dir / BRIDGE_MESSAGES_DB_NAME))
    routes = load_channel_routes(
        data_dir / CHANNEL_ROUTES_FILE_NAME,
        env_enabled=config.bridge_routes_env.enabled,
        env_payload=config.bridge_routes_env.routes_json,
        require_reciprocal=config.bridge_routes_env.require_reciprocal,
        strict=config.bridge_routes_env.strict,
    )
    return _BridgeDependencies(
        profile_store=profile_store,
        message_store=message_store,
        routes=routes,
    )


async def build_discord_app(config: AppConfig) -> DiscordApplication:
    """アプリケーションの依存関係を構築し、DiscordApplication を返す。"""

    data_dir = _initialise_data_directory()
    temp_vc_manager = _build_temp_vc_manager(data_dir)
    bridge_dependencies = _load_bridge_dependencies(data_dir, config)

    client = BotClient(temp_vc_manager=temp_vc_manager)
    client.bridge_manager = ChannelBridgeManager(
        client=client,
        profile_store=bridge_dependencies.profile_store,
        message_store=bridge_dependencies.message_store,
        routes=bridge_dependencies.routes,
    )

    await register_commands(client)
    LOGGER.info("Discord クライアントの初期化が完了し、コマンドを登録しました。")
    return DiscordApplication(client=client, token=config.discord.token)


__all__ = ["DiscordApplication", "build_discord_app"]
