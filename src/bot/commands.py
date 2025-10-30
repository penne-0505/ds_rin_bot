from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.client import BotClient

import discord

from views import SendModalView
from bot.temp_vc import TempVCAlreadyExistsError, TempVCCategoryNotFoundError

async def register_commands(client: "BotClient") -> None:
    tree = client.tree
    
    @tree.command()
    async def command_setup(interaction: discord.Interaction) -> None:
        print("command executed: command_setup")
        await interaction.response.defer()
        """UI付きメッセージを送る"""
        view = SendModalView()
        await interaction.followup.send(
            "📨 下のボタンからメッセージ送信モーダルを開けます。",
            view=view,
        )

    @tree.command(name="vc", description="自分専用のボイスチャンネルを作成します。")
    async def create_temp_vc(interaction: discord.Interaction) -> None:
        manager = client.temp_vc_manager
        if manager is None:
            await interaction.response.send_message(
                "一時VC機能が設定されていません。管理者に連絡してください。",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "このコマンドはサーバー内でのみ使用できます。",
                ephemeral=True,
            )
            return

        try:
            channel = await manager.create_user_channel(guild=guild, user=interaction.user)
        except TempVCAlreadyExistsError as err:
            await interaction.response.send_message(
                f"すでに専用チャンネルがあります: {err.channel.mention}",
                ephemeral=True,
            )
            return
        except TempVCCategoryNotFoundError:
            await interaction.response.send_message(
                "専用チャンネル用のカテゴリーが見つかりませんでした。管理者に連絡してください。",
                ephemeral=True,
            )
            return
        except Exception as exc:  # 予期しないエラーはユーザーに共有しつつログに残す
            print(f"Unexpected error during temporary VC creation: {exc}")
            await interaction.response.send_message(
                "チャンネルの作成中にエラーが発生しました。しばらくしてから再試行してください。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"ボイスチャンネルを作成しました: {channel.mention}\n誰もいなくなったら自動で削除されます。",
            ephemeral=True,
        )

__all__ = [
    "register_commands",
]
