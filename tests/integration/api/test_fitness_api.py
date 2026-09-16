"""HTTP integration tests against direct, existing FitAdapt engine results."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from fitadapt.adaptive.tdee import estimate_adaptive_tdee
from fitadapt.analysis.trends import analyze_observation_trends
from fitadapt.api.app import create_app
from fitadapt.api.schemas import map_adaptive_tdee, map_baseline, map_recommendation, map_trends
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.recommendation.calories import recommend_calorie_adjustment


def _profile_payload(goal: str = "maintain", change: float = 0) -> dict[str, object]:
    return {
        "age_years": 30,
        "height_cm": 180,
        "weight_kg": 80,
        "sex_for_mifflin_equation": "male",
        "activity_level": "moderately_active",
        "goal": goal,
        "requested_weekly_change_kg": change,
    }


def _observations_payload(weight_change_per_day: float = -0.03) -> list[dict[str, object]]:
    start = date(2026, 1, 1)
    return [
        {
            "observed_on": (start + timedelta(days=index)).isoformat(),
            "body_weight_kg": 80 + weight_change_per_day * index,
            "energy_intake_kcal": 2400,
            "steps": 5000,
        }
        for index in range(28)
    ]


def _domain_observations() -> tuple[DailyObservation, ...]:
    return tuple(
        DailyObservation(
            observed_on=date.fromisoformat(item["observed_on"]),
            body_weight_kg=item["body_weight_kg"],
            energy_intake_kcal=item["energy_intake_kcal"],
            steps=item["steps"],
        )
        for item in _observations_payload()
    )


def test_baseline_endpoint_matches_engine_for_all_goal_directions() -> None:
    client = TestClient(create_app())
    cases = (("cut", -0.4), ("maintain", 0), ("gain", 0.2))
    for goal, change in cases:
        profile = UserProfile(
            age_years=30,
            height_cm=180,
            weight_kg=80,
            sex_for_mifflin_equation=SexForMifflinEquation.MALE,
            activity_level=ActivityLevel.MODERATELY_ACTIVE,
            goal=Goal(goal),
            requested_weekly_change_kg=change,
        )
        response = client.post("/v1/baseline", json={"profile": _profile_payload(goal, change)})

        assert response.status_code == 200
        assert response.json() == map_baseline(calculate_calorie_target(profile)).model_dump(
            mode="json"
        )


def test_trends_and_adaptive_endpoints_match_direct_engine_and_preserve_nulls() -> None:
    client = TestClient(create_app())
    payload = {"observations": _observations_payload()}
    observations = _domain_observations()
    trends = analyze_observation_trends(observations)

    trend_response = client.post("/v1/trends", json=payload)
    adaptive_response = client.post("/v1/adaptive-tdee", json=payload)

    assert trend_response.json() == map_trends(trends).model_dump(mode="json")
    assert adaptive_response.json() == map_adaptive_tdee(estimate_adaptive_tdee(trends)).model_dump(
        mode="json"
    )
    assert trend_response.json()["points"][0]["trailing_body_weight_mean_kg"] is None
    assert all(
        isinstance(estimate["eligibility"], str)
        for estimate in adaptive_response.json()["daily_estimates"]
    )
    assert client.post("/v1/trends", json={"observations": []}).json()["points"] == []


def test_trend_and_adaptive_custom_configurations_are_reflected_in_responses() -> None:
    client = TestClient(create_app())
    payload = {
        "observations": _observations_payload(),
        "trend_config": {"window_size_days": 5, "minimum_observations": 3},
        "adaptive_config": {
            "energy_equivalent_kcal_per_kg": 7700,
            "aggregation_window_days": 10,
            "minimum_estimate_points": 3,
        },
    }

    trend = client.post(
        "/v1/trends",
        json={"observations": payload["observations"], "trend_config": payload["trend_config"]},
    )
    adaptive = client.post("/v1/adaptive-tdee", json=payload)

    assert trend.status_code == adaptive.status_code == 200
    assert trend.json()["config"] == {"window_size_days": 5, "minimum_observations": 3}
    assert adaptive.json()["config"] == {
        "energy_equivalent_kcal_per_kg": 7700.0,
        "aggregation_window_days": 10,
        "minimum_estimate_points": 3,
    }


def test_recommendation_endpoint_matches_engine_and_is_deterministic() -> None:
    client = TestClient(create_app())
    payload = {"profile": _profile_payload(), "observations": _observations_payload()}
    profile = UserProfile(
        age_years=30,
        height_cm=180,
        weight_kg=80,
        sex_for_mifflin_equation=SexForMifflinEquation.MALE,
        activity_level=ActivityLevel.MODERATELY_ACTIVE,
        goal=Goal.MAINTAIN,
        requested_weekly_change_kg=0,
    )
    expected = map_recommendation(
        recommend_calorie_adjustment(profile, _domain_observations())
    ).model_dump(mode="json")

    first = client.post("/v1/recommendations/calories", json=payload)
    second = client.post("/v1/recommendations/calories", json=payload)

    assert first.status_code == 200
    assert first.json() == expected == second.json()
    assert isinstance(first.json()["status"], str)
    assert all(isinstance(reason, str) for reason in first.json()["reasons"])


@pytest.mark.parametrize(
    ("weight_change_per_day", "expected_status"),
    [(-0.03, "increase_calories"), (0.0, "hold"), (0.03, "decrease_calories")],
)
def test_recommendation_endpoint_covers_actionable_statuses(
    weight_change_per_day: float, expected_status: str
) -> None:
    response = TestClient(create_app()).post(
        "/v1/recommendations/calories",
        json={
            "profile": _profile_payload(),
            "observations": _observations_payload(weight_change_per_day),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == expected_status


def test_domain_and_transport_errors_have_documented_statuses_and_codes() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)

    assert client.post("/v1/baseline", content="{").status_code == 422
    assert (
        client.post(
            "/v1/baseline", json={"profile": {**_profile_payload(), "unknown": 1}}
        ).status_code
        == 422
    )
    invalid_age = client.post(
        "/v1/baseline", json={"profile": {**_profile_payload(), "age_years": 17}}
    )
    assert invalid_age.status_code == 400
    assert invalid_age.json()["error"]["code"] == "profile_validation_error"
    duplicate = _observations_payload()[:2]
    duplicate[1]["observed_on"] = duplicate[0]["observed_on"]
    duplicate_response = client.post("/v1/trends", json={"observations": duplicate})
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["error"]["code"] == "trend_analysis_error"


def test_observation_and_macro_policy_errors_use_distinct_domain_codes() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    empty_observation = client.post(
        "/v1/trends", json={"observations": [{"observed_on": "2026-01-01"}]}
    )
    macro_infeasible_profile = client.post(
        "/v1/baseline",
        json={
            "profile": {
                "age_years": 80,
                "height_cm": 100,
                "weight_kg": 300,
                "sex_for_mifflin_equation": "female",
                "activity_level": "sedentary",
                "goal": "cut",
                "requested_weekly_change_kg": -2.25,
            }
        },
    )

    assert empty_observation.status_code == 400
    assert empty_observation.json()["error"]["code"] == "observation_validation_error"
    assert macro_infeasible_profile.status_code == 400
    assert macro_infeasible_profile.json()["error"]["code"] == "macro_policy_infeasible"
