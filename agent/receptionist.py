from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from videosdk.agents import Agent, AgentSession, JobContext, function_tool

from agent.prompts import FALLBACK_SPOKEN_MESSAGE, GREETING, build_instructions
from config import Settings
from services.calendar import mock_availability
from services.call_state import CallState
from services.db import save_call
from services.metrics import CallMetrics
from services.notifier import notify

logger = logging.getLogger(__name__)


class ReceptionistAgent(Agent):
    def __init__(
        self,
        settings: Settings,
        state: CallState,
        metrics: CallMetrics,
        ctx: JobContext | None = None,
    ) -> None:
        super().__init__(instructions=build_instructions(settings))
        self.settings = settings
        self.state = state
        self.metrics = metrics
        self.ctx = ctx
        self._finalized = False
        self._fallback_spoken = False

    def _log(self, message: str, **extra: Any) -> None:
        logger.info(message, extra={"call_id": self.state.call_id, **extra})

    async def on_enter(self) -> None:
        room_id = None
        if self.ctx is not None:
            room_options = getattr(self.ctx, "room_options", None)
            room_id = getattr(room_options, "room_id", None)
            room = getattr(self.ctx, "room", None)
            room_id = getattr(room, "id", None) or room_id
        if room_id:
            self.state.call_id = str(room_id)
            self.metrics.call_id = str(room_id)
        greeting = GREETING.format(owner=self.settings.owner_name)
        self.metrics.add_tts_chars(greeting)
        self._log("call_started")
        await self.session.say(greeting)

    async def on_exit(self) -> None:
        await self.finalize(ended_reason=self.state.ended_reason or "session_exit")

    def mark_provider_error(self, _data: dict | None = None) -> None:
        self.state.provider_error = True
        if self.session and not self._fallback_spoken:
            self._fallback_spoken = True
            asyncio.create_task(self._say_fallback())

    async def _say_fallback(self) -> None:
        try:
            if self.session:
                await self.session.say(FALLBACK_SPOKEN_MESSAGE)
                self.metrics.add_tts_chars(FALLBACK_SPOKEN_MESSAGE)
        except Exception:
            logger.exception(
                "fallback_say_failed", extra={"call_id": self.state.call_id}
            )

    async def handle_silence(self) -> None:
        self.state.silence_prompts += 1
        if self.state.silence_prompts <= self.settings.silence_reprompt_limit:
            prompt = "Are you still there? Please tell me your name."
            self.metrics.add_tts_chars(prompt)
            await self.session.say(prompt)
            return
        goodbye = "I didn't hear anything, so I'll end the call. Goodbye."
        self.metrics.add_tts_chars(goodbye)
        await self.session.say(goodbye)
        await self.end_call("silence")

    @function_tool
    async def take_message(
        self,
        name: str,
        reason: str,
        urgency: str,
        callback_number: str,
    ) -> dict:
        """Save the caller's name, reason, urgency (low/normal/urgent), and callback number."""
        self.state.apply_message(name, reason, urgency, callback_number)
        self._log(
            "message_captured",
            metrics=self.state.to_summary_fields(),
        )
        if self.state.urgency == "urgent" and not self.state.urgent_alerted:
            await self.flag_urgent(
                f"{name}: {reason} (callback {callback_number})"
            )
        return {"status": "saved", **self.state.to_summary_fields()}

    @function_tool
    async def flag_urgent(self, summary: str) -> dict:
        """Send an immediate urgent alert to Sandesh. Use only for genuine urgency."""
        if self.state.urgent_alerted:
            return {"status": "already_alerted"}
        self.state.urgent_alerted = True
        self.state.captured_anything = True
        payload = {
            "id": self.state.call_id,
            **self.state.to_summary_fields(),
            "reason": self.state.reason or summary,
            "urgency": "urgent",
            "ended_reason": "urgent_alert",
        }
        try:
            await notify(self.settings, payload, urgent=True)
        except Exception:
            logger.exception(
                "urgent_notify_failed", extra={"call_id": self.state.call_id}
            )
            return {"status": "alert_failed", "summary": summary}
        return {"status": "alerted", "summary": summary}

    @function_tool
    async def check_availability(self) -> dict:
        """Read a mock calendar. Do not book or promise a time."""
        return mock_availability()

    @function_tool
    async def end_call(self, reason: str = "complete") -> dict:
        """End the call after a short goodbye. reason: complete, spam, silence, abusive, unclear_audio, error."""
        self.state.ended_reason = reason
        if reason == "spam":
            self.state.is_spam = True
        asyncio.create_task(self._announce_and_hangup(reason))
        return {"status": "ending_call", "reason": reason}

    async def _announce_and_hangup(self, reason: str) -> None:
        if not self.session:
            return
        try:
            self.session.interrupt()
            await asyncio.sleep(0.4)
            if reason == "spam":
                line = "I'm not able to help with sales calls. Goodbye."
            elif reason == "abusive":
                line = "I'll note that you called. Goodbye."
            elif self.state.provider_error:
                line = FALLBACK_SPOKEN_MESSAGE
            else:
                line = "Thanks, I'll pass this on. Goodbye."
            self.metrics.add_tts_chars(line)
            handle = await self.session.say(line, interruptible=False)
            if handle is not None:
                await handle
            await asyncio.sleep(0.6)
        except Exception:
            logger.exception("hangup_announce_failed", extra={"call_id": self.state.call_id})
        try:
            await self.finalize(ended_reason=reason)
        finally:
            try:
                await self.hangup()
            except Exception:
                logger.exception("hangup_failed", extra={"call_id": self.state.call_id})
                if self.session:
                    await self.session.close()

    async def finalize(self, ended_reason: str) -> None:
        if self._finalized:
            return
        self._finalized = True
        self.state.ended_reason = ended_reason
        history: list[dict[str, Any]] = []
        if self.session:
            try:
                history = self.session.get_context_history(
                    include_function_calls=True,
                    include_system_messages=False,
                )
            except Exception:
                logger.exception(
                    "transcript_read_failed", extra={"call_id": self.state.call_id}
                )
        metrics_dict = self.metrics.as_dict(self.settings)
        summary = {
            "id": self.state.call_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "caller": self.state.caller_name,
            "reason": self.state.reason,
            "urgency": self.state.urgency,
            "callback": self.state.callback_number,
            "transcript": history,
            "duration": metrics_dict["duration_seconds"],
            "duration_seconds": metrics_dict["duration_seconds"],
            "metrics": metrics_dict,
            "estimated_cost_usd": metrics_dict["estimated_cost_usd"],
            "ended_reason": ended_reason,
            "is_spam": self.state.is_spam,
            "provider_error": self.state.provider_error,
        }
        try:
            save_call(self.settings.sqlite_path, summary)
        except Exception:
            logger.exception("db_save_failed", extra={"call_id": self.state.call_id})
        try:
            await notify(self.settings, summary, urgent=False)
        except Exception:
            logger.exception("summary_notify_failed", extra={"call_id": self.state.call_id})
        self._log("call_finalized", metrics=metrics_dict)


def bind_session(
    agent: ReceptionistAgent,
    session: AgentSession,
) -> None:
    async def on_wake_up() -> None:
        await agent.handle_silence()

    session.on_wake_up = on_wake_up
