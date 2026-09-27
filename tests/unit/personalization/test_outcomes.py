"""Contracts for deterministic plan-adherence and outcome evidence."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from fitadapt.analysis.trends import TrendAnalysisError
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.outcomes import (
    GoalProgressStatus,
    IntakeAdherenceStatus,
    OutcomeInterpretability,
    PlanOutcomeConfig,
    PlanOutcomeError,
    PlanOutcomeEvidenceSource,
    WeightTrendStatus,
    assess_plan_outcome,
)


@pytest.fixture
def profile() -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0,
    )


def _history(
    *,
    days: int = 28,
    intake: float | None = 2400.0,
    weight_change_per_day: float = -0.01,
    include_weight: bool = True,
) -> tuple[DailyObservation, ...]:
    start = date(2026, 1, 1)
    return tuple(
        DailyObservation(
            observed_on=start + timedelta(days=index),
            body_weight_kg=(80.0 + weight_change_per_day * index) if include_weight else None,
            energy_intake_kcal=intake,
        )
        for index in range(days)
    )


def test_sufficient_evidence_reports_adherence_and_existing_trend(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(), 2400)

    assert result.assessment_available is True
    assert result.overall_interpretability is OutcomeInterpretability.INTERPRETABLE
    assert result.intake_adherence is IntakeAdherenceStatus.NEAR_TARGET
    assert result.weight_trend_status is WeightTrendStatus.AVAILABLE
    assert result.goal_progress is GoalProgressStatus.BROADLY_ON_TRACK
    assert result.evidence_source is PlanOutcomeEvidenceSource.INTAKE_AND_WEIGHT
    assert result.observed_mean_intake_kcal_per_day == 2400
    assert result.prescribed_calorie_target_kcal_per_day == 2400


def test_as_of_cutoff_excludes_future_observations(profile: UserProfile) -> None:
    observations = _history() + (
        DailyObservation(observed_on=date(2026, 2, 1), body_weight_kg=90, energy_intake_kcal=4000),
    )
    result = assess_plan_outcome(profile, observations, 2400, as_of_date=date(2026, 1, 28))

    assert result.effective_date == date(2026, 1, 28)
    assert result.observed_mean_intake_kcal_per_day == 2400
    assert result.intake_contributor_count == 28


def test_future_cutoff_does_not_inflate_window_coverage(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(days=14), 2400, as_of_date=date(2026, 2, 1))

    assert result.effective_date == date(2026, 2, 1)
    assert result.overall_interpretability is OutcomeInterpretability.LIMITED
    assert result.intake_adherence is IntakeAdherenceStatus.INSUFFICIENT_EVIDENCE


def test_partial_history_does_not_claim_full_window_interpretability(
    profile: UserProfile,
) -> None:
    result = assess_plan_outcome(profile, _history(days=14), 2400)

    assert result.assessment_available is True
    assert result.overall_interpretability is OutcomeInterpretability.LIMITED
    assert result.intake_adherence is IntakeAdherenceStatus.INSUFFICIENT_EVIDENCE
    assert "insufficient_intake_evidence" in result.reason_codes


def test_missing_intake_is_not_zero_or_non_adherence(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(intake=None), 2400)

    assert result.assessment_available is True
    assert result.intake_adherence is IntakeAdherenceStatus.INSUFFICIENT_EVIDENCE
    assert result.observed_mean_intake_kcal_per_day is None
    assert result.evidence_source is PlanOutcomeEvidenceSource.WEIGHT_ONLY


def test_observed_zero_intake_remains_data(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(intake=0), 2400)

    assert result.intake_adherence is IntakeAdherenceStatus.BELOW_TARGET
    assert result.observed_mean_intake_kcal_per_day == 0


def test_nonadherent_intake_makes_weight_outcome_limited(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(intake=2100), 2400)

    assert result.intake_adherence is IntakeAdherenceStatus.BELOW_TARGET
    assert result.overall_interpretability is OutcomeInterpretability.LIMITED


def test_above_target_intake_and_reasons(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(intake=2700), 2400)

    assert result.intake_adherence is IntakeAdherenceStatus.ABOVE_TARGET
    assert "recorded_intake_above_target" in result.reason_codes


def test_intake_only_evidence_is_reported_without_weight_inference(
    profile: UserProfile,
) -> None:
    result = assess_plan_outcome(profile, _history(include_weight=False), 2400)

    assert result.evidence_source is PlanOutcomeEvidenceSource.INTAKE_ONLY
    assert result.weight_trend_status is WeightTrendStatus.INSUFFICIENT_EVIDENCE
    assert result.goal_progress is GoalProgressStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("goal", "requested_rate", "observed_rate", "expected"),
    [
        (Goal.CUT, -0.4, -0.01, GoalProgressStatus.SLOWER_THAN_EXPECTED),
        (Goal.CUT, -0.4, -0.12, GoalProgressStatus.FASTER_THAN_EXPECTED),
        (Goal.GAIN, 0.3, -0.01, GoalProgressStatus.DIRECTION_MISMATCH),
        (Goal.MAINTAIN, 0, -0.12, GoalProgressStatus.OUTSIDE_MAINTENANCE_RANGE),
    ],
)
def test_goal_progress_uses_requested_rate(
    profile: UserProfile,
    goal: Goal,
    requested_rate: float,
    observed_rate: float,
    expected: GoalProgressStatus,
) -> None:
    configured_profile = replace(profile, goal=goal, requested_weekly_change_kg=requested_rate)
    result = assess_plan_outcome(
        configured_profile,
        _history(weight_change_per_day=observed_rate),
        2400,
    )

    assert result.goal_progress is expected


def test_cutoff_before_all_observations_is_unavailable_with_date(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, _history(), 2400, as_of_date=date(2025, 12, 1))

    assert result.assessment_available is False
    assert result.effective_date == date(2025, 12, 1)
    assert result.evidence_source is PlanOutcomeEvidenceSource.INSUFFICIENT


def test_no_history_returns_explicit_unavailable_assessment(profile: UserProfile) -> None:
    result = assess_plan_outcome(profile, (), 2400)

    assert result.assessment_available is False
    assert result.effective_date is None
    assert result.reason_codes == ("no_observations_in_effective_window",)


@pytest.mark.parametrize("target", [0, -1, float("inf"), True])
def test_invalid_target_is_rejected(profile: UserProfile, target: float) -> None:
    with pytest.raises(PlanOutcomeError):
        assess_plan_outcome(profile, (), target)


def test_datetime_cutoff_is_rejected(profile: UserProfile) -> None:
    from datetime import datetime

    with pytest.raises(PlanOutcomeError, match="as_of_date"):
        assess_plan_outcome(profile, (), 2400, as_of_date=datetime(2026, 1, 1))


def test_config_rejects_non_finite_threshold() -> None:
    with pytest.raises(PlanOutcomeError):
        PlanOutcomeConfig(minimum_window_coverage=float("nan"))


@pytest.mark.parametrize(
    "config_values",
    [
        {"policy_version": ""},
        {"trailing_window_days": True},
        {"minimum_intake_contributors": 0},
        {"minimum_weight_contributors": 1.2},
        {"minimum_weight_span_days": -1},
        {"trend_window_days": 0},
        {"minimum_trend_contributors": 8, "trend_window_days": 7},
        {"minimum_intake_completeness": 1.1},
        {"minimum_weight_completeness": float("inf")},
        {"near_target_tolerance_kcal_per_day": -1},
    ],
)
def test_invalid_config_is_rejected(config_values: dict[str, object]) -> None:
    with pytest.raises(PlanOutcomeError):
        PlanOutcomeConfig(**config_values)  # type: ignore[arg-type]


def test_invalid_profile_observations_config_and_trend_config_are_rejected(
    profile: UserProfile,
) -> None:
    with pytest.raises(PlanOutcomeError, match="profile"):
        assess_plan_outcome(object(), (), 2400)  # type: ignore[arg-type]
    with pytest.raises(PlanOutcomeError, match="observations"):
        assess_plan_outcome(profile, (object(),), 2400)  # type: ignore[arg-type]
    with pytest.raises(PlanOutcomeError, match="config"):
        assess_plan_outcome(profile, (), 2400, config=object())  # type: ignore[arg-type]
    with pytest.raises(TrendAnalysisError):
        assess_plan_outcome(profile, (), 2400, trend_config=object())  # type: ignore[arg-type]
