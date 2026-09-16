"""Transparent adaptive estimates derived from observed trend features."""

from fitadapt.adaptive.tdee import (
    ADAPTIVE_TDEE_POLICY_VERSION,
    AdaptiveTdeeConfig,
    AdaptiveTdeeError,
    AdaptiveTdeeResult,
    DailyTdeeEstimate,
    TdeeEligibility,
    estimate_adaptive_tdee,
)

__all__ = [
    "ADAPTIVE_TDEE_POLICY_VERSION",
    "AdaptiveTdeeConfig",
    "AdaptiveTdeeError",
    "AdaptiveTdeeResult",
    "DailyTdeeEstimate",
    "TdeeEligibility",
    "estimate_adaptive_tdee",
]
