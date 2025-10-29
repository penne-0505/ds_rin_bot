from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

@dataclass(frozen=True, slots=True)
class DiscordSettings:
    token: str

@dataclass(frozen=True, slots=True)
class AppConfig:
    discord: DiscordSettings

def _load_env_file(env_file: str | Path | None) -> None:
    """.envファイルを読み込む"""
    if env_file is None:
        load_dotenv()
        return
    
    path = Path(env_file)
    if path.is_file():
        load_dotenv(dotenv_path=path)
    else:
        raise FileNotFoundError(f".env file not found at: {path}")

def _prepare_client_token(raw_token: str | None) -> str:
    """トークンの正規性を確認して返す"""
    if raw_token is None or raw_token.strip() == "":
        raise ValueError("Discord bot token is not set in environment variables.")
    return raw_token.strip()

def load_config(env_file: str | Path | None = Path(".env")) -> AppConfig:
    """設定を読み込む"""
    _load_env_file(env_file)
    
    token = _prepare_client_token(raw_token=os.getenv("DISCORD_BOT_TOKEN"))
    
    print("Configuration loaded successfully.")

    return AppConfig(discord=DiscordSettings(token=token))


__all__ = ["load_config", "AppConfig", "DiscordSettings"]