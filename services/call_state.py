from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Urgency = Literal["low", "normal", "urgent"]


@dataclass
class CallState:
    call_id: str
    caller_name: str | None = None
    reason: str | None = None
    urgency: Urgency | None = None
    callback_number: str | None = None
    is_spam: bool = False
    ended_reason: str | None = None
    urgent_alerted: bool = False
    silence_prompts: int = 0
    provider_error: bool = False
    captured_anything: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def apply_message(
        self,
        name: str,
        reason: str,
        urgency: str,
        callback_number: str,
    ) -> None:
        normalized = urgency.strip().lower()
        if normalized not in ("low", "normal", "urgent"):
            normalized = "normal"
        self.caller_name = name.strip()
        self.reason = reason.strip()
        self.urgency = normalized  # type: ignore[assignment]
        self.callback_number = callback_number.strip()
        self.captured_anything = True

    def to_summary_fields(self) -> dict[str, Any]:
        return {
            "caller": self.caller_name,
            "reason": self.reason,
            "urgency": self.urgency,
            "callback": self.callback_number,
        }
