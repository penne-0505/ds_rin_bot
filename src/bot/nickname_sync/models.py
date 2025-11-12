from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class ChannelNicknameRule:
    guild_id: int
    channel_id: int
    role_id: int
    updated_by: int
    updated_at: datetime


__all__ = ["ChannelNicknameRule"]
