from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .temp_vc import TempVoiceChannelManager

class BotClient(discord.Client):
    def __init__(
        self,
        *,
        intents: discord.Intents | None = None,
        temp_vc_manager: "TempVoiceChannelManager" | None = None,
    ) -> None:
        super().__init__(intents=intents or discord.Intents.all())
        self.tree = discord.app_commands.CommandTree(self)
        self.temp_vc_manager = temp_vc_manager
    
    async def on_ready(self) -> None:
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.tree.sync()
        print("Bot is ready and command tree synced.")

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if self.temp_vc_manager is None:
            return

        await self.temp_vc_manager.handle_voice_state_update(member, before, after)
