from __future__ import annotations

import logging
from typing import Dict, Tuple

import discord

from .models import ChannelNicknameRule
from .repository import ChannelNicknameRuleRepository


LOGGER = logging.getLogger(__name__)


CacheKey = Tuple[int, int]


class NicknameSyncService:
    """Nickname/Role 同期ルールを適用するサービス。"""

    def __init__(self, repository: ChannelNicknameRuleRepository) -> None:
        self._repository = repository
        self._cache: Dict[CacheKey, ChannelNicknameRule | None] = {}

    async def enforce(self, message: discord.Message) -> None:
        guild = message.guild
        if guild is None:
            return

        channel_id = getattr(message.channel, "id", None)
        if channel_id is None:
            return

        rule = await self._get_rule(guild_id=guild.id, channel_id=channel_id)
        if rule is None:
            return

        member = message.author
        if not isinstance(member, discord.Member):
            return

        display_name = self._resolve_display_name(member)
        if display_name and message.content != display_name:
            await self._edit_message_content(message, display_name)

        await self._ensure_role(member, rule.role_id)

    def invalidate_cache(self, guild_id: int, channel_id: int) -> None:
        self._cache.pop((guild_id, channel_id), None)

    async def _get_rule(
        self,
        *,
        guild_id: int,
        channel_id: int,
    ) -> ChannelNicknameRule | None:
        key = (guild_id, channel_id)
        if key not in self._cache:
            self._cache[key] = await self._repository.get_rule_for_channel(
                guild_id=guild_id,
                channel_id=channel_id,
            )
        return self._cache[key]

    @staticmethod
    def _resolve_display_name(member: discord.Member) -> str:
        if member.display_name:
            return member.display_name
        if member.global_name:
            return member.global_name
        return member.name

    async def _edit_message_content(self, message: discord.Message, content: str) -> None:
        try:
            await message.edit(content=content)
            LOGGER.debug(
                "メッセージ内容をニックネームと同期しました (guild=%s, channel=%s, user=%s)",
                message.guild.id if message.guild else "n/a",
                getattr(message.channel, "id", "n/a"),
                message.author.id,
            )
        except discord.Forbidden:
            LOGGER.warning(
                "メッセージ編集権限が不足しているため同期できませんでした (channel=%s)",
                getattr(message.channel, "id", "n/a"),
            )
        except discord.HTTPException as exc:
            LOGGER.warning("メッセージ編集でHTTPエラーが発生しました: %s", exc)

    async def _ensure_role(self, member: discord.Member, role_id: int) -> None:
        role = member.guild.get_role(role_id)
        if role is None:
            LOGGER.warning(
                "同期設定されたロールが見つかりません (guild=%s, role_id=%s)",
                member.guild.id,
                role_id,
            )
            return

        if role in member.roles:
            return

        try:
            await member.add_roles(role, reason="Channel nickname sync enforcement")
            LOGGER.info(
                "ユーザーにロールを付与しました (guild=%s, user=%s, role=%s)",
                member.guild.id,
                member.id,
                role.id,
            )
        except discord.Forbidden:
            LOGGER.warning(
                "ロール付与に必要な権限が不足しています (guild=%s, role=%s)",
                member.guild.id,
                role.id,
            )
        except discord.HTTPException as exc:
            LOGGER.warning("ロール付与でHTTPエラーが発生しました: %s", exc)


__all__ = ["NicknameSyncService"]
