"""Practical nutrition-plan fit assessment from existing dietary and macro contracts."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from fitadapt.personalization.dietary import (
    FOOD_CATEGORY_ROLES,
    FoodCategory,
    FoodCategoryRole,
    FoodSelectionMode,
    NutritionPreferenceAssessment,
    NutritionPreferenceProfile,
)
from fitadapt.personalization.macros import PersonalizedMacroPlan

NUTRITION_FEASIBILITY_POLICY_VERSION = "nutrition_feasibility_v1"


class NutritionFeasibilityError(ValueError):
    """Raised when feasibility assessment inputs violate the domain contract."""


class FeasibilityLevel(StrEnum):
    EASY = "easy"
    MANAGEABLE = "manageable"
    CHALLENGING = "challenging"
    VERY_CHALLENGING = "very_challenging"


class RestrictionCompatibility(StrEnum):
    COMPATIBLE = "compatible"
    LIMITED = "limited"
    HIGHLY_LIMITED = "highly_limited"


class GuidanceCategory(StrEnum):
    PROTEIN = "protein"
    CARBOHYDRATE = "carbohydrate"
    FAT = "fat"
    DIETARY_FLEXIBILITY = "dietary_flexibility"
    RESTRICTION = "restriction"
    CONVENIENCE = "convenience"


class GuidancePriority(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class GuidanceAction(StrEnum):
    FAVOR_ACCEPTED_CATEGORIES = "favor_accepted_categories"
    PLAN_DELIBERATELY = "plan_deliberately"
    MAINTAIN_VARIETY = "maintain_variety"
    REVIEW_RESTRICTIONS = "review_restrictions"
    USE_CONVENIENT_OPTIONS = "use_convenient_options"


@dataclass(frozen=True, slots=True)
class NutritionFeasibilityConfig:
    """Explicit category-count and macro-density rules; no weighted score is used."""

    policy_version: str = NUTRITION_FEASIBILITY_POLICY_VERSION
    protein_very_challenging_categories: int = 1
    protein_challenging_categories: int = 2
    protein_easy_categories: int = 6
    carbohydrate_very_challenging_categories: int = 0
    carbohydrate_challenging_categories: int = 1
    carbohydrate_easy_categories: int = 4
    fat_very_challenging_categories: int = 0
    fat_challenging_categories: int = 1
    fat_easy_categories: int = 3
    high_protein_calorie_share: float = 0.32
    high_carbohydrate_calorie_share: float = 0.60
    fat_floor_proximity_percentage: float = 0.22
    restriction_highly_limited_categories: int = 5
    restriction_limited_categories: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise NutritionFeasibilityError("policy_version must be a non-empty string.")
        integer_fields = (
            "protein_very_challenging_categories",
            "protein_challenging_categories",
            "protein_easy_categories",
            "carbohydrate_very_challenging_categories",
            "carbohydrate_challenging_categories",
            "carbohydrate_easy_categories",
            "fat_very_challenging_categories",
            "fat_challenging_categories",
            "fat_easy_categories",
            "restriction_highly_limited_categories",
            "restriction_limited_categories",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise NutritionFeasibilityError(f"{name} must be a non-negative integer.")
        for very, challenging, easy, prefix in (
            (
                self.protein_very_challenging_categories,
                self.protein_challenging_categories,
                self.protein_easy_categories,
                "protein",
            ),
            (
                self.carbohydrate_very_challenging_categories,
                self.carbohydrate_challenging_categories,
                self.carbohydrate_easy_categories,
                "carbohydrate",
            ),
            (
                self.fat_very_challenging_categories,
                self.fat_challenging_categories,
                self.fat_easy_categories,
                "fat",
            ),
        ):
            if not very <= challenging < easy:
                raise NutritionFeasibilityError(f"{prefix} category thresholds must be ordered.")
        if self.restriction_highly_limited_categories < self.restriction_limited_categories:
            raise NutritionFeasibilityError("restriction thresholds must be ordered.")
        for name in (
            "high_protein_calorie_share",
            "high_carbohydrate_calorie_share",
            "fat_floor_proximity_percentage",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise NutritionFeasibilityError(f"{name} must be a finite number.")
            if not 0 <= float(value) <= 1:
                raise NutritionFeasibilityError(f"{name} must be between 0 and 1.")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class NutritionGuidanceItem:
    category: GuidanceCategory
    priority: GuidancePriority
    reason_code: str
    action: GuidanceAction
    message: str

    def __post_init__(self) -> None:
        for value, enum_type, name in (
            (self.category, GuidanceCategory, "category"),
            (self.priority, GuidancePriority, "priority"),
            (self.action, GuidanceAction, "action"),
        ):
            if not isinstance(value, enum_type):
                raise NutritionFeasibilityError(f"{name} must be a {enum_type.__name__} value.")
        if not isinstance(self.reason_code, str) or not self.reason_code:
            raise NutritionFeasibilityError("reason_code must be a non-empty string.")
        if not isinstance(self.message, str) or not self.message:
            raise NutritionFeasibilityError("message must be a non-empty string.")


@dataclass(frozen=True, slots=True)
class NutritionFeasibilityAssessment:
    assessment_available: bool
    overall_feasibility: FeasibilityLevel | None
    protein_feasibility: FeasibilityLevel | None
    carbohydrate_feasibility: FeasibilityLevel | None
    fat_feasibility: FeasibilityLevel | None
    restriction_compatibility: RestrictionCompatibility | None
    macro_policy_version: str
    training_adjustment_applied: bool
    protein_target_g_per_day: float
    carbohydrate_target_g_per_day: float
    fat_target_g_per_day: float
    calorie_target_kcal_per_day: float
    accepted_protein_categories: tuple[FoodCategory, ...]
    accepted_carbohydrate_categories: tuple[FoodCategory, ...]
    accepted_fat_categories: tuple[FoodCategory, ...]
    disliked_categories: tuple[FoodCategory, ...]
    limiting_categories: tuple[FoodCategory, ...]
    dietary_conflicts: tuple[str, ...]
    guidance: tuple[NutritionGuidanceItem, ...]
    reason_codes: tuple[str, ...]
    policy_version: str
    assumptions: tuple[str, ...]
    training_policy_version: str | None = None
    protein_policy_source: str = "default"
    carbohydrate_policy_source: str = "default"
    baseline_protein_target_g_per_day: float = 0.0
    training_aware_protein_target_g_per_day: float | None = None
    baseline_carbohydrate_target_g_per_day: float = 0.0
    protein_priority: str | None = None
    carbohydrate_performance_priority: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.assessment_available, bool):
            raise NutritionFeasibilityError("assessment_available must be a boolean.")
        if not isinstance(self.training_adjustment_applied, bool):
            raise NutritionFeasibilityError("training_adjustment_applied must be a boolean.")
        enum_fields = (
            (self.overall_feasibility, FeasibilityLevel, "overall_feasibility"),
            (self.protein_feasibility, FeasibilityLevel, "protein_feasibility"),
            (self.carbohydrate_feasibility, FeasibilityLevel, "carbohydrate_feasibility"),
            (self.fat_feasibility, FeasibilityLevel, "fat_feasibility"),
            (self.restriction_compatibility, RestrictionCompatibility, "restriction_compatibility"),
        )
        for value, enum_type, name in enum_fields:
            if value is not None and not isinstance(value, enum_type):
                raise NutritionFeasibilityError(f"{name} must be {enum_type.__name__} or None.")
        if self.assessment_available != (self.overall_feasibility is not None):
            raise NutritionFeasibilityError(
                "assessment availability must agree with overall feasibility presence."
            )
        if not isinstance(self.macro_policy_version, str) or not self.macro_policy_version:
            raise NutritionFeasibilityError("macro_policy_version must be a non-empty string.")
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise NutritionFeasibilityError("policy_version must be a non-empty string.")
        if self.training_policy_version is not None and not isinstance(
            self.training_policy_version, str
        ):
            raise NutritionFeasibilityError("training_policy_version must be a string or None.")
        for name in ("protein_policy_source", "carbohydrate_policy_source"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise NutritionFeasibilityError(f"{name} must be a non-empty string.")
        for name in (
            "baseline_protein_target_g_per_day",
            "baseline_carbohydrate_target_g_per_day",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise NutritionFeasibilityError(f"{name} must be a finite built-in number.")
            object.__setattr__(self, name, float(value))
        if self.training_aware_protein_target_g_per_day is not None:
            value = self.training_aware_protein_target_g_per_day
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise NutritionFeasibilityError(
                    "training_aware_protein_target_g_per_day must be finite or None."
                )
            object.__setattr__(self, "training_aware_protein_target_g_per_day", float(value))
        for name in ("protein_priority", "carbohydrate_performance_priority"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise NutritionFeasibilityError(f"{name} must be a string or None.")
        for name in (
            "protein_target_g_per_day",
            "carbohydrate_target_g_per_day",
            "fat_target_g_per_day",
            "calorie_target_kcal_per_day",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
                raise NutritionFeasibilityError(f"{name} must be a finite built-in number.")
            object.__setattr__(self, name, float(value))
        if any(
            value < 0
            for value in (
                self.protein_target_g_per_day,
                self.carbohydrate_target_g_per_day,
                self.fat_target_g_per_day,
                self.calorie_target_kcal_per_day,
            )
        ):
            raise NutritionFeasibilityError("macro and calorie targets must be non-negative.")
        category_fields = (
            "accepted_protein_categories",
            "accepted_carbohydrate_categories",
            "accepted_fat_categories",
            "disliked_categories",
            "limiting_categories",
        )
        for name in category_fields:
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(
                isinstance(item, FoodCategory) for item in value
            ):
                raise NutritionFeasibilityError(f"{name} must be a tuple of FoodCategory values.")
        for name in ("dietary_conflicts", "reason_codes", "assumptions"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
                raise NutritionFeasibilityError(f"{name} must be a tuple of strings.")
        if not isinstance(self.guidance, tuple) or not all(
            isinstance(item, NutritionGuidanceItem) for item in self.guidance
        ):
            raise NutritionFeasibilityError(
                "guidance must be a tuple of NutritionGuidanceItem values."
            )


def assess_nutrition_feasibility(
    dietary_profile: NutritionPreferenceProfile | None,
    dietary_assessment: NutritionPreferenceAssessment,
    macro_plan: PersonalizedMacroPlan,
    config: NutritionFeasibilityConfig | None = None,
) -> NutritionFeasibilityAssessment:
    """Assess practical category fit for the final macro plan without changing its values."""
    if dietary_profile is not None and not isinstance(dietary_profile, NutritionPreferenceProfile):
        raise NutritionFeasibilityError(
            "dietary_profile must be a NutritionPreferenceProfile or None."
        )
    if not isinstance(dietary_assessment, NutritionPreferenceAssessment):
        raise NutritionFeasibilityError(
            "dietary_assessment must be a NutritionPreferenceAssessment."
        )
    if not isinstance(macro_plan, PersonalizedMacroPlan):
        raise NutritionFeasibilityError("macro_plan must be a PersonalizedMacroPlan.")
    effective = config or NutritionFeasibilityConfig()
    if not isinstance(effective, NutritionFeasibilityConfig):
        raise NutritionFeasibilityError("config must be a NutritionFeasibilityConfig or None.")
    accepted = set(dietary_assessment.accepted_categories) - set(
        dietary_assessment.disliked_categories
    )
    protein = _categories_with_role(accepted, FoodCategoryRole.PROTEIN)
    carbohydrate = _categories_with_role(accepted, FoodCategoryRole.CARBOHYDRATE)
    fat = _categories_with_role(accepted, FoodCategoryRole.FAT)
    hard_limited = (
        set(dietary_assessment.inferred_hard_excluded_categories)
        | set(dietary_assessment.explicit_hard_excluded_categories)
        | set(dietary_assessment.limited_categories)
    )
    limiting = tuple(
        category
        for category in FoodCategory
        if category in hard_limited or category in dietary_assessment.disliked_categories
    )
    if dietary_profile is None or (
        dietary_profile.selection_mode is FoodSelectionMode.SELECTED
        and not dietary_profile.preferences
        and not dietary_profile.constraints
    ):
        return NutritionFeasibilityAssessment(
            False,
            None,
            None,
            None,
            None,
            None,
            macro_plan.macro_policy_version,
            macro_plan.training_adjustment_applied,
            macro_plan.protein_g_per_day,
            macro_plan.carbohydrate_g_per_day,
            macro_plan.fat_g_per_day,
            macro_plan.calorie_target_kcal_per_day,
            (),
            (),
            (),
            (),
            (),
            (),
            (),
            (
                "dietary_profile_unavailable"
                if dietary_profile is None
                else "insufficient_dietary_evidence",
                "insufficient_dietary_evidence",
            ),
            effective.policy_version,
            ("Missing dietary information does not imply broad food acceptance.",),
            training_policy_version=macro_plan.training_policy_version,
            protein_policy_source=macro_plan.protein_policy_source,
            carbohydrate_policy_source=macro_plan.carbohydrate_policy_source,
            baseline_protein_target_g_per_day=(
                macro_plan.baseline_protein_target_g
                if macro_plan.baseline_protein_target_g is not None
                else macro_plan.protein_g_per_day
            ),
            training_aware_protein_target_g_per_day=macro_plan.training_aware_protein_target_g,
            baseline_carbohydrate_target_g_per_day=(
                macro_plan.baseline_carbohydrate_target_g
                if macro_plan.baseline_carbohydrate_target_g is not None
                else macro_plan.carbohydrate_g_per_day
            ),
            protein_priority=macro_plan.protein_priority,
            carbohydrate_performance_priority=macro_plan.carbohydrate_performance_priority,
        )
    protein_level = _dimension_level(
        len(protein),
        effective.protein_very_challenging_categories,
        effective.protein_challenging_categories,
        effective.protein_easy_categories,
    )
    carbohydrate_level = _dimension_level(
        len(carbohydrate),
        effective.carbohydrate_very_challenging_categories,
        effective.carbohydrate_challenging_categories,
        effective.carbohydrate_easy_categories,
    )
    fat_level = _dimension_level(
        len(fat),
        effective.fat_very_challenging_categories,
        effective.fat_challenging_categories,
        effective.fat_easy_categories,
    )
    protein_share = macro_plan.protein_kcal_per_day / macro_plan.calorie_target_kcal_per_day
    carbohydrate_share = (
        macro_plan.carbohydrate_kcal_per_day / macro_plan.calorie_target_kcal_per_day
    )
    if protein_share >= effective.high_protein_calorie_share:
        protein_level = _increase_challenge(protein_level)
    if carbohydrate_share >= effective.high_carbohydrate_calorie_share:
        carbohydrate_level = _increase_challenge(carbohydrate_level)
    fat_near_floor = macro_plan.fat_percentage <= effective.fat_floor_proximity_percentage
    if fat_near_floor:
        fat_level = _increase_challenge(fat_level)
    restriction_compatibility = _restriction_compatibility(len(hard_limited), effective)
    dimensions = (protein_level, carbohydrate_level, fat_level)
    overall = max(dimensions, key=lambda item: tuple(FeasibilityLevel).index(item))
    reasons, guidance = _reasons_and_guidance(
        protein_level,
        carbohydrate_level,
        fat_level,
        restriction_compatibility,
        protein,
        carbohydrate,
        fat,
        limiting,
        dietary_assessment.conflicts,
        dietary_assessment.disliked_categories,
        macro_plan,
    )
    return NutritionFeasibilityAssessment(
        True,
        overall,
        protein_level,
        carbohydrate_level,
        fat_level,
        restriction_compatibility,
        macro_plan.macro_policy_version,
        macro_plan.training_adjustment_applied,
        macro_plan.protein_g_per_day,
        macro_plan.carbohydrate_g_per_day,
        macro_plan.fat_g_per_day,
        macro_plan.calorie_target_kcal_per_day,
        protein,
        carbohydrate,
        fat,
        dietary_assessment.disliked_categories,
        limiting,
        dietary_assessment.conflicts,
        guidance,
        reasons,
        effective.policy_version,
        (
            "Practical feasibility is distinct from mathematical macro and calorie feasibility.",
            "Categories are broad pathways, not individual foods or nutrient data.",
            "Dislikes reduce preferred pathways but are not hard restrictions.",
            "Training-aware macro provenance is reported; this assessment does not alter targets.",
            "No exact meals, recipes, quantities, or adherence guarantees are produced.",
        ),
        training_policy_version=macro_plan.training_policy_version,
        protein_policy_source=macro_plan.protein_policy_source,
        carbohydrate_policy_source=macro_plan.carbohydrate_policy_source,
        baseline_protein_target_g_per_day=(
            macro_plan.baseline_protein_target_g
            if macro_plan.baseline_protein_target_g is not None
            else macro_plan.protein_g_per_day
        ),
        training_aware_protein_target_g_per_day=macro_plan.training_aware_protein_target_g,
        baseline_carbohydrate_target_g_per_day=(
            macro_plan.baseline_carbohydrate_target_g
            if macro_plan.baseline_carbohydrate_target_g is not None
            else macro_plan.carbohydrate_g_per_day
        ),
        protein_priority=macro_plan.protein_priority,
        carbohydrate_performance_priority=macro_plan.carbohydrate_performance_priority,
    )


def _categories_with_role(
    accepted: set[FoodCategory], role: FoodCategoryRole
) -> tuple[FoodCategory, ...]:
    return tuple(
        category
        for category, roles in FOOD_CATEGORY_ROLES.items()
        if category in accepted and role in roles
    )


def _dimension_level(
    count: int, very_challenging: int, challenging: int, easy: int
) -> FeasibilityLevel:
    if count <= very_challenging:
        return FeasibilityLevel.VERY_CHALLENGING
    if count <= challenging:
        return FeasibilityLevel.CHALLENGING
    if count >= easy:
        return FeasibilityLevel.EASY
    return FeasibilityLevel.MANAGEABLE


def _increase_challenge(level: FeasibilityLevel) -> FeasibilityLevel:
    if level is FeasibilityLevel.EASY:
        return FeasibilityLevel.MANAGEABLE
    if level is FeasibilityLevel.MANAGEABLE:
        return FeasibilityLevel.CHALLENGING
    return level


def _restriction_compatibility(
    limiting_count: int, config: NutritionFeasibilityConfig
) -> RestrictionCompatibility:
    if limiting_count >= config.restriction_highly_limited_categories:
        return RestrictionCompatibility.HIGHLY_LIMITED
    if limiting_count >= config.restriction_limited_categories:
        return RestrictionCompatibility.LIMITED
    return RestrictionCompatibility.COMPATIBLE


def _reasons_and_guidance(
    protein_level: FeasibilityLevel,
    carbohydrate_level: FeasibilityLevel,
    fat_level: FeasibilityLevel,
    restriction_compatibility: RestrictionCompatibility,
    protein_categories: tuple[FoodCategory, ...],
    carbohydrate_categories: tuple[FoodCategory, ...],
    fat_categories: tuple[FoodCategory, ...],
    limiting: tuple[FoodCategory, ...],
    dietary_conflicts: tuple[str, ...],
    disliked_categories: tuple[FoodCategory, ...],
    macro_plan: PersonalizedMacroPlan,
) -> tuple[tuple[str, ...], tuple[NutritionGuidanceItem, ...]]:
    reasons: list[str] = []
    guidance: list[NutritionGuidanceItem] = []
    if len(protein_categories) <= 2:
        reasons.append("limited_accepted_protein_categories")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.PROTEIN,
                GuidancePriority.HIGH,
                "limited_accepted_protein_categories",
                GuidanceAction.PLAN_DELIBERATELY,
                "Use familiar accepted protein categories deliberately; the target may take more "
                "planning with fewer options.",
            )
        )
    else:
        reasons.append("broad_accepted_protein_options")
    if macro_plan.training_adjustment_applied and macro_plan.protein_g_per_day > (
        macro_plan.baseline_protein_target_g or 0
    ):
        reasons.append("training_aware_protein_increased_feasibility_demand")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.PROTEIN,
                GuidancePriority.MODERATE,
                "training_aware_protein_increased_feasibility_demand",
                GuidanceAction.FAVOR_ACCEPTED_CATEGORIES,
                "Your training-aware protein target is higher; favor protein-dense categories you "
                "already accept.",
            )
        )
    if macro_plan.training_adjustment_applied and macro_plan.carbohydrate_g_per_day > (
        macro_plan.baseline_carbohydrate_target_g or 0
    ):
        reasons.append("training_aware_carbohydrate_increased_feasibility_demand")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.CARBOHYDRATE,
                GuidancePriority.MODERATE,
                "training_aware_carbohydrate_increased_feasibility_demand",
                GuidanceAction.FAVOR_ACCEPTED_CATEGORIES,
                "Your training-aware plan favors carbohydrates within the same calorie target; use "
                "accepted carbohydrate categories that fit your routine.",
            )
        )
    if carbohydrate_level in (FeasibilityLevel.CHALLENGING, FeasibilityLevel.VERY_CHALLENGING):
        reasons.append("narrow_accepted_carbohydrate_options")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.CARBOHYDRATE,
                GuidancePriority.HIGH,
                "narrow_accepted_carbohydrate_options",
                GuidanceAction.PLAN_DELIBERATELY,
                "Your accepted carbohydrate options are limited, so choosing familiar compatible "
                "categories may make the plan easier to follow.",
            )
        )
    if fat_level in (FeasibilityLevel.CHALLENGING, FeasibilityLevel.VERY_CHALLENGING):
        reasons.append("limited_accepted_fat_options")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.FAT,
                GuidancePriority.MODERATE,
                "limited_accepted_fat_options",
                GuidanceAction.MAINTAIN_VARIETY,
                "Review which accepted fat-source categories fit your preferences; the current "
                "target is unchanged.",
            )
        )
    if restriction_compatibility is not RestrictionCompatibility.COMPATIBLE:
        reasons.append("dietary_restrictions_narrow_available_categories")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.RESTRICTION,
                GuidancePriority.MODERATE,
                "dietary_restrictions_narrow_available_categories",
                GuidanceAction.REVIEW_RESTRICTIONS,
                "Some common categories are excluded or limited. This assessment respects those "
                "rules and does not suggest changing them.",
            )
        )
    if dietary_conflicts:
        reasons.append("dietary_preference_conflicts_present")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.DIETARY_FLEXIBILITY,
                GuidancePriority.MODERATE,
                "dietary_preference_conflicts_present",
                GuidanceAction.REVIEW_RESTRICTIONS,
                "Some stated preferences overlap with stronger exclusions. The exclusions remain "
                "in effect; review the listed conflict details.",
            )
        )
    if disliked_categories:
        reasons.append("guidance_based_on_preferences_not_restrictions")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.DIETARY_FLEXIBILITY,
                GuidancePriority.LOW,
                "guidance_based_on_preferences_not_restrictions",
                GuidanceAction.FAVOR_ACCEPTED_CATEGORIES,
                "Lean on categories you marked okay, like, or favorite; dislikes are preferences, "
                "not hard exclusions.",
            )
        )
    if not guidance:
        reasons.append("macro_plan_broadly_compatible_with_preferences")
        guidance.append(
            NutritionGuidanceItem(
                GuidanceCategory.DIETARY_FLEXIBILITY,
                GuidancePriority.LOW,
                "macro_plan_broadly_compatible_with_preferences",
                GuidanceAction.MAINTAIN_VARIETY,
                "Your current plan appears manageable with the categories you accept. No exact "
                "meals are prescribed.",
            )
        )
    if limiting and not any(item.category is GuidanceCategory.RESTRICTION for item in guidance):
        reasons.append("guidance_respects_limited_or_disliked_categories")
    return tuple(dict.fromkeys(reasons)), tuple(guidance[:4])
