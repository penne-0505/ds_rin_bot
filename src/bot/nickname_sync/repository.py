from __future__ import annotations

from typing import Any

from app.database import Database

from .models import ChannelNicknameRule


UPSERT_RULE_SQL = r"""
INSERT INTO channel_nickname_rules (guild_id, channel_id, role_id, updated_by)
VALUES ($1, $2, $3, $4)
ON CONFLICT (guild_id, channel_id)
DO UPDATE
SET
    role_id = EXCLUDED.role_id,
    updated_by = EXCLUDED.updated_by,
    updated_at = timezone('UTC', now())
RETURNING guild_id, channel_id, role_id, updated_by, updated_at;
"""


GET_RULE_SQL = r"""
SELECT guild_id, channel_id, role_id, updated_by, updated_at
FROM channel_nickname_rules
WHERE guild_id = $1 AND channel_id = $2;
"""


class ChannelNicknameRuleRepository:
    """channel_nickname_rules テーブルを扱うリポジトリ。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert_rule(
        self,
        *,
        guild_id: int,
        channel_id: int,
        role_id: int,
        updated_by: int,
    ) -> ChannelNicknameRule:
        record = await self._database.fetchrow(
            UPSERT_RULE_SQL,
            guild_id,
            channel_id,
            role_id,
            updated_by,
        )
        assert record is not None, "Upsert should always return the affected row."
        return self._record_to_model(record)

    async def get_rule_for_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
    ) -> ChannelNicknameRule | None:
        record = await self._database.fetchrow(
            GET_RULE_SQL,
            guild_id,
            channel_id,
        )
        if record is None:
            return None
        return self._record_to_model(record)

    @staticmethod
    def _record_to_model(record: Any) -> ChannelNicknameRule:
        return ChannelNicknameRule(
            guild_id=int(record["guild_id"]),
            channel_id=int(record["channel_id"]),
            role_id=int(record["role_id"]),
            updated_by=int(record["updated_by"]),
            updated_at=record["updated_at"],
        )


__all__ = ["ChannelNicknameRuleRepository"]
