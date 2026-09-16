"""Conservative recommendation composition over existing FitAdapt calculations."""

import math
from dataclasses import dataclass
from enum import StrEnum

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, estimate_adaptive_tdee
from fitadapt.analysis.trends import TrendAnalysisConfig, analyze_observation_trends
from fitadapt.baseline.targets import (
    ENERGY_EQUIVALENT_POLICY_VERSION,
    calculate_calorie_target,
    calculate_daily_calorie_adjustment,
    minimum_macro_calories_kcal_per_day,
)
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import Goal, UserProfile

RECOMMENDATION_POLICY_VERSION = "calorie_recommendation_v1"
ASSUMPTIONS = (
    "This is decision support, not medical or nutritional treatment.",
    "Self-reported intake and scale trends can be biased by logging, hydration, glycogen, and "
    "noise.",
    "Recommendations are not applied automatically and do not replace baseline outputs.",
    "The synthetic weight-change ML experiment is not used as recommendation evidence.",
)


class CalorieRecommendationError(ValueError):
    """Raised for invalid recommendation contracts."""


class RecommendationStatus(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    HOLD = "hold"
    INCREASE_CALORIES = "increase_calories"
    DECREASE_CALORIES = "decrease_calories"


class RecommendationReason(StrEnum):
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_WEIGHT_COMPLETENESS = "insufficient_weight_completeness"
    INSUFFICIENT_INTAKE_COMPLETENESS = "insufficient_intake_completeness"
    MISSING_RECENT_INTAKE = "missing_recent_intake"
    MISSING_WEIGHT_TREND = "missing_weight_trend"
    ADAPTIVE_TDEE_UNAVAILABLE = "adaptive_tdee_unavailable"
    INSUFFICIENT_ADAPTIVE_ESTIMATES = "insufficient_adaptive_estimates"
    NON_POSITIVE_PROPOSED_TARGET = "non_positive_proposed_target"
    MACRO_POLICY_INFEASIBLE_PROPOSED_TARGET = "macro_policy_infeasible_proposed_target"
    WITHIN_HOLD_THRESHOLD = "within_hold_threshold"
    LIMITED_BY_MAXIMUM_ADJUSTMENT = "limited_by_maximum_adjustment"
    ADJUSTMENT_RECOMMENDED = "adjustment_recommended"


@dataclass(frozen=True, slots=True)
class CalorieRecommendationConfig:
    minimum_calendar_history_days: int = 21
    minimum_weight_completeness: float = 0.7
    minimum_intake_completeness: float = 0.7
    minimum_adaptive_estimates: int = 4
    hold_threshold_kcal_per_day: float = 75.0
    maximum_adjustment_kcal_per_day: float = 150.0

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_calendar_history_days", self.minimum_calendar_history_days),
            ("minimum_adaptive_estimates", self.minimum_adaptive_estimates),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise CalorieRecommendationError(f"{name} must be a positive integer.")
        for name, value, minimum in (
            ("minimum_weight_completeness", self.minimum_weight_completeness, 0.0),
            ("minimum_intake_completeness", self.minimum_intake_completeness, 0.0),
            ("hold_threshold_kcal_per_day", self.hold_threshold_kcal_per_day, 0.0),
            ("maximum_adjustment_kcal_per_day", self.maximum_adjustment_kcal_per_day, 0.0),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < minimum
                or (name.endswith("completeness") and value > 1.0)
                or (name.startswith("maximum") and value <= 0)
            ):
                raise CalorieRecommendationError(f"{name} has an invalid value.")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class CalorieRecommendation:
    status: RecommendationStatus
    reasons: tuple[RecommendationReason, ...]
    goal: Goal
    requested_weekly_change_kg: float
    observed_window_weight_change_kg: float | None
    baseline_estimated_tdee_kcal_per_day: float
    baseline_calorie_target_kcal_per_day: float
    adaptive_tdee_kcal_per_day: float | None
    recent_mean_intake_kcal_per_day: float | None
    personalized_goal_target_kcal_per_day: float | None
    raw_adjustment_kcal_per_day: float | None
    recommended_adjustment_kcal_per_day: float | None
    proposed_intake_target_kcal_per_day: float | None
    calendar_history_days: int
    weight_completeness: float
    intake_completeness: float
    adaptive_estimate_count: int
    recommendation_policy_version: str
    trend_policy_version: str
    adaptive_policy_version: str
    energy_equivalent_policy_version: str
    assumptions: tuple[str, ...]


def recommend_calorie_adjustment(
    profile: UserProfile,
    observations: object,
    config: CalorieRecommendationConfig | None = None,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
) -> CalorieRecommendation:
    """Return hold/adjust/insufficient-data support without mutating upstream outputs."""
    if not isinstance(profile, UserProfile):
        raise CalorieRecommendationError("profile must be a UserProfile.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise CalorieRecommendationError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    effective = config if config is not None else CalorieRecommendationConfig()
    if not isinstance(effective, CalorieRecommendationConfig):
        raise CalorieRecommendationError("config must be a CalorieRecommendationConfig or None.")
    target = calculate_calorie_target(profile)
    trends = analyze_observation_trends(observations, trend_config)
    adaptive = estimate_adaptive_tdee(trends, adaptive_config)
    quality, points = trends.data_quality, trends.points
    latest = points[-1] if points else None
    reasons = []
    if quality.total_calendar_days < effective.minimum_calendar_history_days:
        reasons.append(RecommendationReason.INSUFFICIENT_HISTORY)
    if quality.body_weight_completeness_ratio < effective.minimum_weight_completeness:
        reasons.append(RecommendationReason.INSUFFICIENT_WEIGHT_COMPLETENESS)
    if quality.energy_intake_completeness_ratio < effective.minimum_intake_completeness:
        reasons.append(RecommendationReason.INSUFFICIENT_INTAKE_COMPLETENESS)
    if latest is None or latest.trailing_energy_intake_mean_kcal is None:
        reasons.append(RecommendationReason.MISSING_RECENT_INTAKE)
    if latest is None or latest.window_weight_change_kg is None:
        reasons.append(RecommendationReason.MISSING_WEIGHT_TREND)
    if adaptive.adaptive_tdee_kcal_per_day is None:
        reasons.append(RecommendationReason.ADAPTIVE_TDEE_UNAVAILABLE)
    if adaptive.eligible_points_used < effective.minimum_adaptive_estimates:
        reasons.append(RecommendationReason.INSUFFICIENT_ADAPTIVE_ESTIMATES)
    common = dict(
        goal=profile.goal,
        requested_weekly_change_kg=profile.requested_weekly_change_kg,
        observed_window_weight_change_kg=None if latest is None else latest.window_weight_change_kg,
        baseline_estimated_tdee_kcal_per_day=target.baseline_energy.estimated_tdee_kcal_per_day,
        baseline_calorie_target_kcal_per_day=target.target_calories_kcal_per_day,
        adaptive_tdee_kcal_per_day=adaptive.adaptive_tdee_kcal_per_day,
        recent_mean_intake_kcal_per_day=None
        if latest is None
        else latest.trailing_energy_intake_mean_kcal,
        calendar_history_days=quality.total_calendar_days,
        weight_completeness=quality.body_weight_completeness_ratio,
        intake_completeness=quality.energy_intake_completeness_ratio,
        adaptive_estimate_count=adaptive.eligible_points_used,
        recommendation_policy_version=RECOMMENDATION_POLICY_VERSION,
        trend_policy_version=trends.policy_version,
        adaptive_policy_version=adaptive.policy_version,
        energy_equivalent_policy_version=ENERGY_EQUIVALENT_POLICY_VERSION,
        assumptions=ASSUMPTIONS,
    )
    if reasons:
        return CalorieRecommendation(
            status=RecommendationStatus.INSUFFICIENT_DATA,
            reasons=tuple(reasons),
            personalized_goal_target_kcal_per_day=None,
            raw_adjustment_kcal_per_day=None,
            recommended_adjustment_kcal_per_day=None,
            proposed_intake_target_kcal_per_day=None,
            **common,
        )
    personalized = adaptive.adaptive_tdee_kcal_per_day + calculate_daily_calorie_adjustment(profile)
    raw = personalized - latest.trailing_energy_intake_mean_kcal
    status, reason, limited = _apply_adjustment_policy(raw, effective)
    proposed = latest.trailing_energy_intake_mean_kcal + limited
    safety_reason = _proposed_target_safety_reason(profile, proposed)
    if safety_reason is not None:
        return CalorieRecommendation(
            status=RecommendationStatus.INSUFFICIENT_DATA,
            reasons=(safety_reason,),
            personalized_goal_target_kcal_per_day=None,
            raw_adjustment_kcal_per_day=None,
            recommended_adjustment_kcal_per_day=None,
            proposed_intake_target_kcal_per_day=None,
            **common,
        )
    if status is RecommendationStatus.HOLD:
        return CalorieRecommendation(
            status=RecommendationStatus.HOLD,
            reasons=(RecommendationReason.WITHIN_HOLD_THRESHOLD,),
            personalized_goal_target_kcal_per_day=personalized,
            raw_adjustment_kcal_per_day=raw,
            recommended_adjustment_kcal_per_day=0.0,
            proposed_intake_target_kcal_per_day=proposed,
            **common,
        )
    return CalorieRecommendation(
        status=status,
        reasons=(reason,),
        personalized_goal_target_kcal_per_day=personalized,
        raw_adjustment_kcal_per_day=raw,
        recommended_adjustment_kcal_per_day=limited,
        proposed_intake_target_kcal_per_day=proposed,
        **common,
    )


def _apply_adjustment_policy(
    raw_adjustment_kcal_per_day: float, config: CalorieRecommendationConfig
) -> tuple[RecommendationStatus, RecommendationReason, float]:
    """Apply the explicit hold and maximum-adjustment boundaries without rounding."""
    if abs(raw_adjustment_kcal_per_day) <= config.hold_threshold_kcal_per_day:
        return RecommendationStatus.HOLD, RecommendationReason.WITHIN_HOLD_THRESHOLD, 0.0
    limited = max(
        -config.maximum_adjustment_kcal_per_day,
        min(config.maximum_adjustment_kcal_per_day, raw_adjustment_kcal_per_day),
    )
    status = (
        RecommendationStatus.INCREASE_CALORIES
        if limited > 0
        else RecommendationStatus.DECREASE_CALORIES
    )
    reason = (
        RecommendationReason.LIMITED_BY_MAXIMUM_ADJUSTMENT
        if limited != raw_adjustment_kcal_per_day
        else RecommendationReason.ADJUSTMENT_RECOMMENDED
    )
    return status, reason, limited


def _proposed_target_safety_reason(
    profile: UserProfile, proposed_intake_target_kcal_per_day: float
) -> RecommendationReason | None:
    """Reject non-actionable targets without silently applying a universal floor."""
    if proposed_intake_target_kcal_per_day <= 0:
        return RecommendationReason.NON_POSITIVE_PROPOSED_TARGET
    if proposed_intake_target_kcal_per_day < minimum_macro_calories_kcal_per_day(profile):
        return RecommendationReason.MACRO_POLICY_INFEASIBLE_PROPOSED_TARGET
    return None
