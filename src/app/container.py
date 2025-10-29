import asyncio
from dataclasses import dataclass

from bot import BotClient, register_commands
from app.config import AppConfig

@dataclass(slots=True)
class DiscordApplication:
    client: BotClient
    token: str
    
    async def run(self) -> None:
        async with self.client:
            await self.client.start(self.token)

async def build_discord_app(config: AppConfig) -> DiscordApplication:
    
    client = BotClient()
    await register_commands(client)
    print("Discord bot client initialized with commands registered.")
    return DiscordApplication(client=client, token=config.discord.token)

__all__ = [
    "DiscordApplication",
    "build_discord_app",
]