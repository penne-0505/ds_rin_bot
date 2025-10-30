from __future__ import annotations

import logging
from typing import Dict, Tuple, TYPE_CHECKING

import discord

from bot.bridge.routes import ChannelEndpoint
from bot.temp_vc import (
    TempVCAlreadyExistsError,
    TempVCCategoryNotConfiguredError,
    TempVCCategoryNotFoundError,
)
from views import SendModalView


if TYPE_CHECKING:
    from bot.client import BotClient


LOGGER = logging.getLogger(__name__)


async def register_commands(client: "BotClient") -> None:
    """クライアントのアプリケーションコマンドを登録する。"""

    tree = client.tree

    @tree.command(name="setup", description="メッセージ送信のセットアップを行います。")
    async def command_setup(interaction: discord.Interaction) -> None:
        LOGGER.info("/setup コマンドを実行したユーザー: %s", interaction.user)
        await interaction.response.defer()
        view = SendModalView()
        await interaction.followup.send(
            "📨 下のボタンからメッセージ送信モーダルを開けます。",
            view=view,
        )

    @tree.command(name="vc", description="自分専用のボイスチャンネルを作成します。")
    async def create_temp_vc(interaction: discord.Interaction) -> None:
        manager = client.temp_vc_manager
        if manager is None:
            await _send_ephemeral(
                interaction,
                "一時VC機能が設定されていません。管理者に連絡してください。",
            )
            return

        guild = interaction.guild
        if guild is None:
            await _send_ephemeral(
                interaction,
                "このコマンドはサーバー内でのみ使用できます。",
            )
            return

        try:
            channel = await manager.create_user_channel(guild=guild, user=interaction.user)
        except TempVCAlreadyExistsError as err:
            await _send_ephemeral(
                interaction,
                f"すでに専用チャンネルがあります: {err.channel.mention}",
            )
            return
        except TempVCCategoryNotConfiguredError:
            await _send_ephemeral(
                interaction,
                "専用チャンネル用のカテゴリーが未設定です。管理者に連絡してください。",
            )
            return
        except TempVCCategoryNotFoundError:
            await _send_ephemeral(
                interaction,
                "専用チャンネル用のカテゴリーが見つかりませんでした。管理者に連絡してください。",
            )
            return
        except Exception:  # pragma: no cover - 予期しないエラーの記録
            LOGGER.exception("一時VC作成中に予期しないエラーが発生しました。")
            await _send_ephemeral(
                interaction,
                "チャンネルの作成中にエラーが発生しました。しばらくしてから再試行してください。",
            )
            return

        await _send_ephemeral(
            interaction,
            f"ボイスチャンネルを作成しました: {channel.mention}\n誰もいなくなったら自動で削除されます。",
        )

    @tree.command(name="vc_category", description="一時VCの作成先カテゴリを設定します。")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def configure_temp_vc_category(interaction: discord.Interaction) -> None:
        manager = client.temp_vc_manager
        if manager is None:
            await _send_ephemeral(
                interaction,
                "一時VC機能が初期化されていません。ボットのログを確認してください。",
            )
            return

        guild = interaction.guild
        if guild is None:
            await _send_ephemeral(
                interaction,
                "このコマンドはサーバー内でのみ使用できます。",
            )
            return

        categories = guild.categories[:25]
        if not categories:
            await _send_ephemeral(
                interaction,
                "カテゴリが見つかりません。サーバーにカテゴリを作成してから再試行してください。",
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
                self.view.selected_category_id = selected_id
                for option in self.options:
                    option.default = option.value == str(selected_id)
                await select_interaction.response.edit_message(view=self.view)

        class ConfirmButton(discord.ui.Button):
            def __init__(self) -> None:
                super().__init__(label="確定", style=discord.ButtonStyle.primary)

            async def callback(self, button_interaction: discord.Interaction) -> None:
                selected_id = getattr(self.view, "selected_category_id", None)
                if selected_id is None:
                    await button_interaction.response.send_message(
                        "先にカテゴリを選択してください。",
                        ephemeral=True,
                    )
                    return

                manager.set_category_for_guild(guild_id=guild.id, category_id=selected_id)
                category = guild.get_channel(selected_id)
                category_name = category.mention if isinstance(category, discord.CategoryChannel) else f"ID: {selected_id}"
                await button_interaction.response.edit_message(
                    content=f"一時VCのカテゴリを {category_name} に設定しました。",
                    view=None,
                )
                self.view.stop()

        class CategorySelectView(discord.ui.View):
            def __init__(self) -> None:
                super().__init__(timeout=180)
                self.selected_category_id = current_category_id
                self.add_item(CategorySelect())
                self.add_item(ConfirmButton())

        await interaction.response.send_message(
            "一時VCの作成先カテゴリを選択し、『確定』を押してください。",
            view=CategorySelectView(),
            ephemeral=True,
        )

    @tree.command(name="bridge_links", description="このギルドに設定されているチャンネルブリッジを表示します。")
    async def bridge_links(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await _send_ephemeral(
                interaction,
                "このコマンドはサーバー内でのみ使用できます。",
            )
            return

        manager = client.bridge_manager
        if manager is None:
            await _send_ephemeral(
                interaction,
                "チャンネルブリッジ機能が有効になっていません。",
            )
            return

        guild = interaction.guild
        routes = manager.get_routes_from_guild(guild.id)
        if not routes:
            await _send_ephemeral(
                interaction,
                "このギルドにはブリッジ連携が設定されていません。",
            )
            return

        await interaction.response.defer(ephemeral=True)

        endpoint_cache: Dict[Tuple[int, int], Tuple[str, str]] = {}

        async def resolve_endpoint(endpoint: ChannelEndpoint) -> Tuple[str, str]:
            cache_key = (endpoint.guild, endpoint.channel)
            if cache_key in endpoint_cache:
                return endpoint_cache[cache_key]

            endpoint_guild: discord.Guild | None
            if endpoint.guild == guild.id:
                endpoint_guild = guild
            else:
                endpoint_guild = client.get_guild(endpoint.guild)
                if endpoint_guild is None:
                    try:
                        endpoint_guild = await client.fetch_guild(endpoint.guild)
                    except discord.HTTPException as exc:
                        LOGGER.warning("ギルドの取得に失敗しました: guild=%s, error=%s", endpoint.guild, exc)

            if endpoint_guild is not None:
                guild_label = f"{endpoint_guild.name} (ID: {endpoint_guild.id})"
            else:
                guild_label = f"(取得失敗: Guild ID {endpoint.guild})"

            channel_obj: discord.abc.GuildChannel | discord.Thread | None = None
            if endpoint_guild is not None:
                channel_obj = endpoint_guild.get_channel(endpoint.channel)
            if channel_obj is None:
                generic_channel = client.get_channel(endpoint.channel)
                if isinstance(generic_channel, (discord.abc.GuildChannel, discord.Thread)):
                    channel_obj = generic_channel
            if channel_obj is None:
                try:
                    fetched_channel = await client.fetch_channel(endpoint.channel)
                except discord.HTTPException as exc:
                    LOGGER.warning("チャンネルの取得に失敗しました: channel=%s, error=%s", endpoint.channel, exc)
                else:
                    if isinstance(fetched_channel, (discord.abc.GuildChannel, discord.Thread)):
                        channel_obj = fetched_channel

            if isinstance(channel_obj, discord.Thread):
                channel_label = f"{channel_obj.name} (Thread, ID: {channel_obj.id})"
            elif isinstance(channel_obj, discord.abc.GuildChannel):
                channel_label = f"{channel_obj.name} (ID: {channel_obj.id})"
            else:
                channel_label = f"(取得失敗: Channel ID {endpoint.channel})"

            endpoint_cache[cache_key] = (guild_label, channel_label)
            return guild_label, channel_label

        lines = []
        for index, route in enumerate(routes, start=1):
            src_guild_label, src_channel_label = await resolve_endpoint(route.src)
            dst_guild_label, dst_channel_label = await resolve_endpoint(route.dst)
            lines.append(
                f"{index}. 実行元: {src_guild_label} / {src_channel_label}\n"
                f"   連携先: {dst_guild_label} / {dst_channel_label}"
            )

        message = "🔗 設定されているチャンネルブリッジ\n" + "\n".join(lines)
        await interaction.followup.send(message, ephemeral=True)


async def _send_ephemeral(interaction: discord.Interaction, message: str) -> None:
    """対話からエフェメラルメッセージを送信する補助関数。"""

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


__all__ = ["register_commands"]
