from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CallMetrics:
    call_id: str
    started_at: float = field(default_factory=time.monotonic)
    stt_latencies_ms: list[float] = field(default_factory=list)
    llm_ttft_ms: list[float] = field(default_factory=list)
    llm_duration_ms: list[float] = field(default_factory=list)
    tts_ttfb_ms: list[float] = field(default_factory=list)
    tts_latency_ms: list[float] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    realtime_input_tokens: int = 0
    realtime_output_tokens: int = 0
    tts_chars: int = 0

    def duration_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def record_stt(self, metrics: dict[str, Any]) -> None:
        value = metrics.get("stt_latency")
        if value is not None:
            self.stt_latencies_ms.append(float(value))
        self._log_component("stt", metrics)

    def record_llm(self, metrics: dict[str, Any]) -> None:
        if metrics.get("llm_ttft") is not None:
            self.llm_ttft_ms.append(float(metrics["llm_ttft"]))
        if metrics.get("llm_duration") is not None:
            self.llm_duration_ms.append(float(metrics["llm_duration"]))
        self.prompt_tokens += int(metrics.get("prompt_tokens") or 0)
        self.completion_tokens += int(metrics.get("completion_tokens") or 0)
        self._log_component("llm", metrics)

    def record_tts(self, metrics: dict[str, Any]) -> None:
        if metrics.get("ttfb") is not None:
            self.tts_ttfb_ms.append(float(metrics["ttfb"]))
        if metrics.get("tts_latency") is not None:
            self.tts_latency_ms.append(float(metrics["tts_latency"]))
        self._log_component("tts", metrics)

    def record_realtime(self, metrics: dict[str, Any]) -> None:
        self.realtime_input_tokens += int(metrics.get("realtime_input_tokens") or 0)
        self.realtime_output_tokens += int(metrics.get("realtime_output_tokens") or 0)
        self._log_component("realtime", metrics)

    def record_eou(self, metrics: dict[str, Any]) -> None:
        self._log_component("eou", metrics)

    def add_tts_chars(self, text: str) -> None:
        self.tts_chars += len(text)

    def estimated_cost_usd(self, settings: Settings) -> float:
        llm_in = (self.prompt_tokens + self.realtime_input_tokens) / 1_000_000
        llm_out = (self.completion_tokens + self.realtime_output_tokens) / 1_000_000
        minutes = self.duration_seconds() / 60.0
        tts = self.tts_chars / 1000.0
        return round(
            llm_in * settings.cost_llm_input_per_million
            + llm_out * settings.cost_llm_output_per_million
            + minutes * settings.cost_stt_per_minute
            + tts * settings.cost_tts_per_1k_chars,
            6,
        )

    def as_dict(self, settings: Settings) -> dict[str, Any]:
        def avg(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 2) if values else None

        return {
            "call_id": self.call_id,
            "duration_seconds": round(self.duration_seconds(), 2),
            "stt_latency_ms_avg": avg(self.stt_latencies_ms),
            "llm_ttft_ms_avg": avg(self.llm_ttft_ms),
            "llm_duration_ms_avg": avg(self.llm_duration_ms),
            "tts_ttfb_ms_avg": avg(self.tts_ttfb_ms),
            "tts_latency_ms_avg": avg(self.tts_latency_ms),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "realtime_input_tokens": self.realtime_input_tokens,
            "realtime_output_tokens": self.realtime_output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd(settings),
        }

    def _log_component(self, component: str, metrics: dict[str, Any]) -> None:
        logger.info(
            "component_metrics",
            extra={"call_id": self.call_id, "component": component, "metrics": metrics},
        )
