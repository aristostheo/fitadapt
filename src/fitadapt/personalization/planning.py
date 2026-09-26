"""Entry-by-entry proposed planning composed from existing FitAdapt policies."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig
from fitadapt.analysis.trends import TrendAnalysisConfig, analyze_observation_trends
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import UserProfile
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationRequirement,
    PersonalizationStage,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    NutritionPreferences,
    PersonalizedMacroPlan,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.targets import (
    NutritionTargetEnvelope,
    calculate_nutrition_target_envelope,
)
from fitadapt.personalization.training import TrainingDemandAssessment
from fitadapt.recommendation.calories import (
    CalorieRecommendationConfig,
    RecommendationReason,
    RecommendationStatus,
    recommend_calorie_adjustment,
)

PERSONALIZED_PLANNING_POLICY_VERSION = "personalized_planning_v1"
PERSONALIZED_PLANNING_ASSUMPTIONS = (
    "Each snapshot uses only observations available on or before its as-of date.",
    "Nutrition strategy is explicitly selected by the user and is not learned.",
    "A plan is decision support and is never automatically applied.",
    "The planning layer composes existing baseline, lifecycle, recommendation, and macro policies.",
)


class PersonalizedPlanningError(ValueError):
    """Raised when planning inputs violate the public composition contract."""


class PlanCalorieBasis(StrEnum):
    """The existing calorie calculation selected for the proposed macro plan."""

    BASELINE = "baseline"
    PERSONALIZED = "personalized"


@dataclass(frozen=True, slots=True)
class PersonalizedPlanSnapshot:
    """A transparent proposed plan as of one submitted observation date."""

    as_of_date: date | None
    lifecycle_stage: PersonalizationStage
    lifecycle_requirements: tuple[PersonalizationRequirement, ...]
    calorie_basis: PlanCalorieBasis
    baseline_calorie_target_kcal_per_day: float
    selected_calorie_target_kcal_per_day: float
    previous_selected_calorie_target_kcal_per_day: float | None
    change_from_previous_snapshot_kcal_per_day: float | None
    adaptive_tdee_kcal_per_day: float | None
    adaptive_median_absolute_deviation_kcal_per_day: float | None
    eligible_adaptive_estimate_count: int
    recommendation_status: RecommendationStatus
    recommendation_reasons: tuple[RecommendationReason, ...]
    raw_recommendation_adjustment_kcal_per_day: float | None
    limited_recommendation_adjustment_kcal_per_day: float | None
    macro_plan: PersonalizedMacroPlan
    planning_policy_version: str
    baseline_energy_formula_version: str
    baseline_activity_policy_version: str
    baseline_energy_equivalent_policy_version: str
    baseline_macro_policy_version: str
    lifecycle_policy_version: str
    trend_policy_version: str
    adaptive_policy_version: str
    recommendation_policy_version: str
    personalized_macro_policy_version: str
    assumptions: tuple[str, ...]
    target_envelope: NutritionTargetEnvelope | None = None


@dataclass(frozen=True, slots=True)
class PersonalizedPlanProgression:
    """Chronological snapshot history built from submitted-observation prefixes only."""

    snapshots: tuple[PersonalizedPlanSnapshot, ...]
    submitted_observation_count: int
    planning_policy_version: str
    assumptions: tuple[str, ...]


def build_personalized_plan_snapshot(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
    lifecycle_config: PersonalizationLifecycleConfig | None = None,
    recommendation_config: CalorieRecommendationConfig | None = None,
    training_assessment: TrainingDemandAssessment | None = None,
) -> PersonalizedPlanSnapshot:
    """Build the latest proposal, or an explicit undated baseline plan when history is empty."""
    ordered = _validated_observations(profile, observations, preferences, trend_config)
    if not ordered:
        return _build_snapshot(
            profile,
            (),
            preferences,
            None,
            trend_config,
            adaptive_config,
            lifecycle_config,
            recommendation_config,
            training_assessment,
        )
    return _build_progression(
        profile,
        ordered,
        preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
    ).snapshots[-1]


def build_personalized_plan_progression(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    trend_config: TrendAnalysisConfig | None = None,
    adaptive_config: AdaptiveTdeeConfig | None = None,
    lifecycle_config: PersonalizationLifecycleConfig | None = None,
    recommendation_config: CalorieRecommendationConfig | None = None,
) -> PersonalizedPlanProgression:
    """Recompute one proposal per submitted date using only chronological observation prefixes."""
    ordered = _validated_observations(profile, observations, preferences, trend_config)
    return _build_progression(
        profile,
        ordered,
        preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
    )


def _validated_observations(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    trend_config: TrendAnalysisConfig | None,
) -> tuple[DailyObservation, ...]:
    if not isinstance(profile, UserProfile):
        raise PersonalizedPlanningError("profile must be a UserProfile.")
    if not isinstance(preferences, NutritionPreferences):
        raise PersonalizedPlanningError("preferences must be NutritionPreferences.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise PersonalizedPlanningError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    submitted = tuple(observations)
    # Delegate duplicate-date and trend-config validation to the existing public analysis boundary.
    analyze_observation_trends(submitted, trend_config)
    return tuple(sorted(submitted, key=lambda item: item.observed_on))


def _build_progression(
    profile: UserProfile,
    observations: tuple[DailyObservation, ...],
    preferences: NutritionPreferences,
    trend_config: TrendAnalysisConfig | None,
    adaptive_config: AdaptiveTdeeConfig | None,
    lifecycle_config: PersonalizationLifecycleConfig | None,
    recommendation_config: CalorieRecommendationConfig | None,
) -> PersonalizedPlanProgression:
    snapshots: list[PersonalizedPlanSnapshot] = []
    previous: float | None = None
    for position in range(len(observations)):
        snapshot = _build_snapshot(
            profile,
            observations[: position + 1],
            preferences,
            previous,
            trend_config,
            adaptive_config,
            lifecycle_config,
            recommendation_config,
        )
        snapshots.append(snapshot)
        previous = snapshot.selected_calorie_target_kcal_per_day
    return PersonalizedPlanProgression(
        snapshots=tuple(snapshots),
        submitted_observation_count=len(observations),
        planning_policy_version=PERSONALIZED_PLANNING_POLICY_VERSION,
        assumptions=PERSONALIZED_PLANNING_ASSUMPTIONS,
    )


def _build_snapshot(
    profile: UserProfile,
    observations: tuple[DailyObservation, ...],
    preferences: NutritionPreferences,
    previous_target: float | None,
    trend_config: TrendAnalysisConfig | None,
    adaptive_config: AdaptiveTdeeConfig | None,
    lifecycle_config: PersonalizationLifecycleConfig | None,
    recommendation_config: CalorieRecommendationConfig | None,
    training_assessment: TrainingDemandAssessment | None = None,
) -> PersonalizedPlanSnapshot:
    baseline = calculate_calorie_target(profile)
    lifecycle = assess_personalization_lifecycle(
        profile, observations, lifecycle_config, trend_config, adaptive_config
    )
    recommendation = recommend_calorie_adjustment(
        profile, observations, recommendation_config, trend_config, adaptive_config
    )
    if (
        lifecycle.stage is PersonalizationStage.PERSONALIZED
        and recommendation.proposed_intake_target_kcal_per_day is not None
    ):
        calorie_basis = PlanCalorieBasis.PERSONALIZED
        selected_target = recommendation.proposed_intake_target_kcal_per_day
        macro_source = MacroCalorieSource.PERSONALIZED
        selection_assumption = "The existing actionable recommendation target is selected."
    elif lifecycle.stage is PersonalizationStage.PERSONALIZED:
        calorie_basis = PlanCalorieBasis.BASELINE
        selected_target = baseline.target_calories_kcal_per_day
        macro_source = MacroCalorieSource.BASELINE
        selection_assumption = (
            "The personalized lifecycle has no actionable safe recommendation; "
            "the existing baseline target is retained."
        )
    else:
        calorie_basis = PlanCalorieBasis.BASELINE
        selected_target = baseline.target_calories_kcal_per_day
        macro_source = MacroCalorieSource.BASELINE
        selection_assumption = (
            "The existing baseline target is retained until adaptive personalization is available."
        )
    macro_plan = calculate_personalized_macro_plan(
        profile,
        selected_target,
        macro_source,
        preferences,
        training_assessment=training_assessment,
    )
    target_envelope = calculate_nutrition_target_envelope(
        profile, selected_target, macro_source, preferences, training_assessment=training_assessment
    )
    return PersonalizedPlanSnapshot(
        as_of_date=None if not observations else observations[-1].observed_on,
        lifecycle_stage=lifecycle.stage,
        lifecycle_requirements=lifecycle.requirements,
        calorie_basis=calorie_basis,
        baseline_calorie_target_kcal_per_day=baseline.target_calories_kcal_per_day,
        selected_calorie_target_kcal_per_day=selected_target,
        previous_selected_calorie_target_kcal_per_day=previous_target,
        change_from_previous_snapshot_kcal_per_day=(
            None if previous_target is None else selected_target - previous_target
        ),
        adaptive_tdee_kcal_per_day=lifecycle.adaptive_tdee_kcal_per_day,
        adaptive_median_absolute_deviation_kcal_per_day=(
            lifecycle.median_absolute_deviation_kcal_per_day
        ),
        eligible_adaptive_estimate_count=lifecycle.eligible_adaptive_estimate_count,
        recommendation_status=recommendation.status,
        recommendation_reasons=recommendation.reasons,
        raw_recommendation_adjustment_kcal_per_day=recommendation.raw_adjustment_kcal_per_day,
        limited_recommendation_adjustment_kcal_per_day=(
            recommendation.recommended_adjustment_kcal_per_day
        ),
        macro_plan=macro_plan,
        planning_policy_version=PERSONALIZED_PLANNING_POLICY_VERSION,
        baseline_energy_formula_version=baseline.baseline_energy.ree_formula_version,
        baseline_activity_policy_version=baseline.baseline_energy.activity_policy_version,
        baseline_energy_equivalent_policy_version=baseline.energy_equivalent_policy_version,
        baseline_macro_policy_version=baseline.macro_policy_version,
        lifecycle_policy_version=lifecycle.lifecycle_policy_version,
        trend_policy_version=lifecycle.trend_policy_version,
        adaptive_policy_version=lifecycle.adaptive_policy_version,
        recommendation_policy_version=recommendation.recommendation_policy_version,
        personalized_macro_policy_version=macro_plan.macro_policy_version,
        assumptions=PERSONALIZED_PLANNING_ASSUMPTIONS + (selection_assumption,),
        target_envelope=target_envelope,
    )
