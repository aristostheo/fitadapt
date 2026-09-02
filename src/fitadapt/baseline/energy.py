"""Pure, versioned Mifflin-St Jeor REE and static baseline TDEE calculations."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fitadapt.domain.profile import ActivityLevel, SexForMifflinEquation, UserProfile

REE_FORMULA_VERSION = "mifflin_st_jeor_v1"
ACTIVITY_POLICY_VERSION = "activity_multipliers_v1"

ACTIVITY_MULTIPLIERS: Mapping[ActivityLevel, float] = MappingProxyType(
    {
        ActivityLevel.SEDENTARY: 1.200,
        ActivityLevel.LIGHTLY_ACTIVE: 1.375,
        ActivityLevel.MODERATELY_ACTIVE: 1.550,
        ActivityLevel.VERY_ACTIVE: 1.725,
        ActivityLevel.EXTRA_ACTIVE: 1.900,
    }
)


@dataclass(frozen=True, slots=True)
class BaselineEnergyEstimate:
    """Transparent, unrounded output of the V0.1 static energy baseline."""

    estimated_ree_kcal_per_day: float
    activity_level: ActivityLevel
    activity_multiplier: float
    estimated_tdee_kcal_per_day: float
    ree_formula_version: str
    activity_policy_version: str


def calculate_mifflin_st_jeor_ree(profile: UserProfile) -> float:
    """Estimate REE in kcal/day with the versioned Mifflin-St Jeor equation."""
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age_years

    if profile.sex_for_mifflin_equation is SexForMifflinEquation.MALE:
        return base + 5
    if profile.sex_for_mifflin_equation is SexForMifflinEquation.FEMALE:
        return base - 161
    raise ValueError(f"Unsupported sex_for_mifflin_equation: {profile.sex_for_mifflin_equation!r}.")


def calculate_baseline_energy(profile: UserProfile) -> BaselineEnergyEstimate:
    """Calculate the static, formula-based REE and activity-adjusted TDEE estimate."""
    estimated_ree_kcal_per_day = calculate_mifflin_st_jeor_ree(profile)
    activity_multiplier = ACTIVITY_MULTIPLIERS[profile.activity_level]

    return BaselineEnergyEstimate(
        estimated_ree_kcal_per_day=estimated_ree_kcal_per_day,
        activity_level=profile.activity_level,
        activity_multiplier=activity_multiplier,
        estimated_tdee_kcal_per_day=estimated_ree_kcal_per_day * activity_multiplier,
        ree_formula_version=REE_FORMULA_VERSION,
        activity_policy_version=ACTIVITY_POLICY_VERSION,
    )
