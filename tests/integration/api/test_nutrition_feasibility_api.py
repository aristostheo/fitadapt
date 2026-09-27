"""Unified API contracts for practical nutrition feasibility."""

from datetime import date

from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def _base() -> dict[str, object]:
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
        "observations": [],
        "nutrition_preferences": {"macro_strategy": "balanced"},
    }


def test_missing_dietary_profile_is_unavailable_but_old_fields_remain() -> None:
    response = TestClient(create_app()).post("/v1/profile-intelligence", json=_base())
    body = response.json()
    assert response.status_code == 200
    assert body["nutrition_feasibility"]["assessment_available"] is False
    assert (
        body["latest_plan"]["selected_calorie_target_kcal_per_day"]
        == body["nutrition_feasibility"]["calorie_target_kcal_per_day"]
    )
    assert (
        body["nutrition_feasibility"]["baseline_protein_target_g_per_day"]
        == body["latest_plan"]["macro_plan"]["protein_g_per_day"]
    )
    assert body["latest_plan"]["macro_plan"]["training_adjustment_applied"] is False
    assert "baseline" in body
    assert "recommendation" in body
    assert "dietary_assessment" in body


def test_explicit_broad_and_restriction_profiles_return_feasibility_not_revised_targets() -> None:
    base = _base()
    broad = {
        "dietary_pattern": "unrestricted",
        "selection_mode": "broad",
        "constraints": [],
        "preferences": [],
    }
    response = TestClient(create_app()).post(
        "/v1/profile-intelligence",
        json={**base, "dietary_preference_profile": broad},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["nutrition_feasibility"]["assessment_available"] is True
    assert body["nutrition_feasibility"]["overall_feasibility"] == "easy"
    assert (
        body["nutrition_feasibility"]["calorie_target_kcal_per_day"]
        == body["latest_plan"]["selected_calorie_target_kcal_per_day"]
    )

    vegan = {
        **broad,
        "dietary_pattern": "vegan",
        "selection_mode": "selected",
        "preferences": [
            {"category": "soy", "level": "like"},
            {"category": "legumes", "level": "neutral"},
        ],
    }
    vegan_body = (
        TestClient(create_app())
        .post(
            "/v1/profile-intelligence",
            json={**base, "dietary_preference_profile": vegan},
        )
        .json()
    )
    assert vegan_body["nutrition_feasibility"]["assessment_available"] is True
    assert "dairy" in vegan_body["nutrition_feasibility"]["limiting_categories"]


def test_training_aware_macro_and_feasibility_compose_without_calorie_change() -> None:
    context = {
        "occupation_activity": "mostly_seated",
        "resistance_days_per_week": 4,
        "resistance_minutes_per_week": 240,
        "cardio_days_per_week": 4,
        "cardio_minutes_per_week": 240,
        "cardio_intensity": "moderate",
        "sport_days_per_week": 0,
        "sport_minutes_per_week": 0,
        "primary_training_focus": "mixed",
    }
    dietary = {
        "dietary_pattern": "unrestricted",
        "selection_mode": "selected",
        "constraints": [],
        "preferences": [
            {"category": "dairy", "level": "like"},
            {"category": "rice", "level": "like"},
            {"category": "nuts", "level": "neutral"},
        ],
    }
    body = (
        TestClient(create_app())
        .post(
            "/v1/profile-intelligence",
            json={**_base(), "training_context": context, "dietary_preference_profile": dietary},
        )
        .json()
    )
    macro = body["latest_plan"]["macro_plan"]
    feasibility = body["nutrition_feasibility"]
    assert body["training_assessment"]["assessment_available"] is True
    assert macro["training_adjustment_available"] is True
    assert feasibility["training_adjustment_applied"] is True
    assert feasibility["training_policy_version"] == "training_aware_macros_v1"
    assert feasibility["protein_policy_source"] == macro["protein_policy_source"]
    assert macro["calorie_target_kcal_per_day"] == feasibility["calorie_target_kcal_per_day"]
    assert (
        macro["protein_kcal_per_day"]
        + macro["fat_kcal_per_day"]
        + macro["carbohydrate_kcal_per_day"]
        == macro["calorie_target_kcal_per_day"]
    )


def test_progression_does_not_gain_feasibility_snapshots() -> None:
    base = _base()
    base["observations"] = [{"observed_on": date(2026, 1, 1).isoformat(), "steps": 0}]
    base["dietary_preference_profile"] = {
        "dietary_pattern": "unrestricted",
        "selection_mode": "broad",
        "constraints": [],
        "preferences": [],
    }
    base["include_plan_progression"] = True
    body = TestClient(create_app()).post("/v1/profile-intelligence", json=base).json()
    assert body["nutrition_feasibility"]["assessment_available"] is True
    assert "nutrition_feasibility" not in body["plan_progression"]["snapshots"][0]
