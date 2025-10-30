from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import discord

from .profiles import BridgeProfile, BridgeProfileStore
from .routes import ChannelEndpoint, ChannelRoute


ATTACHMENT_LABELS = {
    "image": "(画像)",
    "video": "(動画)",
    "audio": "(音声)",
    "default": "(ファイル)",
}


@dataclass(slots=True)
class AttachmentBundle:
    files: List[discord.File]
    image_filename: Optional[str]
    notes: List[str]


@dataclass(slots=True)
class MirrorPayload:
    embed: Optional[discord.Embed]
    content: Optional[str]
    files: List[discord.File]


class ChannelBridgeManager:
    """Bridge messages and reactions across configured channel pairs."""

    def __init__(
        self,
        *,
        client: discord.Client,
        profile_store: BridgeProfileStore,
        routes: Sequence[ChannelRoute],
    ) -> None:
        self._client = client
        self._profile_store = profile_store
        self._routes_by_source: Dict[Tuple[int, int], List[ChannelRoute]] = {}
        self._message_links: Dict[int, Set[int]] = {}
        self._message_locations: Dict[int, Tuple[Optional[int], int]] = {}
        self._mirrored_message_ids: Set[int] = set()
        self._build_route_index(routes)

    def _build_route_index(self, routes: Sequence[ChannelRoute]) -> None:
        for route in routes:
            key = route.src.key()
            self._routes_by_source.setdefault(key, []).append(route)
        print(f"Loaded {len(routes)} channel bridge routes.")

    def get_routes_from_guild(self, guild_id: int) -> Sequence[ChannelRoute]:
        matches: List[ChannelRoute] = []
        for (src_guild_id, _), routes in self._routes_by_source.items():
            if src_guild_id == guild_id:
                matches.extend(routes)
        return list(matches)

    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.id in self._mirrored_message_ids:
            return

        key = (message.guild.id, message.channel.id)
        routes = self._routes_by_source.get(key)
        if not routes:
            return

        self._store_message_location(message)

        for route in routes:
            destination = await self._resolve_channel(route.dst)
            if destination is None:
                print(
                    f"Bridge destination not found for guild={route.dst.guild} "
                    f"channel={route.dst.channel}"
                )
                continue

            dicebear_failed = False
            try:
                profile = self._profile_store.get_profile(
                    seed=f"{message.id}-{route.dst.guild}-{route.dst.channel}"
                )
            except Exception as exc:  # noqa: BLE001
                dicebear_failed = True
                print(f"Failed to generate DiceBear profile for message {message.id}: {exc}")
                bot_user = self._client.user
                fallback_avatar = str(bot_user.display_avatar.url) if bot_user else ""
                profile = BridgeProfile(
                    seed="fallback",
                    display_name="仮想伝令",
                    avatar_url=fallback_avatar,
                )

            payload = await self._build_mirror_payload(
                source_message=message,
                profile=profile,
                dicebear_failed=dicebear_failed,
                target=route.dst,
            )

            if payload is None:
                continue

            send_kwargs = {
                "allowed_mentions": discord.AllowedMentions.none(),
            }
            if payload.files:
                send_kwargs["files"] = payload.files
            if payload.embed is not None:
                send_kwargs["embed"] = payload.embed
            if payload.content is not None:
                send_kwargs["content"] = payload.content

            try:
                mirrored = await destination.send(**send_kwargs)
            except discord.HTTPException as exc:
                print(f"Failed to bridge message {message.id} -> {destination.id}: {exc}")
                continue

            self._store_message_location(mirrored)
            self._link_messages(message.id, mirrored.id)
            self._mirrored_message_ids.add(mirrored.id)

    async def handle_reaction(
        self,
        reaction: discord.Reaction,
        user: discord.abc.User,
        *,
        add: bool,
    ) -> None:
        if user.bot:
            return

        message = reaction.message
        self._store_message_location(message)

        linked_ids = list(self._message_links.get(message.id, ()))
        if not linked_ids:
            return

        for linked_id in linked_ids:
            channel = await self._resolve_channel_for_message(linked_id)
            if channel is None:
                self._unlink_messages(message.id, linked_id)
                continue

            try:
                target_message = await channel.fetch_message(linked_id)
            except discord.NotFound:
                self._unlink_messages(message.id, linked_id)
                continue
            except discord.HTTPException as exc:
                print(f"Failed to fetch bridged message {linked_id}: {exc}")
                continue

            try:
                if add:
                    await target_message.add_reaction(reaction.emoji)
                else:
                    bot_user = self._client.user
                    if bot_user is None:
                        continue
                    await target_message.remove_reaction(reaction.emoji, bot_user)
            except discord.HTTPException as exc:
                print(f"Failed to sync reaction for message {linked_id}: {exc}")

    def handle_message_delete(self, message_id: int) -> None:
        linked_ids = self._message_links.pop(message_id, set())
        for linked_id in linked_ids:
            peers = self._message_links.get(linked_id)
            if peers:
                peers.discard(message_id)
                if not peers:
                    self._message_links.pop(linked_id, None)
        self._message_locations.pop(message_id, None)
        self._mirrored_message_ids.discard(message_id)

    def _link_messages(self, source_id: int, target_id: int) -> None:
        self._message_links.setdefault(source_id, set()).add(target_id)
        self._message_links.setdefault(target_id, set()).add(source_id)

    def _unlink_messages(self, message_a: int, message_b: int) -> None:
        peers = self._message_links.get(message_a)
        if peers:
            peers.discard(message_b)
            if not peers:
                self._message_links.pop(message_a, None)

        peers = self._message_links.get(message_b)
        if peers:
            peers.discard(message_a)
            if not peers:
                self._message_links.pop(message_b, None)

        if message_a not in self._message_links:
            self._message_locations.pop(message_a, None)
            self._mirrored_message_ids.discard(message_a)
        if message_b not in self._message_links:
            self._message_locations.pop(message_b, None)
            self._mirrored_message_ids.discard(message_b)

    def _store_message_location(self, message: discord.Message) -> None:
        guild_id = message.guild.id if message.guild else None
        self._message_locations[message.id] = (guild_id, message.channel.id)

    async def _resolve_channel(self, endpoint: ChannelEndpoint) -> Optional[discord.abc.Messageable]:
        channel = self._client.get_channel(endpoint.channel)
        if channel is not None:
            return channel  # type: ignore[return-value]
        try:
            fetched = await self._client.fetch_channel(endpoint.channel)
        except discord.HTTPException as exc:
            print(
                f"Failed to fetch destination channel guild={endpoint.guild} "
                f"channel={endpoint.channel}: {exc}"
            )
            return None
        return fetched  # type: ignore[return-value]

    async def _resolve_channel_for_message(self, message_id: int) -> Optional[discord.abc.Messageable]:
        location = self._message_locations.get(message_id)
        if location is None:
            return None
        _, channel_id = location
        channel = self._client.get_channel(channel_id)
        if channel is not None:
            return channel  # type: ignore[return-value]
        try:
            return await self._client.fetch_channel(channel_id)  # type: ignore[return-value]
        except discord.HTTPException as exc:
            print(f"Failed to fetch channel for message {message_id}: {exc}")
            return None

    async def _build_mirror_payload(
        self,
        *,
        source_message: discord.Message,
        profile: BridgeProfile,
        dicebear_failed: bool,
        target: ChannelEndpoint,
    ) -> Optional[MirrorPayload]:
        attachments = await self._prepare_attachments(source_message.attachments)
        body_lines: List[str] = []

        if source_message.reference:
            reference_line = self._format_reference(source_message, target=target)
            if reference_line:
                body_lines.append(reference_line)

        if dicebear_failed:
            body_lines.append("(DiceBear生成失敗)")

        if source_message.stickers:
            for sticker in source_message.stickers:
                body_lines.append(f"(ステッカー: {sticker.name})")

        body_lines.extend(attachments.notes)

        description = "\n".join(filter(None, body_lines)).strip()

        if not description:
            description = None

        title_text = f"> {source_message.content}" or "(空メッセージ)"
        if len(title_text) > 256:
            title_ellipsis = "..."
            title_text = title_text[: 256 - len(title_ellipsis)] + title_ellipsis

        embed: Optional[discord.Embed] = None
        content: Optional[str] = None

        if len(title_text) <= 256:
            embed = discord.Embed(title=title_text, colour=discord.Colour.blurple())
            if description is not None:
                embed.description = description
            embed.set_author(name=profile.display_name, icon_url=profile.avatar_url)
        else:
            embed = None
            truncated_description = description or ""
            if len(truncated_description) > 1900:
                truncated_description = truncated_description[:1870] + "\n...(省略)"
            content_lines: List[str] = [profile.display_name, title_text]
            if truncated_description:
                content_lines.append(truncated_description)
            content = "\n".join(content_lines)

        if embed is not None:
            if attachments.image_filename:
                embed.set_image(url=f"attachment://{attachments.image_filename}")

        return MirrorPayload(
            embed=embed,
            content=content,
            files=attachments.files,
        )

    async def _prepare_attachments(
        self,
        attachments: Iterable[discord.Attachment],
    ) -> AttachmentBundle:
        files: List[discord.File] = []
        notes: List[str] = []
        image_filename: Optional[str] = None

        for attachment in attachments:
            label = self._attachment_label(attachment)
            try:
                file = await attachment.to_file()
            except discord.HTTPException as exc:
                print(f"Failed to copy attachment {attachment.filename}: {exc}")
                notes.append(f"(添付取得失敗: {attachment.filename})")
                continue

            files.append(file)

            if image_filename is None and label == ATTACHMENT_LABELS["image"]:
                image_filename = file.filename
            else:
                notes.append(f"{label} {attachment.url}")

        return AttachmentBundle(files=files, image_filename=image_filename, notes=notes)

    def _attachment_label(self, attachment: discord.Attachment) -> str:
        content_type = (attachment.content_type or "").lower()
        if content_type.startswith("image"):
            return ATTACHMENT_LABELS["image"]
        if content_type.startswith("video"):
            return ATTACHMENT_LABELS["video"]
        if content_type.startswith("audio"):
            return ATTACHMENT_LABELS["audio"]
        return ATTACHMENT_LABELS["default"]

    def _format_reference(self, message: discord.Message, *, target: ChannelEndpoint) -> Optional[str]:
        ref = message.reference
        if ref is None:
            return None

        if ref.resolved and isinstance(ref.resolved, discord.Message):
            referenced_id = ref.resolved.id
            jump_url = ref.resolved.jump_url
        else:
            if ref.guild_id is None or ref.channel_id is None or ref.message_id is None:
                return None
            referenced_id = ref.message_id
            jump_url = f"https://discord.com/channels/{ref.guild_id}/{ref.channel_id}/{ref.message_id}"

        remapped = self._remap_reference_jump_url(referenced_id=referenced_id, target=target)
        effective_url = remapped or jump_url

        return f"▶ Reply to {effective_url}"

    def _remap_reference_jump_url(
        self,
        *,
        referenced_id: int,
        target: ChannelEndpoint,
    ) -> Optional[str]:
        target_key = (target.guild, target.channel)

        location = self._message_locations.get(referenced_id)
        if location == target_key:
            return f"https://discord.com/channels/{target.guild}/{target.channel}/{referenced_id}"

        linked_ids = self._message_links.get(referenced_id)
        if not linked_ids:
            return None

        for linked_id in linked_ids:
            location = self._message_locations.get(linked_id)
            if location == target_key:
                return f"https://discord.com/channels/{target.guild}/{target.channel}/{linked_id}"

        return None
