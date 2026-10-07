"""Calendar service."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone


def mock_availability(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    windows = []
    cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for _ in range(4):
        busy = cursor.hour in {10, 14, 16}
        windows.append(
            {
                "start": cursor.isoformat(),
                "end": (cursor + timedelta(hours=1)).isoformat(),
                "status": "busy" if busy else "free",
            }
        )
        cursor += timedelta(hours=2)
    return {
        "timezone": "UTC",
        "note": "Mock calendar. Do not confirm meetings. Owner will follow up.",
        "windows": windows,
    }
