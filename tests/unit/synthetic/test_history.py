"""Unit tests for reproducible synthetic longitudinal histories."""

import math
from dataclasses import FrozenInstanceError, astuple
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from fitadapt.domain.observation import DailyObservation
from fitadapt.synthetic.history import (
    CALORIES_PER_CARDIO_MINUTE,
    CALORIES_PER_STEP,
    CALORIES_PER_STRENGTH_TRAINING_MINUTE,
    WEIGHT_CHANGE_ENERGY_EQUIVALENT_KCAL_PER_KG,
    SyntheticConfigurationError,
    SyntheticHistoryConfig,
    generate_synthetic_history,
)


def make_config(**overrides: object) -> SyntheticHistoryConfig:
    """Create a valid, small configuration and override inputs for a focused test."""
    values: dict[str, object] = {
        "start_date": date(2026, 1, 1),
        "days": 14,
        "seed": 123,
        "initial_true_weight_kg": 80.0,
        "base_daily_expenditure_kcal": 1900.0,
        "average_energy_intake_kcal": 2400.0,
    }
    values.update(overrides)
    return SyntheticHistoryConfig(**values)  # type: ignore[arg-type]


def test_same_configuration_and_seed_produce_identical_history() -> None:
    config = make_config()

    assert generate_synthetic_history(config) == generate_synthetic_history(config)


def test_different_seeds_produce_different_history() -> None:
    first = generate_synthetic_history(make_config(seed=1))
    second = generate_synthetic_history(make_config(seed=2))

    assert first.days != second.days


def test_generation_does_not_modify_legacy_global_numpy_random_state() -> None:
    np.random.seed(2026)
    expected_sequence = np.random.random(3)
    np.random.seed(2026)

    generate_synthetic_history(make_config())

    assert np.random.random(3) == pytest.approx(expected_sequence)


def test_generates_requested_number_of_consecutive_ordered_dates() -> None:
    history = generate_synthetic_history(make_config(days=4))

    assert len(history.days) == 4
    assert [day.truth.observed_on for day in history.days] == [
        date(2026, 1, 1) + timedelta(days=index) for index in range(4)
    ]


def test_history_structures_are_immutable() -> None:
    history = generate_synthetic_history(make_config())

    with pytest.raises(FrozenInstanceError):
        history.simulation_policy_version = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        history.days.append(history.days[0])  # type: ignore[attr-defined]


def test_hidden_truth_exists_when_every_observation_is_missing() -> None:
    history = generate_synthetic_history(
        make_config(
            missing_weight_probability=1.0,
            missing_nutrition_probability=1.0,
            missing_activity_probability=1.0,
        )
    )

    assert all(day.truth.true_energy_intake_kcal >= 0 for day in history.days)
    assert all(day.observation is None for day in history.days)


def test_missing_values_remain_none_instead_of_zero() -> None:
    history = generate_synthetic_history(
        make_config(missing_weight_probability=1.0, missing_nutrition_probability=0.0)
    )

    assert all(day.observation is not None for day in history.days)
    assert all(day.observation.body_weight_kg is None for day in history.days if day.observation)
    assert all(
        day.observation.energy_intake_kcal is not None for day in history.days if day.observation
    )


def test_zero_missingness_produces_present_observation_categories() -> None:
    history = generate_synthetic_history(
        make_config(
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
        )
    )

    assert all(day.observation is not None for day in history.days)
    assert all(
        day.observation.body_weight_kg is not None for day in history.days if day.observation
    )
    assert all(
        day.observation.energy_intake_kcal is not None for day in history.days if day.observation
    )
    assert all(day.observation.steps is not None for day in history.days if day.observation)


def test_all_constructed_observations_are_valid_domain_objects() -> None:
    history = generate_synthetic_history(make_config())

    assert all(
        day.observation is None or isinstance(day.observation, DailyObservation)
        for day in history.days
    )


def test_truth_energy_balance_is_intake_minus_expenditure() -> None:
    history = generate_synthetic_history(make_config())

    for day in history.days:
        assert day.truth.true_energy_balance_kcal == pytest.approx(
            day.truth.true_energy_intake_kcal - day.truth.true_daily_energy_expenditure_kcal
        )


def test_truth_daily_weight_change_uses_energy_equivalent_rule() -> None:
    history = generate_synthetic_history(make_config())

    for day in history.days:
        assert day.truth.true_daily_weight_change_kg == pytest.approx(
            day.truth.true_energy_balance_kcal / 7700.0
        )


def test_true_weight_evolves_from_one_day_to_the_next() -> None:
    history = generate_synthetic_history(make_config())

    for current_day, next_day in zip(history.days[:-1], history.days[1:], strict=True):
        assert next_day.truth.true_body_weight_kg == pytest.approx(
            current_day.truth.true_body_weight_kg + current_day.truth.true_daily_weight_change_kg
        )


def test_nonzero_scale_noise_changes_at_least_one_observed_weight() -> None:
    history = generate_synthetic_history(
        make_config(
            days=30,
            scale_weight_noise_standard_deviation_kg=1.0,
            missing_weight_probability=0.0,
        )
    )

    assert any(
        day.observation.body_weight_kg != day.truth.true_body_weight_kg
        for day in history.days
        if day.observation
    )


def test_zero_noise_matches_observed_and_true_values() -> None:
    history = generate_synthetic_history(
        make_config(
            scale_weight_noise_standard_deviation_kg=0.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            steps_observation_noise_standard_deviation=0.0,
            missing_weight_probability=0.0,
            missing_nutrition_probability=0.0,
            missing_activity_probability=0.0,
        )
    )

    for day in history.days:
        assert day.observation is not None
        assert day.observation.body_weight_kg == day.truth.true_body_weight_kg
        assert day.observation.energy_intake_kcal == day.truth.true_energy_intake_kcal
        assert day.observation.steps == day.truth.true_steps


def test_signed_logging_bias_is_applied_without_random_error() -> None:
    positive = generate_synthetic_history(
        make_config(
            calorie_logging_bias_kcal=150.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            missing_nutrition_probability=0.0,
        )
    )
    negative = generate_synthetic_history(
        make_config(
            calorie_logging_bias_kcal=-150.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            missing_nutrition_probability=0.0,
        )
    )

    assert all(
        day.observation is not None
        and day.observation.energy_intake_kcal
        == pytest.approx(day.truth.true_energy_intake_kcal + 150.0)
        for day in positive.days
    )
    assert all(
        day.observation is not None
        and day.observation.energy_intake_kcal
        == pytest.approx(day.truth.true_energy_intake_kcal - 150.0)
        for day in negative.days
    )


def test_zero_logging_bias_preserves_existing_observed_intake_behavior() -> None:
    default_history = generate_synthetic_history(make_config())
    explicit_zero_history = generate_synthetic_history(make_config(calorie_logging_bias_kcal=0.0))

    assert default_history == explicit_zero_history


def test_negative_logging_bias_is_clamped_to_non_negative_observed_intake() -> None:
    history = generate_synthetic_history(
        make_config(
            calorie_logging_bias_kcal=-10_000.0,
            calorie_logging_error_standard_deviation_kcal=0.0,
            missing_nutrition_probability=0.0,
        )
    )

    assert all(
        day.observation is not None and day.observation.energy_intake_kcal == 0.0
        for day in history.days
    )


def test_logged_intake_never_becomes_negative() -> None:
    history = generate_synthetic_history(
        make_config(calorie_logging_error_standard_deviation_kcal=10000.0)
    )

    assert all(
        day.observation is None
        or day.observation.energy_intake_kcal is None
        or day.observation.energy_intake_kcal >= 0
        for day in history.days
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("days", 0),
        ("days", True),
        ("seed", -1),
        ("initial_true_weight_kg", 29.9),
        ("initial_true_weight_kg", math.nan),
        ("average_energy_intake_kcal", -1.0),
        ("intake_standard_deviation_kcal", -0.1),
        ("missing_weight_probability", -0.1),
        ("missing_nutrition_probability", 1.1),
        ("cardio_minutes", 1440.1),
        ("start_date", datetime(2026, 1, 1)),
    ],
)
def test_rejects_invalid_configuration(field_name: str, value: object) -> None:
    with pytest.raises(SyntheticConfigurationError, match=field_name):
        make_config(**{field_name: value})


@pytest.mark.parametrize("value", [True, "100", math.nan, math.inf, -math.inf])
def test_rejects_invalid_logging_bias(value: object) -> None:
    with pytest.raises(SyntheticConfigurationError, match="calorie_logging_bias_kcal"):
        make_config(calorie_logging_bias_kcal=value)


def test_logging_bias_normalizes_integer_input_and_reproducibility_includes_bias() -> None:
    config = make_config(calorie_logging_bias_kcal=100)

    assert config.calorie_logging_bias_kcal == 100.0
    assert type(config.calorie_logging_bias_kcal) is float
    assert generate_synthetic_history(config) == generate_synthetic_history(config)


def test_logging_bias_is_recorded_under_the_version_2_simulation_policy() -> None:
    history = generate_synthetic_history(make_config(calorie_logging_bias_kcal=25.0))

    assert history.simulation_policy_version == "synthetic_history_v2"
    assert any("systematic bias" in assumption for assumption in history.assumptions)


@pytest.mark.parametrize(
    "field_name",
    [
        "missing_weight_probability",
        "missing_nutrition_probability",
        "missing_activity_probability",
        "strength_training_probability",
        "cardio_probability",
    ],
)
@pytest.mark.parametrize("value", [0.0, 1.0])
def test_probabilities_accept_exact_boundaries(field_name: str, value: float) -> None:
    assert make_config(**{field_name: value})


def test_public_truth_numbers_are_finite() -> None:
    history = generate_synthetic_history(make_config())

    for day in history.days:
        values = (
            day.truth.true_body_weight_kg,
            day.truth.true_energy_intake_kcal,
            day.truth.true_daily_energy_expenditure_kcal,
            day.truth.true_energy_balance_kcal,
            day.truth.true_daily_weight_change_kg,
            day.truth.true_strength_training_minutes,
            day.truth.true_cardio_minutes,
        )
        assert all(math.isfinite(value) for value in values)


def test_generator_does_not_mutate_configuration() -> None:
    config = make_config()
    original_values = astuple(config)

    generate_synthetic_history(config)

    assert astuple(config) == original_values


def test_generated_records_have_no_identifying_information() -> None:
    history = generate_synthetic_history(make_config())

    assert not any(
        "name" in field_name or "email" in field_name or field_name.endswith("id")
        for field_name in history.days[0].truth.__dataclass_fields__
    )


def test_simulation_policy_constants_have_documented_values() -> None:
    assert CALORIES_PER_STEP == 0.04
    assert CALORIES_PER_STRENGTH_TRAINING_MINUTE == 6.0
    assert CALORIES_PER_CARDIO_MINUTE == 8.0
    assert WEIGHT_CHANGE_ENERGY_EQUIVALENT_KCAL_PER_KG == 7700.0
