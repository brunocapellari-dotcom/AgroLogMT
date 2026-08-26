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
    max_seconds: float | None = None,
    url: str = AISSTREAM_URL,
) -> Iterator[dict[str, Any]]:
    """Open one AISStream connection and yield normalized AIS records.

    Raw JSON is attached because the upstream service has no durable replay.
    max_seconds allows bounded capture windows suitable for scheduled Cloud Run
    jobs while preserving reconnect behavior between windows.
    """
    try:
        from websockets.sync.client import connect
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("instale websockets>=15,<16 para AIS live") from exc

    subscription = build_subscription(api_key, bounding_boxes, mmsi_filter)
    count = 0
    deadline = time.monotonic() + max_seconds if max_seconds is not None else None
    with connect(url, compression="deflate", open_timeout=15, close_timeout=5) as ws:
        ws.send(json.dumps(subscription, separators=(",", ":")))
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                return
            timeout = None
            if deadline is not None:
                timeout = max(0.1, min(5.0, deadline - time.monotonic()))
            try:
                frame = ws.recv(timeout=timeout)
            except TimeoutError:
                if deadline is not None and time.monotonic() >= deadline:
                    return
                continue
            if frame is None:
                return
            if isinstance(frame, bytes):
                frame = frame.decode("utf-8")
            payload = json.loads(frame)
            if payload.get("MessageType") == "SubscriptionConfirmation":
                continue
            row = parse_aisstream_message(payload)
            if row is None:
                continue
            row["_raw_message"] = payload
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
    stop_after_seconds: float | None = None,
    base_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 60.0,
) -> int:
    """Reconnect with exponential backoff until record/time limit is reached."""
    delivered = 0
    failures = 0
    overall_deadline = time.monotonic() + stop_after_seconds if stop_after_seconds is not None else None
    while stop_after_records is None or delivered < stop_after_records:
        if overall_deadline is not None and time.monotonic() >= overall_deadline:
            break
        remaining_records = None if stop_after_records is None else stop_after_records - delivered
        remaining_seconds = None if overall_deadline is None else max(0.0, overall_deadline - time.monotonic())
        try:
            for row in stream_once(
                api_key=api_key,
                bounding_boxes=bounding_boxes,
                mmsi_filter=mmsi_filter,
                max_messages=remaining_records,
                max_seconds=remaining_seconds,
            ):
                on_record(row)
                delivered += 1
            failures = 0
        except (OSError, TimeoutError, ConnectionError, json.JSONDecodeError):
            failures += 1
            delay = min(max_backoff_seconds, base_backoff_seconds * (2 ** min(failures - 1, 8)))
            if overall_deadline is not None:
                delay = min(delay, max(0.0, overall_deadline - time.monotonic()))
            if delay <= 0:
                break
            time.sleep(delay * (0.75 + random.random() * 0.5))
    return delivered
