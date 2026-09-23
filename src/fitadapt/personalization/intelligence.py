"""Stateless unified composition of FitAdapt's existing profile-intelligence outputs."""

from collections.abc import Sequence
from dataclasses import dataclass

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, AdaptiveTdeeResult, estimate_adaptive_tdee
from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisResult,
    analyze_observation_trends,
)
from fitadapt.baseline.targets import CalorieTargetEstimate, calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import UserProfile
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationLifecycleResult,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import NutritionPreferences
from fitadapt.personalization.planning import (
    PersonalizedPlanProgression,
    PersonalizedPlanSnapshot,
    build_personalized_plan_progression,
    build_personalized_plan_snapshot,
)
from fitadapt.recommendation.calories import (
    CalorieRecommendation,
    CalorieRecommendationConfig,
    recommend_calorie_adjustment,
)

PROFILE_INTELLIGENCE_POLICY_VERSION = "profile_intelligence_v1"
PROFILE_INTELLIGENCE_ASSUMPTIONS = (
    "All sections are recomputed from the same supplied profile and observation history.",
    "This orchestration adds no independent energy, trend, adaptive, lifecycle, recommendation, "
    "or macro formula.",
    "Full plan progression is optional because each snapshot is recomputed from a chronological "
    "prefix.",
    "The operation is stateless and does not retain submitted profile, preference, or observation "
    "data.",
)


class ProfileIntelligenceError(ValueError):
    """Raised when unified-intelligence inputs violate the public composition contract."""


@dataclass(frozen=True, slots=True)
class ProfileIntelligenceResult:
    """Immutable, complete current-state composition for one supplied profile history."""

    baseline: CalorieTargetEstimate
    trends: TrendAnalysisResult
    adaptive_tdee: AdaptiveTdeeResult
    lifecycle: PersonalizationLifecycleResult
    recommendation: CalorieRecommendation
    latest_plan: PersonalizedPlanSnapshot
    plan_progression: PersonalizedPlanProgression | None
    policy_version: str
    assumptions: tuple[str, ...]


def analyze_profile_intelligence(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
    lifecycle_config: PersonalizationLifecycleConfig | None = None,
    recommendation_config: CalorieRecommendationConfig | None = None,
    include_plan_progression: bool = False,
) -> ProfileIntelligenceResult:
    """Compose current FitAdapt outputs without altering their individual policies."""
    _validate_inputs(profile, observations, preferences, include_plan_progression)
    submitted = tuple(observations)
    baseline = calculate_calorie_target(profile)
    trends = analyze_observation_trends(submitted, trend_config)
    adaptive_tdee = estimate_adaptive_tdee(trends, adaptive_config)
    lifecycle = assess_personalization_lifecycle(
        profile, submitted, lifecycle_config, trend_config, adaptive_config
    )
    recommendation = recommend_calorie_adjustment(
        profile, submitted, recommendation_config, trend_config, adaptive_config
    )
    latest_plan = build_personalized_plan_snapshot(
        profile,
        submitted,
        preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
    )
    progression = (
        build_personalized_plan_progression(
            profile,
            submitted,
            preferences,
            trend_config,
            adaptive_config,
            lifecycle_config,
            recommendation_config,
        )
        if include_plan_progression
        else None
    )
    return ProfileIntelligenceResult(
        baseline=baseline,
        trends=trends,
        adaptive_tdee=adaptive_tdee,
        lifecycle=lifecycle,
        recommendation=recommendation,
        latest_plan=latest_plan,
        plan_progression=progression,
        policy_version=PROFILE_INTELLIGENCE_POLICY_VERSION,
        assumptions=PROFILE_INTELLIGENCE_ASSUMPTIONS,
    )


def _validate_inputs(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    include_plan_progression: bool,
) -> None:
    if not isinstance(profile, UserProfile):
        raise ProfileIntelligenceError("profile must be a UserProfile.")
    if not isinstance(preferences, NutritionPreferences):
        raise ProfileIntelligenceError("preferences must be NutritionPreferences.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise ProfileIntelligenceError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    if not isinstance(include_plan_progression, bool):
        raise ProfileIntelligenceError("include_plan_progression must be a bool.")
