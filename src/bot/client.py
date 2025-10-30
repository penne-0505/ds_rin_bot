from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .bridge import ChannelBridgeManager
    from .temp_vc import TempVoiceChannelManager

class BotClient(discord.Client):
    def __init__(
        self,
        *,
        intents: discord.Intents | None = None,
        temp_vc_manager: "TempVoiceChannelManager" | None = None,
        bridge_manager: "ChannelBridgeManager" | None = None,
    ) -> None:
        super().__init__(intents=intents or discord.Intents.all())
        self.tree = discord.app_commands.CommandTree(self)
        self.temp_vc_manager = temp_vc_manager
        self.bridge_manager = bridge_manager
    
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

    async def on_message(self, message: discord.Message) -> None:
        if self.bridge_manager is not None:
            await self.bridge_manager.handle_message(message)

    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        user: discord.abc.User,
    ) -> None:
        if self.bridge_manager is not None:
            await self.bridge_manager.handle_reaction(reaction, user, add=True)

    async def on_reaction_remove(
        self,
        reaction: discord.Reaction,
        user: discord.abc.User,
    ) -> None:
        if self.bridge_manager is not None:
            await self.bridge_manager.handle_reaction(reaction, user, add=False)

    async def on_message_delete(self, message: discord.Message) -> None:
        if self.bridge_manager is not None:
            self.bridge_manager.handle_message_delete(message.id)
