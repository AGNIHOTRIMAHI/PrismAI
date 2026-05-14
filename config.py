"""
config.py — Centralised configuration using Pydantic V2.
All OpenAI references replaced with Google Gemini.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM (Gemini) ──────────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Google AI API key")
    google_model: str = Field("gemini-2.5-flash", description="Gemini model for agents")
    google_temperature: float = Field(0.1, ge=0.0, le=2.0)
    # ✅
    google_embedding_model: str = Field(
         "models/gemini-embedding-001",
         description="Gemini embedding model"
     )

    # ── GitHub ────────────────────────────────────────────────────────────────
    github_token: str = Field(..., description="GitHub Personal Access Token")
    github_webhook_secret: str = Field("default_secret", description="Webhook HMAC secret")

    # ── Tavily ────────────────────────────────────────────────────────────────
    tavily_api_key: str = Field(..., description="Tavily search API key")

    # ── Vector Store ──────────────────────────────────────────────────────────
    vector_store_path: str = Field("./docs/vector_store")

    # ── HITL ──────────────────────────────────────────────────────────────────
    hitl_notification_channel: Literal["slack", "email", "console"] = "console"
    slack_bot_token: str = Field("", description="Slack bot token for HITL")
    slack_review_channel_id: str = Field("", description="Slack channel for reviews")
    hitl_approval_timeout_seconds: int = Field(300, ge=30)

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["development", "staging", "production"] = "development"

    # ── Review Thresholds ─────────────────────────────────────────────────────
    security_block_threshold: int = Field(7, ge=0, le=10)
    max_diff_lines: int = Field(2000, ge=100)

    @field_validator("google_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def hitl_enabled(self) -> bool:
        return True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
