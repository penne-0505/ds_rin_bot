from dataclasses import dataclass

from bot import BotClient, register_commands
from bot.temp_vc import TempVoiceChannelManager
from app.config import AppConfig

@dataclass(slots=True)
class DiscordApplication:
    client: BotClient
    token: str
    
    async def run(self) -> None:
        async with self.client:
            await self.client.start(self.token)

async def build_discord_app(config: AppConfig) -> DiscordApplication:
    temp_vc_manager = None
    if config.discord.temp_vc_category_id is not None:
        temp_vc_manager = TempVoiceChannelManager(category_id=config.discord.temp_vc_category_id)

    client = BotClient(temp_vc_manager=temp_vc_manager)
    await register_commands(client)
    print("Discord bot client initialized with commands registered.")
    return DiscordApplication(client=client, token=config.discord.token)

__all__ = [
    "DiscordApplication",
    "build_discord_app",
]
