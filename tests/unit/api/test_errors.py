"""Stable error-handler contracts for the HTTP adapter."""

from fastapi.testclient import TestClient

from fitadapt.api.app import create_app


def test_unexpected_error_is_safe_and_does_not_leak_internal_details() -> None:
    app = create_app()

    @app.get("/test-unexpected")
    def unexpected() -> None:
        raise RuntimeError("private implementation detail")

    response = TestClient(app, raise_server_exceptions=False).get("/test-unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_server_error", "message": "Internal server error."}
    }
