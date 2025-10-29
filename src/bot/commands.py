from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.client import BotClient

import discord

from views import SendModalView

async def register_commands(client: "BotClient") -> None:
    tree = client.tree
    
    @tree.command()
    async def command_setup(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        """UI付きメッセージを送る"""
        view = SendModalView()
        await interaction.followup.send(
            "📨 下のボタンからメッセージ送信モーダルを開けます。",
            view=view,
            ephemeral=True
        )

__all__ = [
    "register_commands",
]