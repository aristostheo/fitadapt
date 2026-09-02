"""Validated, partial daily fitness observations for later longitudinal analysis."""

from dataclasses import dataclass
from datetime import date, datetime

from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.profile import (
    MAXIMUM_WEIGHT_KG,
    MINIMUM_WEIGHT_KG,
)

MAXIMUM_MINUTES_PER_DAY = 1440.0
MAXIMUM_SLEEP_HOURS = 24.0
MINIMUM_RATING = 1
MAXIMUM_RATING = 5


class ObservationValidationError(ValueError):
    """Raised when a daily observation falls outside FitAdapt's input contract."""


@dataclass(frozen=True, slots=True)
class DailyObservation:
    """Partial measurements observed for one calendar day.

    ``None`` represents missing or unknown data. A numeric zero represents an observed zero.
    The model intentionally stores raw observations without deriving trends or quality scores.
    """

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

    def __post_init__(self) -> None:
        """Validate fields and normalize accepted float-valued measurements."""
        _validate_observed_on(self.observed_on)
        body_weight_kg = _validate_optional_float(
            self.body_weight_kg,
            field_name="body_weight_kg",
            minimum=MINIMUM_WEIGHT_KG,
            maximum=MAXIMUM_WEIGHT_KG,
            unit="kg",
        )
        energy_intake_kcal = _validate_optional_float(
            self.energy_intake_kcal,
            field_name="energy_intake_kcal",
            minimum=0.0,
            maximum=None,
            unit="kcal",
        )
        protein_g = _validate_optional_float(
            self.protein_g,
            field_name="protein_g",
            minimum=0.0,
            maximum=None,
            unit="g",
        )
        carbohydrate_g = _validate_optional_float(
            self.carbohydrate_g,
            field_name="carbohydrate_g",
            minimum=0.0,
            maximum=None,
            unit="g",
        )
        fat_g = _validate_optional_float(
            self.fat_g,
            field_name="fat_g",
            minimum=0.0,
            maximum=None,
            unit="g",
        )
        strength_training_minutes = _validate_optional_float(
            self.strength_training_minutes,
            field_name="strength_training_minutes",
            minimum=0.0,
            maximum=MAXIMUM_MINUTES_PER_DAY,
            unit="minutes",
        )
        cardio_minutes = _validate_optional_float(
            self.cardio_minutes,
            field_name="cardio_minutes",
            minimum=0.0,
            maximum=MAXIMUM_MINUTES_PER_DAY,
            unit="minutes",
        )
        sleep_hours = _validate_optional_float(
            self.sleep_hours,
            field_name="sleep_hours",
            minimum=0.0,
            maximum=MAXIMUM_SLEEP_HOURS,
            unit="hours",
        )
        steps = _validate_optional_integer(self.steps, field_name="steps", minimum=0, maximum=None)
        hunger_rating = _validate_optional_integer(
            self.hunger_rating,
            field_name="hunger_rating",
            minimum=MINIMUM_RATING,
            maximum=MAXIMUM_RATING,
        )
        energy_rating = _validate_optional_integer(
            self.energy_rating,
            field_name="energy_rating",
            minimum=MINIMUM_RATING,
            maximum=MAXIMUM_RATING,
        )

        _validate_has_measurement(
            body_weight_kg,
            energy_intake_kcal,
            protein_g,
            carbohydrate_g,
            fat_g,
            steps,
            strength_training_minutes,
            cardio_minutes,
            sleep_hours,
            hunger_rating,
            energy_rating,
        )

        object.__setattr__(self, "body_weight_kg", body_weight_kg)
        object.__setattr__(self, "energy_intake_kcal", energy_intake_kcal)
        object.__setattr__(self, "protein_g", protein_g)
        object.__setattr__(self, "carbohydrate_g", carbohydrate_g)
        object.__setattr__(self, "fat_g", fat_g)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "strength_training_minutes", strength_training_minutes)
        object.__setattr__(self, "cardio_minutes", cardio_minutes)
        object.__setattr__(self, "sleep_hours", sleep_hours)
        object.__setattr__(self, "hunger_rating", hunger_rating)
        object.__setattr__(self, "energy_rating", energy_rating)


def _validate_observed_on(observed_on: date) -> None:
    if isinstance(observed_on, datetime) or not isinstance(observed_on, date):
        raise ObservationValidationError(
            "observed_on must be a datetime.date, not a datetime, string, or other date-like value."
        )


def _validate_optional_float(
    value: float | None,
    *,
    field_name: str,
    minimum: float,
    maximum: float | None,
    unit: str,
) -> float | None:
    if value is None:
        return None

    value_as_float = validate_finite_number(
        value,
        field_name=field_name,
        error_type=ObservationValidationError,
    )
    if value_as_float < minimum or (maximum is not None and value_as_float > maximum):
        _raise_range_error(field_name, minimum, maximum, unit)
    return value_as_float


def _validate_optional_integer(
    value: int | None,
    *,
    field_name: str,
    minimum: int,
    maximum: int | None,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ObservationValidationError(
            f"{field_name} must be an integer, not a boolean or float."
        )
    if value < minimum or (maximum is not None and value > maximum):
        _raise_range_error(field_name, minimum, maximum, "")
    return value


def _raise_range_error(
    field_name: str,
    minimum: float | int,
    maximum: float | int | None,
    unit: str,
) -> None:
    unit_suffix = f" {unit}" if unit else ""
    if maximum is None:
        raise ObservationValidationError(f"{field_name} must be at least {minimum:g}{unit_suffix}.")
    raise ObservationValidationError(
        f"{field_name} must be between {minimum:g} and {maximum:g}{unit_suffix} inclusive."
    )


def _validate_has_measurement(*values: object | None) -> None:
    if all(value is None for value in values):
        raise ObservationValidationError(
            "At least one observation field besides observed_on is required."
        )
