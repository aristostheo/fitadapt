"""Unit tests for the V0.1 user-profile input contract."""

import math
from dataclasses import FrozenInstanceError

import pytest

from fitadapt.domain.profile import (
    ActivityLevel,
    Goal,
    ProfileValidationError,
    SexForBmr,
    UserProfile,
)


def make_profile(**overrides: object) -> UserProfile:
    """Create a valid profile and override one or more inputs for a focused test."""
    values: dict[str, object] = {
        "age_years": 30,
        "height_cm": 180.0,
        "weight_kg": 100.0,
        "sex_for_bmr": SexForBmr.MALE,
        "activity_level": ActivityLevel.MODERATELY_ACTIVE,
        "goal": Goal.MAINTAIN,
        "requested_weekly_change_kg": 0.0,
    }
    values.update(overrides)
    return UserProfile(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg"),
    [
        (Goal.CUT, -0.5),
        (Goal.MAINTAIN, 0.0),
        (Goal.GAIN, 0.25),
    ],
)
def test_accepts_valid_profiles(goal: Goal, requested_weekly_change_kg: float) -> None:
    profile = make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)

    assert profile.goal is goal
    assert profile.requested_weekly_change_kg == requested_weekly_change_kg
    assert isinstance(profile.height_cm, float)
    assert isinstance(profile.weight_kg, float)


@pytest.mark.parametrize("age_years", [18, 80])
def test_accepts_supported_age_boundaries(age_years: int) -> None:
    assert make_profile(age_years=age_years).age_years == age_years


@pytest.mark.parametrize(("field_name", "value"), [("height_cm", 100), ("height_cm", 250)])
def test_accepts_height_boundaries(field_name: str, value: int) -> None:
    profile = make_profile(**{field_name: value})

    assert profile.height_cm == float(value)


@pytest.mark.parametrize(("field_name", "value"), [("weight_kg", 30), ("weight_kg", 300)])
def test_accepts_weight_boundaries(field_name: str, value: int) -> None:
    profile = make_profile(**{field_name: value})

    assert profile.weight_kg == float(value)


@pytest.mark.parametrize("age_years", [17, 81, 18.0])
def test_rejects_age_outside_supported_scope_or_non_integer(age_years: object) -> None:
    with pytest.raises(ProfileValidationError, match="age_years"):
        make_profile(age_years=age_years)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("height_cm", 99.9),
        ("height_cm", 250.1),
        ("height_cm", math.nan),
        ("height_cm", math.inf),
        ("weight_kg", 29.9),
        ("weight_kg", 300.1),
        ("weight_kg", math.nan),
        ("weight_kg", -math.inf),
    ],
)
def test_rejects_invalid_or_non_finite_measurements(field_name: str, value: float) -> None:
    with pytest.raises(ProfileValidationError, match=field_name):
        make_profile(**{field_name: value})


@pytest.mark.parametrize("requested_weekly_change_kg", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_requested_weekly_change(requested_weekly_change_kg: float) -> None:
    with pytest.raises(ProfileValidationError, match="requested_weekly_change_kg"):
        make_profile(goal=Goal.GAIN, requested_weekly_change_kg=requested_weekly_change_kg)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("height_cm", "180"),
        ("weight_kg", "100"),
        ("requested_weekly_change_kg", "0.25"),
    ],
)
def test_rejects_strings_for_numeric_fields(field_name: str, value: str) -> None:
    with pytest.raises(ProfileValidationError, match=field_name):
        make_profile(**{field_name: value})


def test_normalizes_accepted_integer_measurements_and_change_to_floats() -> None:
    profile = make_profile(
        height_cm=180,
        weight_kg=100,
        requested_weekly_change_kg=0,
    )

    assert profile.height_cm == 180.0
    assert profile.weight_kg == 100.0
    assert profile.requested_weekly_change_kg == 0.0
    assert all(
        isinstance(value, float)
        for value in (profile.height_cm, profile.weight_kg, profile.requested_weekly_change_kg)
    )


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg"),
    [
        (Goal.CUT, 0.1),
        (Goal.CUT, 0.0),
        (Goal.GAIN, -0.1),
        (Goal.GAIN, 0.0),
        (Goal.MAINTAIN, -0.1),
        (Goal.MAINTAIN, 0.1),
    ],
)
def test_rejects_goal_and_change_direction_mismatches(
    goal: Goal, requested_weekly_change_kg: float
) -> None:
    with pytest.raises(ProfileValidationError, match=f"goal '{goal.value}'"):
        make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg"),
    [
        (Goal.CUT, -0.751),
        (Goal.GAIN, 0.501),
    ],
)
def test_rejects_goal_change_exceeding_percentage_limit(
    goal: Goal, requested_weekly_change_kg: float
) -> None:
    with pytest.raises(ProfileValidationError, match=r"0\.(?:75|5)%"):
        make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)


@pytest.mark.parametrize(
    ("goal", "requested_weekly_change_kg"),
    [
        (Goal.CUT, -0.75),
        (Goal.GAIN, 0.5),
    ],
)
def test_accepts_exact_goal_change_percentage_boundaries(
    goal: Goal, requested_weekly_change_kg: float
) -> None:
    profile = make_profile(goal=goal, requested_weekly_change_kg=requested_weekly_change_kg)

    assert profile.requested_weekly_change_kg == requested_weekly_change_kg


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("age_years", True),
        ("height_cm", True),
        ("weight_kg", False),
        ("requested_weekly_change_kg", True),
    ],
)
def test_rejects_booleans_for_numeric_fields(field_name: str, value: bool) -> None:
    with pytest.raises(ProfileValidationError, match=field_name):
        make_profile(**{field_name: value})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("sex_for_bmr", "male"),
        ("activity_level", "active"),
        ("goal", "cut"),
    ],
)
def test_rejects_non_enum_values(field_name: str, value: str) -> None:
    with pytest.raises(ProfileValidationError, match=field_name):
        make_profile(**{field_name: value})


def test_profile_is_immutable() -> None:
    profile = make_profile()

    with pytest.raises(FrozenInstanceError):
        profile.weight_kg = 90.0  # type: ignore[misc]
