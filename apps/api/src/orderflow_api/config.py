"""
File:        apps/api/src/orderflow_api/config.py
Created:     2026-04-26 17:20 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:20 EST

Change Log:
- 2026-04-26 17:20 EST | 1.0.0 | Initial Phase 0 scaffold.

App settings sourced from environment variables (via pydantic-settings).
Local dev uses .env file; Railway uses platform env vars.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_version: str = "0.1.0"

    api_key_salt: str = Field(
        default="dev-only-insecure-salt-change-me",
        description="Salt for hashing per-user API keys. Must be set in production.",
    )

    database_url: str = Field(
        default="",
        description="If empty, falls back to local SQLite at ./data/orderflow.db.",
    )

    redis_url: str = Field(
        default="",
        description="If empty, in-process fakeredis is used (dev only).",
    )

    anthropic_api_key: str = Field(default="", description="Set in Railway Variables.")

    # Phase 4 — populated when wiring Schwab integration
    schwab_client_id: str = ""
    schwab_client_secret: str = ""
    schwab_token_store_path: str = ""

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        local_path = Path("data/orderflow.db").absolute()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{local_path}"

    @property
    def use_fakeredis(self) -> bool:
        return not self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
