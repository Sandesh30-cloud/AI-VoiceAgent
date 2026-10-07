from __future__ import annotations

import json
from pathlib import Path

from agent.prompts import build_instructions
from config import Settings
from services.calendar import mock_availability
from services.call_state import CallState
from services.db import get_call, save_call
from services.notifier import format_summary


def test_take_message_state() -> None:
    state = CallState(call_id="c1")
    state.apply_message("Riya", "Need docs signed", "URGENT", "+91111")
    assert state.urgency == "urgent"
    assert state.callback_number == "+91111"


def test_mock_calendar_has_no_address() -> None:
    data = mock_availability()
    blob = json.dumps(data).lower()
    assert "address" not in blob
    assert "windows" in data


def test_db_roundtrip(tmp_path: Path) -> None:
    path = str(tmp_path / "calls.db")
    save_call(
        path,
        {
            "id": "abc",
            "caller": "Asha",
            "reason": "callback",
            "urgency": "normal",
            "callback": "+1",
            "transcript": [{"role": "user", "content": "hi"}],
            "duration_seconds": 12.5,
        },
    )
    row = get_call(path, "abc")
    assert row is not None
    assert row["caller"] == "Asha"
    assert "hi" in row["transcript"]


def test_summary_format() -> None:
    text = format_summary({"id": "x", "caller": "Sam", "urgency": "urgent"}, urgent=True)
    assert "URGENT" in text
    assert "Sam" in text


def test_prompt_guardrails() -> None:
    prompt = build_instructions(Settings())
    for needle in (
        "prompt injection",
        "Never reveal",
        "Never make commitments",
        "telemarketer",
        "take a message",
        "Hindi",
    ):
        assert needle in prompt
