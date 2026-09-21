"""HTTP contracts for the stateless personalization lifecycle endpoint."""

import json
from datetime import date, timedelta
from math import inf, nan

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app
from fitadapt.api.schemas import map_personalization_lifecycle
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.lifecycle import assess_personalization_lifecycle


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


def _observation_payload(days: int) -> list[dict[str, object]]:
    start = date(2026, 1, 1)
    return [
        {
            "observed_on": (start + timedelta(days=index)).isoformat(),
            "body_weight_kg": 80.0 - 0.03 * index,
            "energy_intake_kcal": 2400.0,
            "steps": 5000,
        }
        for index in range(days)
    ]


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
            observed_on=date.fromisoformat(item["observed_on"]),
            body_weight_kg=item["body_weight_kg"],
            energy_intake_kcal=item["energy_intake_kcal"],
            steps=item["steps"],
        )
        for item in _observation_payload(days)
    )


@pytest.mark.parametrize(
    ("days", "stage"),
    [(0, "baseline"), (1, "calibrating"), (11, "early_personalized"), (14, "personalized")],
)
def test_personalization_endpoint_serializes_each_stage_and_matches_engine(
    days: int, stage: str
) -> None:
    payload = {"profile": _profile_payload(), "observations": _observation_payload(days)}
    response = TestClient(create_app()).post("/v1/personalization/status", json=payload)
    expected = map_personalization_lifecycle(
        assess_personalization_lifecycle(_domain_profile(), _domain_observations(days))
    ).model_dump(mode="json")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.json()["stage"] == stage
    assert all(isinstance(item, str) for item in response.json()["requirements"])


def test_personalization_endpoint_accepts_existing_custom_configs() -> None:
    response = TestClient(create_app()).post(
        "/v1/personalization/status",
        json={
            "profile": _profile_payload(),
            "observations": _observation_payload(6),
            "trend_config": {"window_size_days": 3, "minimum_observations": 2},
            "adaptive_config": {"aggregation_window_days": 4, "minimum_estimate_points": 2},
            "lifecycle_config": {
                "minimum_calendar_history_days": 5,
                "minimum_weight_completeness": 1,
                "minimum_intake_completeness": 1,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "personalized"
    assert response.json()["required_eligible_estimate_count"] == 2


def test_personalization_endpoint_has_stable_domain_and_transport_errors() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    duplicate = _observation_payload(2)
    duplicate[1]["observed_on"] = duplicate[0]["observed_on"]

    domain = client.post(
        "/v1/personalization/status",
        json={"profile": _profile_payload(), "observations": duplicate},
    )
    transport = client.post(
        "/v1/personalization/status",
        json={
            "profile": _profile_payload(),
            "observations": [],
            "lifecycle_config": {"minimum_weight_completeness": True},
        },
    )

    assert domain.status_code == 400
    assert domain.json()["error"]["code"] == "trend_analysis_error"
    assert transport.status_code == 422


@pytest.mark.parametrize(
    "payload_update",
    [
        {"unexpected": "not accepted"},
        {"profile": {**_profile_payload(), "unexpected": "not accepted"}},
        {"lifecycle_config": {"minimum_weight_completeness": True}},
        {"lifecycle_config": {"minimum_weight_completeness": "0.7"}},
    ],
)
def test_personalization_endpoint_strictly_rejects_unknown_and_invalid_transport_values(
    payload_update: dict[str, object],
) -> None:
    payload = {"profile": _profile_payload(), "observations": _observation_payload(1)}
    payload.update(payload_update)

    response = TestClient(create_app()).post("/v1/personalization/status", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "lifecycle_config",
    [
        {"minimum_weight_completeness": nan},
        {"minimum_intake_completeness": inf},
    ],
)
def test_personalization_endpoint_rejects_non_finite_json_numbers(
    lifecycle_config: dict[str, float],
) -> None:
    response = TestClient(create_app()).post(
        "/v1/personalization/status",
        content=json.dumps(
            {
                "profile": _profile_payload(),
                "observations": _observation_payload(1),
                "lifecycle_config": lifecycle_config,
            }
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_personalization_endpoint_uses_opaque_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unexpected(*_: object) -> object:
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr("fitadapt.api.app.assess_personalization_lifecycle", raise_unexpected)
    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/v1/personalization/status",
        json={"profile": _profile_payload(), "observations": []},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error."}
    }


def test_personalization_openapi_documents_enum_and_error_contracts() -> None:
    openapi = TestClient(create_app()).get("/openapi.json").json()
    operation = openapi["paths"]["/v1/personalization/status"]["post"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    properties = openapi["components"]["schemas"]["PersonalizationLifecycleResponse"]["properties"]

    assert response_schema["$ref"].endswith("PersonalizationLifecycleResponse")
    assert properties["stage"] == {"$ref": "#/components/schemas/PersonalizationStage"}
    assert properties["requirements"]["items"] == {
        "$ref": "#/components/schemas/PersonalizationRequirement"
    }
    assert {"200", "400", "422", "500"} <= set(operation["responses"])
    assert operation["responses"]["400"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert list(openapi["paths"]).count("/v1/personalization/status") == 1
