"""Small app-facing status contracts for the unified FitAdapt operation."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fitadapt.personalization.adaptation import PlanAdaptationAction, PlanAdaptationSource
from fitadapt.personalization.decisions import (
    RecommendationDecisionReason,
    RecommendationDecisionType,
)
from fitadapt.personalization.macros import PersonalizedMacroPlan
from fitadapt.personalization.targets import NutritionTargetEnvelope

INTEGRATION_STATUS_POLICY_VERSION = "profile_intelligence_integration_v2"


class IntegrationPlanSource(StrEnum):
    BASELINE = "baseline"
    PERSONALIZED = "personalized"
    PROFILE_RECALCULATION = "profile_recalculation"
    PROGRESS_ADAPTATION = "progress_adaptation"


class IntegrationAppStatus(StrEnum):
    PLAN_REMAINS_APPROPRIATE = "plan_remains_appropriate"
    MORE_DATA_NEEDED = "more_data_needed"
    DEFERRED_ESTIMATOR_STABILIZING = "deferred_estimator_stabilizing"
    DEFERRED_ADAPTIVE_EVIDENCE_AMBIGUOUS = "deferred_adaptive_evidence_ambiguous"
    PROPOSAL_AVAILABLE = "proposal_available"
    PROPOSAL_REQUIRES_REVIEW = "proposal_requires_review"
    REVERSAL_PENDING_CONFIRMATION = "reversal_pending_confirmation"
    UPDATE_AVAILABLE = "update_available"


@dataclass(frozen=True, slots=True)
class CurrentRecommendation:
    """The one authoritative active plan summary intended for the consuming app."""

    calorie_target_kcal_per_day: float
    macro_plan: PersonalizedMacroPlan
    target_envelope: NutritionTargetEnvelope | None
    effective_date: date | None
    source: IntegrationPlanSource
    is_active: bool
    is_authoritative: bool


@dataclass(frozen=True, slots=True)
class IntegrationStatus:
    """Consolidated attention and next-action signals without prose parsing."""

    user_attention_required: bool
    plan_update_available: bool
    more_data_needed: bool
    reversal_suppressed: bool
    current_plan_appropriate: bool
    recommendation_decision: RecommendationDecisionType
    adaptation_action: PlanAdaptationAction
    adaptation_source: PlanAdaptationSource
    app_status: IntegrationAppStatus
    proposal_available: bool
    proposal_requires_review: bool
    activation_ready: bool
    reversal_pending_confirmation: bool
    reason_codes: tuple[RecommendationDecisionReason, ...]
    summary: str
    policy_version: str
