from __future__ import annotations

from typing import Sequence, cast

import discord

from bot.nickname_sync import ChannelNicknameRuleRepository, NicknameSyncService


class NicknameSyncSetupView(discord.ui.View):
    """ニックネーム同期チャンネルを設定するビュー。"""

    def __init__(
        self,
        *,
        guild: discord.Guild,
        requested_by: discord.Member,
        channels: Sequence[discord.TextChannel],
        roles: Sequence[discord.Role],
        repository: ChannelNicknameRuleRepository,
        nickname_sync_service: NicknameSyncService,
    ) -> None:
        super().__init__(timeout=180)
        self.guild = guild
        self._requested_by_id = requested_by.id
        self.repository = repository
        self.nickname_sync_service = nickname_sync_service
        self.selected_channel_id = channels[0].id if channels else None
        self.selected_role_id = roles[0].id if roles else None

        self.add_item(
            _NicknameChannelSelect(
                channels=channels,
                current_channel_id=self.selected_channel_id,
            )
        )
        self.add_item(
            _NicknameRoleSelect(
                roles=roles,
                current_role_id=self.selected_role_id,
            )
        )
        self.add_item(_NicknameConfirmButton())
        self.add_item(_NicknameCancelButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._requested_by_id:
            await interaction.response.send_message(
                "このビューを操作できるのは最初にコマンドを実行したユーザーのみです。",
                ephemeral=True,
            )
            return False
        return True

    async def save_selection(self) -> tuple[int, int]:
        if self.selected_channel_id is None or self.selected_role_id is None:
            raise ValueError("チャンネルとロールが選択されていません。")

        rule = await self.repository.upsert_rule(
            guild_id=self.guild.id,
            channel_id=self.selected_channel_id,
            role_id=self.selected_role_id,
            updated_by=self._requested_by_id,
        )
        self.nickname_sync_service.invalidate_cache(rule.guild_id, rule.channel_id)
        return rule.channel_id, rule.role_id


class _NicknameChannelSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        channels: Sequence[discord.TextChannel],
        current_channel_id: int | None,
    ) -> None:
        options = [
            discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                default=current_channel_id == channel.id,
            )
            for channel in channels
        ]
        super().__init__(
            placeholder="同期するチャンネルを選択",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        view = cast(NicknameSyncSetupView, self.view)
        selected_id = int(self.values[0])
        view.selected_channel_id = selected_id
        for option in self.options:
            option.default = option.value == str(selected_id)
        await interaction.response.edit_message(view=view)


class _NicknameRoleSelect(discord.ui.Select):
    def __init__(
        self,
        *,
        roles: Sequence[discord.Role],
        current_role_id: int | None,
    ) -> None:
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                default=current_role_id == role.id,
            )
            for role in roles
        ]
        super().__init__(
            placeholder="付与するロールを選択",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        view = cast(NicknameSyncSetupView, self.view)
        selected_id = int(self.values[0])
        view.selected_role_id = selected_id
        for option in self.options:
            option.default = option.value == str(selected_id)
        await interaction.response.edit_message(view=view)


class _NicknameConfirmButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="確定", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        view = cast(NicknameSyncSetupView, self.view)
        try:
            channel_id, role_id = await view.save_selection()
        except ValueError:
            await interaction.response.send_message(
                "チャンネルとロールを選択してください。",
                ephemeral=True,
            )
            return
        except Exception as exc:  # pragma: no cover - 予期しないエラーの通知
            await interaction.response.send_message(
                f"設定の保存中にエラーが発生しました: {exc}",
                ephemeral=True,
            )
            return

        channel = view.guild.get_channel(channel_id)
        channel_label = channel.mention if isinstance(channel, discord.TextChannel) else f"ID: {channel_id}"
        role = view.guild.get_role(role_id)
        role_label = role.mention if isinstance(role, discord.Role) else f"ID: {role_id}"
        await interaction.response.edit_message(
            content=f"{channel_label} を同期対象に設定し、投稿者へ {role_label} を付与するよう構成しました。",
            view=None,
        )
        view.stop()


class _NicknameCancelButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="キャンセル", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        view = cast(NicknameSyncSetupView, self.view)
        await interaction.response.edit_message(
            content="ニックネーム同期の設定をキャンセルしました。",
            view=None,
        )
        view.stop()


__all__ = ["NicknameSyncSetupView"]
