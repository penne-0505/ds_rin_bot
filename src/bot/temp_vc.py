from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import discord


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


@dataclass(slots=True)
class TempVoiceChannelManager:
    """Manage creation and cleanup of per-user temporary voice channels."""

    category_id: int
    _user_channels: Dict[int, Dict[int, int]] | None = None  # guild_id -> user_id -> channel_id

    def __post_init__(self) -> None:
        if self._user_channels is None:
            self._user_channels = {}

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
        """

        category = guild.get_channel(self.category_id)
        if not isinstance(category, discord.CategoryChannel):
            raise TempVCCategoryNotFoundError(self.category_id)

        guild_mapping = self._user_channels.setdefault(guild.id, {})
        existing_channel = self._resolve_existing_channel(guild, guild_mapping.get(user.id))
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

        guild_mapping[user.id] = channel.id
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
            print(f"Failed to delete temporary voice channel {channel.id}: {exc}")
            return

        self._forget_channel(channel.guild.id, owner_user_id)

    def _resolve_existing_channel(
        self,
        guild: discord.Guild,
        channel_id: Optional[int],
    ) -> Optional[discord.VoiceChannel]:
        if channel_id is None:
            return None

        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.VoiceChannel):
            return channel

        # Channel was removed externally; forget stale mapping so a new one can be created.
        guild_mapping = self._user_channels.get(guild.id)
        if guild_mapping and channel_id in guild_mapping.values():
            stale_keys = [uid for uid, cid in guild_mapping.items() if cid == channel_id]
            for uid in stale_keys:
                del guild_mapping[uid]

            if not guild_mapping:
                del self._user_channels[guild.id]

        return None

    def _find_owner(self, guild_id: int, channel_id: int) -> Optional[int]:
        guild_mapping = self._user_channels.get(guild_id)
        if not guild_mapping:
            return None

        for user_id, stored_channel_id in guild_mapping.items():
            if stored_channel_id == channel_id:
                return user_id
        return None

    def _forget_channel(self, guild_id: int, user_id: int) -> None:
        guild_mapping = self._user_channels.get(guild_id)
        if not guild_mapping:
            return

        guild_mapping.pop(user_id, None)
        if not guild_mapping:
            del self._user_channels[guild_id]


__all__ = [
    "TempVCError",
    "TempVCAlreadyExistsError",
    "TempVCCategoryNotFoundError",
    "TempVoiceChannelManager",
]
