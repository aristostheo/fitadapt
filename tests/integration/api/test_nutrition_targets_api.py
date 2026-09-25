"""HTTP contracts for additive V1 nutrition target envelopes."""

import json

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def payload(strategy: str = "balanced") -> dict[str, object]:
    preferences: dict[str, object] = {"macro_strategy": strategy}
    if strategy == "custom":
        preferences.update(custom_protein_g_per_kg=2.0, custom_fat_percentage=0.25)
    return {
        "profile": {
            "age_years": 30,
            "height_cm": 180,
            "weight_kg": 80,
            "sex_for_mifflin_equation": "male",
            "activity_level": "moderately_active",
            "goal": "maintain",
            "requested_weekly_change_kg": 0,
        },
        "preferences": preferences,
        "calorie_target_kcal_per_day": 2400,
        "calorie_source": "baseline",
    }


def test_nutrition_target_endpoint_serializes_ranges_and_all_strategies() -> None:
    client = TestClient(create_app())
    for strategy in ("balanced", "higher_carb", "higher_fat", "higher_protein", "custom"):
        response = client.post("/v1/nutrition/targets", json=payload(strategy))
        assert response.status_code == 200
        body = response.json()
        assert body["macro_strategy"] == strategy
        assert body["calorie_adherence_range"] == {
            "lower_bound": 2300.0,
            "selected_value": 2400.0,
            "upper_bound": 2500.0,
            "unit": "kcal/day",
            "interpretation": "An adherence policy band around the selected intake target.",
            "range_kind": "adherence",
        }
        assert (
            body["macro_plan"]["calorie_target_kcal_per_day"]
            == body["selected_calorie_target_kcal_per_day"]
        )


def test_nutrition_target_transport_and_domain_errors_are_stable() -> None:
    client = TestClient(create_app())
    invalid = payload()
    invalid["unexpected"] = True
    assert client.post("/v1/nutrition/targets", json=invalid).status_code == 422
    boolean = payload()
    boolean["calorie_target_kcal_per_day"] = True
    assert client.post("/v1/nutrition/targets", json=boolean).status_code == 422
    infeasible = payload("higher_protein")
    infeasible["calorie_target_kcal_per_day"] = 100
    response = client.post("/v1/nutrition/targets", json=infeasible)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "nutrition_target_envelope_error"


def test_unexpected_target_failure_is_opaque(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unexpected(*_: object) -> object:
        raise RuntimeError("private target implementation detail")

    monkeypatch.setattr("fitadapt.api.app.calculate_nutrition_target_envelope", raise_unexpected)
    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/nutrition/targets", json=payload()
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error."}
    }


def test_openapi_documents_one_target_route_and_error_responses() -> None:
    document = TestClient(create_app()).get("/openapi.json").json()
    assert list(path for path in document["paths"] if path == "/v1/nutrition/targets") == [
        "/v1/nutrition/targets"
    ]
    responses = document["paths"]["/v1/nutrition/targets"]["post"]["responses"]
    assert {"400", "422", "500"} <= set(responses)


def test_unified_response_contains_the_latest_and_prefix_envelopes() -> None:
    body = {
        "profile": payload()["profile"],
        "observations": [],
        "nutrition_preferences": payload()["preferences"],
        "include_plan_progression": True,
    }
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["latest_plan"]["target_envelope"]["calorie_source"] == "baseline"
    assert result["plan_progression"]["snapshots"] == []


def test_target_transport_uses_json_primitives_and_preserves_existing_profile_fields() -> None:
    client = TestClient(create_app())
    target = client.post("/v1/nutrition/targets", json=payload())
    unified = client.post(
        "/v1/profile-intelligence",
        json={
            "profile": payload()["profile"],
            "observations": [],
            "nutrition_preferences": payload()["preferences"],
            "include_plan_progression": False,
        },
    )

    assert target.status_code == unified.status_code == 200
    target_body = target.json()
    unified_body = unified.json()
    json.dumps(target_body, allow_nan=False)
    json.dumps(unified_body, allow_nan=False)
    assert {
        "policy_version",
        "baseline",
        "trends",
        "adaptive_tdee",
        "lifecycle",
        "recommendation",
        "latest_plan",
        "plan_progression",
        "assumptions",
    } <= unified_body.keys()
    assert {
        "as_of_date",
        "lifecycle_stage",
        "calorie_basis",
        "selected_calorie_target_kcal_per_day",
        "macro_plan",
        "planning_policy_version",
        "assumptions",
    } <= unified_body["latest_plan"].keys()
    envelope = unified_body["latest_plan"]["target_envelope"]
    assert envelope.keys() == target_body.keys()
    assert (
        envelope["selected_calorie_target_kcal_per_day"]
        == (unified_body["latest_plan"]["selected_calorie_target_kcal_per_day"])
    )
    assert envelope["macro_plan"] == unified_body["latest_plan"]["macro_plan"]
    assert unified_body["plan_progression"] is None
