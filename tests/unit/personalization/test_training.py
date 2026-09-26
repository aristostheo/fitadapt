"""Domain contracts for deterministic training-demand assessment."""

from dataclasses import FrozenInstanceError, astuple
from datetime import date, timedelta
from math import inf, nan

import pytest

from fitadapt.domain.observation import DailyObservation
from fitadapt.personalization.training import (
    MAXIMUM_TYPICAL_STEPS,
    OccupationActivity,
    PrimaryTrainingFocus,
    TrainingContext,
    TrainingDemandConfig,
    TrainingDemandLevel,
    TrainingDomainError,
    TrainingEvidenceSource,
    TrainingIntensity,
    TrainingPriority,
    assess_training_demand,
)


def observations(
    days: int,
    *,
    steps: int | None = 5000,
    strength: float | None = 0,
    cardio: float | None = 0,
    start=date(2026, 1, 1),
) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=start + timedelta(days=index),
            steps=steps,
            strength_training_minutes=strength,
            cardio_minutes=cardio,
        )
        for index in range(days)
    )


def test_all_public_enums_have_required_values() -> None:
    assert {item.value for item in OccupationActivity} == {
        "mostly_seated",
        "mixed",
        "mostly_on_feet",
        "physically_demanding",
    }
    assert {item.value for item in TrainingIntensity} == {"low", "moderate", "vigorous"}
    assert {item.value for item in PrimaryTrainingFocus} == {
        "general",
        "resistance",
        "endurance",
        "intermittent_sport",
        "mixed",
    }
    assert {item.value for item in TrainingDemandLevel} == {"low", "moderate", "high", "very_high"}
    assert {item.value for item in TrainingPriority} == {"low", "moderate", "high"}
    assert {item.value for item in TrainingEvidenceSource} == {
        "questionnaire",
        "observations",
        "combined",
        "insufficient",
    }


def test_context_validates_boundaries_and_is_frozen_slotted() -> None:
    context = TrainingContext(OccupationActivity.MOSTLY_SEATED)
    assert astuple(context)[1:6] == (0, 0.0, 0, 0.0, None)
    with pytest.raises(FrozenInstanceError):
        context.resistance_days_per_week = 1  # type: ignore[misc]
    with pytest.raises(TrainingDomainError):
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            resistance_days_per_week=1,
            resistance_minutes_per_week=0,
        )
    with pytest.raises(TrainingDomainError):
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED, cardio_days_per_week=1, cardio_minutes_per_week=30
        )
    with pytest.raises(TrainingDomainError):
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED, typical_daily_steps=MAXIMUM_TYPICAL_STEPS + 1
        )
    with pytest.raises(TrainingDomainError):
        TrainingContext(OccupationActivity.MOSTLY_SEATED, typical_daily_steps=True)  # type: ignore[arg-type]
    with pytest.raises(TrainingDomainError):
        TrainingContext(OccupationActivity.MOSTLY_SEATED, resistance_minutes_per_week=nan)  # type: ignore[arg-type]
    with pytest.raises(TrainingDomainError):
        TrainingContext(OccupationActivity.MOSTLY_SEATED, resistance_minutes_per_week=inf)  # type: ignore[arg-type]


def test_questionnaire_only_contexts_classify_without_activity_logs() -> None:
    no_training = assess_training_demand(TrainingContext(OccupationActivity.MOSTLY_SEATED))
    resistance = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            4,
            240,
            primary_training_focus=PrimaryTrainingFocus.RESISTANCE,
        )
    )
    endurance = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            cardio_days_per_week=5,
            cardio_minutes_per_week=360,
            cardio_intensity=TrainingIntensity.VIGOROUS,
            primary_training_focus=PrimaryTrainingFocus.ENDURANCE,
        )
    )
    assert (
        no_training.assessment_available and no_training.overall_demand is TrainingDemandLevel.LOW
    )
    assert resistance.resistance_demand is TrainingDemandLevel.HIGH
    assert resistance.protein_priority is TrainingPriority.HIGH
    assert endurance.aerobic_sport_demand is TrainingDemandLevel.VERY_HIGH
    assert endurance.carbohydrate_performance_priority is TrainingPriority.HIGH
    assert resistance.evidence_source is TrainingEvidenceSource.QUESTIONNAIRE


def test_observation_only_requires_coverage_and_preserves_zero() -> None:
    insufficient = assess_training_demand(None, observations(2))
    sufficient = assess_training_demand(None, observations(14, steps=0, strength=0, cardio=0))
    assert insufficient.assessment_available is False
    assert insufficient.evidence_source is TrainingEvidenceSource.INSUFFICIENT
    assert sufficient.assessment_available is True
    assert sufficient.evidence_source is TrainingEvidenceSource.OBSERVATIONS
    assert sufficient.overall_demand is TrainingDemandLevel.LOW
    assert sufficient.strength_evidence.contributor_count == 14
    assert sufficient.strength_evidence.weekly_equivalent == 0.0
    assert sufficient.cardio_evidence.completeness == 1.0


def test_combined_evidence_uses_observed_streams_and_keeps_questionnaire_context() -> None:
    context = TrainingContext(
        OccupationActivity.MOSTLY_SEATED,
        resistance_days_per_week=4,
        resistance_minutes_per_week=240,
    )
    result = assess_training_demand(context, observations(14, strength=0, cardio=None))
    assert result.evidence_source is TrainingEvidenceSource.COMBINED
    assert result.resistance_demand is TrainingDemandLevel.LOW
    assert "questionnaire_context_used" in result.reason_codes
    assert "observed_strength_minutes_used" in result.reason_codes
    assert result.cardio_evidence.evidence_available is False


def test_unsorted_inputs_are_not_mutated_and_future_values_are_excluded_from_prefix() -> None:
    items = observations(14)
    unsorted = tuple(reversed(items))
    result = assess_training_demand(None, unsorted)
    assert result.effective_date == date(2026, 1, 14)
    assert unsorted == tuple(reversed(items))
    prefix = assess_training_demand(None, items[:7])
    extended = assess_training_demand(None, items)
    assert prefix.effective_date == date(2026, 1, 7)
    assert prefix.effective_date != extended.effective_date


def test_duplicate_dates_and_invalid_config_are_domain_errors() -> None:
    duplicate = observations(1) * 2
    with pytest.raises(TrainingDomainError, match="Duplicate"):
        assess_training_demand(None, duplicate)
    with pytest.raises(TrainingDomainError):
        TrainingDemandConfig(minimum_completeness=0)
    with pytest.raises(TrainingDomainError):
        TrainingDemandConfig(moderate_minutes_per_week=300, high_minutes_per_week=200)


def test_very_high_requires_substantial_multiple_signal_evidence() -> None:
    context = TrainingContext(
        OccupationActivity.PHYSICALLY_DEMANDING,
        resistance_days_per_week=5,
        resistance_minutes_per_week=360,
        cardio_days_per_week=5,
        cardio_minutes_per_week=360,
        cardio_intensity=TrainingIntensity.VIGOROUS,
        primary_training_focus=PrimaryTrainingFocus.MIXED,
    )
    result = assess_training_demand(context)
    assert result.overall_demand is TrainingDemandLevel.VERY_HIGH
    assert "very_high_requires_multiple_supporting_signals" in result.reason_codes
