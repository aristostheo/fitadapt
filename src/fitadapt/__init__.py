"""FitAdapt's framework-independent fitness-intelligence core."""

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
from fitadapt.domain.observation import DailyObservation, ObservationValidationError
from fitadapt.domain.profile import (
    ActivityLevel,
    Goal,
    ProfileValidationError,
    SexForMifflinEquation,
    UserProfile,
)
from fitadapt.synthetic.history import (
    SyntheticConfigurationError,
    SyntheticHistory,
    SyntheticHistoryConfig,
    generate_synthetic_history,
)

__all__ = [
    "ACTIVITY_MULTIPLIERS",
    "ACTIVITY_POLICY_VERSION",
    "REE_FORMULA_VERSION",
    "ActivityLevel",
    "BaselineEnergyEstimate",
    "CalorieTargetEstimate",
    "DailyObservation",
    "ENERGY_EQUIVALENT_POLICY_VERSION",
    "Goal",
    "MACRO_POLICY_VERSION",
    "MacroPolicyInfeasibleError",
    "ObservationValidationError",
    "ProfileValidationError",
    "SexForMifflinEquation",
    "SyntheticConfigurationError",
    "SyntheticHistory",
    "SyntheticHistoryConfig",
    "UserProfile",
    "calculate_baseline_energy",
    "calculate_calorie_target",
    "calculate_daily_calorie_adjustment",
    "calculate_mifflin_st_jeor_ree",
    "generate_synthetic_history",
]
