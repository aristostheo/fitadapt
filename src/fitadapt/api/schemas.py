"""Transport schemas and pure domain-to-HTTP mappings for the FitAdapt API."""

import math
from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from fitadapt.adaptive.tdee import (
    AdaptiveTdeeConfig,
    AdaptiveTdeeResult,
    DailyTdeeEstimate,
    TdeeEligibility,
)
from fitadapt.analysis.trends import (
    DailyTrendPoint,
    DataQualityReport,
    TrendAnalysisConfig,
    TrendAnalysisResult,
)
from fitadapt.baseline.targets import CalorieTargetEstimate
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.intelligence import ProfileIntelligenceResult
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationLifecycleResult,
    PersonalizationRequirement,
    PersonalizationStage,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    PersonalizedMacroPlan,
)
from fitadapt.personalization.planning import (
    PersonalizedPlanProgression,
    PersonalizedPlanSnapshot,
    PlanCalorieBasis,
)
from fitadapt.recommendation.calories import (
    CalorieRecommendation,
    CalorieRecommendationConfig,
    RecommendationReason,
    RecommendationStatus,
)


class ApiModel(BaseModel):
    """Strict JSON boundary shared by all request and response schemas."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class NumericRequestModel(ApiModel):
    """Reject JSON booleans and non-finite numbers before domain mapping."""

    numeric_fields: ClassVar[frozenset[str]] = frozenset()
    integer_fields: ClassVar[frozenset[str]] = frozenset()

    @field_validator("*", mode="before")
    @classmethod
    def validate_numeric_transport_values(cls, value: object, info: object) -> object:
        field_name = getattr(info, "field_name", "")
        if field_name not in cls.numeric_fields or value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be a JSON number, not a boolean or string.")
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite.")
        if field_name in cls.integer_fields and not isinstance(value, int):
            raise ValueError(f"{field_name} must be a JSON integer.")
        return value


class ProfileRequest(NumericRequestModel):
    numeric_fields = frozenset(
        {"age_years", "height_cm", "weight_kg", "requested_weekly_change_kg"}
    )
    integer_fields = frozenset({"age_years"})

    age_years: int
    height_cm: float
    weight_kg: float
    sex_for_mifflin_equation: SexForMifflinEquation
    activity_level: ActivityLevel
    goal: Goal
    requested_weekly_change_kg: float

    def to_domain(self) -> UserProfile:
        return UserProfile(**self.model_dump())


class ObservationRequest(NumericRequestModel):
    numeric_fields = frozenset(
        {
            "body_weight_kg",
            "energy_intake_kcal",
            "protein_g",
            "carbohydrate_g",
            "fat_g",
            "steps",
            "strength_training_minutes",
            "cardio_minutes",
            "sleep_hours",
            "hunger_rating",
            "energy_rating",
        }
    )
    integer_fields = frozenset({"steps", "hunger_rating", "energy_rating"})

    observed_on: date
    body_weight_kg: float | None = None
    energy_intake_kcal: float | None = None
    protein_g: float | None = None
    carbohydrate_g: float | None = None
    fat_g: float | None = None
    steps: int | None = None
    strength_training_minutes: float | None = None
    cardio_minutes: float | None = None
    sleep_hours: float | None = None
    hunger_rating: int | None = None
    energy_rating: int | None = None

    def to_domain(self) -> DailyObservation:
        return DailyObservation(**self.model_dump())


class TrendConfigRequest(NumericRequestModel):
    numeric_fields = frozenset({"window_size_days", "minimum_observations"})
    integer_fields = numeric_fields
    window_size_days: int = 7
    minimum_observations: int = 4

    def to_domain(self) -> TrendAnalysisConfig:
        return TrendAnalysisConfig(**self.model_dump())


class AdaptiveConfigRequest(NumericRequestModel):
    numeric_fields = frozenset(
        {"energy_equivalent_kcal_per_kg", "aggregation_window_days", "minimum_estimate_points"}
    )
    integer_fields = frozenset({"aggregation_window_days", "minimum_estimate_points"})
    energy_equivalent_kcal_per_kg: float = 7700.0
    aggregation_window_days: int = 14
    minimum_estimate_points: int = 4

    def to_domain(self) -> AdaptiveTdeeConfig:
        return AdaptiveTdeeConfig(**self.model_dump())


class RecommendationConfigRequest(NumericRequestModel):
    numeric_fields = frozenset(
        {
            "minimum_calendar_history_days",
            "minimum_weight_completeness",
            "minimum_intake_completeness",
            "minimum_adaptive_estimates",
            "hold_threshold_kcal_per_day",
            "maximum_adjustment_kcal_per_day",
        }
    )
    integer_fields = frozenset({"minimum_calendar_history_days", "minimum_adaptive_estimates"})
    minimum_calendar_history_days: int = 21
    minimum_weight_completeness: float = 0.7
    minimum_intake_completeness: float = 0.7
    minimum_adaptive_estimates: int = 4
    hold_threshold_kcal_per_day: float = 75.0
    maximum_adjustment_kcal_per_day: float = 150.0

    def to_domain(self) -> CalorieRecommendationConfig:
        return CalorieRecommendationConfig(**self.model_dump())


class PersonalizationLifecycleConfigRequest(NumericRequestModel):
    numeric_fields = frozenset(
        {
            "minimum_calendar_history_days",
            "minimum_weight_completeness",
            "minimum_intake_completeness",
        }
    )
    integer_fields = frozenset({"minimum_calendar_history_days"})
    minimum_calendar_history_days: int = 14
    minimum_weight_completeness: float = 0.7
    minimum_intake_completeness: float = 0.7

    def to_domain(self) -> PersonalizationLifecycleConfig:
        return PersonalizationLifecycleConfig(**self.model_dump())


class BaselineRequest(ApiModel):
    profile: ProfileRequest


class TrendsRequest(ApiModel):
    observations: list[ObservationRequest]
    trend_config: TrendConfigRequest | None = None


class AdaptiveTdeeRequest(TrendsRequest):
    adaptive_config: AdaptiveConfigRequest | None = None


class CalorieRecommendationRequest(AdaptiveTdeeRequest):
    profile: ProfileRequest
    recommendation_config: RecommendationConfigRequest | None = None


class PersonalizationLifecycleRequest(AdaptiveTdeeRequest):
    profile: ProfileRequest
    lifecycle_config: PersonalizationLifecycleConfigRequest | None = None


class NutritionPreferencesRequest(NumericRequestModel):
    numeric_fields = frozenset({"custom_protein_g_per_kg", "custom_fat_percentage"})

    macro_strategy: MacroStrategy
    custom_protein_g_per_kg: float | None = None
    custom_fat_percentage: float | None = None

    def to_domain(self) -> NutritionPreferences:
        return NutritionPreferences(**self.model_dump())


class PersonalizedMacroPlanRequest(NumericRequestModel):
    numeric_fields = frozenset({"calorie_target_kcal_per_day"})

    profile: ProfileRequest
    preferences: NutritionPreferencesRequest
    calorie_target_kcal_per_day: float
    calorie_source: MacroCalorieSource


class ProfileIntelligenceRequest(ApiModel):
    """Main client request using existing engine defaults and strict progression opt-in."""

    profile: ProfileRequest
    observations: list[ObservationRequest]
    nutrition_preferences: NutritionPreferencesRequest
    include_plan_progression: StrictBool = False


class BaselineEnergyResponse(ApiModel):
    estimated_ree_kcal_per_day: float
    activity_level: ActivityLevel
    activity_multiplier: float
    estimated_tdee_kcal_per_day: float
    ree_formula_version: str
    activity_policy_version: str


class BaselineResponse(ApiModel):
    baseline_energy: BaselineEnergyResponse
    goal: Goal
    requested_weekly_change_kg: float
    daily_calorie_adjustment_kcal: float
    target_calories_kcal_per_day: float
    protein_g_per_day: float
    fat_g_per_day: float
    carbohydrate_g_per_day: float
    energy_equivalent_policy_version: str
    macro_policy_version: str
    assumptions: tuple[str, ...]


class TrendPointResponse(ApiModel):
    observed_on: date
    observation_present: bool
    body_weight_kg: float | None
    energy_intake_kcal: float | None
    steps: int | None
    trailing_body_weight_mean_kg: float | None
    trailing_energy_intake_mean_kcal: float | None
    trailing_steps_mean: float | None
    body_weight_contributor_count: int
    energy_intake_contributor_count: int
    steps_contributor_count: int
    window_weight_change_kg: float | None


class DataQualityResponse(ApiModel):
    first_date: date | None
    last_date: date | None
    total_calendar_days: int
    submitted_observation_records: int
    missing_calendar_days: int
    present_body_weight_values: int
    missing_body_weight_values: int
    body_weight_completeness_ratio: float
    present_energy_intake_values: int
    missing_energy_intake_values: int
    energy_intake_completeness_ratio: float
    present_step_values: int
    missing_step_values: int
    step_completeness_ratio: float


class TrendConfigResponse(ApiModel):
    window_size_days: int
    minimum_observations: int


class TrendsResponse(ApiModel):
    policy_version: str
    config: TrendConfigResponse
    points: tuple[TrendPointResponse, ...]
    data_quality: DataQualityResponse
    assumptions: tuple[str, ...]


class AdaptiveConfigResponse(ApiModel):
    energy_equivalent_kcal_per_kg: float
    aggregation_window_days: int
    minimum_estimate_points: int


class DailyTdeeEstimateResponse(ApiModel):
    observed_on: date
    trailing_energy_intake_mean_kcal: float | None
    window_weight_change_kg: float | None
    estimated_daily_energy_balance_kcal: float | None
    estimated_tdee_kcal_per_day: float | None
    eligibility: TdeeEligibility


class AdaptiveTdeeResponse(ApiModel):
    policy_version: str
    config: AdaptiveConfigResponse
    daily_estimates: tuple[DailyTdeeEstimateResponse, ...]
    adaptive_tdee_kcal_per_day: float | None
    median_absolute_deviation_kcal_per_day: float | None
    eligible_points_used: int
    total_eligible_points: int
    aggregation_start_date: date | None
    aggregation_end_date: date | None
    assumptions: tuple[str, ...]


class CalorieRecommendationResponse(ApiModel):
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


class PersonalizedMacroPlanResponse(ApiModel):
    calorie_target_kcal_per_day: float
    calorie_source: MacroCalorieSource
    strategy: MacroStrategy
    body_weight_kg: float
    protein_g_per_kg: float
    fat_percentage: float
    protein_g_per_day: float
    fat_g_per_day: float
    carbohydrate_g_per_day: float
    protein_kcal_per_day: float
    fat_kcal_per_day: float
    carbohydrate_kcal_per_day: float
    macro_policy_version: str
    assumptions: tuple[str, ...]


class PersonalizationLifecycleResponse(ApiModel):
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


class PersonalizedPlanSnapshotResponse(ApiModel):
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
    macro_plan: PersonalizedMacroPlanResponse
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


class PersonalizedPlanProgressionResponse(ApiModel):
    snapshots: tuple[PersonalizedPlanSnapshotResponse, ...]
    submitted_observation_count: int
    planning_policy_version: str
    assumptions: tuple[str, ...]


class ProfileIntelligenceResponse(ApiModel):
    policy_version: str
    baseline: BaselineResponse
    trends: TrendsResponse
    adaptive_tdee: AdaptiveTdeeResponse
    lifecycle: PersonalizationLifecycleResponse
    recommendation: CalorieRecommendationResponse
    latest_plan: PersonalizedPlanSnapshotResponse
    plan_progression: PersonalizedPlanProgressionResponse | None
    assumptions: tuple[str, ...]


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
    recommendation_policy_version: str


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody


def map_baseline(result: CalorieTargetEstimate) -> BaselineResponse:
    energy = result.baseline_energy
    return BaselineResponse(
        baseline_energy=BaselineEnergyResponse(
            estimated_ree_kcal_per_day=energy.estimated_ree_kcal_per_day,
            activity_level=energy.activity_level,
            activity_multiplier=energy.activity_multiplier,
            estimated_tdee_kcal_per_day=energy.estimated_tdee_kcal_per_day,
            ree_formula_version=energy.ree_formula_version,
            activity_policy_version=energy.activity_policy_version,
        ),
        goal=result.goal,
        requested_weekly_change_kg=result.requested_weekly_change_kg,
        daily_calorie_adjustment_kcal=result.daily_calorie_adjustment_kcal,
        target_calories_kcal_per_day=result.target_calories_kcal_per_day,
        protein_g_per_day=result.protein_g_per_day,
        fat_g_per_day=result.fat_g_per_day,
        carbohydrate_g_per_day=result.carbohydrate_g_per_day,
        energy_equivalent_policy_version=result.energy_equivalent_policy_version,
        macro_policy_version=result.macro_policy_version,
        assumptions=result.assumptions,
    )


def _map_point(point: DailyTrendPoint) -> TrendPointResponse:
    return TrendPointResponse(
        observed_on=point.observed_on,
        observation_present=point.observation_present,
        body_weight_kg=point.body_weight_kg,
        energy_intake_kcal=point.energy_intake_kcal,
        steps=point.steps,
        trailing_body_weight_mean_kg=point.trailing_body_weight_mean_kg,
        trailing_energy_intake_mean_kcal=point.trailing_energy_intake_mean_kcal,
        trailing_steps_mean=point.trailing_steps_mean,
        body_weight_contributor_count=point.body_weight_contributor_count,
        energy_intake_contributor_count=point.energy_intake_contributor_count,
        steps_contributor_count=point.steps_contributor_count,
        window_weight_change_kg=point.window_weight_change_kg,
    )


def _map_quality(quality: DataQualityReport) -> DataQualityResponse:
    return DataQualityResponse(
        first_date=quality.first_date,
        last_date=quality.last_date,
        total_calendar_days=quality.total_calendar_days,
        submitted_observation_records=quality.submitted_observation_records,
        missing_calendar_days=quality.missing_calendar_days,
        present_body_weight_values=quality.present_body_weight_values,
        missing_body_weight_values=quality.missing_body_weight_values,
        body_weight_completeness_ratio=quality.body_weight_completeness_ratio,
        present_energy_intake_values=quality.present_energy_intake_values,
        missing_energy_intake_values=quality.missing_energy_intake_values,
        energy_intake_completeness_ratio=quality.energy_intake_completeness_ratio,
        present_step_values=quality.present_step_values,
        missing_step_values=quality.missing_step_values,
        step_completeness_ratio=quality.step_completeness_ratio,
    )


def map_trends(result: TrendAnalysisResult) -> TrendsResponse:
    return TrendsResponse(
        policy_version=result.policy_version,
        config=TrendConfigResponse(
            window_size_days=result.config.window_size_days,
            minimum_observations=result.config.minimum_observations,
        ),
        points=tuple(_map_point(point) for point in result.points),
        data_quality=_map_quality(result.data_quality),
        assumptions=result.assumptions,
    )


def _map_daily_estimate(estimate: DailyTdeeEstimate) -> DailyTdeeEstimateResponse:
    return DailyTdeeEstimateResponse(
        observed_on=estimate.observed_on,
        trailing_energy_intake_mean_kcal=estimate.trailing_energy_intake_mean_kcal,
        window_weight_change_kg=estimate.window_weight_change_kg,
        estimated_daily_energy_balance_kcal=estimate.estimated_daily_energy_balance_kcal,
        estimated_tdee_kcal_per_day=estimate.estimated_tdee_kcal_per_day,
        eligibility=estimate.eligibility,
    )


def map_adaptive_tdee(result: AdaptiveTdeeResult) -> AdaptiveTdeeResponse:
    return AdaptiveTdeeResponse(
        policy_version=result.policy_version,
        config=AdaptiveConfigResponse(
            energy_equivalent_kcal_per_kg=result.config.energy_equivalent_kcal_per_kg,
            aggregation_window_days=result.config.aggregation_window_days,
            minimum_estimate_points=result.config.minimum_estimate_points,
        ),
        daily_estimates=tuple(_map_daily_estimate(item) for item in result.daily_estimates),
        adaptive_tdee_kcal_per_day=result.adaptive_tdee_kcal_per_day,
        median_absolute_deviation_kcal_per_day=result.median_absolute_deviation_kcal_per_day,
        eligible_points_used=result.eligible_points_used,
        total_eligible_points=result.total_eligible_points,
        aggregation_start_date=result.aggregation_start_date,
        aggregation_end_date=result.aggregation_end_date,
        assumptions=result.assumptions,
    )


def map_recommendation(result: CalorieRecommendation) -> CalorieRecommendationResponse:
    return CalorieRecommendationResponse(
        status=result.status,
        reasons=result.reasons,
        goal=result.goal,
        requested_weekly_change_kg=result.requested_weekly_change_kg,
        observed_window_weight_change_kg=result.observed_window_weight_change_kg,
        baseline_estimated_tdee_kcal_per_day=result.baseline_estimated_tdee_kcal_per_day,
        baseline_calorie_target_kcal_per_day=result.baseline_calorie_target_kcal_per_day,
        adaptive_tdee_kcal_per_day=result.adaptive_tdee_kcal_per_day,
        recent_mean_intake_kcal_per_day=result.recent_mean_intake_kcal_per_day,
        personalized_goal_target_kcal_per_day=result.personalized_goal_target_kcal_per_day,
        raw_adjustment_kcal_per_day=result.raw_adjustment_kcal_per_day,
        recommended_adjustment_kcal_per_day=result.recommended_adjustment_kcal_per_day,
        proposed_intake_target_kcal_per_day=result.proposed_intake_target_kcal_per_day,
        calendar_history_days=result.calendar_history_days,
        weight_completeness=result.weight_completeness,
        intake_completeness=result.intake_completeness,
        adaptive_estimate_count=result.adaptive_estimate_count,
        recommendation_policy_version=result.recommendation_policy_version,
        trend_policy_version=result.trend_policy_version,
        adaptive_policy_version=result.adaptive_policy_version,
        energy_equivalent_policy_version=result.energy_equivalent_policy_version,
        assumptions=result.assumptions,
    )


def map_personalized_macro_plan(result: PersonalizedMacroPlan) -> PersonalizedMacroPlanResponse:
    return PersonalizedMacroPlanResponse(
        calorie_target_kcal_per_day=result.calorie_target_kcal_per_day,
        calorie_source=result.calorie_source,
        strategy=result.strategy,
        body_weight_kg=result.body_weight_kg,
        protein_g_per_kg=result.protein_g_per_kg,
        fat_percentage=result.fat_percentage,
        protein_g_per_day=result.protein_g_per_day,
        fat_g_per_day=result.fat_g_per_day,
        carbohydrate_g_per_day=result.carbohydrate_g_per_day,
        protein_kcal_per_day=result.protein_kcal_per_day,
        fat_kcal_per_day=result.fat_kcal_per_day,
        carbohydrate_kcal_per_day=result.carbohydrate_kcal_per_day,
        macro_policy_version=result.macro_policy_version,
        assumptions=result.assumptions,
    )


def map_personalization_lifecycle(
    result: PersonalizationLifecycleResult,
) -> PersonalizationLifecycleResponse:
    return PersonalizationLifecycleResponse(
        stage=result.stage,
        requirements=result.requirements,
        calendar_history_days=result.calendar_history_days,
        weight_observation_count=result.weight_observation_count,
        intake_observation_count=result.intake_observation_count,
        weight_completeness=result.weight_completeness,
        intake_completeness=result.intake_completeness,
        eligible_adaptive_estimate_count=result.eligible_adaptive_estimate_count,
        required_eligible_estimate_count=result.required_eligible_estimate_count,
        adaptive_tdee_kcal_per_day=result.adaptive_tdee_kcal_per_day,
        median_absolute_deviation_kcal_per_day=result.median_absolute_deviation_kcal_per_day,
        lifecycle_policy_version=result.lifecycle_policy_version,
        trend_policy_version=result.trend_policy_version,
        adaptive_policy_version=result.adaptive_policy_version,
        assumptions=result.assumptions,
    )


def map_personalized_plan_snapshot(
    result: PersonalizedPlanSnapshot,
) -> PersonalizedPlanSnapshotResponse:
    return PersonalizedPlanSnapshotResponse(
        as_of_date=result.as_of_date,
        lifecycle_stage=result.lifecycle_stage,
        lifecycle_requirements=result.lifecycle_requirements,
        calorie_basis=result.calorie_basis,
        baseline_calorie_target_kcal_per_day=result.baseline_calorie_target_kcal_per_day,
        selected_calorie_target_kcal_per_day=result.selected_calorie_target_kcal_per_day,
        previous_selected_calorie_target_kcal_per_day=result.previous_selected_calorie_target_kcal_per_day,
        change_from_previous_snapshot_kcal_per_day=result.change_from_previous_snapshot_kcal_per_day,
        adaptive_tdee_kcal_per_day=result.adaptive_tdee_kcal_per_day,
        adaptive_median_absolute_deviation_kcal_per_day=(
            result.adaptive_median_absolute_deviation_kcal_per_day
        ),
        eligible_adaptive_estimate_count=result.eligible_adaptive_estimate_count,
        recommendation_status=result.recommendation_status,
        recommendation_reasons=result.recommendation_reasons,
        raw_recommendation_adjustment_kcal_per_day=(
            result.raw_recommendation_adjustment_kcal_per_day
        ),
        limited_recommendation_adjustment_kcal_per_day=(
            result.limited_recommendation_adjustment_kcal_per_day
        ),
        macro_plan=map_personalized_macro_plan(result.macro_plan),
        planning_policy_version=result.planning_policy_version,
        baseline_energy_formula_version=result.baseline_energy_formula_version,
        baseline_activity_policy_version=result.baseline_activity_policy_version,
        baseline_energy_equivalent_policy_version=(
            result.baseline_energy_equivalent_policy_version
        ),
        baseline_macro_policy_version=result.baseline_macro_policy_version,
        lifecycle_policy_version=result.lifecycle_policy_version,
        trend_policy_version=result.trend_policy_version,
        adaptive_policy_version=result.adaptive_policy_version,
        recommendation_policy_version=result.recommendation_policy_version,
        personalized_macro_policy_version=result.personalized_macro_policy_version,
        assumptions=result.assumptions,
    )


def map_personalized_plan_progression(
    result: PersonalizedPlanProgression,
) -> PersonalizedPlanProgressionResponse:
    return PersonalizedPlanProgressionResponse(
        snapshots=tuple(map_personalized_plan_snapshot(item) for item in result.snapshots),
        submitted_observation_count=result.submitted_observation_count,
        planning_policy_version=result.planning_policy_version,
        assumptions=result.assumptions,
    )


def map_profile_intelligence(result: ProfileIntelligenceResult) -> ProfileIntelligenceResponse:
    return ProfileIntelligenceResponse(
        policy_version=result.policy_version,
        baseline=map_baseline(result.baseline),
        trends=map_trends(result.trends),
        adaptive_tdee=map_adaptive_tdee(result.adaptive_tdee),
        lifecycle=map_personalization_lifecycle(result.lifecycle),
        recommendation=map_recommendation(result.recommendation),
        latest_plan=map_personalized_plan_snapshot(result.latest_plan),
        plan_progression=(
            None
            if result.plan_progression is None
            else map_personalized_plan_progression(result.plan_progression)
        ),
        assumptions=result.assumptions,
    )
