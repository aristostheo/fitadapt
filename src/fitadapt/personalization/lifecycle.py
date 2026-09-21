"""Evidence-based readiness stages composed from FitAdapt's existing analyses."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, estimate_adaptive_tdee
from fitadapt.analysis.trends import (
    DailyTrendPoint,
    DataQualityReport,
    TrendAnalysisConfig,
    analyze_observation_trends,
)
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import UserProfile

PERSONALIZATION_LIFECYCLE_POLICY_VERSION = "personalization_lifecycle_v1"
PERSONALIZATION_LIFECYCLE_ASSUMPTIONS = (
    "The assessment is recomputed from the complete supplied observation history.",
    "Lifecycle stages describe available evidence, not clinical accuracy or confidence.",
    "Observed zero intake remains present data; missing values remain missing.",
    "Lifecycle status does not modify baseline targets, macro plans, recommendations, or inputs.",
)


class PersonalizationLifecycleError(ValueError):
    """Raised when lifecycle inputs or configuration violate the public contract."""


class PersonalizationStage(StrEnum):
    """Ordered evidence stages for transparent adaptive readiness."""

    BASELINE = "baseline"
    CALIBRATING = "calibrating"
    EARLY_PERSONALIZED = "early_personalized"
    PERSONALIZED = "personalized"


class PersonalizationRequirement(StrEnum):
    """Focused next actions justified by the current evidence."""

    ADD_HISTORY = "add_history"
    LOG_BODY_WEIGHT = "log_body_weight"
    LOG_ENERGY_INTAKE = "log_energy_intake"
    BUILD_WEIGHT_TREND = "build_weight_trend"
    BUILD_INTAKE_TREND = "build_intake_trend"
    COLLECT_MORE_ELIGIBLE_ESTIMATES = "collect_more_eligible_estimates"


@dataclass(frozen=True, slots=True)
class PersonalizationLifecycleConfig:
    """Versioned thresholds used only to explain the next evidence-building action."""

    minimum_calendar_history_days: int = 14
    minimum_weight_completeness: float = 0.7
    minimum_intake_completeness: float = 0.7

    def __post_init__(self) -> None:
        days = self.minimum_calendar_history_days
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise PersonalizationLifecycleError(
                "minimum_calendar_history_days must be a positive integer."
            )
        for name, value in (
            ("minimum_weight_completeness", self.minimum_weight_completeness),
            ("minimum_intake_completeness", self.minimum_intake_completeness),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise PersonalizationLifecycleError(f"{name} must be a finite number from 0 to 1.")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class PersonalizationLifecycleResult:
    """Immutable readiness evidence without a new estimate or recommendation."""

    stage: PersonalizationStage
    requirements: tuple[PersonalizationRequirement, ...]
    calendar_history_days: int
    weight_observation_count: int
    intake_observation_count: int
    weight_completeness: float
    intake_completeness: float
    eligible_adaptive_estimate_count: int
    required_eligible_estimate_count: int
    adaptive_tdee_kcal_per_day: float | None
    median_absolute_deviation_kcal_per_day: float | None
    lifecycle_policy_version: str
    trend_policy_version: str
    adaptive_policy_version: str
    assumptions: tuple[str, ...]


def assess_personalization_lifecycle(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    config: PersonalizationLifecycleConfig | None = None,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
) -> PersonalizationLifecycleResult:
    """Assess evidence readiness by composing existing trend and adaptive estimators."""
    if not isinstance(profile, UserProfile):
        raise PersonalizationLifecycleError("profile must be a UserProfile.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise PersonalizationLifecycleError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    effective_config = config if config is not None else PersonalizationLifecycleConfig()
    if not isinstance(effective_config, PersonalizationLifecycleConfig):
        raise PersonalizationLifecycleError(
            "config must be a PersonalizationLifecycleConfig or None."
        )

    trends = analyze_observation_trends(observations, trend_config)
    adaptive = estimate_adaptive_tdee(trends, adaptive_config)
    quality = trends.data_quality
    latest = trends.points[-1] if trends.points else None
    has_relevant_history = (
        quality.present_body_weight_values > 0 or quality.present_energy_intake_values > 0
    )

    if not has_relevant_history:
        stage = PersonalizationStage.BASELINE
        requirements = _baseline_requirements(quality, effective_config)
    elif adaptive.total_eligible_points == 0:
        stage = PersonalizationStage.CALIBRATING
        requirements = _calibrating_requirements(quality, latest, effective_config)
    elif adaptive.adaptive_tdee_kcal_per_day is None:
        stage = PersonalizationStage.EARLY_PERSONALIZED
        requirements = (PersonalizationRequirement.COLLECT_MORE_ELIGIBLE_ESTIMATES,)
    else:
        stage = PersonalizationStage.PERSONALIZED
        requirements = ()

    return PersonalizationLifecycleResult(
        stage=stage,
        requirements=requirements,
        calendar_history_days=quality.total_calendar_days,
        weight_observation_count=quality.present_body_weight_values,
        intake_observation_count=quality.present_energy_intake_values,
        weight_completeness=quality.body_weight_completeness_ratio,
        intake_completeness=quality.energy_intake_completeness_ratio,
        eligible_adaptive_estimate_count=adaptive.total_eligible_points,
        required_eligible_estimate_count=adaptive.config.minimum_estimate_points,
        adaptive_tdee_kcal_per_day=adaptive.adaptive_tdee_kcal_per_day,
        median_absolute_deviation_kcal_per_day=adaptive.median_absolute_deviation_kcal_per_day,
        lifecycle_policy_version=PERSONALIZATION_LIFECYCLE_POLICY_VERSION,
        trend_policy_version=trends.policy_version,
        adaptive_policy_version=adaptive.policy_version,
        assumptions=PERSONALIZATION_LIFECYCLE_ASSUMPTIONS,
    )


def _baseline_requirements(
    quality: DataQualityReport, config: PersonalizationLifecycleConfig
) -> tuple[PersonalizationRequirement, ...]:
    requirements: list[PersonalizationRequirement] = []
    if quality.total_calendar_days < config.minimum_calendar_history_days:
        requirements.append(PersonalizationRequirement.ADD_HISTORY)
    if quality.present_body_weight_values == 0:
        requirements.append(PersonalizationRequirement.LOG_BODY_WEIGHT)
    if quality.present_energy_intake_values == 0:
        requirements.append(PersonalizationRequirement.LOG_ENERGY_INTAKE)
    return tuple(requirements)


def _calibrating_requirements(
    quality: DataQualityReport,
    latest: DailyTrendPoint | None,
    config: PersonalizationLifecycleConfig,
) -> tuple[PersonalizationRequirement, ...]:
    requirements: list[PersonalizationRequirement] = []
    if quality.total_calendar_days < config.minimum_calendar_history_days:
        requirements.append(PersonalizationRequirement.ADD_HISTORY)
    if quality.body_weight_completeness_ratio < config.minimum_weight_completeness:
        requirements.append(PersonalizationRequirement.LOG_BODY_WEIGHT)
    if quality.energy_intake_completeness_ratio < config.minimum_intake_completeness:
        requirements.append(PersonalizationRequirement.LOG_ENERGY_INTAKE)
    if quality.present_body_weight_values > 0 and (
        latest is None or latest.window_weight_change_kg is None
    ):
        requirements.append(PersonalizationRequirement.BUILD_WEIGHT_TREND)
    if quality.present_energy_intake_values > 0 and (
        latest is None or latest.trailing_energy_intake_mean_kcal is None
    ):
        requirements.append(PersonalizationRequirement.BUILD_INTAKE_TREND)
    return tuple(requirements)
