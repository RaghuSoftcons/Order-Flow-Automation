"""
File:        packages/shared/src/orderflow_shared/risk/templates.py
Created:     2026-04-26 17:22 EST
Author:      Claude (Anthropic) + Raghu
Version:     1.0.0
Last Modified: 2026-04-26 17:22 EST

Change Log:
- 2026-04-26 17:22 EST | 1.0.0 | Initial Phase 0 scaffold. Apex + ETF tiers
  for 50K/100K/150K/250K/300K. Numbers are placeholders pending exact prop-firm
  spec confirmation in Phase 1; structure is final.

Pattern ported from Futures_Scalper_Phase1/backend/futures_scalp_analyzer/risk.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AccountRiskTemplate:
    tier: str
    account_size_usd: int
    daily_loss_limit_usd: float
    per_trade_risk_usd: float
    profit_target_usd: float
    max_loss_count: int
    max_contracts_es_nq: int
    max_contracts_gc: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# NOTE: These figures are working placeholders aligned to the public Apex/ETF
# evaluation rule structure. Exact per-tier numbers (especially trailing-DD vs
# end-of-day-DD variants and the 300K tier specifics) to be confirmed with the
# user during Phase 1 and adjusted here.
_RAW = [
    # Apex
    ("apex_50k",  50_000, 1_500.0, 300.0,   600.0, 3, 4,  2),
    ("apex_100k", 100_000, 3_000.0, 600.0, 1_200.0, 3, 7,  3),
    ("apex_150k", 150_000, 4_500.0, 900.0, 1_800.0, 3, 10, 4),
    ("apex_250k", 250_000, 6_500.0, 1_500.0, 3_000.0, 3, 14, 6),
    ("apex_300k", 300_000, 7_500.0, 1_500.0, 3_000.0, 3, 17, 7),
    # ETF
    ("etf_50k",  50_000, 1_500.0, 300.0,   600.0, 3, 4,  2),
    ("etf_100k", 100_000, 3_000.0, 600.0, 1_200.0, 3, 7,  3),
    ("etf_150k", 150_000, 4_500.0, 900.0, 1_800.0, 3, 10, 4),
    ("etf_250k", 250_000, 6_500.0, 1_500.0, 3_000.0, 3, 14, 6),
    ("etf_300k", 300_000, 7_500.0, 1_500.0, 3_000.0, 3, 17, 7),
]

RISK_TEMPLATES: dict[str, AccountRiskTemplate] = {
    row[0]: AccountRiskTemplate(
        tier=row[0],
        account_size_usd=row[1],
        daily_loss_limit_usd=row[2],
        per_trade_risk_usd=row[3],
        profit_target_usd=row[4],
        max_loss_count=row[5],
        max_contracts_es_nq=row[6],
        max_contracts_gc=row[7],
    )
    for row in _RAW
}


def lookup_template(tier: str) -> AccountRiskTemplate | None:
    return RISK_TEMPLATES.get(tier)
