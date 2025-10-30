from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.client import BotClient

import discord

from views import SendModalView
from bot.temp_vc import (
    TempVCAlreadyExistsError,
    TempVCCategoryNotConfiguredError,
    TempVCCategoryNotFoundError,
)

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
        except TempVCCategoryNotConfiguredError:
            await interaction.response.send_message(
                "専用チャンネル用のカテゴリーが未設定です。管理者に連絡してください。",
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

    @tree.command(name="vc_category", description="一時VCの作成先カテゴリを設定します。")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def configure_temp_vc_category(interaction: discord.Interaction) -> None:
        manager = client.temp_vc_manager
        if manager is None:
            await interaction.response.send_message(
                "一時VC機能が初期化されていません。ボットのログを確認してください。",
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

        categories = guild.categories[:25]
        if not categories:
            await interaction.response.send_message(
                "カテゴリが見つかりません。サーバーにカテゴリを作成してから再試行してください。",
                ephemeral=True,
            )
            return

        current_category_id = manager.get_category_for_guild(guild.id)

        class CategorySelect(discord.ui.Select):
            def __init__(self) -> None:
                options = [
                    discord.SelectOption(
                        label=category.name,
                        value=str(category.id),
                        default=current_category_id == category.id,
                    )
                    for category in categories
                ]
                super().__init__(
                    placeholder="一時VC用のカテゴリを選択してください",
                    min_values=1,
                    max_values=1,
                    options=options,
                )

            async def callback(self, select_interaction: discord.Interaction) -> None:
                selected_id = int(self.values[0])
                manager.set_category_for_guild(guild_id=guild.id, category_id=selected_id)
                category = guild.get_channel(selected_id)
                category_name = category.mention if isinstance(category, discord.CategoryChannel) else f"ID: {selected_id}"
                await select_interaction.response.edit_message(
                    content=f"一時VCのカテゴリを {category_name} に設定しました。",
                    view=None,
                )
                self.view.stop()

        class CategorySelectView(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=180)
                self.add_item(CategorySelect())

        await interaction.response.send_message(
            "一時VCの作成先カテゴリを選択してください。",
            view=CategorySelectView(),
            ephemeral=True,
        )

__all__ = [
    "register_commands",
]
