"""
File:        tests/unit/test_risk_templates.py
Created:     2026-04-26 17:23 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:23 EST
"""

from __future__ import annotations

import pytest

from orderflow_shared.risk import RISK_TEMPLATES, lookup_template


@pytest.mark.parametrize(
    "tier",
    [
        "apex_50k", "apex_100k", "apex_150k", "apex_250k", "apex_300k",
        "etf_50k", "etf_100k", "etf_150k", "etf_250k", "etf_300k",
    ],
)
def test_all_expected_tiers_exist(tier: str) -> None:
    template = lookup_template(tier)
    assert template is not None
    assert template.tier == tier
    assert template.daily_loss_limit_usd > 0
    assert template.per_trade_risk_usd > 0
    assert template.max_contracts_es_nq > 0
    assert template.max_contracts_gc > 0


def test_lookup_returns_none_for_unknown_tier() -> None:
    assert lookup_template("not_a_tier") is None


def test_300k_tier_added_for_user() -> None:
    """User confirmed 300K is a real tier on 2026-04-26."""
    apex_300k = lookup_template("apex_300k")
    assert apex_300k is not None
    assert apex_300k.account_size_usd == 300_000


def test_to_dict_round_trip() -> None:
    template = lookup_template("apex_100k")
    assert template is not None
    d = template.to_dict()
    assert d["tier"] == "apex_100k"
    assert d["account_size_usd"] == 100_000
    assert isinstance(d["max_contracts_es_nq"], int)


def test_template_is_frozen() -> None:
    template = lookup_template("apex_100k")
    assert template is not None
    with pytest.raises(Exception):
        template.daily_loss_limit_usd = 999.0  # type: ignore[misc]


def test_template_count() -> None:
    assert len(RISK_TEMPLATES) == 10  # 5 Apex + 5 ETF tiers
