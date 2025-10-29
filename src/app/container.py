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

def build_discord_app(config: AppConfig) -> DiscordApplication:
    
    client = BotClient()
    register_commands(client)
    return DiscordApplication(client=client, token=config.discord.token)

__all__ = [
    "DiscordApplication",
    "build_discord_app",
]