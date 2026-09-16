"""Transparent adaptive TDEE estimates from observed intake and weight trends."""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from statistics import median

from fitadapt.analysis.trends import TrendAnalysisResult

ADAPTIVE_TDEE_POLICY_VERSION = "adaptive_tdee_v1"
ADAPTIVE_TDEE_ASSUMPTIONS = (
    "The 7,700 kcal/kg conversion is an approximation.",
    "Logged calorie intake is assumed to approximate actual intake.",
    "Smoothed scale-weight change is assumed to reflect energy-balance direction.",
    "Overlapping rolling estimates are correlated and MAD is only a descriptive spread metric.",
    "The estimator does not model metabolic adaptation and is not medically validated.",
)


class AdaptiveTdeeError(ValueError):
    """Raised for invalid adaptive-estimation contracts or configuration."""


class TdeeEligibility(StrEnum):
    AVAILABLE = "available"
    MISSING_INTAKE_TREND = "missing_intake_trend"
    MISSING_WEIGHT_CHANGE = "missing_weight_change"
    NON_FINITE_RESULT = "non_finite_result"


@dataclass(frozen=True, slots=True)
class AdaptiveTdeeConfig:
    energy_equivalent_kcal_per_kg: float = 7700.0
    aggregation_window_days: int = 14
    minimum_estimate_points: int = 4

    def __post_init__(self) -> None:
        value = self.energy_equivalent_kcal_per_kg
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise AdaptiveTdeeError(
                "energy_equivalent_kcal_per_kg must be a finite positive number."
            )
        if (
            isinstance(self.aggregation_window_days, bool)
            or not isinstance(self.aggregation_window_days, int)
            or self.aggregation_window_days <= 0
        ):
            raise AdaptiveTdeeError("aggregation_window_days must be a positive integer.")
        if (
            isinstance(self.minimum_estimate_points, bool)
            or not isinstance(self.minimum_estimate_points, int)
            or self.minimum_estimate_points <= 0
        ):
            raise AdaptiveTdeeError("minimum_estimate_points must be a positive integer.")
        if self.minimum_estimate_points > self.aggregation_window_days:
            raise AdaptiveTdeeError(
                "minimum_estimate_points cannot exceed aggregation_window_days."
            )
        object.__setattr__(self, "energy_equivalent_kcal_per_kg", float(value))


@dataclass(frozen=True, slots=True)
class DailyTdeeEstimate:
    observed_on: date
    trailing_energy_intake_mean_kcal: float | None
    window_weight_change_kg: float | None
    estimated_daily_energy_balance_kcal: float | None
    estimated_tdee_kcal_per_day: float | None
    eligibility: TdeeEligibility

    def __post_init__(self) -> None:
        """Keep the public eligibility status within the versioned enum contract."""
        if not isinstance(self.eligibility, TdeeEligibility):
            raise AdaptiveTdeeError("eligibility must be a TdeeEligibility.")


@dataclass(frozen=True, slots=True)
class AdaptiveTdeeResult:
    policy_version: str
    config: AdaptiveTdeeConfig
    daily_estimates: tuple[DailyTdeeEstimate, ...]
    adaptive_tdee_kcal_per_day: float | None
    median_absolute_deviation_kcal_per_day: float | None
    eligible_points_used: int
    total_eligible_points: int
    aggregation_start_date: date | None
    aggregation_end_date: date | None
    assumptions: tuple[str, ...]


def estimate_adaptive_tdee(
    trend_result: TrendAnalysisResult, config: AdaptiveTdeeConfig | None = None
) -> AdaptiveTdeeResult:
    """Estimate observed TDEE from intake trends and configured-window weight change."""
    if not isinstance(trend_result, TrendAnalysisResult):
        raise AdaptiveTdeeError("trend_result must be a TrendAnalysisResult.")
    effective = config if config is not None else AdaptiveTdeeConfig()
    if not isinstance(effective, AdaptiveTdeeConfig):
        raise AdaptiveTdeeError("config must be an AdaptiveTdeeConfig or None.")
    daily = tuple(
        _daily(point, trend_result.config.window_size_days, effective)
        for point in trend_result.points
    )
    if not daily:
        return AdaptiveTdeeResult(
            ADAPTIVE_TDEE_POLICY_VERSION,
            effective,
            (),
            None,
            None,
            0,
            0,
            None,
            None,
            ADAPTIVE_TDEE_ASSUMPTIONS,
        )
    end = daily[-1].observed_on
    start = end - timedelta(days=effective.aggregation_window_days - 1)
    eligible = [
        item.estimated_tdee_kcal_per_day
        for item in daily
        if item.eligibility == TdeeEligibility.AVAILABLE
    ]
    recent = [
        item.estimated_tdee_kcal_per_day
        for item in daily
        if item.observed_on >= start and item.eligibility == TdeeEligibility.AVAILABLE
    ]
    if len(recent) < effective.minimum_estimate_points:
        aggregate = mad = None
    else:
        aggregate = float(median(recent))
        mad = float(median([abs(value - aggregate) for value in recent]))
    return AdaptiveTdeeResult(
        ADAPTIVE_TDEE_POLICY_VERSION,
        effective,
        daily,
        aggregate,
        mad,
        len(recent),
        len(eligible),
        start,
        end,
        ADAPTIVE_TDEE_ASSUMPTIONS,
    )


def _daily(point: object, window_days: int, config: AdaptiveTdeeConfig) -> DailyTdeeEstimate:
    intake = point.trailing_energy_intake_mean_kcal
    change = point.window_weight_change_kg
    if intake is None:
        return DailyTdeeEstimate(
            point.observed_on, intake, change, None, None, TdeeEligibility.MISSING_INTAKE_TREND
        )
    if change is None:
        return DailyTdeeEstimate(
            point.observed_on, intake, change, None, None, TdeeEligibility.MISSING_WEIGHT_CHANGE
        )
    balance = change * config.energy_equivalent_kcal_per_kg / window_days
    tdee = intake - balance
    if not math.isfinite(balance) or not math.isfinite(tdee):
        return DailyTdeeEstimate(
            point.observed_on, intake, change, None, None, TdeeEligibility.NON_FINITE_RESULT
        )
    return DailyTdeeEstimate(
        point.observed_on,
        float(intake),
        float(change),
        float(balance),
        float(tdee),
        TdeeEligibility.AVAILABLE,
    )
