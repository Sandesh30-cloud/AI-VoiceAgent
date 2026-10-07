from __future__ import annotations

import logging
import os

from videosdk.agents import FallbackLLM, FallbackSTT, FallbackTTS, InterruptConfig, Pipeline

from config import Settings
from services.metrics import CallMetrics

logger = logging.getLogger(__name__)


def _cascade_pipeline(settings: Settings) -> Pipeline:
    from videosdk.agents.plugins import (
        AnthropicLLM,
        DeepgramSTT,
        ElevenLabsTTS,
        SileroVAD,
        TurnDetector,
    )

    stt_primary = DeepgramSTT(
        model=settings.deepgram_model,
        language=settings.deepgram_language,
    )
    llm_primary = AnthropicLLM(model=settings.anthropic_model)
    tts_kwargs: dict = {"model": settings.elevenlabs_model}
    if settings.elevenlabs_voice_id:
        tts_kwargs["voice_id"] = settings.elevenlabs_voice_id
    tts_primary = ElevenLabsTTS(**tts_kwargs)

    stt = stt_primary
    llm = llm_primary
    tts = tts_primary

    if settings.openai_api_key:
        from videosdk.agents.plugins import OpenAILLM, OpenAISTT

        stt = FallbackSTT(
            [stt_primary, OpenAISTT()],
            temporary_disable_sec=30.0,
            permanent_disable_after_attempts=3,
        )
        llm = FallbackLLM(
            [llm_primary, OpenAILLM(model=settings.openai_llm_model)],
            temporary_disable_sec=30.0,
            permanent_disable_after_attempts=3,
        )
    if settings.google_api_key:
        from videosdk.agents.plugins import GoogleTTS

        tts = FallbackTTS(
            [tts_primary, GoogleTTS()],
            temporary_disable_sec=30.0,
            permanent_disable_after_attempts=3,
        )

    return Pipeline(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=SileroVAD(threshold=0.35),
        turn_detector=TurnDetector(threshold=0.8),
        interrupt_config=InterruptConfig(
            mode="HYBRID",
            interrupt_min_duration=0.5,
            interrupt_min_words=2,
            resume_on_false_interrupt=False,
        ),
    )


def _realtime_pipeline(settings: Settings) -> Pipeline:
    from videosdk.agents.plugins import GeminiLiveConfig, GeminiRealtime

    model = GeminiRealtime(
        model=settings.gemini_realtime_model,
        config=GeminiLiveConfig(
            voice=settings.gemini_voice,
            response_modalities=["AUDIO"],
        ),
    )
    return Pipeline(llm=model)


def create_pipeline(settings: Settings) -> Pipeline:
    if settings.pipeline_mode == "realtime":
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError(
                "PIPELINE_MODE=realtime requires GOOGLE_API_KEY for Gemini Live."
            )
        return _realtime_pipeline(settings)
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Cascade mode requires ANTHROPIC_API_KEY.")
    if not os.getenv("DEEPGRAM_API_KEY"):
        raise RuntimeError("Cascade mode requires DEEPGRAM_API_KEY.")
    if not os.getenv("ELEVENLABS_API_KEY"):
        raise RuntimeError("Cascade mode requires ELEVENLABS_API_KEY.")
    return _cascade_pipeline(settings)


def attach_observability(
    pipeline: Pipeline,
    metrics: CallMetrics,
    on_provider_error=None,
) -> None:
    @pipeline.metrics.on("stt")
    def on_stt(payload: dict) -> None:
        metrics.record_stt(payload)

    @pipeline.metrics.on("llm")
    def on_llm(payload: dict) -> None:
        metrics.record_llm(payload)

    @pipeline.metrics.on("tts")
    def on_tts(payload: dict) -> None:
        metrics.record_tts(payload)

    @pipeline.metrics.on("eou")
    def on_eou(payload: dict) -> None:
        metrics.record_eou(payload)

    @pipeline.metrics.on("realtime")
    def on_realtime(payload: dict) -> None:
        metrics.record_realtime(payload)

    @pipeline.on("error")
    def on_error(data: dict) -> None:
        logger.error(
            "pipeline_error",
            extra={
                "call_id": metrics.call_id,
                "component": data.get("source", "unknown"),
                "errors": [str(data.get("error"))],
            },
        )
        if on_provider_error:
            on_provider_error(data)
