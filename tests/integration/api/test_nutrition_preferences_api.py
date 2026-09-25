"""HTTP contracts for dietary preference assessment integration."""

import json
from datetime import date, timedelta
from math import nan

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def _profile() -> dict[str, object]:
    return {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "moderately_active",
        "goal": "maintain",
        "requested_weekly_change_kg": 0,
    }


def _dietary(
    pattern: str = "unrestricted",
    mode: str = "broad",
    constraints: list[dict[str, object]] | None = None,
    preferences: list[dict[str, object]] | None = None,
    description: str | None = None,
) -> dict[str, object]:
    return {
        "dietary_pattern": pattern,
        "selection_mode": mode,
        "constraints": constraints or [],
        "preferences": preferences or [],
        "other_description": description,
    }


def _payload(
    dietary_profile: dict[str, object] | None = None, **dietary_updates: object
) -> dict[str, object]:
    return {
        "profile": _profile(),
        "preferences": {"macro_strategy": "balanced"},
        "calorie_target_kcal_per_day": 2400,
        "calorie_source": "baseline",
        "dietary_preference_profile": dietary_profile or _dietary(**dietary_updates),
    }


def _unified_payload(
    days: int = 0, dietary_profile: dict[str, object] | None = None
) -> dict[str, object]:
    start = date(2026, 1, 1)
    observations = [
        {
            "observed_on": (start + timedelta(days=index)).isoformat(),
            "body_weight_kg": 80.0 - 0.03 * index,
            "energy_intake_kcal": 2400.0,
            "steps": 5000,
        }
        for index in range(days)
    ]
    payload: dict[str, object] = {
        "profile": _profile(),
        "observations": observations,
        "nutrition_preferences": {"macro_strategy": "balanced"},
    }
    if dietary_profile is not None:
        payload["dietary_preference_profile"] = dietary_profile
    return payload


def test_standalone_assessment_returns_envelope_provenance_and_policy_versions() -> None:
    response = TestClient(create_app()).post("/v1/nutrition/preferences/assess", json=_payload())
    body = response.json()

    assert response.status_code == 200
    assert body["dietary_pattern"] == "unrestricted"
    assert body["selection_mode"] == "broad"
    assert body["protein_target_range"]["selected_value"] == 144.0
    assert body["usable_protein_source_count"] == 13
    assert body["protein_flexibility_status"] == "supported"
    assert body["target_range_policy_version"] == "nutrition_target_ranges_v1"
    assert body["category_policy_version"] == "dietary_categories_v1"
    assert body["assessment_policy_version"] == "dietary_assessment_v1"
    assert body["protein_flexibility_policy_version"] == "protein_flexibility_v1"
    assert body["assumptions"]


@pytest.mark.parametrize(
    ("pattern", "excluded", "notice"),
    [
        ("vegetarian", {"poultry", "beef", "pork", "fish", "shellfish"}, False),
        ("vegan", {"poultry", "beef", "pork", "fish", "shellfish", "eggs", "dairy"}, False),
        ("pescatarian", {"poultry", "beef", "pork"}, False),
        ("halal", {"pork"}, True),
        ("kosher", {"pork", "shellfish"}, True),
    ],
)
def test_standalone_patterns_are_conservative(
    pattern: str, excluded: set[str], notice: bool
) -> None:
    response = TestClient(create_app()).post(
        "/v1/nutrition/preferences/assess", json=_payload(dietary_profile=_dietary(pattern))
    )
    body = response.json()

    assert response.status_code == 200
    assert set(body["inferred_hard_excluded_categories"]) == excluded
    assert bool(body["verification_notices"]) is notice


def test_standalone_selected_foods_and_all_preference_levels_serialize() -> None:
    categories = ("eggs", "soy", "legumes", "nuts")
    response = TestClient(create_app()).post(
        "/v1/nutrition/preferences/assess",
        json=_payload(
            dietary_profile=_dietary(
                mode="selected",
                preferences=[
                    {"category": "beef", "level": "dislike"},
                    {"category": "eggs", "level": "neutral"},
                    {"category": "soy", "level": "like"},
                    {"category": "legumes", "level": "favorite"},
                    {"category": "nuts", "level": "neutral"},
                ],
            )
        ),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["disliked_categories"] == ["beef"]
    assert body["preferred_categories"] == ["eggs", "soy", "nuts"]
    assert body["favorite_categories"] == ["legumes"]
    assert body["usable_protein_source_categories"] == list(categories)
    assert body["usable_protein_source_count"] == 4
    assert body["protein_flexibility_status"] == "supported"


def test_standalone_other_manual_review_and_constraint_precedence() -> None:
    response = TestClient(create_app()).post(
        "/v1/nutrition/preferences/assess",
        json=_payload(
            dietary_profile=_dietary(
                pattern="other",
                description="Culturally specific pattern requiring review",
                constraints=[
                    {"category": "beef", "constraint_type": "allergy", "action": "exclude"},
                    {"category": "dairy", "constraint_type": "intolerance", "action": "limit"},
                    {
                        "category": "pork",
                        "constraint_type": "required_exclusion",
                        "action": "exclude",
                    },
                ],
                preferences=[
                    {"category": "beef", "level": "favorite"},
                    {"category": "pork", "level": "like"},
                ],
            )
        ),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["explicit_hard_excluded_categories"] == ["beef", "pork"]
    assert body["limited_categories"] == ["dairy"]
    assert len(body["conflicts"]) == 2
    assert body["verification_notices"] == [
        "The other dietary pattern has no inferred exclusions and requires manual review."
    ]


def test_standalone_selected_thresholds_cover_zero_through_four_sources() -> None:
    client = TestClient(create_app())
    protein_categories = ("poultry", "beef", "pork", "fish")
    expected = ("infeasible", "difficult", "limited", "limited", "supported")
    for count, status in enumerate(expected):
        response = client.post(
            "/v1/nutrition/preferences/assess",
            json=_payload(
                dietary_profile=_dietary(
                    mode="selected",
                    preferences=[
                        {"category": category, "level": "neutral"}
                        for category in protein_categories[:count]
                    ],
                )
            ),
        )
        assert response.status_code == 200
        assert response.json()["usable_protein_source_count"] == count
        assert response.json()["protein_flexibility_status"] == status


def test_standalone_transport_domain_and_unexpected_errors() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    unknown = _payload()
    unknown["unexpected"] = True
    assert client.post("/v1/nutrition/preferences/assess", json=unknown).status_code == 422
    invalid_enum = _payload(dietary_profile=_dietary(pattern="sometimes"))
    assert client.post("/v1/nutrition/preferences/assess", json=invalid_enum).status_code == 422
    boolean = _payload()
    boolean["calorie_target_kcal_per_day"] = True
    assert client.post("/v1/nutrition/preferences/assess", json=boolean).status_code == 422
    string_number = _payload()
    string_number["calorie_target_kcal_per_day"] = "2400"
    assert client.post("/v1/nutrition/preferences/assess", json=string_number).status_code == 422
    non_finite = _payload()
    non_finite["calorie_target_kcal_per_day"] = nan
    response = client.post(
        "/v1/nutrition/preferences/assess",
        content=json.dumps(non_finite),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    duplicate = _payload(
        dietary_profile=_dietary(
            constraints=[
                {"category": "beef", "constraint_type": "allergy", "action": "exclude"},
                {"category": "beef", "constraint_type": "allergy", "action": "exclude"},
            ]
        )
    )
    response = client.post("/v1/nutrition/preferences/assess", json=duplicate)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "nutrition_dietary_error"

    def fail(*_: object) -> object:
        raise RuntimeError("private dietary detail")

    import fitadapt.api.app as app_module

    original = app_module.assess_nutrition_preferences
    app_module.assess_nutrition_preferences = fail
    try:
        response = client.post("/v1/nutrition/preferences/assess", json=_payload())
    finally:
        app_module.assess_nutrition_preferences = original
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error."}
    }


def test_standalone_openapi_has_one_route_and_documented_errors() -> None:
    document = TestClient(create_app()).get("/openapi.json").json()
    assert list(document["paths"]).count("/v1/nutrition/preferences/assess") == 1
    responses = document["paths"]["/v1/nutrition/preferences/assess"]["post"]["responses"]
    assert {"200", "400", "422", "500"} <= set(responses)


def test_unified_uses_default_latest_assessment_without_changing_existing_plan() -> None:
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=_unified_payload())
    body = response.json()

    assert response.status_code == 200
    assert body["dietary_assessment"]["dietary_pattern"] == "unrestricted"
    assert body["dietary_assessment"]["selection_mode"] == "broad"
    assert (
        body["dietary_assessment"]["protein_target_range"]
        == body["latest_plan"]["target_envelope"]["protein_preferred_range"]
    )
    assert body["plan_progression"] is None


def test_unified_accepts_selected_profile_and_preserves_latest_envelope() -> None:
    dietary_profile = _dietary(
        mode="selected",
        preferences=[
            {"category": "eggs", "level": "neutral"},
            {"category": "soy", "level": "like"},
        ],
    )
    response = TestClient(create_app()).post(
        "/v1/profile-intelligence", json=_unified_payload(14, dietary_profile)
    )
    body = response.json()

    assert response.status_code == 200
    assert body["dietary_assessment"]["selection_mode"] == "selected"
    assert body["dietary_assessment"]["usable_protein_source_count"] == 2
    assert body["dietary_assessment"]["protein_flexibility_status"] == "limited"
    assert (
        body["dietary_assessment"]["protein_target_range"]
        == body["latest_plan"]["target_envelope"]["protein_preferred_range"]
    )
    assert (
        body["latest_plan"]["macro_plan"]["calorie_target_kcal_per_day"]
        == body["latest_plan"]["target_envelope"]["macro_plan"]["calorie_target_kcal_per_day"]
    )


def test_unified_patterns_and_conflicts_are_visible() -> None:
    for pattern in (
        "unrestricted",
        "vegetarian",
        "vegan",
        "pescatarian",
        "halal",
        "kosher",
        "other",
    ):
        profile = _dietary(pattern=pattern, description="manual" if pattern == "other" else None)
        response = TestClient(create_app()).post(
            "/v1/profile-intelligence", json=_unified_payload(0, profile)
        )
        assert response.status_code == 200
        assessment = response.json()["dietary_assessment"]
        if pattern in ("halal", "kosher", "other"):
            assert assessment["verification_notices"]
    conflict = _dietary(
        pattern="vegetarian",
        preferences=[{"category": "poultry", "level": "favorite"}],
    )
    response = TestClient(create_app()).post(
        "/v1/profile-intelligence", json=_unified_payload(0, conflict)
    )
    assert response.status_code == 200
    assert response.json()["dietary_assessment"]["conflicts"]


def test_unified_unknown_dietary_fields_remain_transport_422() -> None:
    payload = _unified_payload()
    payload["dietary_preference_profile"] = {**_dietary(), "unknown": True}
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=payload)
    assert response.status_code == 422
