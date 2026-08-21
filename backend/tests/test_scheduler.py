from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from libs.scheduler.timing import calculate_next_run, next_window_run


def test_daily_window_returns_next_slot_in_user_timezone():
    now = datetime(2026, 8, 19, 6, 10, tzinfo=timezone.utc)  # 10:10 Dubai
    next_run = next_window_run(now, "Asia/Dubai", "09:00", "17:00", 60)
    assert next_run == datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)  # 11:00 Dubai


def test_overnight_window_continues_after_midnight():
    now = datetime(2026, 8, 19, 21, 20, tzinfo=timezone.utc)  # 01:20 Dubai
    next_run = next_window_run(now, "Asia/Dubai", "22:00", "02:00", 30)
    assert next_run == datetime(2026, 8, 19, 21, 30, tzinfo=timezone.utc)  # 01:30 Dubai


def test_one_time_schedule_rejects_past_time():
    with pytest.raises(ValueError, match="future"):
        calculate_next_run(
            mode="once",
            now_utc=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc),
            run_at=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_schedule_api_persists_and_lists_next_run(client: AsyncClient):
    created = await client.post(
        "/api/workflows/from-text",
        json={"text": "Research AI developments and summarize them"},
    )
    workflow = created.json()["workflow"]
    response = await client.put(
        f"/api/workflows/{workflow['id']}/schedule",
        json={
            "mode": "once",
            "enabled": True,
            "input_text": "Research the latest release",
            "timezone": "Asia/Dubai",
            "run_at": "2099-08-20T05:00:00Z",
        },
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["next_run_at"]

    listing = await client.get("/api/workflows")
    summary = next(item for item in listing.json()["workflows"] if item["id"] == workflow["id"])
    assert summary["schedule_enabled"] is True
    assert summary["schedule_mode"] == "once"
    assert summary["next_run_at"]

    deleted = await client.delete(f"/api/workflows/{workflow['id']}/schedule")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
