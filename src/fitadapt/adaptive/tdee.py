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
    STABILIZING = "stabilizing"
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
    minimum_intake_completeness: float = 0.7
    minimum_weight_contributors_per_half: int = 2
    maximum_days_since_last_weigh_in: int = 3
    intake_regime_change_kcal_per_day: float = 250.0
    intake_regime_lookback_days: int = 42
    minimum_old_regime_days: int = 7
    minimum_new_regime_days: int = 7
    intake_regime_stabilization_days: int = 14
    maximum_intake_regime_mad_kcal_per_day: float = 200.0
    stability_residual_mad_kg: float = 0.50
    subwindow_slope_disagreement_kcal_per_day: float = 300.0
    minimum_subwindow_weight_contributors: int = 5
    block_sensitivity_threshold_kcal_per_day: float = 300.0
    multi_horizon_disagreement_threshold_kcal_per_day: float = 300.0
    minimum_sensitivity_estimates: int = 3
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
            "minimum_weight_contributors_per_half",
            "maximum_days_since_last_weigh_in",
            "intake_regime_lookback_days",
            "minimum_old_regime_days",
            "minimum_new_regime_days",
            "intake_regime_stabilization_days",
            "minimum_subwindow_weight_contributors",
            "minimum_sensitivity_estimates",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise AdaptiveTdeeError(f"{name} must be a positive integer.")
        if self.minimum_calendar_span_days > self.estimator_window_days:
            raise AdaptiveTdeeError(
                "minimum_calendar_span_days cannot exceed estimator_window_days."
            )
        if self.intake_regime_lookback_days < (
            self.minimum_old_regime_days + self.minimum_new_regime_days
        ):
            raise AdaptiveTdeeError(
                "intake_regime_lookback_days must cover minimum old and new regime support."
            )
        if (
            isinstance(self.maximum_intake_regime_mad_kcal_per_day, bool)
            or not isinstance(self.maximum_intake_regime_mad_kcal_per_day, (int, float))
            or not math.isfinite(self.maximum_intake_regime_mad_kcal_per_day)
            or self.maximum_intake_regime_mad_kcal_per_day <= 0
        ):
            raise AdaptiveTdeeError(
                "maximum_intake_regime_mad_kcal_per_day must be finite and positive."
            )
        if (
            isinstance(self.minimum_intake_completeness, bool)
            or not isinstance(self.minimum_intake_completeness, (int, float))
            or not math.isfinite(self.minimum_intake_completeness)
            or not 0 < self.minimum_intake_completeness <= 1
        ):
            raise AdaptiveTdeeError("minimum_intake_completeness must be within (0, 1].")
        if (
            isinstance(self.intake_regime_change_kcal_per_day, bool)
            or not isinstance(self.intake_regime_change_kcal_per_day, (int, float))
            or not math.isfinite(self.intake_regime_change_kcal_per_day)
            or self.intake_regime_change_kcal_per_day <= 0
        ):
            raise AdaptiveTdeeError(
                "intake_regime_change_kcal_per_day must be finite and positive."
            )
        if not isinstance(self.robust_slope_method, str) or not self.robust_slope_method:
            raise AdaptiveTdeeError("robust_slope_method must be a non-empty string.")
        if (
            isinstance(self.subwindow_slope_disagreement_kcal_per_day, bool)
            or not isinstance(self.subwindow_slope_disagreement_kcal_per_day, (int, float))
            or not math.isfinite(self.subwindow_slope_disagreement_kcal_per_day)
            or self.subwindow_slope_disagreement_kcal_per_day <= 0
        ):
            raise AdaptiveTdeeError(
                "subwindow_slope_disagreement_kcal_per_day must be finite and positive."
            )
        for name in (
            "block_sensitivity_threshold_kcal_per_day",
            "multi_horizon_disagreement_threshold_kcal_per_day",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise AdaptiveTdeeError(f"{name} must be finite and positive.")
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
    weight_evidence_start_date: date | None = None
    weight_evidence_end_date: date | None = None
    aligned_intake_start_date: date | None = None
    aligned_intake_end_date: date | None = None
    uncertainty_kcal_per_day: float | None = None
    weight_residual_mad_kg: float | None = None
    intake_regime_change_date: date | None = None
    stabilizing_until_date: date | None = None


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
    weight_window = tuple(
        point for point in trend_result.points if start <= point.observed_on <= end
    )
    intake_start = max(start, trend_result.points[0].observed_on)
    intake_end = end
    intake_window = tuple(
        point for point in trend_result.points if intake_start <= point.observed_on <= intake_end
    )
    regime_start = max(
        trend_result.points[0].observed_on,
        end - timedelta(days=config.intake_regime_lookback_days - 1),
    )
    regime_window = tuple(
        point for point in trend_result.points if regime_start <= point.observed_on <= end
    )
    weights = tuple(
        (point.observed_on, point.body_weight_kg)
        for point in weight_window
        if point.body_weight_kg is not None
    )
    intakes = tuple(
        point.energy_intake_kcal for point in intake_window if point.energy_intake_kcal is not None
    )
    span = (weights[-1][0] - weights[0][0]).days + 1 if len(weights) >= 2 else 0
    aligned_days = max((intake_end - intake_start).days + 1, 0)
    completeness = len(intakes) / aligned_days if aligned_days else 0.0
    midpoint = weights[0][0] + timedelta(days=(weights[-1][0] - weights[0][0]).days // 2)
    first_half = tuple(item for item in weights if item[0] <= midpoint)
    second_half = tuple(item for item in weights if item[0] > midpoint)
    latest_weight_age = 0 if not weights else (end - weights[-1][0]).days
    reasons: list[str] = []
    if len(weights) < config.minimum_weight_contributors:
        reasons.append("insufficient_weight_contributors")
    required_intake = min(config.minimum_intake_contributors, config.aggregation_window_days)
    if len(intakes) < required_intake:
        reasons.append("insufficient_intake_contributors")
    if completeness < config.minimum_intake_completeness:
        reasons.append("insufficient_intake_completeness")
    required_span = min(config.minimum_calendar_span_days, config.aggregation_window_days)
    if span < required_span:
        reasons.append("insufficient_calendar_span")
    if (
        len(first_half) < config.minimum_weight_contributors_per_half
        or len(second_half) < config.minimum_weight_contributors_per_half
    ):
        reasons.append("insufficient_weight_window_geometry")
    if latest_weight_age > config.maximum_days_since_last_weigh_in:
        reasons.append("stale_latest_weigh_in")
    if reasons:
        legacy_mad = _legacy_daily_mad(daily, start, end, config)
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
            None,
            weight_window[0].observed_on if weight_window else None,
            weight_window[-1].observed_on if weight_window else None,
            intake_start,
            intake_end,
            legacy_mad=legacy_mad,
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
    regime_change_date = _intake_regime_change_date(regime_window, config)
    stabilizing_until = (
        None
        if regime_change_date is None
        else regime_change_date
        + timedelta(
            days=config.minimum_new_regime_days - 1 + config.intake_regime_stabilization_days
        )
    )
    recent_regime_change = stabilizing_until is not None and end <= stabilizing_until
    subwindow_disagreement = _subwindow_tdee_disagrees(weights, intake_window, midpoint, config)
    reasons = [] if stability is TdeeStability.STABLE else ["weight_slope_residual_dispersion"]
    if recent_regime_change:
        stability = TdeeStability.STABILIZING
        reasons = ["intake_regime_change", "post_regime_stabilization"]
    elif subwindow_disagreement:
        stability = TdeeStability.STABILIZING
        reasons = ["weight_subwindow_slope_disagreement"]
    legacy_mad = _legacy_daily_mad(daily, start, end, config)
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
        float(residual_mad),
        weight_window[0].observed_on if weight_window else None,
        weight_window[-1].observed_on if weight_window else None,
        intake_start,
        intake_end,
        float(residual_mad * config.energy_equivalent_kcal_per_kg / max(span, 1)),
        legacy_mad,
        regime_change_date,
        stabilizing_until,
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
    residual_mad: float | None = None,
    weight_start: date | None = None,
    weight_end: date | None = None,
    intake_start: date | None = None,
    intake_end: date | None = None,
    uncertainty: float | None = None,
    legacy_mad: float | None = None,
    regime_change_date: date | None = None,
    stabilizing_until: date | None = None,
) -> AdaptiveTdeeResult:
    return AdaptiveTdeeResult(
        ADAPTIVE_TDEE_POLICY_VERSION,
        config,
        daily,
        estimate,
        legacy_mad,
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
            "V2 aligns intake and weight observations by calendar date without inferring "
            "within-day timing.",
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
        weight_start,
        weight_end,
        intake_start,
        intake_end,
        uncertainty,
        residual_mad if estimate is not None else None,
        regime_change_date,
        stabilizing_until,
    )


def _legacy_daily_mad(
    daily: tuple[DailyTdeeEstimate, ...],
    start: date,
    end: date,
    config: AdaptiveTdeeConfig,
) -> float | None:
    recent = tuple(
        item.estimated_tdee_kcal_per_day
        for item in daily
        if start <= item.observed_on <= end
        and item.eligibility is TdeeEligibility.AVAILABLE
        and item.estimated_tdee_kcal_per_day is not None
    )
    if len(recent) < config.minimum_estimate_points:
        return None
    center = float(median(recent))
    return float(median([abs(value - center) for value in recent]))


def _intake_regime_change_date(intake_window, config: AdaptiveTdeeConfig) -> date | None:
    if not intake_window:
        return None
    values = tuple(
        (point.observed_on, point.energy_intake_kcal)
        for point in intake_window
        if point.energy_intake_kcal is not None
    )
    old_days = config.minimum_old_regime_days
    new_days = config.minimum_new_regime_days
    if len(values) < old_days + new_days:
        return None
    candidates: list[tuple[float, float, date]] = []
    for split_index in range(old_days, len(values) - new_days + 1):
        old = values[split_index - old_days : split_index]
        new = values[split_index : split_index + new_days]
        if (old[-1][0] - old[0][0]).days + 1 < old_days:
            continue
        if (new[-1][0] - new[0][0]).days + 1 < new_days:
            continue
        old_median = median(value for _, value in old)
        new_median = median(value for _, value in new)
        shift = new_median - old_median
        old_mad = median(abs(value - old_median) for _, value in old)
        new_mad = median(abs(value - new_median) for _, value in new)
        support_tolerance = 2.0 * config.maximum_intake_regime_mad_kcal_per_day
        old_support = sum(abs(value - old_median) <= support_tolerance for _, value in old)
        new_support = sum(abs(value - new_median) <= support_tolerance for _, value in new)
        if (
            abs(shift) >= config.intake_regime_change_kcal_per_day
            and max(old_mad, new_mad) <= config.maximum_intake_regime_mad_kcal_per_day
            and old_support >= old_days
            and new_support >= new_days
        ):
            dispersion = old_mad + new_mad
            candidates.append((dispersion, -abs(shift), new[0][0]))
    if not candidates:
        return None
    return min(candidates)[2]


def _subwindow_tdee_disagrees(
    weights: tuple[tuple[date, float], ...],
    intake_window,
    midpoint: date,
    config: AdaptiveTdeeConfig,
) -> bool:
    early = tuple(item for item in weights if item[0] <= midpoint)
    late = tuple(item for item in weights if item[0] > midpoint)
    early_intakes = tuple(
        point.energy_intake_kcal
        for point in intake_window
        if point.observed_on <= midpoint and point.energy_intake_kcal is not None
    )
    late_intakes = tuple(
        point.energy_intake_kcal
        for point in intake_window
        if point.observed_on > midpoint and point.energy_intake_kcal is not None
    )
    required = config.minimum_subwindow_weight_contributors
    if min(len(early), len(late), len(early_intakes), len(late_intakes)) < required:
        return False
    early_slope, _ = _theil_sen(early)
    late_slope, _ = _theil_sen(late)
    early_tdee = sum(early_intakes) / len(early_intakes) - (
        early_slope * config.energy_equivalent_kcal_per_kg
    )
    late_tdee = sum(late_intakes) / len(late_intakes) - (
        late_slope * config.energy_equivalent_kcal_per_kg
    )
    disagreement = abs(early_tdee - late_tdee)
    return disagreement >= config.subwindow_slope_disagreement_kcal_per_day
