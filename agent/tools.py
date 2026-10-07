"""Tool schemas used by evals. Runtime tools live on ReceptionistAgent (SDK internal tools)."""

from __future__ import annotations

from typing import Any

ANTHROPIC_TOOLS: list[dict[str, Any]] = [
    {
        "name": "take_message",
        "description": "Save the caller's name, reason, urgency (low/normal/urgent), and callback number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "reason": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "normal", "urgent"]},
                "callback_number": {"type": "string"},
            },
            "required": ["name", "reason", "urgency", "callback_number"],
        },
    },
    {
        "name": "flag_urgent",
        "description": "Send an immediate urgent alert. Use only for genuine urgency.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
    {
        "name": "check_availability",
        "description": "Read a mock calendar. Do not book or promise a time.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "end_call",
        "description": "End the call. reason: complete, spam, silence, abusive, unclear_audio, error.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


def normalize_urgency(value: str) -> str:
    v = (value or "normal").strip().lower()
    return v if v in {"low", "normal", "urgent"} else "normal"
