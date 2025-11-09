from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, Sequence, Tuple, TYPE_CHECKING, cast

import discord

from bot.bridge.routes import ChannelEndpoint, ChannelRoute
from bot.temp_vc import (
    TempVCAlreadyExistsError,
    TempVCCategoryNotConfiguredError,
    TempVCCategoryNotFoundError,
    TempVoiceChannelManager,
)
from views import SendModalView


if TYPE_CHECKING:
    from bot.client import BotClient


LOGGER = logging.getLogger(__name__)


async def register_commands(client: "BotClient") -> None:
    """クライアントのアプリケーションコマンドを登録する。"""

    registrar = _CommandRegistrar(client)
    registrar.register()


@dataclass(slots=True)
class _CommandRegistrar:
    client: "BotClient"

    def register(self) -> None:
        self._register_setup()
        self._register_temp_vc_creation()
        self._register_temp_vc_category()
        self._register_bridge_links()

    @property
    def tree(self) -> discord.app_commands.CommandTree:
        return self.client.tree

    def _register_setup(self) -> None:
        @self.tree.command(
            name="setup", description="メッセージ送信のセットアップを行います。"
        )
        async def command_setup(interaction: discord.Interaction) -> None:
            LOGGER.info("/setup コマンドを実行したユーザー: %s", interaction.user)
            await interaction.response.defer()
            view = SendModalView()
            await interaction.followup.send(
                "📨 下のボタンからメッセージ送信モーダルを開けます。",
                view=view,
            )

    def _register_temp_vc_creation(self) -> None:
        @self.tree.command(
            name="vc", description="自分専用のボイスチャンネルを作成します。"
        )
        async def create_temp_vc(interaction: discord.Interaction) -> None:
            manager = self.client.temp_vc_manager
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
                channel = await manager.create_user_channel(
                    guild=guild, user=interaction.user
                )
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

    def _register_temp_vc_category(self) -> None:
        @self.tree.command(
            name="vc_category", description="一時VCの作成先カテゴリを設定します。"
        )
        @discord.app_commands.checks.has_permissions(administrator=True)
        async def configure_temp_vc_category(
            interaction: discord.Interaction,
        ) -> None:
            manager = self.client.temp_vc_manager
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

            view = _CategorySelectView(
                categories=categories,
                manager=manager,
                guild=guild,
            )

            await interaction.response.send_message(
                "一時VCの作成先カテゴリを選択し、『確定』を押してください。",
                view=view,
                ephemeral=True,
            )

    def _register_bridge_links(self) -> None:
        @self.tree.command(
            name="bridge_links",
            description="このギルドに設定されているチャンネルブリッジを表示します。",
        )
        async def bridge_links(interaction: discord.Interaction) -> None:
            if interaction.guild is None:
                await _send_ephemeral(
                    interaction,
                    "このコマンドはサーバー内でのみ使用できます。",
                )
                return

            manager = self.client.bridge_manager
            if manager is None:
                await _send_ephemeral(
                    interaction,
                    "チャンネルブリッジ機能が有効になっていません。",
                )
                return

            routes = manager.get_routes_from_guild(interaction.guild.id)
            if not routes:
                await _send_ephemeral(
                    interaction,
                    "このギルドにはブリッジ連携が設定されていません。",
                )
                return

            await interaction.response.defer(ephemeral=True)

            formatter = _BridgeRouteFormatter(client=self.client, guild=interaction.guild)
            lines = await formatter.describe_routes(routes)
            message = "🔗 設定されているチャンネルブリッジ\n" + "\n".join(lines)
            await interaction.followup.send(message, ephemeral=True)


class _CategorySelectView(discord.ui.View):
    def __init__(
        self,
        *,
        categories: Sequence[discord.CategoryChannel],
        manager: TempVoiceChannelManager,
        guild: discord.Guild,
    ) -> None:
        super().__init__(timeout=180)
        self._categories = tuple(categories)
        self.manager = manager
        self.guild = guild
        self.selected_category_id = self.manager.get_category_for_guild(self.guild.id)
        self.add_item(
            _CategorySelect(
                categories=self._categories,
                current_category_id=self.selected_category_id,
            )
        )
        self.add_item(_ConfirmButton())


class _CategorySelect(discord.ui.Select):
    def __init__(
        self,
        *,
        categories: Sequence[discord.CategoryChannel],
        current_category_id: int | None,
    ) -> None:
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

    async def callback(self, interaction: discord.Interaction) -> None:
        view = cast(_CategorySelectView, self.view)
        selected_id = int(self.values[0])
        view.selected_category_id = selected_id
        for option in self.options:
            option.default = option.value == str(selected_id)
        await interaction.response.edit_message(view=view)


class _ConfirmButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="確定", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = cast(_CategorySelectView, self.view)
        selected_id = view.selected_category_id
        if selected_id is None:
            await interaction.response.send_message(
                "先にカテゴリを選択してください。",
                ephemeral=True,
            )
            return

        view.manager.set_category_for_guild(
            guild_id=view.guild.id,
            category_id=selected_id,
        )
        category = view.guild.get_channel(selected_id)
        if isinstance(category, discord.CategoryChannel):
            category_name = category.mention
        else:
            category_name = f"ID: {selected_id}"
        await interaction.response.edit_message(
            content=f"一時VCのカテゴリを {category_name} に設定しました。",
            view=None,
        )
        view.stop()


@dataclass(slots=True)
class _BridgeRouteFormatter:
    client: "BotClient"
    guild: discord.Guild
    _cache: Dict[Tuple[int, int], Tuple[str, str]] = field(default_factory=dict)

    async def describe_routes(self, routes: Iterable[ChannelRoute]) -> list[str]:
        lines: list[str] = []
        for index, route in enumerate(routes, start=1):
            src_guild_label, src_channel_label = await self._describe_endpoint(route.src)
            dst_guild_label, dst_channel_label = await self._describe_endpoint(route.dst)
            lines.append(
                f"{index}. 実行元: {src_guild_label} / {src_channel_label}\n"
                f"   連携先: {dst_guild_label} / {dst_channel_label}"
            )
        return lines

    async def _describe_endpoint(
        self, endpoint: ChannelEndpoint
    ) -> Tuple[str, str]:
        cache_key = (endpoint.guild, endpoint.channel)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        endpoint_guild = await self._resolve_guild(endpoint.guild)
        if endpoint_guild is not None:
            guild_label = f"{endpoint_guild.name} (ID: {endpoint_guild.id})"
            channel_obj: discord.abc.GuildChannel | discord.Thread | None = (
                endpoint_guild.get_channel(endpoint.channel)
            )
        else:
            guild_label = f"(取得失敗: Guild ID {endpoint.guild})"
            channel_obj = None

        if channel_obj is None:
            channel_obj = await self._resolve_channel(endpoint.channel)

        if isinstance(channel_obj, discord.Thread):
            channel_label = f"{channel_obj.name} (Thread, ID: {channel_obj.id})"
        elif isinstance(channel_obj, discord.abc.GuildChannel):
            channel_label = f"{channel_obj.name} (ID: {channel_obj.id})"
        else:
            channel_label = f"(取得失敗: Channel ID {endpoint.channel})"

        value = (guild_label, channel_label)
        self._cache[cache_key] = value
        return value

    async def _resolve_guild(self, guild_id: int) -> discord.Guild | None:
        if guild_id == self.guild.id:
            return self.guild

        guild = self.client.get_guild(guild_id)
        if guild is not None:
            return guild

        try:
            return await self.client.fetch_guild(guild_id)
        except discord.HTTPException as exc:
            LOGGER.warning("ギルドの取得に失敗しました: guild=%s, error=%s", guild_id, exc)
            return None

    async def _resolve_channel(
        self, channel_id: int
    ) -> discord.abc.GuildChannel | discord.Thread | None:
        channel = self.client.get_channel(channel_id)
        if isinstance(channel, (discord.abc.GuildChannel, discord.Thread)):
            return channel

        try:
            fetched = await self.client.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            LOGGER.warning(
                "チャンネルの取得に失敗しました: channel=%s, error=%s",
                channel_id,
                exc,
            )
            return None

        if isinstance(fetched, (discord.abc.GuildChannel, discord.Thread)):
            return fetched

        return None


async def _send_ephemeral(interaction: discord.Interaction, message: str) -> None:
    """対話からエフェメラルメッセージを送信する補助関数。"""

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


__all__ = ["register_commands"]

