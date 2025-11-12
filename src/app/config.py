from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscordSettings:
    """Discord 関連の設定値を保持するデータクラス。"""

    token: str


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """データベース接続に必要な設定値を保持するデータクラス。"""

    url: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    """アプリケーション全体の設定を保持するデータクラス。"""

    discord: DiscordSettings
    database: DatabaseSettings


def _load_env_file(env_file: str | Path | None) -> None:
    """環境変数ファイルを読み込む。"""

    if env_file is None:
        load_dotenv()
        return

    path = Path(env_file)
    if path.is_file():
        load_dotenv(dotenv_path=path)
        return

    raise FileNotFoundError(f".env file not found at: {path}")


def _prepare_client_token(raw_token: str | None) -> str:
    """Discord Bot トークンを検証して整形する。"""

    if raw_token is None or raw_token.strip() == "":
        raise ValueError("Discord bot token is not set in environment variables.")
    return raw_token.strip()


def _prepare_database_url(raw_url: str | None) -> str:
    """データベース接続URLを検証して整形する。"""

    if raw_url is None or raw_url.strip() == "":
        raise ValueError("DATABASE_URL is not set in environment variables.")
    return raw_url.strip()


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """環境変数と設定ファイルからアプリケーション設定を読み込む。"""

    _load_env_file(env_file)

    token = _prepare_client_token(raw_token=os.getenv("DISCORD_BOT_TOKEN"))
    database_url = _prepare_database_url(raw_url=os.getenv("DATABASE_URL"))

    LOGGER.info("設定の読み込みが完了しました。")

    return AppConfig(
        discord=DiscordSettings(token=token),
        database=DatabaseSettings(url=database_url),
    )


__all__ = [
    "load_config",
    "AppConfig",
    "DiscordSettings",
    "DatabaseSettings",
]
