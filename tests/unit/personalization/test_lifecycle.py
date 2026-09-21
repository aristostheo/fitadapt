"""Focused contracts for the evidence-based personalization lifecycle."""

from dataclasses import FrozenInstanceError, astuple
from datetime import date, timedelta
from math import inf, nan

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, estimate_adaptive_tdee
from fitadapt.analysis.trends import (
    TrendAnalysisConfig,
    TrendAnalysisError,
    analyze_observation_trends,
)
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.lifecycle import (
    PERSONALIZATION_LIFECYCLE_POLICY_VERSION,
    PersonalizationLifecycleConfig,
    PersonalizationLifecycleError,
    PersonalizationRequirement,
    PersonalizationStage,
    assess_personalization_lifecycle,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.recommendation.calories import recommend_calorie_adjustment


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
    days: int,
    *,
    start: date = date(2026, 1, 1),
    include_weight: bool = True,
    include_intake: bool = True,
    intake: float = 2400.0,
) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=start + timedelta(days=index),
            body_weight_kg=80.0 - 0.03 * index if include_weight else None,
            energy_intake_kcal=intake if include_intake else None,
            steps=5000,
        )
        for index in range(days)
    )


def test_empty_and_non_relevant_history_remain_baseline(profile: UserProfile) -> None:
    empty = assess_personalization_lifecycle(profile, ())
    sleep_only = assess_personalization_lifecycle(
        profile,
        (DailyObservation(observed_on=date(2026, 1, 1), sleep_hours=8),),
    )

    assert empty.stage is PersonalizationStage.BASELINE
    assert empty.requirements == (
        PersonalizationRequirement.ADD_HISTORY,
        PersonalizationRequirement.LOG_BODY_WEIGHT,
        PersonalizationRequirement.LOG_ENERGY_INTAKE,
    )
    assert sleep_only.stage is PersonalizationStage.BASELINE
    assert sleep_only.weight_observation_count == sleep_only.intake_observation_count == 0


def test_steps_only_history_remains_baseline(profile: UserProfile) -> None:
    result = assess_personalization_lifecycle(
        profile,
        (DailyObservation(observed_on=date(2026, 1, 1), steps=5000),),
    )

    assert result.stage is PersonalizationStage.BASELINE
    assert result.requirements == (
        PersonalizationRequirement.ADD_HISTORY,
        PersonalizationRequirement.LOG_BODY_WEIGHT,
        PersonalizationRequirement.LOG_ENERGY_INTAKE,
    )


def test_first_relevant_entry_and_insufficient_history_are_calibrating(
    profile: UserProfile,
) -> None:
    result = assess_personalization_lifecycle(profile, _history(1))

    assert result.stage is PersonalizationStage.CALIBRATING
    assert result.requirements == (
        PersonalizationRequirement.ADD_HISTORY,
        PersonalizationRequirement.BUILD_WEIGHT_TREND,
        PersonalizationRequirement.BUILD_INTAKE_TREND,
    )
    assert result.adaptive_tdee_kcal_per_day is None


@pytest.mark.parametrize(
    ("observations", "requirements"),
    [
        (
            _history(1, include_intake=False),
            (
                PersonalizationRequirement.ADD_HISTORY,
                PersonalizationRequirement.LOG_ENERGY_INTAKE,
                PersonalizationRequirement.BUILD_WEIGHT_TREND,
            ),
        ),
        (
            _history(1, include_weight=False),
            (
                PersonalizationRequirement.ADD_HISTORY,
                PersonalizationRequirement.LOG_BODY_WEIGHT,
                PersonalizationRequirement.BUILD_INTAKE_TREND,
            ),
        ),
    ],
)
def test_one_sided_evidence_calibrates_with_only_supported_requirements(
    profile: UserProfile,
    observations: tuple[DailyObservation, ...],
    requirements: tuple[PersonalizationRequirement, ...],
) -> None:
    result = assess_personalization_lifecycle(profile, observations)

    assert result.stage is PersonalizationStage.CALIBRATING
    assert result.requirements == requirements


def test_early_and_personalized_stages_follow_existing_adaptive_aggregation(
    profile: UserProfile,
) -> None:
    early = assess_personalization_lifecycle(profile, _history(11))
    personalized = assess_personalization_lifecycle(profile, _history(14))
    expected = estimate_adaptive_tdee(analyze_observation_trends(_history(14)))

    assert early.stage is PersonalizationStage.EARLY_PERSONALIZED
    assert early.eligible_adaptive_estimate_count == 1
    assert early.requirements == (PersonalizationRequirement.COLLECT_MORE_ELIGIBLE_ESTIMATES,)
    assert early.adaptive_tdee_kcal_per_day is None
    assert early.median_absolute_deviation_kcal_per_day is None
    assert personalized.stage is PersonalizationStage.PERSONALIZED
    assert personalized.requirements == ()
    assert personalized.adaptive_tdee_kcal_per_day == expected.adaptive_tdee_kcal_per_day
    assert (
        personalized.median_absolute_deviation_kcal_per_day
        == expected.median_absolute_deviation_kcal_per_day
    )


def test_append_only_complete_history_progresses_and_updates_evidence(profile: UserProfile) -> None:
    stages = [
        assess_personalization_lifecycle(profile, _history(days)).stage for days in (0, 1, 11, 14)
    ]
    before, after = (assess_personalization_lifecycle(profile, _history(days)) for days in (11, 12))

    assert stages == [
        PersonalizationStage.BASELINE,
        PersonalizationStage.CALIBRATING,
        PersonalizationStage.EARLY_PERSONALIZED,
        PersonalizationStage.PERSONALIZED,
    ]
    assert before.stage is after.stage is PersonalizationStage.EARLY_PERSONALIZED
    assert after.calendar_history_days == before.calendar_history_days + 1
    assert after.eligible_adaptive_estimate_count == before.eligible_adaptive_estimate_count + 1


def test_missing_zero_and_sparse_measurements_keep_evidence_distinct(profile: UserProfile) -> None:
    zero = assess_personalization_lifecycle(profile, _history(1, intake=0.0))
    sparse = assess_personalization_lifecycle(
        profile,
        tuple(
            DailyObservation(
                observed_on=date(2026, 1, 1) + timedelta(days=index),
                body_weight_kg=80.0 if index in (0, 6) else None,
                energy_intake_kcal=2400.0 if index in (0, 6) else None,
                steps=0,
            )
            for index in range(7)
        ),
    )

    assert zero.intake_observation_count == 1
    assert zero.intake_completeness == 1.0
    assert sparse.calendar_history_days == 7
    assert sparse.weight_observation_count == sparse.intake_observation_count == 2
    assert sparse.weight_completeness == sparse.intake_completeness == 2 / 7
    assert PersonalizationRequirement.LOG_BODY_WEIGHT in sparse.requirements
    assert PersonalizationRequirement.LOG_ENERGY_INTAKE in sparse.requirements


def test_calibrating_requirement_order_is_deterministic_and_deduplicated(
    profile: UserProfile,
) -> None:
    observations = tuple(
        DailyObservation(
            observed_on=date(2026, 1, 1) + timedelta(days=index),
            body_weight_kg=80.0 if index in (0, 6) else None,
            energy_intake_kcal=2400.0 if index in (0, 6) else None,
            steps=0,
        )
        for index in range(7)
    )
    result = assess_personalization_lifecycle(profile, observations)

    assert result.requirements == (
        PersonalizationRequirement.ADD_HISTORY,
        PersonalizationRequirement.LOG_BODY_WEIGHT,
        PersonalizationRequirement.LOG_ENERGY_INTAKE,
        PersonalizationRequirement.BUILD_WEIGHT_TREND,
        PersonalizationRequirement.BUILD_INTAKE_TREND,
    )
    assert len(result.requirements) == len(set(result.requirements))


def test_unsorted_history_is_equivalent_and_duplicate_dates_propagate(profile: UserProfile) -> None:
    sorted_history = _history(14)
    assert assess_personalization_lifecycle(
        profile, sorted_history
    ) == assess_personalization_lifecycle(profile, tuple(reversed(sorted_history)))
    duplicate = (sorted_history[0], sorted_history[0])
    with pytest.raises(TrendAnalysisError, match="Duplicate observed_on dates"):
        assess_personalization_lifecycle(profile, duplicate)


def test_custom_existing_configs_are_composed(profile: UserProfile) -> None:
    trend_config = TrendAnalysisConfig(window_size_days=3, minimum_observations=2)
    adaptive_config = AdaptiveTdeeConfig(aggregation_window_days=4, minimum_estimate_points=2)
    result = assess_personalization_lifecycle(
        profile, _history(6), trend_config=trend_config, adaptive_config=adaptive_config
    )

    assert result.stage is PersonalizationStage.PERSONALIZED
    assert result.required_eligible_estimate_count == adaptive_config.minimum_estimate_points
    assert result.trend_policy_version == "calendar_trends_v1"
    assert result.adaptive_policy_version == "adaptive_tdee_v1"


@pytest.mark.parametrize(
    "kwargs",
    [{"minimum_calendar_history_days": value} for value in (True, 0, -1, 1.5, "1", None)]
    + [
        {field: value}
        for field in ("minimum_weight_completeness", "minimum_intake_completeness")
        for value in (True, "0.7", None, nan, inf, -inf, -0.1, 1.1)
    ],
)
def test_config_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(PersonalizationLifecycleError):
        PersonalizationLifecycleConfig(**kwargs)  # type: ignore[arg-type]


def test_config_normalizes_integer_completeness_and_models_are_immutable(
    profile: UserProfile,
) -> None:
    config = PersonalizationLifecycleConfig(
        minimum_calendar_history_days=1,
        minimum_weight_completeness=1,
        minimum_intake_completeness=0,
    )
    result = assess_personalization_lifecycle(profile, _history(14), config)

    assert config.minimum_weight_completeness == 1.0
    assert isinstance(config.minimum_weight_completeness, float)
    assert not hasattr(config, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        config.minimum_calendar_history_days = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.stage = PersonalizationStage.BASELINE  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.requirements.append(PersonalizationRequirement.ADD_HISTORY)  # type: ignore[attr-defined]


def test_result_uses_plain_python_types_and_does_not_mutate_inputs(profile: UserProfile) -> None:
    observations = list(_history(14))
    profile_snapshot = astuple(profile)
    observation_snapshot = tuple(astuple(item) for item in observations)
    first = assess_personalization_lifecycle(profile, observations)
    second = assess_personalization_lifecycle(profile, observations)

    assert first == second
    assert astuple(profile) == profile_snapshot
    assert tuple(astuple(item) for item in observations) == observation_snapshot
    assert first.lifecycle_policy_version == PERSONALIZATION_LIFECYCLE_POLICY_VERSION
    assert isinstance(first.calendar_history_days, int)
    assert isinstance(first.weight_completeness, float)
    assert isinstance(first.eligible_adaptive_estimate_count, int)
    assert isinstance(first.assumptions, tuple)
    with pytest.raises(AttributeError):
        first.assumptions.append("not mutable")  # type: ignore[attr-defined]
    assert all(isinstance(item, PersonalizationRequirement) for item in first.requirements)
    assert isinstance(first.stage, PersonalizationStage)
    assert type(first.calendar_history_days) is int
    assert type(first.weight_observation_count) is int
    assert type(first.intake_observation_count) is int
    assert type(first.weight_completeness) is float
    assert type(first.intake_completeness) is float
    assert type(first.eligible_adaptive_estimate_count) is int
    assert type(first.required_eligible_estimate_count) is int
    assert type(first.adaptive_tdee_kcal_per_day) is float
    assert type(first.median_absolute_deviation_kcal_per_day) is float


def test_lifecycle_does_not_change_existing_calculation_outputs(profile: UserProfile) -> None:
    observations = _history(14)
    baseline_before = calculate_calorie_target(profile)
    trend_before = analyze_observation_trends(observations)
    adaptive_before = estimate_adaptive_tdee(trend_before)
    recommendation_before = recommend_calorie_adjustment(profile, observations)
    macro_before = calculate_personalized_macro_plan(
        profile,
        baseline_before.target_calories_kcal_per_day,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
    )

    assess_personalization_lifecycle(profile, observations)

    assert calculate_calorie_target(profile) == baseline_before
    assert analyze_observation_trends(observations) == trend_before
    assert estimate_adaptive_tdee(trend_before) == adaptive_before
    assert recommend_calorie_adjustment(profile, observations) == recommendation_before
    assert (
        calculate_personalized_macro_plan(
            profile,
            baseline_before.target_calories_kcal_per_day,
            MacroCalorieSource.BASELINE,
            NutritionPreferences(MacroStrategy.BALANCED),
        )
        == macro_before
    )
