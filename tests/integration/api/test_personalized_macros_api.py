"""HTTP contracts for explicit personalized macro plans."""

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def _payload(strategy: str = "balanced") -> dict[str, object]:
    preferences: dict[str, object] = {"macro_strategy": strategy}
    if strategy == "custom":
        preferences.update({"custom_protein_g_per_kg": 2.2, "custom_fat_percentage": 0.3})
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


@pytest.mark.parametrize(
    "strategy", ["balanced", "higher_carb", "higher_fat", "higher_protein", "custom"]
)
def test_personalized_macros_endpoint_serializes_every_strategy(strategy: str) -> None:
    response = TestClient(create_app()).post("/v1/macros/personalized", json=_payload(strategy))

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == strategy
    assert body["calorie_source"] == "baseline"
    assert body["macro_policy_version"] == "preference_macros_v1"
    assert isinstance(body["assumptions"], list)


def test_personalized_macros_domain_and_transport_errors_are_stable() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    domain = client.post(
        "/v1/macros/personalized", json={**_payload(), "calorie_target_kcal_per_day": 100}
    )
    transport = client.post(
        "/v1/macros/personalized", json={**_payload(), "calorie_target_kcal_per_day": True}
    )

    assert domain.status_code == 400
    assert domain.json()["error"]["code"] == "macro_plan_infeasible"
    assert transport.status_code == 422


def test_personalized_macros_openapi_documents_domain_and_transport_errors() -> None:
    operation = (
        TestClient(create_app())
        .get("/openapi.json")
        .json()["paths"]["/v1/macros/personalized"]["post"]
    )

    assert {"200", "400", "422", "500"}.issubset(operation["responses"])
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("PersonalizedMacroPlanResponse")
