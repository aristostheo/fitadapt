"""Smoke tests for the deterministic portfolio demonstration."""

import importlib.util
import json
from pathlib import Path

from fitadapt.api.schemas import (
    BaselineRequest,
    CalorieRecommendationRequest,
    ProfileRequest,
    TrendsRequest,
)


def _demo_module() -> object:
    path = Path(__file__).parents[2] / "examples" / "demo.py"
    specification = importlib.util.spec_from_file_location("fitadapt_demo", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_demo_is_deterministic(capsys: object) -> None:
    demo = _demo_module()
    assert demo.build_demo_inputs() == demo.build_demo_inputs()  # type: ignore[attr-defined]
    demo.main()  # type: ignore[attr-defined]
    first_output = capsys.readouterr().out  # type: ignore[attr-defined]
    demo.main()  # type: ignore[attr-defined]
    second_output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert first_output == second_output
    assert "FitAdapt demonstration" in first_output


def test_example_payloads_validate_through_api_schemas() -> None:
    examples = Path(__file__).parents[2] / "examples"
    ProfileRequest.model_validate_json((examples / "profile.json").read_text())
    BaselineRequest.model_validate_json((examples / "baseline_request.json").read_text())
    TrendsRequest.model_validate(
        {"observations": json.loads((examples / "observations.json").read_text())}
    )
    CalorieRecommendationRequest.model_validate_json(
        (examples / "recommendation_request.json").read_text()
    )
