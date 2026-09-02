"""Deterministic baseline energy calculations."""

from fitadapt.baseline.energy import (
    ACTIVITY_MULTIPLIERS,
    ACTIVITY_POLICY_VERSION,
    REE_FORMULA_VERSION,
    BaselineEnergyEstimate,
    calculate_baseline_energy,
    calculate_mifflin_st_jeor_ree,
)

__all__ = [
    "ACTIVITY_MULTIPLIERS",
    "ACTIVITY_POLICY_VERSION",
    "REE_FORMULA_VERSION",
    "BaselineEnergyEstimate",
    "calculate_baseline_energy",
    "calculate_mifflin_st_jeor_ree",
]
