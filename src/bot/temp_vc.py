from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import discord
from tinydb import Query, TinyDB
from tinydb.table import Table


LOGGER = logging.getLogger(__name__)


class TempVCError(Exception):
    """Base class for temporary voice channel related errors."""


class TempVCAlreadyExistsError(TempVCError):
    """Raised when a user already has an associated temporary voice channel."""

    def __init__(self, channel: discord.VoiceChannel) -> None:
        super().__init__("temporary voice channel already exists")
        self.channel = channel


class TempVCCategoryNotFoundError(TempVCError):
    """Raised when the configured category does not exist in the guild."""

    def __init__(self, category_id: int) -> None:
        super().__init__("temporary voice channel category not found")
        self.category_id = category_id


class TempVCCategoryNotConfiguredError(TempVCError):
    """Raised when no category has been configured for the guild."""

    def __init__(self, guild_id: int) -> None:
        super().__init__("temporary voice channel category not configured")
        self.guild_id = guild_id


@dataclass(slots=True)
class TempVCCategoryStore:
    """Persist and retrieve configured temporary VC categories."""

    db: TinyDB
    table_name: str = "temp_vc_categories"
    _table: Table = field(init=False, repr=False)
    _query: Query = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._table = self.db.table(self.table_name)
        self._query = Query()

    def get_category_id(self, guild_id: int) -> Optional[int]:
        record = self._table.get(self._query.guild_id == guild_id)
        if record is None:
            return None
        # Store values as int for consistency even if TinyDB loads as other types.
        return int(record["category_id"])

    def set_category_id(self, guild_id: int, category_id: int) -> None:
        self._table.upsert(
            {"guild_id": int(guild_id), "category_id": int(category_id)},
            self._query.guild_id == guild_id,
        )


@dataclass(slots=True)
class TempVCChannelStore:
    """Persist and retrieve temporary VC ownership mappings."""

    db: TinyDB
    table_name: str = "temp_vc_channels"
    _table: Table = field(init=False, repr=False)
    _query: Query = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._table = self.db.table(self.table_name)
        self._query = Query()

    def load_all(self) -> Dict[int, Dict[int, List[int]]]:
        snapshot: Dict[int, Dict[int, List[int]]] = {}
        for record in self._table.all():
            try:
                guild_id = int(record["guild_id"])
                user_id = int(record["user_id"])
            except (KeyError, TypeError, ValueError):
                LOGGER.warning("無効な一時VCレコードをスキップしました: %s", record)
                continue

            channel_ids = self._sanitize_channel_ids(record.get("channel_ids"))
            if not channel_ids:
                continue

            guild_mapping = snapshot.setdefault(guild_id, {})
            guild_mapping[user_id] = channel_ids
        return snapshot

    def add_channel(self, guild_id: int, user_id: int, channel_id: int) -> None:
        existing = self._get_channel_ids(guild_id, user_id)
        existing.append(int(channel_id))
        self.set_channels(guild_id, user_id, existing)

    def remove_channel(self, guild_id: int, user_id: int, channel_id: int) -> None:
        existing = self._get_channel_ids(guild_id, user_id)
        filtered = [cid for cid in existing if cid != int(channel_id)]
        self.set_channels(guild_id, user_id, filtered)

    def set_channels(self, guild_id: int, user_id: int, channel_ids: List[int]) -> None:
        condition = (self._query.guild_id == int(guild_id)) & (self._query.user_id == int(user_id))
        sanitized = self._sanitize_channel_ids(channel_ids)
        if sanitized:
            self._table.upsert(
                {
                    "guild_id": int(guild_id),
                    "user_id": int(user_id),
                    "channel_ids": sanitized,
                },
                condition,
            )
        else:
            self._table.remove(condition)

    def clear_guild(self, guild_id: int) -> None:
        self._table.remove(self._query.guild_id == int(guild_id))

    def _get_channel_ids(self, guild_id: int, user_id: int) -> List[int]:
        condition = (self._query.guild_id == int(guild_id)) & (self._query.user_id == int(user_id))
        record = self._table.get(condition)
        return self._sanitize_channel_ids(record.get("channel_ids") if record else None)

    @staticmethod
    def _sanitize_channel_ids(raw: Optional[List[object]]) -> List[int]:
        sanitized: List[int] = []
        if not raw:
            return sanitized

        for value in raw:
            try:
                channel_id = int(value)
            except (TypeError, ValueError):
                continue
            if channel_id not in sanitized:
                sanitized.append(channel_id)
        return sanitized


@dataclass(slots=True)
class TempVoiceChannelManager:
    """Manage creation and cleanup of per-user temporary voice channels."""

    category_store: TempVCCategoryStore
    channel_store: TempVCChannelStore
    _user_channels: Dict[int, Dict[int, List[int]]] | None = None  # guild_id -> user_id -> [channel_id]

    def __post_init__(self) -> None:
        if self._user_channels is None:
            self._user_channels = self.channel_store.load_all()

    async def create_user_channel(
        self,
        *,
        guild: discord.Guild,
        user: discord.abc.User,
    ) -> discord.VoiceChannel:
        """Create a temporary voice channel for the given user.

        Raises:
            TempVCAlreadyExistsError: If the user already has a managed channel.
            TempVCCategoryNotFoundError: If the configured category is missing.
            TempVCCategoryNotConfiguredError: If the category is not set for the guild.
        """

        category_id = self.category_store.get_category_id(guild.id)
        if category_id is None:
            raise TempVCCategoryNotConfiguredError(guild.id)

        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            raise TempVCCategoryNotFoundError(category_id)

        guild_mapping = self._user_channels.setdefault(guild.id, {})
        existing_channel = self._resolve_existing_channel(
            guild,
            user_id=user.id,
            channel_ids=list(guild_mapping.get(user.id, [])),
        )
        if existing_channel is not None:
            raise TempVCAlreadyExistsError(existing_channel)

        overwrites = {
            user: discord.PermissionOverwrite(manage_channels=True),
        }

        channel = await guild.create_voice_channel(
            name=f"{user.display_name}のVC",
            category=category,
            overwrites=overwrites,
            reason=f"Temporary voice channel requested by {user} ({user.id})",
        )

        user_channels = guild_mapping.setdefault(user.id, [])
        user_channels.append(channel.id)
        self.channel_store.add_channel(guild.id, user.id, channel.id)
        return channel

    async def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Delete temporary channels when they become empty."""

        channel = before.channel
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            return

        owner_user_id = self._find_owner(channel.guild.id, channel.id)
        if owner_user_id is None:
            return

        if channel.members:
            return

        try:
            await channel.delete(reason="Temporary voice channel cleanup (empty)")
        except discord.HTTPException as exc:
            LOGGER.warning("一時VCの削除に失敗しました: channel_id=%s error=%s", channel.id, exc)
            return

        self._forget_channel(channel.guild.id, owner_user_id, channel.id)

    def set_category_for_guild(self, *, guild_id: int, category_id: int) -> None:
        """Persist the category used for temporary voice channels in the given guild."""

        self.category_store.set_category_id(guild_id, category_id)
        # Reset state so future creations use the fresh category and stale mappings don't linger.
        self._user_channels.pop(guild_id, None)
        self.channel_store.clear_guild(guild_id)

    def get_category_for_guild(self, guild_id: int) -> Optional[int]:
        """Return the configured category id for the given guild, if any."""

        return self.category_store.get_category_id(guild_id)

    def _resolve_existing_channel(
        self,
        guild: discord.Guild,
        *,
        user_id: int,
        channel_ids: List[int],
    ) -> Optional[discord.VoiceChannel]:
        if not channel_ids:
            return None

        guild_mapping = self._user_channels.setdefault(guild.id, {})
        valid_ids: List[int] = []
        existing: Optional[discord.VoiceChannel] = None

        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.VoiceChannel):
                if channel_id not in valid_ids:
                    valid_ids.append(channel_id)
                if existing is None:
                    existing = channel
            else:
                LOGGER.info(
                    "存在しない一時VCを登録解除します: guild_id=%s user_id=%s channel_id=%s",
                    guild.id,
                    user_id,
                    channel_id,
                )
                self.channel_store.remove_channel(guild.id, user_id, channel_id)

        if valid_ids:
            guild_mapping[user_id] = valid_ids
            self.channel_store.set_channels(guild.id, user_id, valid_ids)
        else:
            guild_mapping.pop(user_id, None)
            self.channel_store.set_channels(guild.id, user_id, [])
            if not guild_mapping:
                self._user_channels.pop(guild.id, None)

        return existing

    def _find_owner(self, guild_id: int, channel_id: int) -> Optional[int]:
        guild_mapping = self._user_channels.get(guild_id)
        if not guild_mapping:
            return None

        for user_id, stored_channel_ids in guild_mapping.items():
            if channel_id in stored_channel_ids:
                return user_id
        return None

    def _forget_channel(self, guild_id: int, user_id: int, channel_id: int) -> None:
        guild_mapping = self._user_channels.get(guild_id)
        if not guild_mapping:
            self.channel_store.set_channels(guild_id, user_id, [])
            return

        user_channels = guild_mapping.get(user_id)
        if not user_channels:
            self.channel_store.set_channels(guild_id, user_id, [])
            if not guild_mapping:
                self._user_channels.pop(guild_id, None)
            return

        filtered = [cid for cid in user_channels if cid != channel_id]
        if filtered:
            guild_mapping[user_id] = filtered
            self.channel_store.set_channels(guild_id, user_id, filtered)
        else:
            guild_mapping.pop(user_id, None)
            self.channel_store.set_channels(guild_id, user_id, [])
            if not guild_mapping:
                self._user_channels.pop(guild_id, None)


__all__ = [
    "TempVCError",
    "TempVCAlreadyExistsError",
    "TempVCCategoryNotFoundError",
    "TempVCCategoryNotConfiguredError",
    "TempVCCategoryStore",
    "TempVCChannelStore",
    "TempVoiceChannelManager",
]
