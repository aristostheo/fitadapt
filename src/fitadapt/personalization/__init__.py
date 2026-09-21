"""Explicit nutrition-preference and macro-planning contracts."""

from fitadapt.personalization.macros import (
    MACRO_PLAN_POLICY_VERSION,
    MacroCalorieSource,
    MacroPlanInfeasibleError,
    MacroStrategy,
    NutritionPreferences,
    NutritionPreferencesError,
    PersonalizedMacroPlan,
    calculate_personalized_macro_plan,
)

__all__ = [
    "MACRO_PLAN_POLICY_VERSION",
    "MacroCalorieSource",
    "MacroPlanInfeasibleError",
    "MacroStrategy",
    "NutritionPreferences",
    "NutritionPreferencesError",
    "PersonalizedMacroPlan",
    "calculate_personalized_macro_plan",
]
