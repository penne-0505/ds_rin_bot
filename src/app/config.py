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
class BridgeRouteEnvSettings:
    """チャンネルブリッジの環境変数設定を保持する。"""

    enabled: bool
    routes_json: str | None
    require_reciprocal: bool
    strict: bool


@dataclass(frozen=True, slots=True)
class AppConfig:
    """アプリケーション全体の設定を保持するデータクラス。"""

    discord: DiscordSettings
    bridge_routes_env: BridgeRouteEnvSettings


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


def load_config(env_file: str | Path | None = None) -> AppConfig:
    """環境変数と設定ファイルからアプリケーション設定を読み込む。"""

    _load_env_file(env_file)

    token = _prepare_client_token(raw_token=os.getenv("DISCORD_BOT_TOKEN"))
    bridge_routes_env = _load_bridge_env_settings()

    LOGGER.info("設定の読み込みが完了しました。")

    return AppConfig(
        discord=DiscordSettings(token=token),
        bridge_routes_env=bridge_routes_env,
    )


def _load_bridge_env_settings() -> BridgeRouteEnvSettings:
    enabled = _read_bool_env("BRIDGE_ROUTES_ENABLED", default=False)
    require_reciprocal = _read_bool_env(
        "BRIDGE_ROUTES_REQUIRE_RECIPROCAL", default=False
    )
    strict = _read_bool_env("BRIDGE_ROUTES_STRICT", default=False)
    routes_json = os.getenv("BRIDGE_ROUTES")

    if enabled and (routes_json is None or routes_json.strip() == ""):
        raise ValueError(
            "BRIDGE_ROUTES_ENABLED=true ですが BRIDGE_ROUTES が未設定です。"
        )

    if routes_json is not None and routes_json.strip() == "":
        routes_json = None

    return BridgeRouteEnvSettings(
        enabled=enabled,
        routes_json=routes_json,
        require_reciprocal=require_reciprocal,
        strict=strict,
    )


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    LOGGER.warning(
        "環境変数 %s の値 '%s' はブール値として解釈できません。既定値 %s を使用します。",
        name,
        raw,
        default,
    )
    return default


__all__ = [
    "load_config",
    "AppConfig",
    "DiscordSettings",
    "BridgeRouteEnvSettings",
]
