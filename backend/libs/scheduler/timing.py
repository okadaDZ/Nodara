from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_clock(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid time '{value}'. Use HH:MM.") from exc


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{name}'.") from exc


def next_window_run(
    now_utc: datetime,
    timezone_name: str,
    window_start: str,
    window_end: str,
    interval_minutes: int,
) -> datetime:
    zone = resolve_timezone(timezone_name)
    now_local = utc_aware(now_utc).astimezone(zone)
    start_clock = parse_clock(window_start)
    end_clock = parse_clock(window_end)

    candidates: list[datetime] = []
    for day_offset in (-1, 0, 1, 2):
        day = now_local.date() + timedelta(days=day_offset)
        start = datetime.combine(day, start_clock, tzinfo=zone)
        end = datetime.combine(day, end_clock, tzinfo=zone)
        if end <= start:
            end += timedelta(days=1)
        if now_local < start:
            candidate = start
        else:
            elapsed = (now_local - start).total_seconds() / 60
            steps = max(0, math.floor(elapsed / interval_minutes) + 1)
            candidate = start + timedelta(minutes=steps * interval_minutes)
        if candidate <= end and candidate > now_local:
            candidates.append(candidate)

    if not candidates:
        raise ValueError("Could not calculate the next window occurrence.")
    return min(candidates).astimezone(timezone.utc)


def calculate_next_run(
    *,
    mode: str,
    now_utc: datetime,
    run_at: datetime | None = None,
    timezone_name: str = "UTC",
    window_start: str | None = None,
    window_end: str | None = None,
    interval_minutes: int | None = None,
) -> datetime | None:
    if mode == "once":
        if run_at is None:
            raise ValueError("A one-time schedule requires run_at.")
        candidate = utc_aware(run_at)
        if candidate <= utc_aware(now_utc):
            raise ValueError("Choose a future date and time.")
        return candidate
    if mode == "window":
        if not window_start or not window_end or not interval_minutes:
            raise ValueError("A repeating window requires start, end, and interval.")
        return next_window_run(
            now_utc, timezone_name, window_start, window_end, interval_minutes
        )
    raise ValueError(f"Unsupported schedule mode '{mode}'.")
