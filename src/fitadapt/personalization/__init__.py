"""Explicit nutrition-preference and macro-planning contracts."""

from fitadapt.personalization.lifecycle import (
    PERSONALIZATION_LIFECYCLE_POLICY_VERSION,
    PersonalizationLifecycleConfig,
    PersonalizationLifecycleError,
    PersonalizationLifecycleResult,
    PersonalizationRequirement,
    PersonalizationStage,
    assess_personalization_lifecycle,
)
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
    "PERSONALIZATION_LIFECYCLE_POLICY_VERSION",
    "MacroCalorieSource",
    "MacroPlanInfeasibleError",
    "MacroStrategy",
    "NutritionPreferences",
    "NutritionPreferencesError",
    "PersonalizedMacroPlan",
    "PersonalizationLifecycleConfig",
    "PersonalizationLifecycleError",
    "PersonalizationLifecycleResult",
    "PersonalizationRequirement",
    "PersonalizationStage",
    "assess_personalization_lifecycle",
    "calculate_personalized_macro_plan",
]
