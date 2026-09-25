"""Versioned, policy-based nutrition target envelopes around exact macro plans."""

from dataclasses import dataclass
from enum import StrEnum

from fitadapt.baseline.targets import (
    CARBOHYDRATE_KCAL_PER_GRAM,
    FAT_KCAL_PER_GRAM,
    PROTEIN_KCAL_PER_GRAM,
)
from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.profile import UserProfile
from fitadapt.personalization.macros import (
    CUSTOM_FAT_MAXIMUM_PERCENTAGE,
    CUSTOM_FAT_MINIMUM_PERCENTAGE,
    CUSTOM_PROTEIN_MAXIMUM_G_PER_KG,
    CUSTOM_PROTEIN_MINIMUM_G_PER_KG,
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    PersonalizedMacroPlan,
    calculate_personalized_macro_plan,
)

NUTRITION_TARGET_RANGE_POLICY_VERSION = "nutrition_target_ranges_v1"


class NutritionTargetEnvelopeError(ValueError):
    """Raised when a deterministic policy envelope cannot be constructed."""


class NutritionRangeKind(StrEnum):
    ADHERENCE = "adherence"
    PREFERRED = "preferred"
    FLEXIBLE_REMAINDER = "flexible_remainder"


@dataclass(frozen=True, slots=True)
class NutritionTargetRange:
    """One selected numeric target with an explicit, non-clinical policy band."""

    lower_bound: float
    selected_value: float
    upper_bound: float
    unit: str
    interpretation: str
    range_kind: NutritionRangeKind

    def __post_init__(self) -> None:
        lower = validate_finite_number(
            self.lower_bound, field_name="lower_bound", error_type=NutritionTargetEnvelopeError
        )
        selected = validate_finite_number(
            self.selected_value,
            field_name="selected_value",
            error_type=NutritionTargetEnvelopeError,
        )
        upper = validate_finite_number(
            self.upper_bound, field_name="upper_bound", error_type=NutritionTargetEnvelopeError
        )
        if lower > selected or selected > upper:
            raise NutritionTargetEnvelopeError(
                "nutrition target ranges require lower_bound <= selected_value <= upper_bound."
            )
        if not isinstance(self.unit, str) or not self.unit:
            raise NutritionTargetEnvelopeError("unit must be a non-empty string.")
        if not isinstance(self.interpretation, str) or not self.interpretation:
            raise NutritionTargetEnvelopeError("interpretation must be a non-empty string.")
        if not isinstance(self.range_kind, NutritionRangeKind):
            raise NutritionTargetEnvelopeError(
                "range_kind must be a NutritionRangeKind enum value."
            )
        object.__setattr__(self, "lower_bound", lower)
        object.__setattr__(self, "selected_value", selected)
        object.__setattr__(self, "upper_bound", upper)


@dataclass(frozen=True, slots=True)
class NutritionTargetRangeConfig:
    """Conservative V1 product-policy widths, not medical requirements."""

    calorie_adherence_tolerance_kcal_per_day: float = 100.0
    protein_preferred_tolerance_g_per_kg: float = 0.2
    fat_preferred_tolerance_percentage: float = 0.05

    def __post_init__(self) -> None:
        for name in (
            "calorie_adherence_tolerance_kcal_per_day",
            "protein_preferred_tolerance_g_per_kg",
            "fat_preferred_tolerance_percentage",
        ):
            value = validate_finite_number(
                getattr(self, name), field_name=name, error_type=NutritionTargetEnvelopeError
            )
            if value < 0:
                raise NutritionTargetEnvelopeError(f"{name} must be greater than or equal to zero.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class NutritionTargetEnvelope:
    """Exact selected plan plus policy bands whose endpoints are not jointly combinable."""

    selected_calorie_target_kcal_per_day: float
    calorie_adherence_range: NutritionTargetRange
    protein_preferred_range: NutritionTargetRange
    fat_preferred_range: NutritionTargetRange
    carbohydrate_flexible_range: NutritionTargetRange
    macro_plan: PersonalizedMacroPlan
    macro_strategy: MacroStrategy
    calorie_source: MacroCalorieSource
    policy_floors: tuple[str, ...]
    range_policy_version: str
    macro_policy_version: str
    assumptions: tuple[str, ...]


def calculate_nutrition_target_envelope(
    profile: UserProfile,
    calorie_target_kcal_per_day: float,
    calorie_source: MacroCalorieSource,
    preferences: NutritionPreferences,
    config: NutritionTargetRangeConfig | None = None,
) -> NutritionTargetEnvelope:
    """Compose the existing exact macro plan with bounded V1 flexibility bands."""
    if not isinstance(config, (NutritionTargetRangeConfig, type(None))):
        raise NutritionTargetEnvelopeError("config must be a NutritionTargetRangeConfig or None.")
    effective = config or NutritionTargetRangeConfig()
    try:
        plan = calculate_personalized_macro_plan(
            profile, calorie_target_kcal_per_day, calorie_source, preferences
        )
    except ValueError as error:
        raise NutritionTargetEnvelopeError(str(error)) from error
    calories = plan.calorie_target_kcal_per_day
    calorie_range = NutritionTargetRange(
        max(0.0, calories - effective.calorie_adherence_tolerance_kcal_per_day),
        calories,
        calories + effective.calorie_adherence_tolerance_kcal_per_day,
        "kcal/day",
        "An adherence policy band around the selected intake target.",
        NutritionRangeKind.ADHERENCE,
    )
    protein_lower = (
        max(
            CUSTOM_PROTEIN_MINIMUM_G_PER_KG,
            plan.protein_g_per_kg - effective.protein_preferred_tolerance_g_per_kg,
        )
        * profile.weight_kg
    )
    protein_upper = (
        min(
            CUSTOM_PROTEIN_MAXIMUM_G_PER_KG,
            plan.protein_g_per_kg + effective.protein_preferred_tolerance_g_per_kg,
        )
        * profile.weight_kg
    )
    protein_range = NutritionTargetRange(
        protein_lower,
        plan.protein_g_per_day,
        protein_upper,
        "g/day",
        "A preferred protein policy band, bounded by supported strategy limits.",
        NutritionRangeKind.PREFERRED,
    )
    fat_lower = (
        max(
            CUSTOM_FAT_MINIMUM_PERCENTAGE,
            plan.fat_percentage - effective.fat_preferred_tolerance_percentage,
        )
        * calories
        / FAT_KCAL_PER_GRAM
    )
    fat_upper = (
        min(
            CUSTOM_FAT_MAXIMUM_PERCENTAGE,
            plan.fat_percentage + effective.fat_preferred_tolerance_percentage,
        )
        * calories
        / FAT_KCAL_PER_GRAM
    )
    fat_range = NutritionTargetRange(
        fat_lower,
        plan.fat_g_per_day,
        fat_upper,
        "g/day",
        "A preferred fat policy band, bounded by supported strategy limits.",
        NutritionRangeKind.PREFERRED,
    )
    carbohydrate_lower = max(
        0.0,
        (
            calorie_range.lower_bound
            - protein_range.upper_bound * PROTEIN_KCAL_PER_GRAM
            - fat_range.upper_bound * FAT_KCAL_PER_GRAM
        )
        / CARBOHYDRATE_KCAL_PER_GRAM,
    )
    carbohydrate_upper = max(
        0.0,
        (
            calorie_range.upper_bound
            - protein_range.lower_bound * PROTEIN_KCAL_PER_GRAM
            - fat_range.lower_bound * FAT_KCAL_PER_GRAM
        )
        / CARBOHYDRATE_KCAL_PER_GRAM,
    )
    carbohydrate_range = NutritionTargetRange(
        carbohydrate_lower,
        plan.carbohydrate_g_per_day,
        carbohydrate_upper,
        "g/day",
        "A flexible carbohydrate remainder after protein and fat allocations.",
        NutritionRangeKind.FLEXIBLE_REMAINDER,
    )
    return NutritionTargetEnvelope(
        calories,
        calorie_range,
        protein_range,
        fat_range,
        carbohydrate_range,
        plan,
        plan.strategy,
        calorie_source,
        (
            "Protein is bounded to supported 1.2–2.4 g/kg policy limits.",
            "Fat is bounded to supported 20–40% calorie policy limits.",
        ),
        NUTRITION_TARGET_RANGE_POLICY_VERSION,
        plan.macro_policy_version,
        (
            "The selected macro plan is the exact existing feasible point.",
            "Ranges are decision-support policy bands, not medical prescriptions.",
            "Independent range endpoints are not arbitrary jointly energy-reconciling "
            "combinations.",
            "Carbohydrates remain the feasible energy remainder after protein and fat.",
        ),
    )
