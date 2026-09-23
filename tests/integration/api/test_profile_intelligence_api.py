"""HTTP contracts for the single stateless profile-intelligence operation."""

import json
from datetime import date, timedelta
from math import inf, nan

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app
from fitadapt.api.schemas import map_profile_intelligence
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.intelligence import analyze_profile_intelligence
from fitadapt.personalization.macros import MacroStrategy, NutritionPreferences


def _profile_payload() -> dict[str, object]:
    return {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "moderately_active",
        "goal": "maintain",
        "requested_weekly_change_kg": 0,
    }


def _observations_payload(days: int, intake: float | None = 2400.0) -> list[dict[str, object]]:
    start = date(2026, 1, 1)
    return [
        {
            "observed_on": (start + timedelta(days=index)).isoformat(),
            "body_weight_kg": 80.0 - 0.03 * index,
            "energy_intake_kcal": intake,
            "steps": 5000,
        }
        for index in range(days)
    ]


def _payload(days: int = 14) -> dict[str, object]:
    return {
        "profile": _profile_payload(),
        "observations": _observations_payload(days),
        "nutrition_preferences": {"macro_strategy": "balanced"},
    }


def _domain_profile() -> UserProfile:
    return UserProfile(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0,
    )


def _domain_observations(days: int) -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=date(2026, 1, 1) + timedelta(days=index),
            body_weight_kg=80.0 - 0.03 * index,
            energy_intake_kcal=2400.0,
            steps=5000,
        )
        for index in range(days)
    )


def test_profile_intelligence_endpoint_matches_complete_direct_empty_result() -> None:
    payload = _payload(0)
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)
    expected = map_profile_intelligence(
        analyze_profile_intelligence(
            _domain_profile(), (), NutritionPreferences(MacroStrategy.BALANCED)
        )
    ).model_dump(mode="json")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.json()["plan_progression"] is None
    assert response.json()["latest_plan"]["as_of_date"] is None
    assert response.json()["latest_plan"]["calorie_basis"] == "baseline"


@pytest.mark.parametrize("days", [0, 1, 11, 14])
def test_profile_intelligence_endpoint_serializes_each_lifecycle_stage(days: int) -> None:
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=_payload(days))
    expected = ("baseline", "calibrating", "early_personalized", "personalized")

    assert response.status_code == 200
    assert response.json()["lifecycle"]["stage"] == expected[[0, 1, 11, 14].index(days)]
    assert (
        response.json()["latest_plan"]["lifecycle_stage"] == response.json()["lifecycle"]["stage"]
    )
    assert isinstance(response.json()["recommendation"]["status"], str)
    assert response.json()["adaptive_tdee"]["adaptive_tdee_kcal_per_day"] is None or isinstance(
        response.json()["adaptive_tdee"]["adaptive_tdee_kcal_per_day"], float
    )


def test_progression_is_opt_in_and_uses_chronological_history() -> None:
    payload = _payload(14)
    payload["observations"] = list(reversed(payload["observations"]))  # type: ignore[arg-type]
    omitted = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)
    payload["include_plan_progression"] = False
    explicit_false = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)
    payload["include_plan_progression"] = True
    included = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)

    assert omitted.status_code == explicit_false.status_code == included.status_code == 200
    assert omitted.json()["plan_progression"] is None
    assert explicit_false.json()["plan_progression"] is None
    progression = included.json()["plan_progression"]
    assert progression is not None
    assert len(progression["snapshots"]) == 14
    assert progression["snapshots"][-1] == included.json()["latest_plan"]
    assert [item["as_of_date"] for item in progression["snapshots"]] == sorted(
        item["as_of_date"] for item in progression["snapshots"]
    )


@pytest.mark.parametrize(
    "preferences",
    [
        {"macro_strategy": "higher_carb"},
        {"macro_strategy": "higher_fat"},
        {"macro_strategy": "higher_protein"},
        {
            "macro_strategy": "custom",
            "custom_protein_g_per_kg": 2.2,
            "custom_fat_percentage": 0.30,
        },
    ],
)
def test_profile_intelligence_endpoint_applies_explicit_macro_preferences(
    preferences: dict[str, object],
) -> None:
    payload = _payload(14)
    payload["nutrition_preferences"] = preferences
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)
    macro = response.json()["latest_plan"]["macro_plan"]

    assert response.status_code == 200
    assert macro["strategy"] == preferences["macro_strategy"]
    assert macro["protein_kcal_per_day"] + macro["fat_kcal_per_day"] + macro[
        "carbohydrate_kcal_per_day"
    ] == pytest.approx(response.json()["latest_plan"]["selected_calorie_target_kcal_per_day"])


def test_zero_and_missing_values_are_preserved_as_distinct_json_values() -> None:
    zero_payload = _payload(14)
    zero_payload["observations"] = _observations_payload(14, intake=0.0)
    missing_payload = _payload(14)
    missing_payload["observations"] = _observations_payload(14, intake=None)
    zero = TestClient(create_app()).post("/v1/profile-intelligence", json=zero_payload)
    missing = TestClient(create_app()).post("/v1/profile-intelligence", json=missing_payload)

    assert zero.status_code == missing.status_code == 200
    assert zero.json()["trends"]["points"][-1]["energy_intake_kcal"] == 0.0
    assert missing.json()["trends"]["points"][-1]["energy_intake_kcal"] is None
    assert zero.json()["recommendation"]["recent_mean_intake_kcal_per_day"] == 0.0
    assert missing.json()["recommendation"]["recent_mean_intake_kcal_per_day"] is None


@pytest.mark.parametrize(
    "payload_update",
    [
        {"unknown": True},
        {"nutrition_preferences": {"macro_strategy": "balanced", "unknown": True}},
        {"include_plan_progression": 1},
        {"include_plan_progression": "true"},
        {"profile": {**_profile_payload(), "weight_kg": True}},
        {"profile": {**_profile_payload(), "weight_kg": "80"}},
    ],
)
def test_profile_intelligence_endpoint_rejects_strict_transport_values(
    payload_update: dict[str, object],
) -> None:
    payload = _payload(1)
    payload.update(payload_update)

    response = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("value", [nan, inf])
def test_profile_intelligence_endpoint_rejects_non_finite_json_numbers(value: float) -> None:
    payload = _payload(1)
    payload["profile"] = {**_profile_payload(), "weight_kg": value}

    response = TestClient(create_app()).post(
        "/v1/profile-intelligence",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_profile_intelligence_endpoint_preserves_domain_and_opaque_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = _payload(2)
    duplicate["observations"][1]["observed_on"] = duplicate["observations"][0]["observed_on"]  # type: ignore[index]
    client = TestClient(create_app(), raise_server_exceptions=False)
    domain = client.post("/v1/profile-intelligence", json=duplicate)

    def raise_unexpected(*_: object) -> object:
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr("fitadapt.api.app.analyze_profile_intelligence", raise_unexpected)
    unexpected = client.post("/v1/profile-intelligence", json=_payload(0))

    assert domain.status_code == 400
    assert domain.json()["error"]["code"] == "trend_analysis_error"
    assert unexpected.status_code == 500
    assert unexpected.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error."}
    }


def test_profile_intelligence_openapi_documents_complete_enum_and_error_contract() -> None:
    openapi = TestClient(create_app()).get("/openapi.json").json()
    operation = openapi["paths"]["/v1/profile-intelligence"]["post"]
    schemas = openapi["components"]["schemas"]
    properties = schemas["PersonalizedPlanSnapshotResponse"]["properties"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProfileIntelligenceResponse"
    }
    assert {"200", "400", "422", "500"} <= set(operation["responses"])
    assert operation["responses"]["400"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert properties["lifecycle_stage"] == {"$ref": "#/components/schemas/PersonalizationStage"}
    assert properties["recommendation_status"] == {
        "$ref": "#/components/schemas/RecommendationStatus"
    }
    assert list(openapi["paths"]).count("/v1/profile-intelligence") == 1
