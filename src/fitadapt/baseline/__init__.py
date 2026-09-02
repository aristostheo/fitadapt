"""Deterministic baseline energy calculations."""

from fitadapt.baseline.energy import (
    ACTIVITY_MULTIPLIERS,
    ACTIVITY_POLICY_VERSION,
    REE_FORMULA_VERSION,
    BaselineEnergyEstimate,
    calculate_baseline_energy,
    calculate_mifflin_st_jeor_ree,
)
from fitadapt.baseline.targets import (
    ENERGY_EQUIVALENT_POLICY_VERSION,
    MACRO_POLICY_VERSION,
    CalorieTargetEstimate,
    MacroPolicyInfeasibleError,
    calculate_calorie_target,
    calculate_daily_calorie_adjustment,
)

__all__ = [
    "ACTIVITY_MULTIPLIERS",
    "ACTIVITY_POLICY_VERSION",
    "REE_FORMULA_VERSION",
    "BaselineEnergyEstimate",
    "CalorieTargetEstimate",
    "ENERGY_EQUIVALENT_POLICY_VERSION",
    "MACRO_POLICY_VERSION",
    "MacroPolicyInfeasibleError",
    "calculate_baseline_energy",
    "calculate_calorie_target",
    "calculate_daily_calorie_adjustment",
    "calculate_mifflin_st_jeor_ree",
]
