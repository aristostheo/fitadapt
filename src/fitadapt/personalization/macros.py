"""Pure, explicit V1 macro allocation policies separate from baseline macros."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from fitadapt.baseline.targets import (
    CARBOHYDRATE_KCAL_PER_GRAM,
    FAT_KCAL_PER_GRAM,
    FLOATING_POINT_CALORIE_TOLERANCE_KCAL,
    PROTEIN_KCAL_PER_GRAM,
)
from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.profile import UserProfile

MACRO_PLAN_POLICY_VERSION = "preference_macros_v1"
CUSTOM_PROTEIN_MINIMUM_G_PER_KG = 1.2
CUSTOM_PROTEIN_MAXIMUM_G_PER_KG = 2.4
CUSTOM_FAT_MINIMUM_PERCENTAGE = 0.20
CUSTOM_FAT_MAXIMUM_PERCENTAGE = 0.40


class NutritionPreferencesError(ValueError):
    """Raised when explicit nutrition preferences violate the V1 contract."""


class MacroPlanInfeasibleError(ValueError):
    """Raised when valid preferences cannot fit within the supplied calorie target."""


class MacroStrategy(StrEnum):
    """Explicit macro-allocation strategies; none is universally superior."""

    BALANCED = "balanced"
    HIGHER_CARB = "higher_carb"
    HIGHER_FAT = "higher_fat"
    HIGHER_PROTEIN = "higher_protein"
    CUSTOM = "custom"


class MacroCalorieSource(StrEnum):
    """The caller-declared origin of calories supplied to macro allocation."""

    BASELINE = "baseline"
    PERSONALIZED = "personalized"


@dataclass(frozen=True, slots=True)
class NutritionPreferences:
    """User-selected macro strategy, intentionally separate from ``UserProfile``."""

    macro_strategy: MacroStrategy
    custom_protein_g_per_kg: float | None = None
    custom_fat_percentage: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.macro_strategy, MacroStrategy):
            raise NutritionPreferencesError(
                "macro_strategy must be a MacroStrategy enum value; "
                f"received {self.macro_strategy!r}."
            )
        has_custom_values = (
            self.custom_protein_g_per_kg is not None or self.custom_fat_percentage is not None
        )
        if self.macro_strategy is not MacroStrategy.CUSTOM:
            if has_custom_values:
                raise NutritionPreferencesError(
                    "custom protein and fat values are allowed only with macro_strategy 'custom'."
                )
            return
        if self.custom_protein_g_per_kg is None or self.custom_fat_percentage is None:
            raise NutritionPreferencesError(
                "macro_strategy 'custom' requires custom_protein_g_per_kg and "
                "custom_fat_percentage."
            )
        protein = validate_finite_number(
            self.custom_protein_g_per_kg,
            field_name="custom_protein_g_per_kg",
            error_type=NutritionPreferencesError,
        )
        fat = validate_finite_number(
            self.custom_fat_percentage,
            field_name="custom_fat_percentage",
            error_type=NutritionPreferencesError,
        )
        if not CUSTOM_PROTEIN_MINIMUM_G_PER_KG <= protein <= CUSTOM_PROTEIN_MAXIMUM_G_PER_KG:
            raise NutritionPreferencesError(
                "custom_protein_g_per_kg must be between 1.2 and 2.4 g/kg/day inclusive."
            )
        if not CUSTOM_FAT_MINIMUM_PERCENTAGE <= fat <= CUSTOM_FAT_MAXIMUM_PERCENTAGE:
            raise NutritionPreferencesError(
                "custom_fat_percentage must be between 0.20 and 0.40 inclusive."
            )
        object.__setattr__(self, "custom_protein_g_per_kg", protein)
        object.__setattr__(self, "custom_fat_percentage", fat)


@dataclass(frozen=True, slots=True)
class PersonalizedMacroPlan:
    """Transparent, unrounded allocation of caller-supplied daily calories."""

    calorie_target_kcal_per_day: float
    calorie_source: MacroCalorieSource
    strategy: MacroStrategy
    body_weight_kg: float
    protein_g_per_kg: float
    fat_percentage: float
    protein_g_per_day: float
    fat_g_per_day: float
    carbohydrate_g_per_day: float
    protein_kcal_per_day: float
    fat_kcal_per_day: float
    carbohydrate_kcal_per_day: float
    macro_policy_version: str
    assumptions: tuple[str, ...]


_STRATEGY_ALLOCATION = MappingProxyType(
    {
        MacroStrategy.BALANCED: (1.8, 0.25),
        MacroStrategy.HIGHER_CARB: (1.6, 0.20),
        MacroStrategy.HIGHER_FAT: (1.6, 0.35),
        MacroStrategy.HIGHER_PROTEIN: (2.0, 0.25),
    }
)


def calculate_personalized_macro_plan(
    profile: UserProfile,
    calorie_target_kcal_per_day: float,
    calorie_source: MacroCalorieSource,
    preferences: NutritionPreferences,
) -> PersonalizedMacroPlan:
    """Allocate supplied calories from explicit V1 preferences without hidden coupling."""
    if not isinstance(profile, UserProfile):
        raise NutritionPreferencesError("profile must be a UserProfile.")
    if not isinstance(calorie_source, MacroCalorieSource):
        raise NutritionPreferencesError("calorie_source must be a MacroCalorieSource enum value.")
    if not isinstance(preferences, NutritionPreferences):
        raise NutritionPreferencesError("preferences must be NutritionPreferences.")
    calories = validate_finite_number(
        calorie_target_kcal_per_day,
        field_name="calorie_target_kcal_per_day",
        error_type=NutritionPreferencesError,
    )
    if calories <= 0:
        raise NutritionPreferencesError("calorie_target_kcal_per_day must be greater than 0.")
    protein_per_kg, fat_percentage = _resolve_strategy(preferences)
    protein_g = profile.weight_kg * protein_per_kg
    protein_kcal = protein_g * PROTEIN_KCAL_PER_GRAM
    fat_kcal = calories * fat_percentage
    remaining_kcal = calories - protein_kcal - fat_kcal
    if remaining_kcal < -FLOATING_POINT_CALORIE_TOLERANCE_KCAL:
        raise MacroPlanInfeasibleError(
            "The supplied calorie target cannot fund the selected protein and fat allocation."
        )
    carbohydrate_kcal = max(remaining_kcal, 0.0)
    fat_g = fat_kcal / FAT_KCAL_PER_GRAM
    carbohydrate_g = carbohydrate_kcal / CARBOHYDRATE_KCAL_PER_GRAM
    return PersonalizedMacroPlan(
        calorie_target_kcal_per_day=calories,
        calorie_source=calorie_source,
        strategy=preferences.macro_strategy,
        body_weight_kg=profile.weight_kg,
        protein_g_per_kg=protein_per_kg,
        fat_percentage=fat_percentage,
        protein_g_per_day=protein_g,
        fat_g_per_day=fat_g,
        carbohydrate_g_per_day=carbohydrate_g,
        protein_kcal_per_day=protein_kcal,
        fat_kcal_per_day=fat_kcal,
        carbohydrate_kcal_per_day=carbohydrate_kcal,
        macro_policy_version=MACRO_PLAN_POLICY_VERSION,
        assumptions=(
            "This plan uses an explicit V1 macro strategy; "
            "FitAdapt does not learn food preferences.",
            "Protein is allocated from total body weight and fat from supplied target calories.",
            "Carbohydrates receive remaining calories after protein and fat allocations.",
            "Custom limits are general-adult product-policy boundaries, not medical requirements.",
        ),
    )


def _resolve_strategy(preferences: NutritionPreferences) -> tuple[float, float]:
    if preferences.macro_strategy is MacroStrategy.CUSTOM:
        assert preferences.custom_protein_g_per_kg is not None
        assert preferences.custom_fat_percentage is not None
        return preferences.custom_protein_g_per_kg, preferences.custom_fat_percentage
    return _STRATEGY_ALLOCATION[preferences.macro_strategy]
