from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from tinydb import Query, TinyDB


@dataclass(slots=True)
class BridgeMessageAttachmentMetadata:
    """Store attachment summary information for mirrored messages."""

    image_filename: Optional[str]
    notes: List[str]

    def to_record(self) -> dict:
        return {
            "image_filename": self.image_filename,
            "notes": list(self.notes),
        }

    @classmethod
    def from_record(cls, record: Optional[dict]) -> "BridgeMessageAttachmentMetadata":
        if not record:
            return cls(image_filename=None, notes=[])
        return cls(
            image_filename=record.get("image_filename"),
            notes=list(record.get("notes") or []),
        )


@dataclass(slots=True)
class BridgeMessageRecord:
    """Persist metadata required to synchronise bridge messages."""

    source_id: int
    destination_ids: List[int]
    profile_seed: str
    display_name: str
    avatar_url: str
    dicebear_failed: bool
    attachments: BridgeMessageAttachmentMetadata
    updated_at: datetime

    def to_record(self) -> dict:
        return {
            "source_id": self.source_id,
            "destination_ids": list(self.destination_ids),
            "profile_seed": self.profile_seed,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "dicebear_failed": self.dicebear_failed,
            "attachments": self.attachments.to_record(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: dict) -> "BridgeMessageRecord":
        return cls(
            source_id=int(record["source_id"]),
            destination_ids=[int(value) for value in record.get("destination_ids", [])],
            profile_seed=str(record.get("profile_seed", "")),
            display_name=str(record.get("display_name", "")),
            avatar_url=str(record.get("avatar_url", "")),
            dicebear_failed=bool(record.get("dicebear_failed", False)),
            attachments=BridgeMessageAttachmentMetadata.from_record(record.get("attachments")),
            updated_at=_parse_datetime(record.get("updated_at")),
        )


class BridgeMessageStore:
    """Persist bridge message metadata for later synchronisation."""

    def __init__(self, db: TinyDB, table_name: str = "bridge_messages") -> None:
        self._table = db.table(table_name)
        self._query = Query()

    def upsert(
        self,
        *,
        source_id: int,
        destination_ids: Iterable[int],
        profile_seed: str,
        display_name: str,
        avatar_url: str,
        dicebear_failed: bool,
        attachments: BridgeMessageAttachmentMetadata,
    ) -> None:
        record = self.get(source_id)
        now = datetime.now(timezone.utc)
        if record is None:
            record = BridgeMessageRecord(
                source_id=source_id,
                destination_ids=list(dict.fromkeys(int(i) for i in destination_ids)),
                profile_seed=profile_seed,
                display_name=display_name,
                avatar_url=avatar_url,
                dicebear_failed=dicebear_failed,
                attachments=attachments,
                updated_at=now,
            )
        else:
            existing_ids = {int(i) for i in record.destination_ids}
            existing_ids.update(int(i) for i in destination_ids)
            record.destination_ids = sorted(existing_ids)
            record.profile_seed = profile_seed
            record.display_name = display_name
            record.avatar_url = avatar_url
            record.dicebear_failed = dicebear_failed
            record.attachments = attachments
            record.updated_at = now

        self._table.upsert(record.to_record(), self._query.source_id == record.source_id)

    def get(self, source_id: int) -> Optional[BridgeMessageRecord]:
        stored = self._table.get(self._query.source_id == int(source_id))
        if stored is None:
            return None
        return BridgeMessageRecord.from_record(stored)

    def update_metadata(
        self,
        *,
        source_id: int,
        attachments: Optional[BridgeMessageAttachmentMetadata] = None,
    ) -> None:
        record = self.get(source_id)
        if record is None:
            return

        if attachments is not None:
            record.attachments = attachments
        record.updated_at = datetime.now(timezone.utc)
        self._table.update(record.to_record(), self._query.source_id == record.source_id)

    def delete(self, source_id: int) -> bool:
        removed = self._table.remove(self._query.source_id == int(source_id))
        return bool(removed)

    def remove_destination(self, destination_id: int) -> None:
        stored = self._table.get(
            self._query.destination_ids.test(
                lambda values: destination_id in set(int(v) for v in values or [])
            )
        )
        if stored is None:
            return
        record = BridgeMessageRecord.from_record(stored)
        record.destination_ids = [value for value in record.destination_ids if value != destination_id]
        if record.destination_ids:
            record.updated_at = datetime.now(timezone.utc)
            self._table.update(record.to_record(), self._query.source_id == record.source_id)
        else:
            self.delete(record.source_id)

    def purge_older_than(self, *, threshold: datetime) -> int:
        cutoff_iso = threshold.isoformat()
        removed = self._table.remove(self._query.updated_at < cutoff_iso)
        return len(removed)


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


__all__ = [
    "BridgeMessageAttachmentMetadata",
    "BridgeMessageRecord",
    "BridgeMessageStore",
]
