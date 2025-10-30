from dataclasses import dataclass
from pathlib import Path

from bot import BotClient, register_commands
from bot.temp_vc import TempVoiceChannelManager, TempVCCategoryStore
from app.config import AppConfig
from tinydb import TinyDB

@dataclass(slots=True)
class DiscordApplication:
    client: BotClient
    token: str
    
    async def run(self) -> None:
        async with self.client:
            await self.client.start(self.token)

async def build_discord_app(config: AppConfig) -> DiscordApplication:
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    temp_vc_db = TinyDB(data_dir / "temp_vc.json")
    temp_vc_manager = TempVoiceChannelManager(
        category_store=TempVCCategoryStore(temp_vc_db),
    )

    client = BotClient(temp_vc_manager=temp_vc_manager)
    await register_commands(client)
    print("Discord bot client initialized with commands registered.")
    return DiscordApplication(client=client, token=config.discord.token)

__all__ = [
    "DiscordApplication",
    "build_discord_app",
]
