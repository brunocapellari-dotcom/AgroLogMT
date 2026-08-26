from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Iterator
from typing import Any

from collector.ais_stream import build_subscription, parse_aisstream_message


AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"


def stream_once(
    *,
    api_key: str,
    bounding_boxes: list[list[list[float]]],
    mmsi_filter: list[str] | None = None,
    max_messages: int | None = None,
    url: str = AISSTREAM_URL,
) -> Iterator[dict[str, Any]]:
    """Open one AISStream connection and yield normalized AIS records.

    The service requires a complete subscription shortly after connect. The
    websocket library negotiates permessage-deflate by default, matching the
    service recommendation for compressed connections.
    """
    try:
        from websockets.sync.client import connect
    except ImportError as exc:  # pragma: no cover - deployment/runtime guard
        raise RuntimeError("instale websockets>=15,<16 para AIS live") from exc

    subscription = build_subscription(api_key, bounding_boxes, mmsi_filter)
    count = 0
    with connect(url, compression="deflate", open_timeout=15, close_timeout=5) as ws:
        ws.send(json.dumps(subscription, separators=(",", ":")))
        for frame in ws:
            if isinstance(frame, bytes):
                frame = frame.decode("utf-8")
            payload = json.loads(frame)
            if payload.get("MessageType") == "SubscriptionConfirmation":
                continue
            row = parse_aisstream_message(payload)
            if row is None:
                continue
            yield row
            count += 1
            if max_messages is not None and count >= max_messages:
                return


def run_forever(
    *,
    api_key: str,
    bounding_boxes: list[list[list[float]]],
    on_record: Callable[[dict[str, Any]], None],
    mmsi_filter: list[str] | None = None,
    stop_after_records: int | None = None,
    base_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 60.0,
) -> int:
    """Reconnect indefinitely with exponential backoff and jitter.

    Returns the number of records delivered when stop_after_records is used.
    Exceptions from the callback are not swallowed because persistence failures
    must be visible instead of silently dropping observations.
    """
    delivered = 0
    failures = 0
    while stop_after_records is None or delivered < stop_after_records:
        try:
            remaining = None if stop_after_records is None else stop_after_records - delivered
            for row in stream_once(
                api_key=api_key,
                bounding_boxes=bounding_boxes,
                mmsi_filter=mmsi_filter,
                max_messages=remaining,
            ):
                on_record(row)
                delivered += 1
            failures = 0
        except (OSError, TimeoutError, ConnectionError, json.JSONDecodeError):
            failures += 1
            delay = min(max_backoff_seconds, base_backoff_seconds * (2 ** min(failures - 1, 8)))
            time.sleep(delay * (0.75 + random.random() * 0.5))
    return delivered
