import math

import pytest

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, AdaptiveTdeeError


@pytest.mark.parametrize(
    "kwargs",
    [
        {"estimator_window_days": 0},
        {"minimum_weight_contributors": 0},
        {"minimum_intake_contributors": True},
        {"minimum_calendar_span_days": 29},
        {"robust_slope_method": ""},
        {"stability_residual_mad_kg": math.nan},
        {"minimum_old_regime_days": 0},
        {"minimum_new_regime_days": 0},
        {"intake_regime_lookback_days": 13},
        {"intake_regime_stabilization_days": 0},
        {"subwindow_slope_disagreement_kcal_per_day": math.inf},
        {"minimum_subwindow_weight_contributors": 0},
        {"maximum_intake_regime_mad_kcal_per_day": math.nan},
        {"block_sensitivity_threshold_kcal_per_day": 0},
        {"multi_horizon_disagreement_threshold_kcal_per_day": math.inf},
        {"minimum_sensitivity_estimates": 0},
    ],
)
def test_v2_config_rejects_invalid_robust_estimator_settings(kwargs: dict[str, object]) -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(**kwargs)  # type: ignore[arg-type]


def test_v2_config_rejects_span_larger_than_window() -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(estimator_window_days=14, minimum_calendar_span_days=15)


def test_v2_config_rejects_falsey_method_and_nonpositive_stability() -> None:
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(robust_slope_method=None)  # type: ignore[arg-type]
    with pytest.raises(AdaptiveTdeeError):
        AdaptiveTdeeConfig(stability_residual_mad_kg=0)
