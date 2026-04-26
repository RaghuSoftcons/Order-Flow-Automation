"""
File:        tests/unit/test_config.py
Created:     2026-04-26 17:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:23 EST
"""

from __future__ import annotations

import pytest

from orderflow_api.config import Settings, get_settings


def test_defaults_are_safe_for_dev() -> None:
    s = Settings()
    assert s.environment == "development"
    assert s.log_level == "INFO"
    assert s.use_fakeredis is True


def test_database_url_falls_back_to_sqlite_when_unset() -> None:
    s = Settings(database_url="")
    assert s.effective_database_url.startswith("sqlite:///")


def test_database_url_passes_through_when_set() -> None:
    s = Settings(database_url="postgresql://user:pw@host/db")
    assert s.effective_database_url == "postgresql://user:pw@host/db"


def test_use_fakeredis_flips_when_redis_url_set() -> None:
    s = Settings(redis_url="redis://localhost:6379/0")
    assert s.use_fakeredis is False


def test_get_settings_is_cached() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b


def test_environment_must_be_valid_literal() -> None:
    with pytest.raises(Exception):
        Settings(environment="invalid-env")  # type: ignore[arg-type]
