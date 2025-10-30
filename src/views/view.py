import discord

class SendModalView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(_SendModalButton())


class _SendModalButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="メッセージ送信", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SendMessageModal())


class SendMessageModal(discord.ui.Modal, title="メッセージ送信"):
    channel_id = discord.ui.TextInput(label="チャンネルID", placeholder="送信先チャンネルのIDを入力", required=True)
    message = discord.ui.TextInput(label="本文", style=discord.TextStyle.paragraph, placeholder="メッセージ内容を入力", required=True)

    ERROR_INVALID_ID = "チャンネルIDは有効な整数である必要があります。"
    ERROR_CHANNEL_NOT_FOUND = "チャンネルが見つかりません。Botがアクセスできるか確認してください。"
    SUCCESS_MESSAGE = "<#{channel_id}> にメッセージを送信しました。"
    ERROR_GENERAL = "エラー: {error}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            channel_id_int = int(self.channel_id.value)
        except ValueError:
            await interaction.response.send_message(self.ERROR_INVALID_ID, ephemeral=True)
            return

        try:
            channel = interaction.client.get_channel(channel_id_int)
            if channel is None:
                await interaction.response.send_message(self.ERROR_CHANNEL_NOT_FOUND, ephemeral=True)
                return

            await channel.send(self.message.value)
            await interaction.response.send_message(self.SUCCESS_MESSAGE.format(channel_id=channel.id), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(self.ERROR_GENERAL.format(error=str(e)), ephemeral=True)