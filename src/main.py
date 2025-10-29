from __future__ import annotations

import asyncio

from app import load_config, build_discord_app

async def run_bot() -> None:
    try:
        config = load_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    
    app = build_discord_app(config)
    await app.run()

def main() -> None:
    asyncio.run(run_bot())

if __name__ == '__main__':
    main()