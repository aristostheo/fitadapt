"""Stateless unified composition of FitAdapt's existing profile-intelligence outputs."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, AdaptiveTdeeResult, estimate_adaptive_tdee
from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisResult,
    analyze_observation_trends,
)
from fitadapt.baseline.targets import CalorieTargetEstimate, calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import UserProfile
from fitadapt.personalization.adaptation import (
    PlanAdaptationDecision,
    PlanAdaptationEvent,
    PlanAdaptationSource,
    evaluate_plan_adaptation,
)
from fitadapt.personalization.decisions import (
    RecommendationDecision,
    decide_plan_adjustment,
)
from fitadapt.personalization.dietary import (
    DEFAULT_NUTRITION_PREFERENCE_PROFILE,
    NutritionPreferenceAssessment,
    NutritionPreferenceProfile,
    assess_nutrition_preferences,
)
from fitadapt.personalization.history import RecommendationHistory, build_recommendation_history
from fitadapt.personalization.integration import (
    INTEGRATION_STATUS_POLICY_VERSION,
    CurrentRecommendation,
    IntegrationPlanSource,
    IntegrationStatus,
)
from fitadapt.personalization.lifecycle import (
    PersonalizationLifecycleConfig,
    PersonalizationLifecycleResult,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import (
    NutritionPreferences,
    PersonalizedMacroPlan,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.nutrition_feasibility import (
    NutritionFeasibilityAssessment,
    assess_nutrition_feasibility,
)
from fitadapt.personalization.outcomes import PlanOutcomeAssessment, assess_plan_outcome
from fitadapt.personalization.planning import (
    PersonalizedPlanProgression,
    PersonalizedPlanSnapshot,
    build_personalized_plan_progression,
    build_personalized_plan_snapshot,
)
from fitadapt.personalization.safety import TargetEligibilityAssessment, assess_target_eligibility
from fitadapt.personalization.targets import (
    NutritionTargetEnvelope,
    calculate_nutrition_target_envelope,
)
from fitadapt.personalization.training import (
    TrainingContext,
    TrainingDemandAssessment,
    assess_training_demand,
)
from fitadapt.recommendation.calories import (
    CalorieRecommendation,
    CalorieRecommendationConfig,
    recommend_calorie_adjustment,
)

PROFILE_INTELLIGENCE_POLICY_VERSION = "profile_intelligence_v1"
MAX_PROFILE_INTELLIGENCE_OBSERVATIONS = 1095
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
    dietary_assessment: NutritionPreferenceAssessment
    training_assessment: TrainingDemandAssessment
    nutrition_feasibility: NutritionFeasibilityAssessment
    plan_outcome: PlanOutcomeAssessment
    recommendation_decision: RecommendationDecision
    proposed_macro_plan: PersonalizedMacroPlan | None
    proposed_target_envelope: NutritionTargetEnvelope | None
    plan_adaptation: PlanAdaptationDecision
    recommendation_history: RecommendationHistory
    current_recommendation: CurrentRecommendation
    integration_status: IntegrationStatus
    target_safety: TargetEligibilityAssessment
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
    dietary_profile: NutritionPreferenceProfile | None = None,
    training_context: TrainingContext | None = None,
    outcome_as_of_date: date | None = None,
    adaptation_history: Sequence[PlanAdaptationEvent] = (),
    adaptation_source: PlanAdaptationSource = PlanAdaptationSource.PROGRESS_ADAPTATION,
) -> ProfileIntelligenceResult:
    """Compose current FitAdapt outputs without altering their individual policies."""
    _validate_inputs(
        profile,
        observations,
        preferences,
        include_plan_progression,
        dietary_profile,
        training_context,
    )
    effective_dietary_profile = dietary_profile or DEFAULT_NUTRITION_PREFERENCE_PROFILE
    submitted = tuple(observations)
    baseline = calculate_calorie_target(profile)
    target_safety = assess_target_eligibility(profile, baseline.baseline_energy)
    trends = analyze_observation_trends(submitted, trend_config)
    adaptive_tdee = estimate_adaptive_tdee(trends, adaptive_config)
    lifecycle = assess_personalization_lifecycle(
        profile, submitted, lifecycle_config, trend_config, adaptive_config
    )
    recommendation = recommend_calorie_adjustment(
        profile, submitted, recommendation_config, trend_config, adaptive_config
    )
    training_assessment = assess_training_demand(training_context, submitted)
    latest_plan = build_personalized_plan_snapshot(
        profile,
        submitted,
        preferences,
        trend_config,
        adaptive_config,
        lifecycle_config,
        recommendation_config,
        training_assessment,
    )
    decision_observations = (
        submitted
        if outcome_as_of_date is None
        else tuple(item for item in submitted if item.observed_on <= outcome_as_of_date)
    )
    scoped_plan = (
        latest_plan
        if outcome_as_of_date is None
        else build_personalized_plan_snapshot(
            profile,
            decision_observations,
            preferences,
            trend_config,
            adaptive_config,
            lifecycle_config,
            recommendation_config,
            assess_training_demand(training_context, decision_observations),
        )
    )
    effective_adaptation_history = (
        ()
        if adaptation_source is PlanAdaptationSource.PROFILE_RECALCULATION
        else adaptation_history
    )
    accepted_activation = _latest_accepted_activation(effective_adaptation_history)
    decision_training_assessment = (
        training_assessment
        if outcome_as_of_date is None
        else assess_training_demand(training_context, decision_observations)
    )
    active_macro_plan = scoped_plan.macro_plan
    active_source = _plan_source(scoped_plan, adaptation_source)
    active_effective_date = scoped_plan.as_of_date
    if accepted_activation is not None and (
        accepted_activation.new_active_target_kcal_per_day
        != scoped_plan.selected_calorie_target_kcal_per_day
    ):
        active_macro_plan = calculate_personalized_macro_plan(
            profile,
            accepted_activation.new_active_target_kcal_per_day,
            scoped_plan.macro_plan.calorie_source,
            preferences,
            training_assessment=decision_training_assessment,
        )
        active_effective_date = accepted_activation.effective_date
        active_source = (
            IntegrationPlanSource.PROFILE_RECALCULATION
            if adaptation_source is PlanAdaptationSource.PROFILE_RECALCULATION
            else IntegrationPlanSource.PROGRESS_ADAPTATION
        )
    dietary_assessment = assess_nutrition_preferences(
        effective_dietary_profile, latest_plan.target_envelope
    )
    nutrition_feasibility = assess_nutrition_feasibility(
        dietary_profile, dietary_assessment, latest_plan.macro_plan
    )
    decision_observations = (
        submitted
        if outcome_as_of_date is None
        else tuple(item for item in submitted if item.observed_on <= outcome_as_of_date)
    )
    plan_outcome = assess_plan_outcome(
        profile,
        submitted,
        active_macro_plan.calorie_target_kcal_per_day,
        as_of_date=outcome_as_of_date,
    )
    decision_adaptive_tdee = estimate_adaptive_tdee(
        analyze_observation_trends(decision_observations, trend_config), adaptive_config
    ).adaptive_tdee_kcal_per_day
    recommendation_decision = decide_plan_adjustment(
        profile,
        active_macro_plan.calorie_target_kcal_per_day,
        active_macro_plan,
        plan_outcome,
        decision_adaptive_tdee,
        target_safety=target_safety,
    )
    proposed_macro_plan = None
    proposed_target_envelope = None
    if recommendation_decision.numerical_change_proposed:
        proposed_macro_plan = calculate_personalized_macro_plan(
            profile,
            recommendation_decision.proposed_calorie_target_kcal_per_day,
            active_macro_plan.calorie_source,
            preferences,
            training_assessment=decision_training_assessment,
        )
        proposed_target_envelope = calculate_nutrition_target_envelope(
            profile,
            recommendation_decision.proposed_calorie_target_kcal_per_day,
            active_macro_plan.calorie_source,
            preferences,
            training_assessment=decision_training_assessment,
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
    plan_adaptation = evaluate_plan_adaptation(
        active_macro_plan,
        recommendation_decision,
        proposed_macro_plan,
        outcome_as_of_date
        or (None if not decision_observations else decision_observations[-1].observed_on),
        effective_adaptation_history,
        decision_observations,
        plan_outcome,
        source=adaptation_source,
    )
    recommendation_history = build_recommendation_history(
        adaptation_history,
        current_active_macro_plan=plan_adaptation.next_active_macro_plan,
        proposed_macro_plan=proposed_macro_plan,
        initial_plan_date=(
            None if not decision_observations else decision_observations[0].observed_on
        ),
    )
    current_recommendation = CurrentRecommendation(
        calorie_target_kcal_per_day=active_macro_plan.calorie_target_kcal_per_day,
        macro_plan=active_macro_plan,
        target_envelope=calculate_nutrition_target_envelope(
            profile,
            active_macro_plan.calorie_target_kcal_per_day,
            active_macro_plan.calorie_source,
            preferences,
            training_assessment=decision_training_assessment,
        ),
        effective_date=active_effective_date,
        source=active_source,
        is_active=True,
        is_authoritative=True,
    )
    integration_status = _integration_status(
        recommendation_decision, plan_adaptation, adaptation_source
    )
    return ProfileIntelligenceResult(
        baseline=baseline,
        trends=trends,
        adaptive_tdee=adaptive_tdee,
        lifecycle=lifecycle,
        recommendation=recommendation,
        latest_plan=latest_plan,
        dietary_assessment=dietary_assessment,
        training_assessment=training_assessment,
        nutrition_feasibility=nutrition_feasibility,
        plan_outcome=plan_outcome,
        recommendation_decision=recommendation_decision,
        proposed_macro_plan=proposed_macro_plan,
        proposed_target_envelope=proposed_target_envelope,
        plan_adaptation=plan_adaptation,
        recommendation_history=recommendation_history,
        current_recommendation=current_recommendation,
        integration_status=integration_status,
        target_safety=target_safety,
        plan_progression=progression,
        policy_version=PROFILE_INTELLIGENCE_POLICY_VERSION,
        assumptions=PROFILE_INTELLIGENCE_ASSUMPTIONS,
    )


def _latest_accepted_activation(adaptation_history: Sequence[PlanAdaptationEvent]):
    activations = tuple(event for event in adaptation_history if event.action.value == "activate")
    return max(activations, key=lambda event: event.effective_date) if activations else None


def _plan_source(latest_plan: PersonalizedPlanSnapshot, source: PlanAdaptationSource):
    if source is PlanAdaptationSource.PROFILE_RECALCULATION:
        return IntegrationPlanSource.PROFILE_RECALCULATION
    return (
        IntegrationPlanSource.PERSONALIZED
        if latest_plan.calorie_basis.value == "personalized"
        else IntegrationPlanSource.BASELINE
    )


def _integration_status(
    decision: RecommendationDecision,
    adaptation: PlanAdaptationDecision,
    source: PlanAdaptationSource,
) -> IntegrationStatus:
    return IntegrationStatus(
        user_attention_required=adaptation.user_attention_required,
        plan_update_available=adaptation.activation_available,
        more_data_needed=adaptation.action.value == "defer",
        reversal_suppressed=adaptation.action.value == "suppress",
        current_plan_appropriate=adaptation.action.value == "hold",
        recommendation_decision=decision.decision,
        adaptation_action=adaptation.action,
        adaptation_source=source,
        summary=(
            "A plan update is available for review."
            if adaptation.activation_available
            else "More data is needed before another plan change."
            if adaptation.action.value == "defer"
            else "A reversal was suppressed pending stronger evidence."
            if adaptation.action.value == "suppress"
            else "The current plan remains appropriate."
        ),
        policy_version=INTEGRATION_STATUS_POLICY_VERSION,
    )


def _validate_inputs(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    preferences: NutritionPreferences,
    include_plan_progression: bool,
    dietary_profile: NutritionPreferenceProfile | None,
    training_context: TrainingContext | None,
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
    if len(observations) > MAX_PROFILE_INTELLIGENCE_OBSERVATIONS:
        raise ProfileIntelligenceError(
            "observations cannot contain more than "
            f"{MAX_PROFILE_INTELLIGENCE_OBSERVATIONS} records."
        )
    if not isinstance(include_plan_progression, bool):
        raise ProfileIntelligenceError("include_plan_progression must be a bool.")
    if dietary_profile is not None and not isinstance(dietary_profile, NutritionPreferenceProfile):
        raise ProfileIntelligenceError(
            "dietary_profile must be a NutritionPreferenceProfile or None."
        )
    if training_context is not None and not isinstance(training_context, TrainingContext):
        raise ProfileIntelligenceError("training_context must be a TrainingContext or None.")
