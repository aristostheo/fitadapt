"""Transparent adaptive TDEE estimates from observed intake and weight trends."""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from statistics import median

from fitadapt.analysis.trends import TrendAnalysisResult

ADAPTIVE_TDEE_POLICY_VERSION = "adaptive_tdee_v2"
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


class TdeeStability(StrEnum):
    INSUFFICIENT = "insufficient"
    UNSTABLE = "unstable"
    STABLE = "stable"


@dataclass(frozen=True, slots=True)
class AdaptiveTdeeConfig:
    energy_equivalent_kcal_per_kg: float = 7700.0
    aggregation_window_days: int = 14
    minimum_estimate_points: int = 4
    estimator_window_days: int = 28
    minimum_weight_contributors: int = 5
    minimum_intake_contributors: int = 14
    minimum_calendar_span_days: int = 14
    stability_residual_mad_kg: float = 0.15
    robust_slope_method: str = "theil_sen_v1"

    def __post_init__(self) -> None:
        energy_equivalent = self.energy_equivalent_kcal_per_kg
        if (
            isinstance(energy_equivalent, bool)
            or not isinstance(energy_equivalent, (int, float))
            or not math.isfinite(energy_equivalent)
            or energy_equivalent <= 0
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
        for name in (
            "estimator_window_days",
            "minimum_weight_contributors",
            "minimum_intake_contributors",
            "minimum_calendar_span_days",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise AdaptiveTdeeError(f"{name} must be a positive integer.")
        if self.minimum_calendar_span_days > self.estimator_window_days:
            raise AdaptiveTdeeError(
                "minimum_calendar_span_days cannot exceed estimator_window_days."
            )
        if not isinstance(self.robust_slope_method, str) or not self.robust_slope_method:
            raise AdaptiveTdeeError("robust_slope_method must be a non-empty string.")
        stability = self.stability_residual_mad_kg
        if (
            isinstance(stability, bool)
            or not isinstance(stability, (int, float))
            or not math.isfinite(stability)
            or stability <= 0
        ):
            raise AdaptiveTdeeError("stability_residual_mad_kg must be finite and positive.")
        object.__setattr__(self, "energy_equivalent_kcal_per_kg", float(energy_equivalent))


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
    observed_weight_slope_kg_per_day: float | None = None
    observed_weight_slope_kg_per_week: float | None = None
    aligned_mean_intake_kcal_per_day: float | None = None
    weight_contributor_count: int = 0
    intake_contributor_count: int = 0
    intake_completeness: float = 0.0
    evidence_calendar_span_days: int = 0
    estimator_method: str = "legacy_v1"
    stability: TdeeStability = TdeeStability.INSUFFICIENT
    reason_codes: tuple[str, ...] = ()


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
    if any(point.body_weight_kg is not None for point in trend_result.points):
        return _estimate_v2(trend_result, effective, daily)
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


def _estimate_v2(
    trend_result: TrendAnalysisResult,
    config: AdaptiveTdeeConfig,
    daily: tuple[DailyTdeeEstimate, ...],
) -> AdaptiveTdeeResult:
    """Estimate TDEE from one aligned raw-observation window using Theil-Sen slope."""
    end = trend_result.points[-1].observed_on
    start = end - timedelta(days=config.estimator_window_days - 1)
    window = tuple(point for point in trend_result.points if start <= point.observed_on <= end)
    weights = tuple(
        (point.observed_on, point.body_weight_kg)
        for point in window
        if point.body_weight_kg is not None
    )
    intakes = tuple(
        point.energy_intake_kcal for point in window if point.energy_intake_kcal is not None
    )
    span = (weights[-1][0] - weights[0][0]).days + 1 if len(weights) >= 2 else 0
    completeness = len(intakes) / len(window) if window else 0.0
    reasons: list[str] = []
    if len(weights) < config.minimum_weight_contributors:
        reasons.append("insufficient_weight_contributors")
    required_intake = min(config.minimum_intake_contributors, config.aggregation_window_days)
    if len(intakes) < required_intake:
        reasons.append("insufficient_intake_contributors")
    required_span = min(config.minimum_calendar_span_days, config.aggregation_window_days)
    if span < required_span:
        reasons.append("insufficient_calendar_span")
    if reasons:
        return _v2_result(
            config,
            daily,
            start,
            end,
            weights,
            intakes,
            span,
            completeness,
            None,
            None,
            TdeeStability.INSUFFICIENT,
            tuple(reasons),
            None,
        )
    slope, residual_mad = _theil_sen(weights)
    mean_intake = float(sum(intakes) / len(intakes))
    balance = slope * config.energy_equivalent_kcal_per_kg
    estimate = mean_intake - balance
    stability = (
        TdeeStability.STABLE
        if residual_mad <= config.stability_residual_mad_kg
        else TdeeStability.UNSTABLE
    )
    reasons = [] if stability is TdeeStability.STABLE else ["weight_slope_residual_dispersion"]
    return _v2_result(
        config,
        daily,
        start,
        end,
        weights,
        intakes,
        span,
        completeness,
        float(slope),
        float(slope * 7.0),
        stability,
        tuple(reasons),
        float(estimate),
    )


def _theil_sen(weights: tuple[tuple[date, float], ...]) -> tuple[float, float]:
    slopes = tuple(
        (second_weight - first_weight) / (second_date - first_date).days
        for index, (first_date, first_weight) in enumerate(weights)
        for second_date, second_weight in weights[index + 1 :]
        if (second_date - first_date).days > 0
    )
    slope = float(median(slopes))
    intercepts = tuple(weight - slope * day.toordinal() for day, weight in weights)
    intercept = float(median(intercepts))
    residuals = tuple(
        abs(weight - (intercept + slope * day.toordinal())) for day, weight in weights
    )
    return slope, float(median(residuals))


def _v2_result(
    config: AdaptiveTdeeConfig,
    daily: tuple[DailyTdeeEstimate, ...],
    start: date,
    end: date,
    weights: tuple[tuple[date, float], ...],
    intakes: tuple[float, ...],
    span: int,
    completeness: float,
    slope_day: float | None,
    slope_week: float | None,
    stability: TdeeStability,
    reasons: tuple[str, ...],
    estimate: float | None,
) -> AdaptiveTdeeResult:
    return AdaptiveTdeeResult(
        ADAPTIVE_TDEE_POLICY_VERSION,
        config,
        daily,
        estimate,
        0.0 if estimate is not None else None,
        (min(len(weights), len(intakes)) if estimate is not None else 0),
        (
            min(len(weights), len(intakes))
            if estimate is not None
            else sum(item.eligibility is TdeeEligibility.AVAILABLE for item in daily)
        ),
        start,
        end,
        ADAPTIVE_TDEE_ASSUMPTIONS
        + (
            "V2 aligns raw intake and weight evidence over the same trailing calendar window.",
            "V2 uses a deterministic Theil-Sen slope over valid weigh-ins; missing weights are not "
            "interpolated.",
            "Stability is based on median absolute slope residual dispersion, not a confidence "
            "percentage.",
        ),
        slope_day,
        slope_week,
        None if not intakes else float(sum(intakes) / len(intakes)),
        len(weights),
        len(intakes),
        completeness,
        span,
        config.robust_slope_method,
        stability,
        reasons,
    )
