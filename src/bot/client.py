import discord

class BotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents | None = None) -> None:
        super().__init__(intents=intents or discord.Intents.all())
        self.tree = discord.app_commands.CommandTree(self)
    
    async def on_ready(self) -> None:
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.tree.sync()
        print("Bot is ready and command tree synced.")
