"""CORS configuration stays explicit and local by default."""

import pytest
from fastapi.testclient import TestClient

from fitadapt.api.app import DEFAULT_CORS_ORIGINS, app, cors_origins


def test_local_vite_origins_are_the_default() -> None:
    assert cors_origins("") == DEFAULT_CORS_ORIGINS
    client = TestClient(app)
    for origin in DEFAULT_CORS_ORIGINS:
        response = client.options(
            "/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        assert response.headers["access-control-allow-origin"] == origin
    unrelated = client.options(
        "/health",
        headers={"Origin": "https://unrelated.test", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in unrelated.headers
    assert "access-control-allow-credentials" not in unrelated.headers


def test_configured_origins_are_trimmed_deduplicated_and_exclude_unrelated_origin() -> None:
    assert cors_origins("https://example.test, https://other.test,https://example.test") == (
        "https://example.test",
        "https://other.test",
    )
    assert "https://unrelated.test" not in cors_origins("https://example.test")


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        cors_origins("*")
