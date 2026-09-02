"""Unit tests for partial, validated daily fitness observations."""

import math
from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from fitadapt.domain.observation import DailyObservation, ObservationValidationError

OBSERVED_ON = date(2026, 9, 2)


def make_observation(**overrides: object) -> DailyObservation:
    """Create a minimal valid observation and override inputs for a focused test."""
    values: dict[str, object] = {
        "observed_on": OBSERVED_ON,
        "steps": 5000,
    }
    values.update(overrides)
    return DailyObservation(**values)  # type: ignore[arg-type]


def test_accepts_complete_valid_observation() -> None:
    observation = DailyObservation(
        observed_on=OBSERVED_ON,
        body_weight_kg=80,
        energy_intake_kcal=2500,
        protein_g=150,
        carbohydrate_g=275,
        fat_g=75,
        steps=10000,
        strength_training_minutes=60,
        cardio_minutes=30,
        sleep_hours=8,
        hunger_rating=3,
        energy_rating=4,
    )

    assert observation.observed_on == OBSERVED_ON
    assert observation.steps == 10000
    assert observation.hunger_rating == 3
    assert observation.energy_rating == 4
    assert all(
        isinstance(value, float)
        for value in (
            observation.body_weight_kg,
            observation.energy_intake_kcal,
            observation.protein_g,
            observation.carbohydrate_g,
            observation.fat_g,
            observation.strength_training_minutes,
            observation.cardio_minutes,
            observation.sleep_hours,
        )
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("body_weight_kg", 80.0),
        ("energy_intake_kcal", 0.0),
        ("protein_g", 0.0),
        ("carbohydrate_g", 0.0),
        ("fat_g", 0.0),
        ("steps", 0),
        ("strength_training_minutes", 0.0),
        ("cardio_minutes", 0.0),
        ("sleep_hours", 0.0),
        ("hunger_rating", 1),
        ("energy_rating", 1),
    ],
)
def test_accepts_one_observation_field_besides_date(field_name: str, value: object) -> None:
    observation = DailyObservation(observed_on=OBSERVED_ON, **{field_name: value})

    assert getattr(observation, field_name) == value


def test_accepts_partial_nutrition_without_forcing_reconciliation() -> None:
    observation = DailyObservation(
        observed_on=OBSERVED_ON,
        energy_intake_kcal=2000.0,
        protein_g=100.0,
    )

    assert observation.energy_intake_kcal == 2000.0
    assert observation.protein_g == 100.0
    assert observation.carbohydrate_g is None
    assert observation.fat_g is None


def test_preserves_difference_between_missing_and_observed_zero() -> None:
    missing = DailyObservation(observed_on=OBSERVED_ON, steps=1)
    observed_zero = DailyObservation(
        observed_on=OBSERVED_ON,
        energy_intake_kcal=0,
        steps=0,
        cardio_minutes=0,
    )

    assert missing.energy_intake_kcal is None
    assert missing.cardio_minutes is None
    assert observed_zero.energy_intake_kcal == 0.0
    assert observed_zero.steps == 0
    assert observed_zero.cardio_minutes == 0.0


def test_rejects_date_only_observation() -> None:
    with pytest.raises(ObservationValidationError, match="At least one observation field"):
        DailyObservation(observed_on=OBSERVED_ON)


def test_accepts_date_without_current_clock_validation() -> None:
    observation = DailyObservation(observed_on=date(3000, 1, 1), steps=1)

    assert observation.observed_on == date(3000, 1, 1)


@pytest.mark.parametrize("observed_on", [datetime(2026, 9, 2), "2026-09-02", 20260902])
def test_rejects_datetime_strings_and_other_invalid_date_types(observed_on: object) -> None:
    with pytest.raises(ObservationValidationError, match="observed_on"):
        make_observation(observed_on=observed_on)


@pytest.mark.parametrize("body_weight_kg", [30.0, 300.0])
def test_accepts_weight_boundaries(body_weight_kg: float) -> None:
    assert make_observation(body_weight_kg=body_weight_kg).body_weight_kg == body_weight_kg


@pytest.mark.parametrize("body_weight_kg", [29.9, 300.1, math.nan, math.inf, -math.inf])
def test_rejects_invalid_body_weight(body_weight_kg: float) -> None:
    with pytest.raises(ObservationValidationError, match="body_weight_kg"):
        make_observation(body_weight_kg=body_weight_kg)


@pytest.mark.parametrize(
    "field_name", ["energy_intake_kcal", "protein_g", "carbohydrate_g", "fat_g"]
)
def test_accepts_zero_energy_and_macro_values(field_name: str) -> None:
    observation = DailyObservation(observed_on=OBSERVED_ON, **{field_name: 0})

    assert getattr(observation, field_name) == 0.0


@pytest.mark.parametrize(
    "field_name", ["energy_intake_kcal", "protein_g", "carbohydrate_g", "fat_g"]
)
def test_rejects_negative_energy_and_macro_values(field_name: str) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        DailyObservation(observed_on=OBSERVED_ON, **{field_name: -0.1})


@pytest.mark.parametrize(
    "field_name",
    [
        "body_weight_kg",
        "energy_intake_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "strength_training_minutes",
        "cardio_minutes",
        "sleep_hours",
    ],
)
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_optional_float_measurements(field_name: str, value: float) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        make_observation(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
        "body_weight_kg",
        "energy_intake_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "strength_training_minutes",
        "cardio_minutes",
        "sleep_hours",
    ],
)
def test_rejects_strings_for_optional_float_measurements(field_name: str) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        make_observation(**{field_name: "1"})


def test_accepts_zero_steps() -> None:
    assert DailyObservation(observed_on=OBSERVED_ON, steps=0).steps == 0


@pytest.mark.parametrize("steps", [-1, 1.0, True, "1000"])
def test_rejects_invalid_step_counts(steps: object) -> None:
    with pytest.raises(ObservationValidationError, match="steps"):
        make_observation(steps=steps)


@pytest.mark.parametrize("field_name", ["strength_training_minutes", "cardio_minutes"])
@pytest.mark.parametrize("value", [0.0, 1440.0])
def test_accepts_training_and_cardio_minute_boundaries(field_name: str, value: float) -> None:
    assert DailyObservation(observed_on=OBSERVED_ON, **{field_name: value})


@pytest.mark.parametrize("field_name", ["strength_training_minutes", "cardio_minutes"])
@pytest.mark.parametrize("value", [-0.1, 1440.1])
def test_rejects_invalid_training_and_cardio_minutes(field_name: str, value: float) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        make_observation(**{field_name: value})


@pytest.mark.parametrize("sleep_hours", [0.0, 24.0])
def test_accepts_sleep_boundaries(sleep_hours: float) -> None:
    assert DailyObservation(observed_on=OBSERVED_ON, sleep_hours=sleep_hours)


@pytest.mark.parametrize("sleep_hours", [-0.1, 24.1])
def test_rejects_invalid_sleep_hours(sleep_hours: float) -> None:
    with pytest.raises(ObservationValidationError, match="sleep_hours"):
        make_observation(sleep_hours=sleep_hours)


@pytest.mark.parametrize("field_name", ["hunger_rating", "energy_rating"])
@pytest.mark.parametrize("value", [1, 5])
def test_accepts_rating_boundaries(field_name: str, value: int) -> None:
    assert DailyObservation(observed_on=OBSERVED_ON, **{field_name: value})


@pytest.mark.parametrize("field_name", ["hunger_rating", "energy_rating"])
@pytest.mark.parametrize("value", [0, 6, 3.0, True, "3"])
def test_rejects_invalid_rating_values_and_types(field_name: str, value: object) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        make_observation(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
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
    ],
)
def test_rejects_booleans_for_every_numeric_field(field_name: str) -> None:
    with pytest.raises(ObservationValidationError, match=field_name):
        make_observation(**{field_name: True})


def test_normalizes_accepted_integer_float_measurements() -> None:
    observation = DailyObservation(
        observed_on=OBSERVED_ON,
        body_weight_kg=80,
        energy_intake_kcal=2500,
        protein_g=150,
        carbohydrate_g=275,
        fat_g=75,
        strength_training_minutes=60,
        cardio_minutes=30,
        sleep_hours=8,
    )

    normalized_values = (
        observation.body_weight_kg,
        observation.energy_intake_kcal,
        observation.protein_g,
        observation.carbohydrate_g,
        observation.fat_g,
        observation.strength_training_minutes,
        observation.cardio_minutes,
        observation.sleep_hours,
    )
    assert all(isinstance(value, float) for value in normalized_values)


def test_observation_is_immutable() -> None:
    observation = make_observation()

    with pytest.raises(FrozenInstanceError):
        observation.steps = 1  # type: ignore[misc]


def test_construction_is_deterministic() -> None:
    assert make_observation() == make_observation()
