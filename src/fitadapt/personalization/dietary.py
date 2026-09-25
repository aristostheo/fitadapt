"""Framework-independent dietary constraints and protein-source flexibility policy."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from fitadapt.personalization.targets import NutritionTargetEnvelope, NutritionTargetRange

DIETARY_CATEGORY_POLICY_VERSION = "dietary_categories_v1"
DIETARY_PATTERN_POLICY_VERSION = "dietary_patterns_v1"
DIETARY_ASSESSMENT_POLICY_VERSION = "dietary_assessment_v1"
PROTEIN_FLEXIBILITY_POLICY_VERSION = "protein_flexibility_v1"


class NutritionDietaryError(ValueError):
    """Raised when dietary inputs or a dietary assessment violate the domain contract."""


class DietaryPattern(StrEnum):
    UNRESTRICTED = "unrestricted"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"
    HALAL = "halal"
    KOSHER = "kosher"
    OTHER = "other"


class FoodSelectionMode(StrEnum):
    BROAD = "broad"
    SELECTED = "selected"


class FoodCategory(StrEnum):
    POULTRY = "poultry"
    BEEF = "beef"
    PORK = "pork"
    FISH = "fish"
    SHELLFISH = "shellfish"
    EGGS = "eggs"
    DAIRY = "dairy"
    SOY = "soy"
    LEGUMES = "legumes"
    PROTEIN_SUPPLEMENTS = "protein_supplements"
    RICE = "rice"
    PASTA = "pasta"
    BREAD = "bread"
    POTATOES = "potatoes"
    OATS = "oats"
    TORTILLAS = "tortillas"
    FRUIT = "fruit"
    VEGETABLES = "vegetables"
    NUTS = "nuts"
    SEEDS = "seeds"
    NUT_BUTTERS = "nut_butters"
    AVOCADO = "avocado"
    COOKING_OILS = "cooking_oils"


class FoodCategoryRole(StrEnum):
    PROTEIN = "protein"
    CARBOHYDRATE = "carbohydrate"
    PRODUCE = "produce"
    FAT = "fat"


FOOD_CATEGORY_ROLES = MappingProxyType(
    {
        FoodCategory.POULTRY: (FoodCategoryRole.PROTEIN,),
        FoodCategory.BEEF: (FoodCategoryRole.PROTEIN,),
        FoodCategory.PORK: (FoodCategoryRole.PROTEIN,),
        FoodCategory.FISH: (FoodCategoryRole.PROTEIN,),
        FoodCategory.SHELLFISH: (FoodCategoryRole.PROTEIN,),
        FoodCategory.EGGS: (FoodCategoryRole.PROTEIN,),
        FoodCategory.DAIRY: (FoodCategoryRole.PROTEIN,),
        FoodCategory.SOY: (FoodCategoryRole.PROTEIN,),
        FoodCategory.LEGUMES: (FoodCategoryRole.PROTEIN,),
        FoodCategory.PROTEIN_SUPPLEMENTS: (FoodCategoryRole.PROTEIN,),
        FoodCategory.RICE: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.PASTA: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.BREAD: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.POTATOES: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.OATS: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.TORTILLAS: (FoodCategoryRole.CARBOHYDRATE,),
        FoodCategory.FRUIT: (FoodCategoryRole.PRODUCE,),
        FoodCategory.VEGETABLES: (FoodCategoryRole.PRODUCE,),
        FoodCategory.NUTS: (FoodCategoryRole.PROTEIN, FoodCategoryRole.FAT),
        FoodCategory.SEEDS: (FoodCategoryRole.PROTEIN, FoodCategoryRole.FAT),
        FoodCategory.NUT_BUTTERS: (FoodCategoryRole.PROTEIN, FoodCategoryRole.FAT),
        FoodCategory.AVOCADO: (FoodCategoryRole.FAT,),
        FoodCategory.COOKING_OILS: (FoodCategoryRole.FAT,),
    }
)

PROTEIN_CATEGORIES = tuple(
    category for category, roles in FOOD_CATEGORY_ROLES.items() if FoodCategoryRole.PROTEIN in roles
)


class FoodConstraintType(StrEnum):
    ALLERGY = "allergy"
    REQUIRED_EXCLUSION = "required_exclusion"
    INTOLERANCE = "intolerance"


class FoodConstraintAction(StrEnum):
    EXCLUDE = "exclude"
    LIMIT = "limit"


class FoodPreferenceLevel(StrEnum):
    DISLIKE = "dislike"
    NEUTRAL = "neutral"
    LIKE = "like"
    FAVORITE = "favorite"


@dataclass(frozen=True, slots=True)
class FoodConstraint:
    category: FoodCategory
    constraint_type: FoodConstraintType
    action: FoodConstraintAction
    note: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.category, FoodCategory, "category")
        _require_enum(self.constraint_type, FoodConstraintType, "constraint_type")
        _require_enum(self.action, FoodConstraintAction, "action")
        if self.constraint_type is not FoodConstraintType.INTOLERANCE:
            if self.action is not FoodConstraintAction.EXCLUDE:
                raise NutritionDietaryError(
                    "allergy and required_exclusion constraints must use exclude."
                )
        if self.note is not None and (not isinstance(self.note, str) or not self.note.strip()):
            raise NutritionDietaryError("note must be None or a non-empty string.")


@dataclass(frozen=True, slots=True)
class FoodPreference:
    category: FoodCategory
    level: FoodPreferenceLevel

    def __post_init__(self) -> None:
        _require_enum(self.category, FoodCategory, "category")
        _require_enum(self.level, FoodPreferenceLevel, "level")


@dataclass(frozen=True, slots=True)
class NutritionPreferenceProfile:
    dietary_pattern: DietaryPattern
    selection_mode: FoodSelectionMode
    constraints: tuple[FoodConstraint, ...] = ()
    preferences: tuple[FoodPreference, ...] = ()
    other_description: str | None = None

    def __post_init__(self) -> None:
        _require_enum(self.dietary_pattern, DietaryPattern, "dietary_pattern")
        _require_enum(self.selection_mode, FoodSelectionMode, "selection_mode")
        if not isinstance(self.constraints, tuple) or not all(
            isinstance(item, FoodConstraint) for item in self.constraints
        ):
            raise NutritionDietaryError("constraints must be a tuple of FoodConstraint values.")
        if not isinstance(self.preferences, tuple) or not all(
            isinstance(item, FoodPreference) for item in self.preferences
        ):
            raise NutritionDietaryError("preferences must be a tuple of FoodPreference values.")
        constraint_keys = [(item.category, item.constraint_type) for item in self.constraints]
        if len(constraint_keys) != len(set(constraint_keys)):
            raise NutritionDietaryError(
                "duplicate constraints for one category and type are not allowed."
            )
        preference_categories = [item.category for item in self.preferences]
        if len(preference_categories) != len(set(preference_categories)):
            raise NutritionDietaryError("duplicate preferences for one category are not allowed.")
        if self.dietary_pattern is DietaryPattern.OTHER:
            if not isinstance(self.other_description, str) or not self.other_description.strip():
                raise NutritionDietaryError("other_description is required for the other pattern.")
        elif self.other_description is not None:
            raise NutritionDietaryError(
                "other_description is allowed only for the other dietary pattern."
            )


_PATTERN_EXCLUSIONS = MappingProxyType(
    {
        DietaryPattern.UNRESTRICTED: (),
        DietaryPattern.VEGETARIAN: (
            FoodCategory.POULTRY,
            FoodCategory.BEEF,
            FoodCategory.PORK,
            FoodCategory.FISH,
            FoodCategory.SHELLFISH,
        ),
        DietaryPattern.VEGAN: (
            FoodCategory.POULTRY,
            FoodCategory.BEEF,
            FoodCategory.PORK,
            FoodCategory.FISH,
            FoodCategory.SHELLFISH,
            FoodCategory.EGGS,
            FoodCategory.DAIRY,
        ),
        DietaryPattern.PESCATARIAN: (
            FoodCategory.POULTRY,
            FoodCategory.BEEF,
            FoodCategory.PORK,
        ),
        DietaryPattern.HALAL: (FoodCategory.PORK,),
        DietaryPattern.KOSHER: (FoodCategory.PORK, FoodCategory.SHELLFISH),
        DietaryPattern.OTHER: (),
    }
)


@dataclass(frozen=True, slots=True)
class ProteinFlexibilityConfig:
    """Versioned product thresholds for food-choice flexibility, not physiology."""

    infeasible_max_usable_categories: int = 0
    difficult_max_usable_categories: int = 1
    limited_max_usable_categories: int = 3
    policy_version: str = PROTEIN_FLEXIBILITY_POLICY_VERSION

    def __post_init__(self) -> None:
        values = (
            self.infeasible_max_usable_categories,
            self.difficult_max_usable_categories,
            self.limited_max_usable_categories,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise NutritionDietaryError("protein flexibility thresholds must be integers.")
        if not (
            self.infeasible_max_usable_categories
            < self.difficult_max_usable_categories
            < self.limited_max_usable_categories
        ):
            raise NutritionDietaryError(
                "protein flexibility thresholds must be strictly increasing."
            )
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise NutritionDietaryError("policy_version must be a non-empty string.")


class ProteinFlexibilityStatus(StrEnum):
    INFEASIBLE = "infeasible"
    DIFFICULT = "difficult"
    LIMITED = "limited"
    SUPPORTED = "supported"


@dataclass(frozen=True, slots=True)
class NutritionPreferenceAssessment:
    dietary_pattern: DietaryPattern
    selection_mode: FoodSelectionMode
    protein_target_range: NutritionTargetRange
    protein_target_provenance: str
    inferred_hard_excluded_categories: tuple[FoodCategory, ...]
    explicit_hard_excluded_categories: tuple[FoodCategory, ...]
    limited_categories: tuple[FoodCategory, ...]
    disliked_categories: tuple[FoodCategory, ...]
    accepted_categories: tuple[FoodCategory, ...]
    preferred_categories: tuple[FoodCategory, ...]
    favorite_categories: tuple[FoodCategory, ...]
    usable_protein_source_categories: tuple[FoodCategory, ...]
    usable_protein_source_count: int
    protein_flexibility_status: ProteinFlexibilityStatus
    conflicts: tuple[str, ...]
    verification_notices: tuple[str, ...]
    actionable_requirements: tuple[str, ...]
    category_policy_version: str
    pattern_policy_version: str
    assessment_policy_version: str
    protein_flexibility_policy_version: str
    target_range_policy_version: str
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_enum(self.dietary_pattern, DietaryPattern, "dietary_pattern")
        _require_enum(self.selection_mode, FoodSelectionMode, "selection_mode")
        if not isinstance(self.protein_target_range, NutritionTargetRange):
            raise NutritionDietaryError("protein_target_range must be a NutritionTargetRange.")
        tuple_fields = (
            "inferred_hard_excluded_categories",
            "explicit_hard_excluded_categories",
            "limited_categories",
            "disliked_categories",
            "accepted_categories",
            "preferred_categories",
            "favorite_categories",
            "usable_protein_source_categories",
            "conflicts",
            "verification_notices",
            "actionable_requirements",
            "assumptions",
        )
        for name in tuple_fields:
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise NutritionDietaryError(f"{name} must be a tuple.")
            if name in {
                "inferred_hard_excluded_categories",
                "explicit_hard_excluded_categories",
                "limited_categories",
                "disliked_categories",
                "accepted_categories",
                "preferred_categories",
                "favorite_categories",
                "usable_protein_source_categories",
            } and not all(isinstance(item, FoodCategory) for item in value):
                raise NutritionDietaryError(f"{name} must contain FoodCategory enum values.")
            if name not in {
                "inferred_hard_excluded_categories",
                "explicit_hard_excluded_categories",
                "limited_categories",
                "disliked_categories",
                "accepted_categories",
                "preferred_categories",
                "favorite_categories",
                "usable_protein_source_categories",
            } and not all(isinstance(item, str) and item for item in value):
                raise NutritionDietaryError(f"{name} must contain non-empty strings.")
        if not isinstance(self.usable_protein_source_count, int) or isinstance(
            self.usable_protein_source_count, bool
        ):
            raise NutritionDietaryError("usable_protein_source_count must be an integer.")
        if self.usable_protein_source_count < 0:
            raise NutritionDietaryError("usable_protein_source_count cannot be negative.")
        if self.usable_protein_source_count != len(self.usable_protein_source_categories):
            raise NutritionDietaryError("usable protein source count must match its tuple.")
        _require_enum(
            self.protein_flexibility_status,
            ProteinFlexibilityStatus,
            "protein_flexibility_status",
        )


def assess_nutrition_preferences(
    preference_profile: NutritionPreferenceProfile,
    target_envelope: NutritionTargetEnvelope,
    config: ProteinFlexibilityConfig | None = None,
) -> NutritionPreferenceAssessment:
    """Assess deterministic food-choice flexibility against an existing target envelope."""
    if not isinstance(preference_profile, NutritionPreferenceProfile):
        raise NutritionDietaryError("preference_profile must be a NutritionPreferenceProfile.")
    if not isinstance(target_envelope, NutritionTargetEnvelope):
        raise NutritionDietaryError("target_envelope must be a NutritionTargetEnvelope.")
    if config is not None and not isinstance(config, ProteinFlexibilityConfig):
        raise NutritionDietaryError("config must be a ProteinFlexibilityConfig or None.")
    effective = config or ProteinFlexibilityConfig()
    inferred = tuple(_PATTERN_EXCLUSIONS[preference_profile.dietary_pattern])
    explicit_hard = tuple(
        dict.fromkeys(
            constraint.category
            for constraint in preference_profile.constraints
            if constraint.constraint_type
            in (FoodConstraintType.ALLERGY, FoodConstraintType.REQUIRED_EXCLUSION)
            or constraint.action is FoodConstraintAction.EXCLUDE
        )
    )
    hard_excluded = set(inferred) | set(explicit_hard)
    limited = tuple(
        dict.fromkeys(
            constraint.category
            for constraint in preference_profile.constraints
            if constraint.constraint_type is FoodConstraintType.INTOLERANCE
            and constraint.action is FoodConstraintAction.LIMIT
            and constraint.category not in hard_excluded
        )
    )
    disliked = tuple(
        preference.category
        for preference in preference_profile.preferences
        if preference.level is FoodPreferenceLevel.DISLIKE
    )
    preferred = tuple(
        preference.category
        for preference in preference_profile.preferences
        if preference.level in (FoodPreferenceLevel.LIKE, FoodPreferenceLevel.NEUTRAL)
    )
    favorite = tuple(
        preference.category
        for preference in preference_profile.preferences
        if preference.level is FoodPreferenceLevel.FAVORITE
    )
    allowed = tuple(
        category
        for category in FoodCategory
        if category not in hard_excluded and category not in limited
    )
    accepted = tuple(
        category
        for category in allowed
        if (
            preference_profile.selection_mode is FoodSelectionMode.BROAD
            or category in set(preferred) | set(favorite)
        )
    )
    usable = tuple(
        category
        for category in PROTEIN_CATEGORIES
        if category in accepted
        and (
            preference_profile.selection_mode is FoodSelectionMode.BROAD
            or category in set(preferred) | set(favorite)
        )
    )
    status = _protein_status(len(usable), effective)
    conflicts = tuple(
        f"Preference for {preference.category.value} conflicts with a stronger exclusion."
        for preference in preference_profile.preferences
        if preference.category in hard_excluded
    )
    notices: list[str] = []
    if preference_profile.dietary_pattern in (DietaryPattern.HALAL, DietaryPattern.KOSHER):
        notices.append(
            preference_profile.dietary_pattern.value
            + " categories require ingredient, preparation, "
            "and certification verification."
        )
    if preference_profile.dietary_pattern is DietaryPattern.OTHER:
        notices.append(
            "The other dietary pattern has no inferred exclusions and requires manual review."
        )
    requirements = []
    if status is ProteinFlexibilityStatus.INFEASIBLE:
        requirements.append(
            "Select at least one usable protein-source category before assessing feasibility."
        )
    elif status is ProteinFlexibilityStatus.DIFFICULT:
        requirements.append(
            "Review the single usable protein source for food-choice adherence difficulty."
        )
    return NutritionPreferenceAssessment(
        dietary_pattern=preference_profile.dietary_pattern,
        selection_mode=preference_profile.selection_mode,
        protein_target_range=target_envelope.protein_preferred_range,
        protein_target_provenance=(
            f"Protein target comes from the selected {target_envelope.range_policy_version} "
            f"envelope and its exact {target_envelope.macro_policy_version} macro plan."
        ),
        inferred_hard_excluded_categories=inferred,
        explicit_hard_excluded_categories=explicit_hard,
        limited_categories=limited,
        disliked_categories=disliked,
        accepted_categories=accepted,
        preferred_categories=preferred,
        favorite_categories=favorite,
        usable_protein_source_categories=usable,
        usable_protein_source_count=len(usable),
        protein_flexibility_status=status,
        conflicts=conflicts,
        verification_notices=tuple(notices),
        actionable_requirements=tuple(requirements),
        category_policy_version=DIETARY_CATEGORY_POLICY_VERSION,
        pattern_policy_version=DIETARY_PATTERN_POLICY_VERSION,
        assessment_policy_version=DIETARY_ASSESSMENT_POLICY_VERSION,
        protein_flexibility_policy_version=effective.policy_version,
        target_range_policy_version=target_envelope.range_policy_version,
        assumptions=(
            "Food categories are V1 policy groups, not individual foods or recipes.",
            "Hard exclusions take precedence over intolerances and soft preferences.",
            "Broad-mode flexibility measures policy-allowed categories after hard exclusions "
            "and limits.",
            "Selected-mode flexibility counts only explicitly neutral, liked, or favorite "
            "categories.",
            "Protein flexibility describes food-choice and adherence difficulty, not "
            "physiological impossibility.",
        ),
    )


def _protein_status(count: int, config: ProteinFlexibilityConfig) -> ProteinFlexibilityStatus:
    if count <= config.infeasible_max_usable_categories:
        return ProteinFlexibilityStatus.INFEASIBLE
    if count <= config.difficult_max_usable_categories:
        return ProteinFlexibilityStatus.DIFFICULT
    if count <= config.limited_max_usable_categories:
        return ProteinFlexibilityStatus.LIMITED
    return ProteinFlexibilityStatus.SUPPORTED


def _require_enum(value: object, enum_type: type[StrEnum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise NutritionDietaryError(f"{field_name} must be a {enum_type.__name__} enum value.")


DEFAULT_NUTRITION_PREFERENCE_PROFILE = NutritionPreferenceProfile(
    DietaryPattern.UNRESTRICTED,
    FoodSelectionMode.BROAD,
)
