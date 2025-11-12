from __future__ import annotations

import logging
from typing import Any, Sequence

import asyncpg


LOGGER = logging.getLogger(__name__)


_CREATE_CHANNEL_RULES_TABLE = r"""
CREATE TABLE IF NOT EXISTS channel_nickname_rules (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('UTC', now())),
    PRIMARY KEY (guild_id, channel_id)
);
"""


class Database:
    """asyncpg ベースのシンプルなデータベースラッパー。"""

    def __init__(self, *, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        LOGGER.info("データベースへの接続を開始します。")
        self._pool = await asyncpg.create_pool(self._dsn)
        await self._initialise_schema()
        LOGGER.info("データベース接続と初期化が完了しました。")

    async def close(self) -> None:
        pool = self._pool
        if pool is None:
            return

        self._pool = None
        LOGGER.info("データベース接続を終了します。")
        await pool.close()

    async def execute(self, query: str, *args: Any) -> str:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> Sequence[asyncpg.Record]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialised. Call connect() first.")
        return self._pool

    async def _initialise_schema(self) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(_CREATE_CHANNEL_RULES_TABLE)


__all__ = ["Database"]
