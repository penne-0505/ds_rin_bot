from __future__ import annotations

import logging

import discord
from discord.abc import Messageable

LOGGER = logging.getLogger(__name__)


class SendModalView(discord.ui.View):
    """セットアップメッセージに添付される送信モーダル用ビュー。"""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(_SendModalButton())


class _SendModalButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="メッセージ送信", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        await interaction.response.send_modal(SendMessageModal())


class SendMessageModal(discord.ui.Modal, title="メッセージ送信"):
    channel_id = discord.ui.TextInput(label="チャンネルID", placeholder="送信先チャンネルのIDを入力", required=True)
    message = discord.ui.TextInput(
        label="本文",
        style=discord.TextStyle.paragraph,
        placeholder="メッセージ内容を入力",
        required=True,
    )

    ERROR_INVALID_ID = "チャンネルIDは有効な整数である必要があります。"
    ERROR_CHANNEL_NOT_FOUND = "チャンネルが見つかりません。Botがアクセスできるか確認してください。"
    SUCCESS_MESSAGE = "<#{channel_id}> にメッセージを送信しました。"
    ERROR_GENERAL = "エラー: {error}"

    async def on_submit(self, interaction: discord.Interaction) -> None:  # pragma: no cover - UI コールバック
        try:
            channel_id_int = int(self.channel_id.value)
        except ValueError:
            await interaction.response.send_message(self.ERROR_INVALID_ID, ephemeral=True)
            return

        try:
            channel = interaction.client.get_channel(channel_id_int)
            if channel is None:
                try:
                    channel = await interaction.client.fetch_channel(channel_id_int)
                except discord.NotFound:
                    await interaction.response.send_message(self.ERROR_CHANNEL_NOT_FOUND, ephemeral=True)
                    return
                except discord.HTTPException as exc:
                    await interaction.response.send_message(
                        self.ERROR_GENERAL.format(error=str(exc)),
                        ephemeral=True,
                    )
                    return

            if not isinstance(channel, Messageable):
                await interaction.response.send_message(self.ERROR_CHANNEL_NOT_FOUND, ephemeral=True)
                return

            await channel.send(self.message.value)
            await interaction.response.send_message(
                self.SUCCESS_MESSAGE.format(channel_id=channel.id),
                ephemeral=True,
            )
        except Exception as exc:  # pragma: no cover - 想定外エラーの通知
            LOGGER.exception("モーダル送信処理中にエラーが発生しました。")
            await interaction.response.send_message(
                self.ERROR_GENERAL.format(error=str(exc)),
                ephemeral=True,
            )


__all__ = ["SendModalView"]
