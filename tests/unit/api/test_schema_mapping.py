"""Transport-schema tests independent of HTTP routing."""

from datetime import date

import pytest
from pydantic import ValidationError

from fitadapt.api.schemas import ObservationRequest, ProfileRequest
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile


def test_profile_request_maps_exactly_to_domain_profile() -> None:
    request = ProfileRequest(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation="male",
        activity_level="moderately_active",
        goal="cut",
        requested_weekly_change_kg=-0.4,
    )

    assert request.to_domain() == UserProfile(
        age_years=30,
        height_cm=180.0,
        weight_kg=80.0,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.CUT,
        requested_weekly_change_kg=-0.4,
    )


def test_observation_request_preserves_null_zero_and_all_supported_fields() -> None:
    request = ObservationRequest(
        observed_on="2026-01-02",
        body_weight_kg=None,
        energy_intake_kcal=0,
        protein_g=100,
        carbohydrate_g=200,
        fat_g=60,
        steps=0,
        strength_training_minutes=0,
        cardio_minutes=30,
        sleep_hours=8,
        hunger_rating=3,
        energy_rating=4,
    )
    observation = request.to_domain()

    assert observation.observed_on == date(2026, 1, 2)
    assert observation.body_weight_kg is None
    assert observation.energy_intake_kcal == 0.0
    assert observation.steps == 0
    assert observation.protein_g == 100.0
    assert observation.carbohydrate_g == 200.0


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (ProfileRequest, {"age_years": True}),
        (ObservationRequest, {"observed_on": "2026-01-02", "steps": True}),
        (ObservationRequest, {"observed_on": "2026-01-02", "energy_intake_kcal": float("inf")}),
    ],
)
def test_numeric_transport_values_reject_boolean_and_non_finite_values(
    model: type[ProfileRequest] | type[ObservationRequest], payload: dict[str, object]
) -> None:
    base: dict[str, object] = {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "sedentary",
        "goal": "maintain",
        "requested_weekly_change_kg": 0,
    }
    if model is ObservationRequest:
        base = {"observed_on": "2026-01-02", "steps": 10}
    base.update(payload)

    with pytest.raises(ValidationError):
        model.model_validate(base)


def test_unknown_transport_fields_are_rejected_without_mutating_input() -> None:
    payload = {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "sedentary",
        "goal": "maintain",
        "requested_weekly_change_kg": 0,
        "unknown": "not accepted",
    }
    original = payload.copy()

    with pytest.raises(ValidationError):
        ProfileRequest.model_validate(payload)

    assert payload == original
