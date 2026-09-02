"""Validated profile inputs for deterministic FitAdapt calculations."""

import math
from dataclasses import dataclass
from enum import Enum, StrEnum


class ProfileValidationError(ValueError):
    """Raised when a user profile falls outside FitAdapt's supported input contract."""


class SexForMifflinEquation(StrEnum):
    """Values required by the selected Mifflin-St Jeor REE equation."""

    FEMALE = "female"
    MALE = "male"


class ActivityLevel(StrEnum):
    """Rough population-level categories used by the future baseline TDEE calculation."""

    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"
    EXTRA_ACTIVE = "extra_active"


class Goal(StrEnum):
    """The intended direction of body-weight change."""

    CUT = "cut"
    MAINTAIN = "maintain"
    GAIN = "gain"


MINIMUM_AGE_YEARS = 18
MAXIMUM_AGE_YEARS = 80
MINIMUM_HEIGHT_CM = 100.0
MAXIMUM_HEIGHT_CM = 250.0
MINIMUM_WEIGHT_KG = 30.0
MAXIMUM_WEIGHT_KG = 300.0
MAXIMUM_CUT_RATE_FRACTION = 0.0075
MAXIMUM_GAIN_RATE_FRACTION = 0.005


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Profile inputs required by V0.1 baseline calculations.

    ``requested_weekly_change_kg`` is signed: negative for a cut, zero for maintenance,
    and positive for a gain. The field is explicit so the core calculation engine never
    silently chooses a rate on behalf of a caller.
    """

    age_years: int
    height_cm: float
    weight_kg: float
    sex_for_mifflin_equation: SexForMifflinEquation
    activity_level: ActivityLevel
    goal: Goal
    requested_weekly_change_kg: float

    def __post_init__(self) -> None:
        """Validate profile inputs and normalize accepted numeric values to floats."""
        _validate_age(self.age_years)
        height_cm = _validate_finite_measurement(
            self.height_cm,
            field_name="height_cm",
            minimum=MINIMUM_HEIGHT_CM,
            maximum=MAXIMUM_HEIGHT_CM,
            unit="cm",
        )
        weight_kg = _validate_finite_measurement(
            self.weight_kg,
            field_name="weight_kg",
            minimum=MINIMUM_WEIGHT_KG,
            maximum=MAXIMUM_WEIGHT_KG,
            unit="kg",
        )
        _validate_enum(
            self.sex_for_mifflin_equation,
            SexForMifflinEquation,
            "sex_for_mifflin_equation",
        )
        _validate_enum(self.activity_level, ActivityLevel, "activity_level")
        _validate_enum(self.goal, Goal, "goal")
        requested_weekly_change_kg = _validate_finite_number(
            self.requested_weekly_change_kg,
            "requested_weekly_change_kg",
        )
        _validate_goal_change(self.goal, weight_kg, requested_weekly_change_kg)

        object.__setattr__(self, "height_cm", height_cm)
        object.__setattr__(self, "weight_kg", weight_kg)
        object.__setattr__(self, "requested_weekly_change_kg", requested_weekly_change_kg)


def _validate_age(age_years: int) -> None:
    if isinstance(age_years, bool) or not isinstance(age_years, int):
        raise ProfileValidationError("age_years must be an integer number of years, not a boolean.")
    if not MINIMUM_AGE_YEARS <= age_years <= MAXIMUM_AGE_YEARS:
        raise ProfileValidationError(
            f"age_years must be between {MINIMUM_AGE_YEARS} and {MAXIMUM_AGE_YEARS} inclusive."
        )


def _validate_finite_measurement(
    value: float,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
    unit: str,
) -> float:
    value_as_float = _validate_finite_number(value, field_name)
    if not minimum <= value_as_float <= maximum:
        raise ProfileValidationError(
            f"{field_name} must be between {minimum:g} and {maximum:g} {unit} inclusive."
        )
    return value_as_float


def _validate_finite_number(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileValidationError(
            f"{field_name} must be a finite number, not a boolean or text value."
        )

    value_as_float = float(value)
    if not math.isfinite(value_as_float):
        raise ProfileValidationError(f"{field_name} must be finite, not NaN or infinity.")
    return value_as_float


def _validate_enum(value: Enum, expected_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, expected_type):
        allowed_values = ", ".join(member.value for member in expected_type)
        raise ProfileValidationError(
            f"{field_name} must be a {expected_type.__name__} enum value "
            f"({allowed_values}); received {value!r}."
        )


def _validate_goal_change(goal: Goal, weight_kg: float, requested_weekly_change_kg: float) -> None:
    if goal is Goal.MAINTAIN:
        if requested_weekly_change_kg != 0:
            raise ProfileValidationError(
                "goal 'maintain' requires requested_weekly_change_kg to be exactly 0."
            )
        return

    if goal is Goal.CUT:
        maximum_cut_kg = weight_kg * MAXIMUM_CUT_RATE_FRACTION
        if not -maximum_cut_kg <= requested_weekly_change_kg < 0:
            raise ProfileValidationError(
                "goal 'cut' requires requested_weekly_change_kg to be negative and no less than "
                f"{-maximum_cut_kg:g} kg/week (0.75% of body weight)."
            )
        return

    if goal is Goal.GAIN:
        maximum_gain_kg = weight_kg * MAXIMUM_GAIN_RATE_FRACTION
        if not 0 < requested_weekly_change_kg <= maximum_gain_kg:
            raise ProfileValidationError(
                "goal 'gain' requires requested_weekly_change_kg to be positive and no greater "
                f"than {maximum_gain_kg:g} kg/week (0.5% of body weight)."
            )
        return

    raise ProfileValidationError(f"Unsupported goal: {goal!r}.")
