"""Pure, versioned calorie-target and macronutrient-allocation calculations."""

from dataclasses import dataclass

from fitadapt.baseline.energy import BaselineEnergyEstimate, calculate_baseline_energy
from fitadapt.domain.profile import Goal, UserProfile

ENERGY_EQUIVALENT_POLICY_VERSION = "energy_equivalent_7700_v1"
MACRO_POLICY_VERSION = "baseline_macros_v1"

ENERGY_EQUIVALENT_KCAL_PER_KG = 7700.0
DAYS_PER_WEEK = 7.0
PROTEIN_GRAMS_PER_KG_BODY_WEIGHT = 1.6
FAT_GRAMS_PER_KG_BODY_WEIGHT = 0.6
PROTEIN_KCAL_PER_GRAM = 4.0
CARBOHYDRATE_KCAL_PER_GRAM = 4.0
FAT_KCAL_PER_GRAM = 9.0
FLOATING_POINT_CALORIE_TOLERANCE_KCAL = 1e-9

TARGET_POLICY_ASSUMPTIONS = (
    "The 7,700 kcal/kg energy equivalent is a simplified planning approximation.",
    "Protein is allocated from total body weight at 1.6 g/kg/day.",
    "Fat is allocated as a 0.6 g/kg/day floor.",
    "All remaining target energy is allocated to carbohydrates.",
)


class MacroPolicyInfeasibleError(ValueError):
    """Raised when a target cannot fund the required protein and fat allocations."""


@dataclass(frozen=True, slots=True)
class CalorieTargetEstimate:
    """Transparent, unrounded output of the V0.1 calorie-target and macro policy."""

    baseline_energy: BaselineEnergyEstimate
    goal: Goal
    requested_weekly_change_kg: float
    daily_calorie_adjustment_kcal: float
    target_calories_kcal_per_day: float
    protein_g_per_day: float
    fat_g_per_day: float
    carbohydrate_g_per_day: float
    energy_equivalent_policy_version: str
    macro_policy_version: str
    assumptions: tuple[str, ...]


def calculate_daily_calorie_adjustment(profile: UserProfile) -> float:
    """Convert the signed requested weekly weight change into a daily kcal adjustment."""
    return profile.requested_weekly_change_kg * ENERGY_EQUIVALENT_KCAL_PER_KG / DAYS_PER_WEEK


def calculate_calorie_target(profile: UserProfile) -> CalorieTargetEstimate:
    """Calculate a goal-based calorie target and its policy-constrained macro allocation."""
    baseline_energy = calculate_baseline_energy(profile)
    daily_calorie_adjustment_kcal = calculate_daily_calorie_adjustment(profile)
    target_calories_kcal_per_day = (
        baseline_energy.estimated_tdee_kcal_per_day + daily_calorie_adjustment_kcal
    )
    protein_g_per_day = profile.weight_kg * PROTEIN_GRAMS_PER_KG_BODY_WEIGHT
    fat_g_per_day = profile.weight_kg * FAT_GRAMS_PER_KG_BODY_WEIGHT
    remaining_calories = (
        target_calories_kcal_per_day
        - protein_g_per_day * PROTEIN_KCAL_PER_GRAM
        - fat_g_per_day * FAT_KCAL_PER_GRAM
    )

    carbohydrate_g_per_day = _calculate_carbohydrate_allocation(remaining_calories)
    return CalorieTargetEstimate(
        baseline_energy=baseline_energy,
        goal=profile.goal,
        requested_weekly_change_kg=profile.requested_weekly_change_kg,
        daily_calorie_adjustment_kcal=daily_calorie_adjustment_kcal,
        target_calories_kcal_per_day=target_calories_kcal_per_day,
        protein_g_per_day=protein_g_per_day,
        fat_g_per_day=fat_g_per_day,
        carbohydrate_g_per_day=carbohydrate_g_per_day,
        energy_equivalent_policy_version=ENERGY_EQUIVALENT_POLICY_VERSION,
        macro_policy_version=MACRO_POLICY_VERSION,
        assumptions=TARGET_POLICY_ASSUMPTIONS,
    )


def _calculate_carbohydrate_allocation(remaining_calories: float) -> float:
    """Allocate remaining calories to carbohydrates or reject a materially infeasible target."""
    if remaining_calories < -FLOATING_POINT_CALORIE_TOLERANCE_KCAL:
        raise MacroPolicyInfeasibleError(
            "Target calories cannot fund the current protein and fat policy; "
            f"remaining calories are {remaining_calories:g}."
        )
    if remaining_calories < 0:
        remaining_calories = 0.0
    return remaining_calories / CARBOHYDRATE_KCAL_PER_GRAM
