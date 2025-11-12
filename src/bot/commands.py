from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING, cast

import discord

from bot.temp_vc import (
    TempVCAlreadyExistsError,
    TempVCCategoryNotConfiguredError,
    TempVCCategoryNotFoundError,
    TempVoiceChannelManager,
)
from views import NicknameSyncSetupView, SendModalView


if TYPE_CHECKING:
    from bot.client import BotClient
    from bot.nickname_sync import ChannelNicknameRuleRepository, NicknameSyncService


LOGGER = logging.getLogger(__name__)


async def register_commands(
    client: "BotClient",
    *,
    nickname_sync_service: "NicknameSyncService" | None = None,
    nickname_rule_repository: "ChannelNicknameRuleRepository" | None = None,
) -> None:
    """クライアントのアプリケーションコマンドを登録する。"""

    registrar = _CommandRegistrar(
        client=client,
        nickname_sync_service=nickname_sync_service,
        nickname_rule_repository=nickname_rule_repository,
    )
    registrar.register()


@dataclass(slots=True)
class _CommandRegistrar:
    client: "BotClient"
    nickname_sync_service: "NicknameSyncService | None" = None
    nickname_rule_repository: "ChannelNicknameRuleRepository | None" = None

    def register(self) -> None:
        self._register_setup()
        self._register_temp_vc_creation()
        self._register_temp_vc_category()
        self._register_nickname_sync_setup()
        # ブリッジ機能は temp/bridge_base へ移行済み

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

    def _register_nickname_sync_setup(self) -> None:
        @self.tree.command(
            name="nickname_sync_setup",
            description="指定したチャンネルでニックネームとロールを同期します。",
        )
        @discord.app_commands.checks.has_permissions(manage_guild=True)
        async def nickname_sync_setup(interaction: discord.Interaction) -> None:
            repository = self.nickname_rule_repository
            service = self.nickname_sync_service
            if repository is None or service is None:
                await _send_ephemeral(
                    interaction,
                    "ニックネーム同期機能が初期化されていません。ボットの設定を確認してください。",
                )
                return

            guild = interaction.guild
            if guild is None:
                await _send_ephemeral(
                    interaction,
                    "このコマンドはサーバー内でのみ使用できます。",
                )
                return

            if not isinstance(interaction.user, discord.Member):
                await _send_ephemeral(
                    interaction,
                    "ユーザー情報を取得できませんでした。再度お試しください。",
                )
                return

            bot_member = guild.me
            if bot_member is None:
                await _send_ephemeral(
                    interaction,
                    "Bot メンバー情報の取得に失敗しました。Bot を再起動してください。",
                )
                return

            missing_permissions: list[str] = []
            bot_permissions = bot_member.guild_permissions
            if not bot_permissions.manage_messages:
                missing_permissions.append("メッセージの管理")
            if not bot_permissions.manage_roles:
                missing_permissions.append("ロールの管理")
            if missing_permissions:
                await _send_ephemeral(
                    interaction,
                    "Bot に以下の権限を付与してください: " + ", ".join(missing_permissions),
                )
                return

            channels = self._collect_text_channels(guild=guild, bot_member=bot_member)
            if not channels:
                await _send_ephemeral(
                    interaction,
                    "設定可能なテキスト/アナウンスチャンネルが見つかりません。",
                )
                return

            roles = self._collect_assignable_roles(guild=guild, bot_member=bot_member)
            if not roles:
                await _send_ephemeral(
                    interaction,
                    "Bot が付与できるロールがありません。Bot のロール順位を確認してください。",
                )
                return

            view = NicknameSyncSetupView(
                guild=guild,
                requested_by=interaction.user,
                channels=channels,
                roles=roles,
                repository=repository,
                nickname_sync_service=service,
            )

            await interaction.response.send_message(
                "ニックネーム同期の対象チャンネルとロールを選択してください。",
                view=view,
                ephemeral=True,
            )

    @staticmethod
    def _collect_text_channels(
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> Sequence[discord.TextChannel]:
        eligible = [
            channel
            for channel in guild.text_channels
            if channel.permissions_for(bot_member).send_messages
        ]
        return tuple(eligible[:25])

    @staticmethod
    def _collect_assignable_roles(
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> Sequence[discord.Role]:
        eligible = [
            role
            for role in guild.roles
            if not role.is_default()
            and not role.managed
            and role < bot_member.top_role
        ]
        eligible.sort(key=lambda role: role.position, reverse=True)
        return tuple(eligible[:25])

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


async def _send_ephemeral(interaction: discord.Interaction, message: str) -> None:
    """対話からエフェメラルメッセージを送信する補助関数。"""

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


__all__ = ["register_commands"]
