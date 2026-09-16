"""Application metadata and documentation endpoint tests."""

from importlib.metadata import version

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def test_application_and_health_metadata_are_stable() -> None:
    first, second = create_app(), create_app()

    assert isinstance(first, FastAPI)
    assert first is not second
    response = TestClient(first).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "fitadapt"
    assert first.version == version("fitadapt")
    assert response.json()["version"] == version("fitadapt")


def test_openapi_and_swagger_expose_versioned_routes() -> None:
    client = TestClient(create_app())

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "FitAdapt API"
    assert {
        "/v1/baseline",
        "/v1/trends",
        "/v1/adaptive-tdee",
        "/v1/recommendations/calories",
    } <= set(openapi.json()["paths"])
    assert client.get("/docs").status_code == 200


def test_openapi_uses_enum_response_schemas_and_documents_error_responses() -> None:
    openapi = TestClient(create_app()).get("/openapi.json").json()
    schemas = openapi["components"]["schemas"]

    assert schemas["DailyTdeeEstimateResponse"]["properties"]["eligibility"] == {
        "$ref": "#/components/schemas/TdeeEligibility"
    }
    assert schemas["CalorieRecommendationResponse"]["properties"]["status"] == {
        "$ref": "#/components/schemas/RecommendationStatus"
    }
    assert schemas["CalorieRecommendationResponse"]["properties"]["reasons"]["items"] == {
        "$ref": "#/components/schemas/RecommendationReason"
    }
    for path in ("/v1/baseline", "/v1/trends", "/v1/adaptive-tdee", "/v1/recommendations/calories"):
        responses = openapi["paths"][path]["post"]["responses"]
        assert {"400", "422", "500"} <= set(responses)
        assert responses["400"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
