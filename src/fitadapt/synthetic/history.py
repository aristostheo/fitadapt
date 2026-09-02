"""In-memory, reproducible synthetic daily fitness histories."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
from numpy.random import Generator

from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import MAXIMUM_WEIGHT_KG, MINIMUM_WEIGHT_KG

SIMULATION_POLICY_VERSION = "synthetic_history_v1"
CALORIES_PER_STEP = 0.04
CALORIES_PER_STRENGTH_TRAINING_MINUTE = 6.0
CALORIES_PER_CARDIO_MINUTE = 8.0
WEIGHT_CHANGE_ENERGY_EQUIVALENT_KCAL_PER_KG = 7700.0

SIMULATION_ASSUMPTIONS = (
    "True body weight is stored at the start of each simulated day.",
    "Daily weight change is energy balance divided by 7,700 kcal/kg.",
    "Intake and steps use normal noise and are clamped at zero.",
    "Observed scale weight, logged intake, and steps include independent normal noise.",
    "Missingness is applied after hidden truth is generated for each observation category.",
    "Observed scale weight is clamped to the supported DailyObservation weight range.",
)


class SyntheticConfigurationError(ValueError):
    """Raised when synthetic-history configuration violates the simulation contract."""


@dataclass(frozen=True, slots=True)
class SyntheticHistoryConfig:
    """Explicit inputs for a simple, reproducible daily-history simulation."""

    start_date: date
    days: int
    seed: int
    initial_true_weight_kg: float
    base_daily_expenditure_kcal: float
    average_energy_intake_kcal: float
    intake_standard_deviation_kcal: float = 150.0
    average_steps: float = 8000.0
    steps_standard_deviation: float = 1500.0
    strength_training_probability: float = 0.4
    strength_training_minutes: float = 60.0
    cardio_probability: float = 0.25
    cardio_minutes: float = 30.0
    scale_weight_noise_standard_deviation_kg: float = 0.4
    calorie_logging_error_standard_deviation_kcal: float = 100.0
    steps_observation_noise_standard_deviation: float = 500.0
    missing_weight_probability: float = 0.15
    missing_nutrition_probability: float = 0.1
    missing_activity_probability: float = 0.1

    def __post_init__(self) -> None:
        """Validate simulation inputs without introducing clock-dependent behaviour."""
        _validate_date(self.start_date, "start_date")
        _validate_positive_integer(self.days, "days")
        _validate_non_negative_integer(self.seed, "seed")
        initial_true_weight_kg = _validate_number_in_range(
            self.initial_true_weight_kg,
            field_name="initial_true_weight_kg",
            minimum=MINIMUM_WEIGHT_KG,
            maximum=MAXIMUM_WEIGHT_KG,
        )
        base_daily_expenditure_kcal = _validate_number_at_least(
            self.base_daily_expenditure_kcal,
            field_name="base_daily_expenditure_kcal",
            minimum=0.0,
        )
        average_energy_intake_kcal = _validate_number_at_least(
            self.average_energy_intake_kcal,
            field_name="average_energy_intake_kcal",
            minimum=0.0,
        )
        intake_standard_deviation_kcal = _validate_number_at_least(
            self.intake_standard_deviation_kcal,
            field_name="intake_standard_deviation_kcal",
            minimum=0.0,
        )
        average_steps = _validate_number_at_least(
            self.average_steps,
            field_name="average_steps",
            minimum=0.0,
        )
        steps_standard_deviation = _validate_number_at_least(
            self.steps_standard_deviation,
            field_name="steps_standard_deviation",
            minimum=0.0,
        )
        strength_training_probability = _validate_probability(
            self.strength_training_probability,
            "strength_training_probability",
        )
        strength_training_minutes = _validate_number_in_range(
            self.strength_training_minutes,
            field_name="strength_training_minutes",
            minimum=0.0,
            maximum=1440.0,
        )
        cardio_probability = _validate_probability(self.cardio_probability, "cardio_probability")
        cardio_minutes = _validate_number_in_range(
            self.cardio_minutes,
            field_name="cardio_minutes",
            minimum=0.0,
            maximum=1440.0,
        )
        scale_weight_noise_standard_deviation_kg = _validate_number_at_least(
            self.scale_weight_noise_standard_deviation_kg,
            field_name="scale_weight_noise_standard_deviation_kg",
            minimum=0.0,
        )
        calorie_logging_error_standard_deviation_kcal = _validate_number_at_least(
            self.calorie_logging_error_standard_deviation_kcal,
            field_name="calorie_logging_error_standard_deviation_kcal",
            minimum=0.0,
        )
        steps_observation_noise_standard_deviation = _validate_number_at_least(
            self.steps_observation_noise_standard_deviation,
            field_name="steps_observation_noise_standard_deviation",
            minimum=0.0,
        )
        missing_weight_probability = _validate_probability(
            self.missing_weight_probability,
            "missing_weight_probability",
        )
        missing_nutrition_probability = _validate_probability(
            self.missing_nutrition_probability,
            "missing_nutrition_probability",
        )
        missing_activity_probability = _validate_probability(
            self.missing_activity_probability,
            "missing_activity_probability",
        )

        for field_name, value in (
            ("initial_true_weight_kg", initial_true_weight_kg),
            ("base_daily_expenditure_kcal", base_daily_expenditure_kcal),
            ("average_energy_intake_kcal", average_energy_intake_kcal),
            ("intake_standard_deviation_kcal", intake_standard_deviation_kcal),
            ("average_steps", average_steps),
            ("steps_standard_deviation", steps_standard_deviation),
            ("strength_training_probability", strength_training_probability),
            ("strength_training_minutes", strength_training_minutes),
            ("cardio_probability", cardio_probability),
            ("cardio_minutes", cardio_minutes),
            ("scale_weight_noise_standard_deviation_kg", scale_weight_noise_standard_deviation_kg),
            (
                "calorie_logging_error_standard_deviation_kcal",
                calorie_logging_error_standard_deviation_kcal,
            ),
            (
                "steps_observation_noise_standard_deviation",
                steps_observation_noise_standard_deviation,
            ),
            ("missing_weight_probability", missing_weight_probability),
            ("missing_nutrition_probability", missing_nutrition_probability),
            ("missing_activity_probability", missing_activity_probability),
        ):
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class SyntheticDayTruth:
    """Hidden start-of-day values used to simulate one daily observation."""

    observed_on: date
    true_body_weight_kg: float
    true_energy_intake_kcal: float
    true_daily_energy_expenditure_kcal: float
    true_energy_balance_kcal: float
    true_daily_weight_change_kg: float
    true_steps: int
    true_strength_training_minutes: float
    true_cardio_minutes: float


@dataclass(frozen=True, slots=True)
class SyntheticDay:
    """One hidden-truth day paired with an optional noisy, partial observation."""

    truth: SyntheticDayTruth
    observation: DailyObservation | None


@dataclass(frozen=True, slots=True)
class SyntheticHistory:
    """Immutable in-memory output of one simulation configuration and seed."""

    config: SyntheticHistoryConfig
    simulation_policy_version: str
    days: tuple[SyntheticDay, ...]
    assumptions: tuple[str, ...]


def generate_synthetic_history(config: SyntheticHistoryConfig) -> SyntheticHistory:
    """Generate a deterministic hidden-truth history and independent noisy observations."""
    rng = np.random.default_rng(config.seed)
    current_true_weight_kg = config.initial_true_weight_kg
    simulated_days: list[SyntheticDay] = []

    for day_index in range(config.days):
        observed_on = config.start_date + timedelta(days=day_index)
        truth = _generate_truth(observed_on, current_true_weight_kg, config, rng)
        observation = _generate_observation(truth, config, rng)
        simulated_days.append(SyntheticDay(truth=truth, observation=observation))
        current_true_weight_kg += truth.true_daily_weight_change_kg

    return SyntheticHistory(
        config=config,
        simulation_policy_version=SIMULATION_POLICY_VERSION,
        days=tuple(simulated_days),
        assumptions=SIMULATION_ASSUMPTIONS,
    )


def _generate_truth(
    observed_on: date,
    current_true_weight_kg: float,
    config: SyntheticHistoryConfig,
    rng: Generator,
) -> SyntheticDayTruth:
    true_energy_intake_kcal = max(
        0.0,
        float(rng.normal(config.average_energy_intake_kcal, config.intake_standard_deviation_kcal)),
    )
    true_steps = max(
        0, int(round(rng.normal(config.average_steps, config.steps_standard_deviation)))
    )
    true_strength_training_minutes = (
        config.strength_training_minutes
        if rng.random() < config.strength_training_probability
        else 0.0
    )
    true_cardio_minutes = config.cardio_minutes if rng.random() < config.cardio_probability else 0.0
    true_daily_energy_expenditure_kcal = (
        config.base_daily_expenditure_kcal
        + true_steps * CALORIES_PER_STEP
        + true_strength_training_minutes * CALORIES_PER_STRENGTH_TRAINING_MINUTE
        + true_cardio_minutes * CALORIES_PER_CARDIO_MINUTE
    )
    true_energy_balance_kcal = true_energy_intake_kcal - true_daily_energy_expenditure_kcal
    true_daily_weight_change_kg = (
        true_energy_balance_kcal / WEIGHT_CHANGE_ENERGY_EQUIVALENT_KCAL_PER_KG
    )
    return SyntheticDayTruth(
        observed_on=observed_on,
        true_body_weight_kg=current_true_weight_kg,
        true_energy_intake_kcal=true_energy_intake_kcal,
        true_daily_energy_expenditure_kcal=true_daily_energy_expenditure_kcal,
        true_energy_balance_kcal=true_energy_balance_kcal,
        true_daily_weight_change_kg=true_daily_weight_change_kg,
        true_steps=true_steps,
        true_strength_training_minutes=true_strength_training_minutes,
        true_cardio_minutes=true_cardio_minutes,
    )


def _generate_observation(
    truth: SyntheticDayTruth,
    config: SyntheticHistoryConfig,
    rng: Generator,
) -> DailyObservation | None:
    body_weight_kg = None
    if rng.random() >= config.missing_weight_probability:
        body_weight_kg = _clamp(
            truth.true_body_weight_kg
            + float(rng.normal(0.0, config.scale_weight_noise_standard_deviation_kg)),
            MINIMUM_WEIGHT_KG,
            MAXIMUM_WEIGHT_KG,
        )

    energy_intake_kcal = None
    if rng.random() >= config.missing_nutrition_probability:
        energy_intake_kcal = max(
            0.0,
            truth.true_energy_intake_kcal
            + float(rng.normal(0.0, config.calorie_logging_error_standard_deviation_kcal)),
        )

    steps: int | None = None
    strength_training_minutes: float | None = None
    cardio_minutes: float | None = None
    if rng.random() >= config.missing_activity_probability:
        steps = max(
            0,
            int(
                round(
                    truth.true_steps
                    + rng.normal(0.0, config.steps_observation_noise_standard_deviation)
                )
            ),
        )
        strength_training_minutes = truth.true_strength_training_minutes
        cardio_minutes = truth.true_cardio_minutes

    if all(value is None for value in (body_weight_kg, energy_intake_kcal, steps)):
        return None
    return DailyObservation(
        observed_on=truth.observed_on,
        body_weight_kg=body_weight_kg,
        energy_intake_kcal=energy_intake_kcal,
        steps=steps,
        strength_training_minutes=strength_training_minutes,
        cardio_minutes=cardio_minutes,
    )


def _validate_date(value: date, field_name: str) -> None:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise SyntheticConfigurationError(
            f"{field_name} must be a datetime.date, not a datetime or text."
        )


def _validate_positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SyntheticConfigurationError(f"{field_name} must be a positive integer.")


def _validate_non_negative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SyntheticConfigurationError(f"{field_name} must be a non-negative integer.")


def _validate_number_at_least(value: float, *, field_name: str, minimum: float) -> float:
    value_as_float = validate_finite_number(
        value,
        field_name=field_name,
        error_type=SyntheticConfigurationError,
    )
    if value_as_float < minimum:
        raise SyntheticConfigurationError(f"{field_name} must be at least {minimum:g}.")
    return value_as_float


def _validate_number_in_range(
    value: float,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float:
    value_as_float = _validate_number_at_least(value, field_name=field_name, minimum=minimum)
    if value_as_float > maximum:
        raise SyntheticConfigurationError(
            f"{field_name} must be between {minimum:g} and {maximum:g} inclusive."
        )
    return value_as_float


def _validate_probability(value: float, field_name: str) -> float:
    return _validate_number_in_range(value, field_name=field_name, minimum=0.0, maximum=1.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
