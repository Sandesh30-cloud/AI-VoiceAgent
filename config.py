from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    videosdk_auth_token: str = ""
    agent_id: str = "sandesh-missed-call-receptionist"
    owner_name: str = "Sandesh"
    worker_host: str = "0.0.0.0"
    worker_port: int = 8081
    max_processes: int = 10

    pipeline_mode: Literal["cascade", "realtime"] = "cascade"
    anthropic_model: str = "claude-sonnet-4-20250514"
    deepgram_model: str = "nova-3"
    deepgram_language: str = "en"
    elevenlabs_model: str = "eleven_flash_v2_5"
    elevenlabs_voice_id: str = ""
    openai_llm_model: str = "gpt-4o-mini"
    gemini_realtime_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice: str = "Leda"

    wake_up_seconds: int = 12
    silence_reprompt_limit: int = 1
    playground: bool = False

    sqlite_path: str = "./data/calls.db"
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""

    notify_channel: Literal["telegram", "whatsapp", "both"] = "telegram"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_to: str = ""

    cost_llm_input_per_million: float = 3.00
    cost_llm_output_per_million: float = 15.00
    cost_stt_per_minute: float = 0.0043
    cost_tts_per_1k_chars: float = 0.15

    log_level: str = "INFO"

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    deepgram_api_key: str = Field(default="", alias="DEEPGRAM_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
