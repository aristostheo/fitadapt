"""HTTP contracts for informational training-demand assessment."""

import json
from datetime import date, timedelta
from math import nan

from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def profile() -> dict[str, object]:
    return {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "moderately_active",
        "goal": "maintain",
        "requested_weekly_change_kg": 0,
    }


def observations(
    days: int = 14, *, strength: float | None = 0, cardio: float | None = 0
) -> list[dict[str, object]]:
    return [
        {
            "observed_on": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "steps": 5000,
            "strength_training_minutes": strength,
            "cardio_minutes": cardio,
        }
        for index in range(days)
    ]


def context(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "occupation_activity": "mostly_seated",
        "resistance_days_per_week": 0,
        "resistance_minutes_per_week": 0,
        "cardio_days_per_week": 0,
        "cardio_minutes_per_week": 0,
        "sport_days_per_week": 0,
        "sport_minutes_per_week": 0,
        "primary_training_focus": "general",
    }
    value.update(updates)
    return value


def test_standalone_questionnaire_observation_and_insufficient_assessments() -> None:
    client = TestClient(create_app())
    questionnaire = client.post(
        "/v1/training/demand",
        json={
            "training_context": context(
                resistance_days_per_week=4, resistance_minutes_per_week=240
            ),
            "observations": [],
        },
    )
    observed = client.post("/v1/training/demand", json={"observations": observations()})
    insufficient = client.post("/v1/training/demand", json={"observations": observations(2)})
    assert questionnaire.status_code == observed.status_code == insufficient.status_code == 200
    assert questionnaire.json()["evidence_source"] == "questionnaire"
    assert questionnaire.json()["resistance_demand"] == "high"
    assert observed.json()["evidence_source"] == "observations"
    assert observed.json()["effective_date"] == "2026-01-14"
    assert observed.json()["strength_evidence"]["weekly_equivalent"] == 0.0
    assert insufficient.json()["assessment_available"] is False
    assert insufficient.json()["evidence_source"] == "insufficient"


def test_unified_training_is_additive_and_latest_only() -> None:
    client = TestClient(create_app())
    payload = {
        "profile": profile(),
        "observations": observations(),
        "nutrition_preferences": {"macro_strategy": "balanced"},
        "training_context": context(
            resistance_days_per_week=3,
            resistance_minutes_per_week=180,
            primary_training_focus="resistance",
        ),
        "include_plan_progression": True,
    }
    response = client.post("/v1/profile-intelligence", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["training_assessment"]["evidence_source"] == "combined"
    assert body["training_assessment"]["resistance_demand"] == "low"
    assert body["plan_progression"] is not None
    assert "training_assessment" not in body["plan_progression"]["snapshots"][0]
    assert (
        body["latest_plan"]["selected_calorie_target_kcal_per_day"]
        == body["latest_plan"]["target_envelope"]["selected_calorie_target_kcal_per_day"]
    )


def test_transport_domain_errors_and_openapi() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    unknown = client.post("/v1/training/demand", json={"unknown": True})
    assert unknown.status_code == 422
    invalid = client.post(
        "/v1/training/demand", json={"training_context": context(resistance_days_per_week=True)}
    )
    assert invalid.status_code == 422
    string_number = client.post(
        "/v1/training/demand", json={"training_context": context(resistance_days_per_week="2")}
    )
    assert string_number.status_code == 422
    nonfinite = client.post(
        "/v1/training/demand",
        content=json.dumps({"training_context": context(resistance_minutes_per_week=nan)}),
        headers={"content-type": "application/json"},
    )
    assert nonfinite.status_code == 422
    duplicate = observations(1) * 2
    domain = client.post("/v1/training/demand", json={"observations": duplicate})
    assert domain.status_code == 400
    assert domain.json()["error"]["code"] == "training_domain_error"
    responses = client.get("/openapi.json").json()["paths"]["/v1/training/demand"]["post"][
        "responses"
    ]
    assert {"200", "400", "422", "500"} <= set(responses)
