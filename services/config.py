"""Central configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # Groq (primary LLM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Anthropic (fallback LLM)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    # anthropic = try Anthropic first (recommended when Groq is rate-limited)
    llm_primary: str = "anthropic"

    # Sarvam AI
    sarvam_api_key: str = ""

    # Cal.com
    calcom_api_key: str = ""
    calcom_api_base: str = "https://api.cal.com/v2"

    # App
    app_base_url: str = "http://localhost:8000"
    database_url: str = "data/clinics.db"
    log_level: str = "INFO"
    environment: str = "development"
    # False = Polly Say (fast, reliable). True = Sarvam Play (better accent, needs tunnel).
    use_sarvam_play: bool = False


settings = Settings()
