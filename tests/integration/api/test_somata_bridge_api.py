"""The Somata transport authenticates without changing engine results."""

from fastapi.testclient import TestClient

from fitadapt.api.app import create_app

PAYLOAD = {
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
PATH = "/v1/integrations/somata/profile-intelligence"


def test_bridge_fails_closed_without_server_credential(monkeypatch) -> None:
    monkeypatch.delenv("FITADAPT_BRIDGE_TOKEN", raising=False)
    response = TestClient(create_app()).post(PATH, json=PAYLOAD)
    assert response.status_code == 503


def test_bridge_rejects_missing_and_wrong_credentials(monkeypatch) -> None:
    monkeypatch.setenv("FITADAPT_BRIDGE_TOKEN", "test-only-token")
    client = TestClient(create_app())
    assert client.post(PATH, json=PAYLOAD).status_code == 401
    assert client.post(PATH, json={}).status_code == 401
    invalid = client.post(PATH, json=PAYLOAD, headers={"Authorization": "Bearer wrong"})
    assert invalid.status_code == 401


def test_bridge_matches_existing_profile_intelligence_contract(monkeypatch) -> None:
    monkeypatch.setenv("FITADAPT_BRIDGE_TOKEN", "test-only-token")
    client = TestClient(create_app())
    protected = client.post(PATH, json=PAYLOAD, headers={"Authorization": "Bearer test-only-token"})
    existing = client.post("/v1/profile-intelligence", json=PAYLOAD)
    assert protected.status_code == existing.status_code == 200
    assert protected.json() == existing.json()


def test_production_mode_protects_both_intelligence_paths_and_health(monkeypatch) -> None:
    monkeypatch.setenv("FITADAPT_BRIDGE_TOKEN", "test-only-token")
    monkeypatch.setenv("FITADAPT_SOMATA_ONLY", "1")
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    assert "test-only-token" not in health.text
    assert "profile" not in health.json()
    assert client.post("/v1/profile-intelligence", json=PAYLOAD).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.post(PATH, json=PAYLOAD).status_code == 401
    authenticated = client.post(
        PATH, json=PAYLOAD, headers={"Authorization": "Bearer test-only-token"}
    )
    assert authenticated.status_code == 200
    canonical = client.post(
        "/v1/profile-intelligence",
        json=PAYLOAD,
        headers={"Authorization": "Bearer test-only-token"},
    )
    assert canonical.status_code == 200
    assert canonical.json() == authenticated.json()


def test_bridge_rejects_oversized_request_without_echoing_body(monkeypatch) -> None:
    monkeypatch.setenv("FITADAPT_BRIDGE_TOKEN", "test-only-token")
    client = TestClient(create_app())
    private_marker = "private-user-data-" * 8192
    response = client.post(
        PATH,
        json={**PAYLOAD, "extra": private_marker},
        headers={"Authorization": "Bearer test-only-token"},
    )
    assert response.status_code == 413
    assert private_marker not in response.text
