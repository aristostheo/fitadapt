"""Inspect and smoke-test the local production image without publishing it."""

import argparse
import json
import os
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CANONICAL = "/v1/profile-intelligence"
BRIDGE = "/v1/integrations/somata/profile-intelligence"
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
RESPONSE_KEYS = {
    "adaptive_tdee",
    "assumptions",
    "baseline",
    "current_recommendation",
    "dietary_assessment",
    "integration_status",
    "latest_plan",
    "lifecycle",
    "nutrition_feasibility",
    "plan_adaptation",
    "plan_outcome",
    "plan_progression",
    "policy_version",
    "proposed_macro_plan",
    "proposed_target_envelope",
    "recommendation",
    "recommendation_decision",
    "recommendation_history",
    "target_safety",
    "training_assessment",
    "trends",
}
PRIVATE_MARKER = "synthetic-private-payload-marker"


def docker(*args: str) -> str:
    """Keep command arguments, which may contain the temporary token, out of failures."""
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Docker command failed with status {result.returncode}.")
    return result.stdout + result.stderr if args[0] == "logs" else result.stdout


def inspect_image(image: str) -> None:
    details = json.loads(docker("image", "inspect", image))[0]
    config = details["Config"]
    assert config["User"] == "65532:65532"
    assert "8080/tcp" in config["ExposedPorts"]
    assert "FITADAPT_SOMATA_ONLY=1" in config["Env"]
    assert not any(
        marker in item.split("=", 1)[0]
        for item in config["Env"]
        for marker in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "_KEY")
    )
    command = " ".join(config["Cmd"])
    assert "uvicorn fitadapt.api.app:app" in command
    assert "--host 0.0.0.0" in command
    assert "--port ${PORT:-8080}" in command
    assert "--no-access-log" in command

    check_filesystem = """
from importlib.util import find_spec
from pathlib import Path
app = Path('/app')
assert {entry.name for entry in app.iterdir()} == {'.venv'}
assert find_spec('fitadapt') is not None
assert find_spec('pytest') is None
assert find_spec('ruff') is None
package = Path(find_spec('fitadapt').origin).parent
assert (package / 'api' / 'app.py').is_file()
assert not any(path.name.startswith('.env') for path in app.rglob('*'))
assert not any(part in {'web', 'data', 'docs', 'examples', 'tests'}
               for path in package.rglob('*') for part in path.relative_to(package).parts)
"""
    docker("run", "--rm", "--entrypoint", "/app/.venv/bin/python", image, "-c", check_filesystem)
    print("image config and filesystem: passed")


def request(base: str, path: str, payload: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(
        base + path, data=body, headers=headers, method="POST" if body is not None else "GET"
    )
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def smoke_http(base: str, token: str) -> None:
    status, body = request(base, "/health")
    assert status == 200
    health = json.loads(body)
    assert set(health) == {"status", "service", "version", "recommendation_policy_version"}
    assert health["status"] == "ok" and health["service"] == "fitadapt"
    assert token not in body and PRIVATE_MARKER not in body
    print("health: passed")

    for path in (CANONICAL, BRIDGE):
        assert request(base, path, PAYLOAD)[0] == 401
        assert request(base, path, PAYLOAD, "incorrect-test-token")[0] == 401
    print("missing and incorrect credentials: rejected")

    canonical_status, canonical_body = request(base, CANONICAL, PAYLOAD, token)
    bridge_status, bridge_body = request(base, BRIDGE, PAYLOAD, token)
    assert canonical_status == bridge_status == 200
    canonical = json.loads(canonical_body)
    assert canonical == json.loads(bridge_body)
    assert set(canonical) == RESPONSE_KEYS
    assert isinstance(canonical["policy_version"], str) and canonical["policy_version"]
    assert canonical["baseline"]["target_calories_kcal_per_day"] > 0
    assert canonical["lifecycle"]["stage"] in {
        "baseline",
        "calibrating",
        "early_personalized",
        "personalized",
    }
    assert canonical["recommendation"]["status"] in {
        "insufficient_data",
        "hold",
        "increase_calories",
        "decrease_calories",
    }
    assert token not in canonical_body and PRIVATE_MARKER not in canonical_body
    print("authenticated intelligence response and contract: passed")

    oversized = {**PAYLOAD, "synthetic_filler": PRIVATE_MARKER + ("x" * 131072)}
    for path in (CANONICAL, BRIDGE):
        status, body = request(base, path, oversized, token)
        assert status == 413
        assert token not in body and PRIVATE_MARKER not in body
    print("oversized requests: rejected")

    for path in ("/", "/demo", "/docs", "/redoc", "/openapi.json"):
        assert request(base, path)[0] == 404
    assert request(base, "/v1/baseline", PAYLOAD)[0] == 404
    print("demo, docs, and other API routes: unavailable")


def smoke_container(image: str) -> None:
    inspect_image(image)
    token = secrets.token_urlsafe(48)
    name = f"fitadapt-smoke-{os.getpid()}"
    started = False
    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--publish",
            "127.0.0.1::8080",
            "--env",
            f"FITADAPT_BRIDGE_TOKEN={token}",
            image,
        )
        started = True
        address = docker("port", name, "8080/tcp").strip()
        port = address.rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                if request(base, "/health")[0] == 200:
                    break
            except (URLError, TimeoutError):
                time.sleep(0.5)
        else:
            raise AssertionError("Container health endpoint did not become ready.")
        smoke_http(base, token)
        logs = docker("logs", name)
        assert not any(
            marker in logs
            for marker in (token, PRIVATE_MARKER, "Authorization", "Bearer ", '"age_years"')
        )
        print("container logs: no credential or personal payload")
    finally:
        if started:
            subprocess.run(["docker", "stop", name], capture_output=True, check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--image")
    target.add_argument("--url")
    args = parser.parse_args()
    if args.image:
        smoke_container(args.image)
    else:
        token = os.environ.get("FITADAPT_BRIDGE_TOKEN")
        if not token:
            raise SystemExit("A temporary local bridge credential is required.")
        smoke_http(args.url.rstrip("/"), token)


if __name__ == "__main__":
    main()
