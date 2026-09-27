"""Deterministic evidence assessment for current-plan adherence and observed outcomes."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    analyze_observation_trends,
)
from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import Goal, UserProfile

PLAN_OUTCOME_POLICY_VERSION = "plan_outcome_assessment_v1"


class PlanOutcomeError(ValueError):
    """Raised when plan-outcome assessment inputs violate the domain contract."""


class OutcomeInterpretability(StrEnum):
    INSUFFICIENT = "insufficient"
    LIMITED = "limited"
    INTERPRETABLE = "interpretable"


class IntakeAdherenceStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BELOW_TARGET = "below_target"
    NEAR_TARGET = "near_target"
    ABOVE_TARGET = "above_target"


class WeightTrendStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AVAILABLE = "available"


class GoalProgressStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SLOWER_THAN_EXPECTED = "slower_than_expected"
    BROADLY_ON_TRACK = "broadly_on_track"
    FASTER_THAN_EXPECTED = "faster_than_expected"
    DIRECTION_MISMATCH = "direction_mismatch"
    OUTSIDE_MAINTENANCE_RANGE = "outside_maintenance_range"
    NOT_APPLICABLE = "not_applicable"


class PlanOutcomeEvidenceSource(StrEnum):
    INTAKE_ONLY = "intake_only"
    WEIGHT_ONLY = "weight_only"
    INTAKE_AND_WEIGHT = "intake_and_weight"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class PlanOutcomeConfig:
    policy_version: str = PLAN_OUTCOME_POLICY_VERSION
    trailing_window_days: int = 28
    minimum_intake_contributors: int = 14
    minimum_weight_contributors: int = 4
    minimum_intake_completeness: float = 0.7
    minimum_weight_completeness: float = 0.3
    minimum_window_coverage: float = 0.7
    near_target_tolerance_kcal_per_day: float = 150.0
    progress_rate_tolerance_kg_per_week: float = 0.1
    minimum_weight_span_days: int = 14
    trend_window_days: int = 7
    minimum_trend_contributors: int = 4

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise PlanOutcomeError("policy_version must be a non-empty string.")
        for name in (
            "trailing_window_days",
            "minimum_intake_contributors",
            "minimum_weight_contributors",
            "minimum_weight_span_days",
            "trend_window_days",
            "minimum_trend_contributors",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise PlanOutcomeError(f"{name} must be a positive integer.")
        for name in (
            "minimum_intake_completeness",
            "minimum_weight_completeness",
            "minimum_window_coverage",
        ):
            value = validate_finite_number(
                getattr(self, name), field_name=name, error_type=PlanOutcomeError
            )
            if not 0.0 <= value <= 1.0:
                raise PlanOutcomeError(f"{name} must be between 0 and 1.")
            object.__setattr__(self, name, value)
        for name in ("near_target_tolerance_kcal_per_day", "progress_rate_tolerance_kg_per_week"):
            value = validate_finite_number(
                getattr(self, name), field_name=name, error_type=PlanOutcomeError
            )
            if value < 0:
                raise PlanOutcomeError(f"{name} must be a non-negative number.")
            object.__setattr__(self, name, value)
        if self.minimum_trend_contributors > self.trend_window_days:
            raise PlanOutcomeError("minimum_trend_contributors cannot exceed trend_window_days.")


@dataclass(frozen=True, slots=True)
class PlanOutcomeAssessment:
    assessment_available: bool
    effective_date: date | None
    observation_window_days: int
    overall_interpretability: OutcomeInterpretability
    intake_adherence: IntakeAdherenceStatus
    weight_trend_status: WeightTrendStatus
    goal_progress: GoalProgressStatus
    observed_mean_intake_kcal_per_day: float | None
    prescribed_calorie_target_kcal_per_day: float
    intake_deviation_kcal_per_day: float | None
    observed_weight_change_kg_per_week: float | None
    intended_weight_change_kg_per_week: float
    intake_observation_records: int
    intake_contributor_count: int
    intake_completeness: float
    weight_observation_records: int
    weight_contributor_count: int
    weight_completeness: float
    weight_span_days: int
    evidence_source: PlanOutcomeEvidenceSource
    reason_codes: tuple[str, ...]
    policy_version: str
    assumptions: tuple[str, ...]


def assess_plan_outcome(
    profile: UserProfile,
    observations: Sequence[DailyObservation],
    prescribed_calorie_target_kcal_per_day: float,
    config: PlanOutcomeConfig | None = None,
    trend_config: TrendAnalysisConfig | None = None,
    as_of_date: date | None = None,
) -> PlanOutcomeAssessment:
    """Assess current plan adherence and outcome without making plan changes."""
    if not isinstance(profile, UserProfile):
        raise PlanOutcomeError("profile must be a UserProfile.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise PlanOutcomeError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    if as_of_date is not None and (
        isinstance(as_of_date, datetime) or not isinstance(as_of_date, date)
    ):
        raise PlanOutcomeError("as_of_date must be a datetime.date or None.")
    target = validate_finite_number(
        prescribed_calorie_target_kcal_per_day,
        field_name="prescribed_calorie_target_kcal_per_day",
        error_type=PlanOutcomeError,
    )
    if target <= 0:
        raise PlanOutcomeError("prescribed_calorie_target_kcal_per_day must be greater than zero.")
    effective = config or PlanOutcomeConfig()
    if not isinstance(effective, PlanOutcomeConfig):
        raise PlanOutcomeError("config must be a PlanOutcomeConfig or None.")
    submitted = tuple(observations)
    analyze_observation_trends(submitted, trend_config)
    latest_date = max((item.observed_on for item in submitted), default=None)
    cutoff = as_of_date or latest_date
    eligible = tuple(
        item for item in submitted if cutoff is not None and item.observed_on <= cutoff
    )
    if not eligible:
        return _empty_assessment(target, profile, effective, cutoff)
    trends = analyze_observation_trends(
        eligible,
        trend_config
        or TrendAnalysisConfig(effective.trend_window_days, effective.minimum_trend_contributors),
    )
    quality = trends.data_quality
    end = cutoff
    start = end - timedelta(days=effective.trailing_window_days - 1)
    window_points = tuple(point for point in trends.points if start <= point.observed_on <= end)
    intake_values = tuple(
        point.energy_intake_kcal for point in window_points if point.energy_intake_kcal is not None
    )
    weight_values = tuple(
        point.body_weight_kg for point in window_points if point.body_weight_kg is not None
    )
    intake_records = sum(point.observation_present for point in window_points)
    window_days = min(
        effective.trailing_window_days,
        (min(end, quality.last_date) - max(start, quality.first_date)).days + 1,
    )
    window_coverage = window_days / effective.trailing_window_days
    intake_count = len(intake_values)
    weight_count = len(weight_values)
    intake_completeness = 0.0 if window_days == 0 else intake_count / window_days
    weight_completeness = 0.0 if window_days == 0 else weight_count / window_days
    intake_sufficient = (
        window_coverage >= effective.minimum_window_coverage
        and intake_count >= effective.minimum_intake_contributors
        and intake_completeness >= effective.minimum_intake_completeness
    )
    weight_dates = tuple(
        point.observed_on for point in window_points if point.body_weight_kg is not None
    )
    weight_span = 0 if len(weight_dates) < 2 else (weight_dates[-1] - weight_dates[0]).days
    weight_sufficient = (
        window_coverage >= effective.minimum_window_coverage
        and weight_count >= effective.minimum_weight_contributors
        and weight_completeness >= effective.minimum_weight_completeness
        and weight_span >= effective.minimum_weight_span_days
    )
    mean_intake = None if not intake_sufficient else sum(intake_values) / intake_count
    deviation = None if mean_intake is None else mean_intake - target
    adherence = (
        _intake_adherence(deviation, effective)
        if deviation is not None
        else IntakeAdherenceStatus.INSUFFICIENT_EVIDENCE
    )
    observed_rate = _weight_rate(window_points, weight_sufficient)
    weight_status = (
        WeightTrendStatus.AVAILABLE
        if observed_rate is not None
        else WeightTrendStatus.INSUFFICIENT_EVIDENCE
    )
    progress = (
        _goal_progress(profile, observed_rate, effective)
        if observed_rate is not None
        else GoalProgressStatus.INSUFFICIENT_EVIDENCE
    )
    overall = (
        OutcomeInterpretability.INTERPRETABLE
        if (
            intake_sufficient
            and adherence is IntakeAdherenceStatus.NEAR_TARGET
            and weight_sufficient
        )
        else OutcomeInterpretability.LIMITED
        if intake_count > 0 or weight_count > 0
        else OutcomeInterpretability.INSUFFICIENT
    )
    has_intake = intake_count > 0
    has_weight = weight_count > 0
    evidence_source = (
        PlanOutcomeEvidenceSource.INTAKE_AND_WEIGHT
        if has_intake and has_weight
        else PlanOutcomeEvidenceSource.INTAKE_ONLY
        if has_intake
        else PlanOutcomeEvidenceSource.WEIGHT_ONLY
        if has_weight
        else PlanOutcomeEvidenceSource.INSUFFICIENT
    )
    reasons = _reasons(intake_sufficient, weight_sufficient, adherence, progress)
    return PlanOutcomeAssessment(
        assessment_available=has_intake or has_weight,
        effective_date=end,
        observation_window_days=effective.trailing_window_days,
        overall_interpretability=overall,
        intake_adherence=adherence,
        weight_trend_status=weight_status,
        goal_progress=progress,
        observed_mean_intake_kcal_per_day=None if mean_intake is None else float(mean_intake),
        prescribed_calorie_target_kcal_per_day=target,
        intake_deviation_kcal_per_day=None if deviation is None else float(deviation),
        observed_weight_change_kg_per_week=observed_rate,
        intended_weight_change_kg_per_week=float(profile.requested_weekly_change_kg),
        intake_observation_records=intake_records,
        intake_contributor_count=intake_count,
        intake_completeness=float(intake_completeness),
        weight_observation_records=intake_records,
        weight_contributor_count=weight_count,
        weight_completeness=float(weight_completeness),
        weight_span_days=weight_span,
        evidence_source=evidence_source,
        reason_codes=reasons,
        policy_version=effective.policy_version,
        assumptions=(
            "Missing intake or weight records remain unknown and are not converted to zero.",
            "Adherence compares recorded intake with the prescribed target; it does not estimate "
            "unlogged intake.",
            "Weight trends use existing trailing calendar means and compare with the requested "
            "rate.",
            "Outcome interpretation is not a confidence score and does not change targets.",
        ),
    )


def _intake_adherence(deviation: float, config: PlanOutcomeConfig) -> IntakeAdherenceStatus:
    if deviation < -config.near_target_tolerance_kcal_per_day:
        return IntakeAdherenceStatus.BELOW_TARGET
    if deviation > config.near_target_tolerance_kcal_per_day:
        return IntakeAdherenceStatus.ABOVE_TARGET
    return IntakeAdherenceStatus.NEAR_TARGET


def _empty_assessment(
    target: float,
    profile: UserProfile,
    config: PlanOutcomeConfig,
    effective_date: date | None,
) -> PlanOutcomeAssessment:
    return PlanOutcomeAssessment(
        assessment_available=False,
        effective_date=effective_date,
        observation_window_days=config.trailing_window_days,
        overall_interpretability=OutcomeInterpretability.INSUFFICIENT,
        intake_adherence=IntakeAdherenceStatus.INSUFFICIENT_EVIDENCE,
        weight_trend_status=WeightTrendStatus.INSUFFICIENT_EVIDENCE,
        goal_progress=GoalProgressStatus.INSUFFICIENT_EVIDENCE,
        observed_mean_intake_kcal_per_day=None,
        prescribed_calorie_target_kcal_per_day=target,
        intake_deviation_kcal_per_day=None,
        observed_weight_change_kg_per_week=None,
        intended_weight_change_kg_per_week=float(profile.requested_weekly_change_kg),
        intake_observation_records=0,
        intake_contributor_count=0,
        intake_completeness=0.0,
        weight_observation_records=0,
        weight_contributor_count=0,
        weight_completeness=0.0,
        weight_span_days=0,
        evidence_source=PlanOutcomeEvidenceSource.INSUFFICIENT,
        reason_codes=("no_observations_in_effective_window",),
        policy_version=config.policy_version,
        assumptions=(
            "No observations were available on or before the effective date.",
            "Missing information is unknown and does not imply non-adherence.",
        ),
    )


def _weight_rate(points: tuple[object, ...], sufficient: bool) -> float | None:
    if not sufficient:
        return None
    smoothed = tuple(point for point in points if point.trailing_body_weight_mean_kg is not None)
    if len(smoothed) < 2:
        return None
    span_days = (smoothed[-1].observed_on - smoothed[0].observed_on).days
    if span_days <= 0:
        return None
    return float(
        (smoothed[-1].trailing_body_weight_mean_kg - smoothed[0].trailing_body_weight_mean_kg)
        * 7
        / span_days
    )


def _goal_progress(
    profile: UserProfile, observed_rate: float, config: PlanOutcomeConfig
) -> GoalProgressStatus:
    target = profile.requested_weekly_change_kg
    tolerance = config.progress_rate_tolerance_kg_per_week
    if profile.goal is Goal.MAINTAIN:
        if abs(observed_rate) <= tolerance:
            return GoalProgressStatus.BROADLY_ON_TRACK
        return GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE
    if target == 0:
        return GoalProgressStatus.INSUFFICIENT_EVIDENCE
    if observed_rate * target < 0:
        return GoalProgressStatus.DIRECTION_MISMATCH
    difference = abs(observed_rate) - abs(target)
    if difference < -tolerance:
        return GoalProgressStatus.SLOWER_THAN_EXPECTED
    if difference > tolerance:
        return GoalProgressStatus.FASTER_THAN_EXPECTED
    return GoalProgressStatus.BROADLY_ON_TRACK


def _reasons(
    intake_sufficient: bool,
    weight_sufficient: bool,
    adherence: IntakeAdherenceStatus,
    progress: GoalProgressStatus,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not intake_sufficient:
        reasons.append("insufficient_intake_evidence")
    if not weight_sufficient:
        reasons.append("insufficient_weight_evidence")
    if adherence is IntakeAdherenceStatus.BELOW_TARGET:
        reasons.append("recorded_intake_below_target")
    elif adherence is IntakeAdherenceStatus.ABOVE_TARGET:
        reasons.append("recorded_intake_above_target")
    elif adherence is IntakeAdherenceStatus.NEAR_TARGET:
        reasons.append("recorded_intake_near_target")
    if progress is GoalProgressStatus.SLOWER_THAN_EXPECTED:
        reasons.append("weight_progress_slower_than_requested")
    elif progress is GoalProgressStatus.FASTER_THAN_EXPECTED:
        reasons.append("weight_progress_faster_than_requested")
    elif progress is GoalProgressStatus.DIRECTION_MISMATCH:
        reasons.append("weight_change_direction_differs_from_goal")
    elif progress is GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE:
        reasons.append("weight_change_outside_maintenance_range")
    elif progress is GoalProgressStatus.BROADLY_ON_TRACK:
        reasons.append("weight_progress_broadly_on_track")
    if intake_sufficient and weight_sufficient and adherence is IntakeAdherenceStatus.NEAR_TARGET:
        reasons.append("outcome_interpretable_for_review")
    return tuple(dict.fromkeys(reasons))
