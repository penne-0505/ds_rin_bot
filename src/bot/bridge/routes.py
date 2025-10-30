from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True, slots=True)
class ChannelEndpoint:
    guild: int
    channel: int

    @classmethod
    def from_payload(cls, payload: dict) -> "ChannelEndpoint":
        return cls(
            guild=int(payload["guild"]),
            channel=int(payload["channel"]),
        )

    def key(self) -> tuple[int, int]:
        return (self.guild, self.channel)


@dataclass(frozen=True, slots=True)
class ChannelRoute:
    src: ChannelEndpoint
    dst: ChannelEndpoint


DEFAULT_ROUTE_SAMPLE = [
    {
        "src": {"guild": 111111111111111111, "channel": 222222222222222222},
        "dst": {"guild": 333333333333333333, "channel": 444444444444444444},
    },
    {
        "src": {"guild": 333333333333333333, "channel": 444444444444444444},
        "dst": {"guild": 111111111111111111, "channel": 222222222222222222},
    },
]


def load_channel_routes(path: Path) -> Sequence[ChannelRoute]:
    """Load channel routing configuration, creating a sample file if missing."""

    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text(
            json.dumps(DEFAULT_ROUTE_SAMPLE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Channel routing configuration not found. Sample created at: {path}")
        return ()

    try:
        payload: Iterable[dict] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse channel routing configuration ({path}): {exc}") from exc

    routes: List[ChannelRoute] = []
    for entry in payload:
        try:
            src = ChannelEndpoint.from_payload(entry["src"])
            dst = ChannelEndpoint.from_payload(entry["dst"])
        except (KeyError, TypeError, ValueError) as exc:
            print(f"Invalid route entry skipped: {entry} ({exc})")
            continue
        
        print(f"Loaded channel route: {src} -> {dst}")
        
        routes.append(ChannelRoute(src=src, dst=dst))

    return routes
