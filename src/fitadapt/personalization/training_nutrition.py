"""Deterministic training-aware macro policy layered on the existing allocator."""

from dataclasses import dataclass, replace
from enum import StrEnum

from fitadapt.baseline.targets import FAT_KCAL_PER_GRAM, PROTEIN_KCAL_PER_GRAM
from fitadapt.domain._validation import validate_finite_number
from fitadapt.personalization.macros import PersonalizedMacroPlan
from fitadapt.personalization.training import (
    TrainingDemandAssessment,
    TrainingDemandLevel,
    TrainingPriority,
)

TRAINING_AWARE_MACRO_POLICY_VERSION = "training_aware_macros_v1"
TRAINING_AWARE_FAT_FLOOR_PERCENTAGE = 0.20


class TrainingAwareMacroError(ValueError):
    """Raised when a training-aware macro policy cannot be applied."""


class TrainingMacroPolicySource(StrEnum):
    DEFAULT = "default"
    TRAINING_AWARE = "training_aware"
    CONSTRAINED = "training_aware_constrained"


@dataclass(frozen=True, slots=True)
class TrainingAwareMacroConfig:
    """Explicit V1 training-aware protein and carbohydrate policy thresholds."""

    policy_version: str = TRAINING_AWARE_MACRO_POLICY_VERSION
    low_resistance_protein_g_per_kg: float = 1.8
    moderate_resistance_protein_g_per_kg: float = 2.0
    high_resistance_protein_g_per_kg: float = 2.2
    very_high_resistance_protein_g_per_kg: float = 2.4
    carbohydrate_fat_floor_percentage: float = TRAINING_AWARE_FAT_FLOOR_PERCENTAGE

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise TrainingAwareMacroError("policy_version must be a non-empty string.")
        values = tuple(
            validate_finite_number(
                getattr(self, name), field_name=name, error_type=TrainingAwareMacroError
            )
            for name in (
                "low_resistance_protein_g_per_kg",
                "moderate_resistance_protein_g_per_kg",
                "high_resistance_protein_g_per_kg",
                "very_high_resistance_protein_g_per_kg",
                "carbohydrate_fat_floor_percentage",
            )
        )
        if not values[0] <= values[1] <= values[2] <= values[3]:
            raise TrainingAwareMacroError("resistance protein thresholds must be ordered.")
        if not 0 < values[4] <= 0.40:
            raise TrainingAwareMacroError("carbohydrate fat floor must be within policy bounds.")
        for name, value in zip(
            (
                "low_resistance_protein_g_per_kg",
                "moderate_resistance_protein_g_per_kg",
                "high_resistance_protein_g_per_kg",
                "very_high_resistance_protein_g_per_kg",
                "carbohydrate_fat_floor_percentage",
            ),
            values,
            strict=True,
        ):
            object.__setattr__(self, name, value)


def apply_training_aware_macro_policy(
    plan: PersonalizedMacroPlan,
    assessment: TrainingDemandAssessment | None,
    config: TrainingAwareMacroConfig | None = None,
) -> PersonalizedMacroPlan:
    """Apply training-aware composition to an existing feasible calorie plan."""
    effective_config = config or TrainingAwareMacroConfig()
    if not isinstance(effective_config, TrainingAwareMacroConfig):
        raise TrainingAwareMacroError("config must be a TrainingAwareMacroConfig or None.")
    if assessment is None or not assessment.assessment_available:
        return plan
    if not isinstance(assessment, TrainingDemandAssessment):
        raise TrainingAwareMacroError("assessment must be a TrainingDemandAssessment or None.")
    protein_by_resistance = {
        TrainingDemandLevel.LOW: effective_config.low_resistance_protein_g_per_kg,
        TrainingDemandLevel.MODERATE: effective_config.moderate_resistance_protein_g_per_kg,
        TrainingDemandLevel.HIGH: effective_config.high_resistance_protein_g_per_kg,
        TrainingDemandLevel.VERY_HIGH: effective_config.very_high_resistance_protein_g_per_kg,
    }
    desired_protein_per_kg = plan.protein_g_per_kg
    if assessment.resistance_demand is not None:
        desired_protein_per_kg = max(
            desired_protein_per_kg,
            protein_by_resistance[assessment.resistance_demand],
        )
    desired_fat_percentage = plan.fat_percentage
    if assessment.carbohydrate_performance_priority in (
        TrainingPriority.HIGH,
        TrainingPriority.MODERATE,
    ):
        desired_fat_percentage = max(
            effective_config.carbohydrate_fat_floor_percentage,
            min(desired_fat_percentage, effective_config.carbohydrate_fat_floor_percentage),
        )
    desired_protein_g = plan.body_weight_kg * desired_protein_per_kg
    desired_fat_kcal = plan.calorie_target_kcal_per_day * desired_fat_percentage
    available_protein_kcal = plan.calorie_target_kcal_per_day - desired_fat_kcal
    feasible_protein_g = max(0.0, available_protein_kcal / PROTEIN_KCAL_PER_GRAM)
    effective_protein_g = min(desired_protein_g, feasible_protein_g)
    constrained = effective_protein_g < desired_protein_g
    effective_protein_per_kg = effective_protein_g / plan.body_weight_kg
    protein_kcal = effective_protein_g * PROTEIN_KCAL_PER_GRAM
    carbohydrate_kcal = plan.calorie_target_kcal_per_day - protein_kcal - desired_fat_kcal
    if carbohydrate_kcal < 0:
        raise TrainingAwareMacroError("Training-aware macro allocation is infeasible.")
    fat_g = desired_fat_kcal / FAT_KCAL_PER_GRAM
    carbohydrate_g = carbohydrate_kcal / 4.0
    source = (
        TrainingMacroPolicySource.CONSTRAINED
        if constrained
        else TrainingMacroPolicySource.TRAINING_AWARE
    )
    reasons = list(assessment.reason_codes)
    if desired_protein_per_kg > plan.protein_g_per_kg:
        reasons.append("training_resistance_increased_protein_preference")
    if desired_fat_percentage < plan.fat_percentage:
        reasons.append("training_performance_increased_carbohydrate_preference")
    if constrained:
        reasons.append("calorie_budget_limited_preferred_protein_target")
    reasons.append("training_aware_adjustment_applied")
    assumptions = plan.assumptions + (
        "Training-aware macro composition preserves the supplied calorie target.",
        "Training-aware protein and carbohydrate values are deterministic product-policy "
        "preferences, not medical requirements.",
        "The established fat floor is preserved before carbohydrate allocation.",
    )
    return replace(
        plan,
        protein_g_per_kg=float(effective_protein_per_kg),
        fat_percentage=float(desired_fat_percentage),
        protein_g_per_day=float(effective_protein_g),
        fat_g_per_day=float(fat_g),
        carbohydrate_g_per_day=float(carbohydrate_g),
        protein_kcal_per_day=float(protein_kcal),
        fat_kcal_per_day=float(desired_fat_kcal),
        carbohydrate_kcal_per_day=float(carbohydrate_kcal),
        training_adjustment_available=True,
        training_adjustment_applied=True,
        training_policy_version=effective_config.policy_version,
        protein_policy_source=source.value,
        carbohydrate_policy_source=(
            TrainingMacroPolicySource.TRAINING_AWARE.value
            if desired_fat_percentage < plan.fat_percentage
            else TrainingMacroPolicySource.DEFAULT.value
        ),
        baseline_protein_target_g=float(plan.protein_g_per_day),
        training_aware_protein_target_g=float(desired_protein_g),
        effective_protein_target_g=float(effective_protein_g),
        baseline_carbohydrate_target_g=float(plan.carbohydrate_g_per_day),
        effective_carbohydrate_target_g=float(carbohydrate_g),
        protein_priority=(
            None if assessment.protein_priority is None else assessment.protein_priority.value
        ),
        carbohydrate_performance_priority=(
            None
            if assessment.carbohydrate_performance_priority is None
            else assessment.carbohydrate_performance_priority.value
        ),
        training_reason_codes=tuple(dict.fromkeys(reasons)),
        assumptions=assumptions,
    )
