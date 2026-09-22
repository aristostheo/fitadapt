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
from fitadapt.personalization.planning import (
    PERSONALIZED_PLANNING_POLICY_VERSION,
    PersonalizedPlanningError,
    PersonalizedPlanProgression,
    PersonalizedPlanSnapshot,
    PlanCalorieBasis,
    build_personalized_plan_progression,
    build_personalized_plan_snapshot,
)

__all__ = [
    "MACRO_PLAN_POLICY_VERSION",
    "PERSONALIZATION_LIFECYCLE_POLICY_VERSION",
    "PERSONALIZED_PLANNING_POLICY_VERSION",
    "MacroCalorieSource",
    "MacroPlanInfeasibleError",
    "MacroStrategy",
    "NutritionPreferences",
    "NutritionPreferencesError",
    "PersonalizedMacroPlan",
    "PersonalizedPlanProgression",
    "PersonalizedPlanSnapshot",
    "PersonalizedPlanningError",
    "PersonalizationLifecycleConfig",
    "PersonalizationLifecycleError",
    "PersonalizationLifecycleResult",
    "PersonalizationRequirement",
    "PersonalizationStage",
    "PlanCalorieBasis",
    "assess_personalization_lifecycle",
    "build_personalized_plan_progression",
    "build_personalized_plan_snapshot",
    "calculate_personalized_macro_plan",
]
