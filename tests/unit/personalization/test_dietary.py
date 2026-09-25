"""Focused domain contracts for dietary constraints and food flexibility."""

from dataclasses import FrozenInstanceError

import pytest

from fitadapt import (
    ActivityLevel,
    DietaryPattern,
    FoodCategory,
    FoodCategoryRole,
    FoodConstraint,
    FoodConstraintAction,
    FoodConstraintType,
    FoodPreference,
    FoodPreferenceLevel,
    FoodSelectionMode,
    Goal,
    MacroCalorieSource,
    MacroStrategy,
    NutritionDietaryError,
    NutritionPreferenceProfile,
    NutritionPreferences,
    ProteinFlexibilityConfig,
    ProteinFlexibilityStatus,
    SexForMifflinEquation,
    UserProfile,
    assess_nutrition_preferences,
    calculate_nutrition_target_envelope,
)


@pytest.fixture
def target_envelope():
    profile = UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.MAINTAIN, 0
    )
    return calculate_nutrition_target_envelope(
        profile,
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
    )


def profile_for(
    *,
    pattern=DietaryPattern.UNRESTRICTED,
    mode=FoodSelectionMode.BROAD,
    constraints=(),
    preferences=(),
    description=None,
):
    return NutritionPreferenceProfile(pattern, mode, constraints, preferences, description)


def test_enums_and_category_catalog_are_stable() -> None:
    assert {item.value for item in DietaryPattern} == {
        "unrestricted",
        "vegetarian",
        "vegan",
        "pescatarian",
        "halal",
        "kosher",
        "other",
    }
    assert {item.value for item in FoodSelectionMode} == {"broad", "selected"}
    assert FoodCategory.NUTS.value == "nuts"
    assert FoodCategoryRole.PROTEIN.value == "protein"


def test_valid_profiles_are_frozen_and_typed() -> None:
    profile = profile_for(
        mode=FoodSelectionMode.SELECTED,
        constraints=(
            FoodConstraint(
                FoodCategory.DAIRY, FoodConstraintType.INTOLERANCE, FoodConstraintAction.LIMIT
            ),
        ),
        preferences=(FoodPreference(FoodCategory.SOY, FoodPreferenceLevel.FAVORITE),),
    )
    assert isinstance(profile.constraints, tuple)
    with pytest.raises(FrozenInstanceError):
        profile.selection_mode = FoodSelectionMode.BROAD  # type: ignore[misc]


def test_pattern_exclusions_are_conservative(target_envelope) -> None:
    expected = {
        DietaryPattern.UNRESTRICTED: (),
        DietaryPattern.VEGETARIAN: ("poultry", "beef", "pork", "fish", "shellfish"),
        DietaryPattern.VEGAN: ("poultry", "beef", "pork", "fish", "shellfish", "eggs", "dairy"),
        DietaryPattern.PESCATARIAN: ("poultry", "beef", "pork"),
        DietaryPattern.HALAL: ("pork",),
        DietaryPattern.KOSHER: ("pork", "shellfish"),
        DietaryPattern.OTHER: (),
    }
    for pattern, categories in expected.items():
        description = "manual pattern" if pattern is DietaryPattern.OTHER else None
        result = assess_nutrition_preferences(
            profile_for(pattern=pattern, description=description), target_envelope
        )
        assert tuple(item.value for item in result.inferred_hard_excluded_categories) == categories
    assert assess_nutrition_preferences(
        profile_for(pattern=DietaryPattern.HALAL), target_envelope
    ).verification_notices
    assert assess_nutrition_preferences(
        profile_for(pattern=DietaryPattern.KOSHER), target_envelope
    ).verification_notices
    assert assess_nutrition_preferences(
        profile_for(pattern=DietaryPattern.OTHER, description="manual"), target_envelope
    ).verification_notices


def test_hard_constraints_precede_limits_and_soft_preferences(target_envelope) -> None:
    constraints = (
        FoodConstraint(FoodCategory.BEEF, FoodConstraintType.ALLERGY, FoodConstraintAction.EXCLUDE),
        FoodConstraint(
            FoodCategory.DAIRY, FoodConstraintType.INTOLERANCE, FoodConstraintAction.LIMIT
        ),
        FoodConstraint(
            FoodCategory.PORK, FoodConstraintType.REQUIRED_EXCLUSION, FoodConstraintAction.EXCLUDE
        ),
    )
    preferences = (
        FoodPreference(FoodCategory.BEEF, FoodPreferenceLevel.FAVORITE),
        FoodPreference(FoodCategory.PORK, FoodPreferenceLevel.LIKE),
        FoodPreference(FoodCategory.SOY, FoodPreferenceLevel.FAVORITE),
    )
    result = assess_nutrition_preferences(
        profile_for(constraints=constraints, preferences=preferences), target_envelope
    )
    assert result.explicit_hard_excluded_categories == (FoodCategory.BEEF, FoodCategory.PORK)
    assert result.limited_categories == (FoodCategory.DAIRY,)
    assert FoodCategory.BEEF not in result.accepted_categories
    assert len(result.conflicts) == 2


def test_intolerance_actions_and_preference_groups(target_envelope) -> None:
    constraints = (
        FoodConstraint(
            FoodCategory.PORK, FoodConstraintType.INTOLERANCE, FoodConstraintAction.EXCLUDE
        ),
    )
    preferences = tuple(
        FoodPreference(category, level)
        for category, level in (
            (FoodCategory.BEEF, FoodPreferenceLevel.DISLIKE),
            (FoodCategory.SOY, FoodPreferenceLevel.NEUTRAL),
            (FoodCategory.LEGUMES, FoodPreferenceLevel.LIKE),
            (FoodCategory.EGGS, FoodPreferenceLevel.FAVORITE),
        )
    )
    result = assess_nutrition_preferences(
        profile_for(constraints=constraints, preferences=preferences), target_envelope
    )
    assert result.explicit_hard_excluded_categories == (FoodCategory.PORK,)
    assert result.disliked_categories == (FoodCategory.BEEF,)
    assert result.preferred_categories == (FoodCategory.SOY, FoodCategory.LEGUMES)
    assert result.favorite_categories == (FoodCategory.EGGS,)


def test_broad_mode_uses_allowed_categories_and_selected_mode_requires_explicit_acceptance(
    target_envelope,
) -> None:
    broad = assess_nutrition_preferences(profile_for(), target_envelope)
    selected = assess_nutrition_preferences(
        profile_for(
            mode=FoodSelectionMode.SELECTED,
            preferences=tuple(
                FoodPreference(category, FoodPreferenceLevel.NEUTRAL)
                for category in (
                    FoodCategory.EGGS,
                    FoodCategory.SOY,
                    FoodCategory.LEGUMES,
                    FoodCategory.NUTS,
                )
            ),
        ),
        target_envelope,
    )
    assert broad.usable_protein_source_count == 13
    assert selected.usable_protein_source_categories == (
        FoodCategory.EGGS,
        FoodCategory.SOY,
        FoodCategory.LEGUMES,
        FoodCategory.NUTS,
    )
    assert selected.protein_flexibility_status is ProteinFlexibilityStatus.SUPPORTED


@pytest.mark.parametrize(
    ("count", "status"),
    [
        (0, ProteinFlexibilityStatus.INFEASIBLE),
        (1, ProteinFlexibilityStatus.DIFFICULT),
        (2, ProteinFlexibilityStatus.LIMITED),
        (3, ProteinFlexibilityStatus.LIMITED),
        (4, ProteinFlexibilityStatus.SUPPORTED),
    ],
)
def test_protein_status_thresholds(
    count: int, status: ProteinFlexibilityStatus, target_envelope
) -> None:
    preferences = tuple(
        FoodPreference(category, FoodPreferenceLevel.NEUTRAL)
        for category in tuple(FoodCategory)[0:count]
    )
    result = assess_nutrition_preferences(
        profile_for(mode=FoodSelectionMode.SELECTED, preferences=preferences), target_envelope
    )
    assert result.usable_protein_source_count == count
    assert result.protein_flexibility_status is status


def test_validation_rejects_wrong_types_duplicates_and_other_description(target_envelope) -> None:
    with pytest.raises(NutritionDietaryError):
        FoodConstraint("beef", FoodConstraintType.ALLERGY, FoodConstraintAction.EXCLUDE)  # type: ignore[arg-type]
    with pytest.raises(NutritionDietaryError):
        FoodConstraint(FoodCategory.BEEF, FoodConstraintType.ALLERGY, FoodConstraintAction.LIMIT)
    duplicate = FoodConstraint(
        FoodCategory.BEEF, FoodConstraintType.ALLERGY, FoodConstraintAction.EXCLUDE
    )
    with pytest.raises(NutritionDietaryError):
        profile_for(constraints=(duplicate, duplicate))
    preference = FoodPreference(FoodCategory.BEEF, FoodPreferenceLevel.LIKE)
    with pytest.raises(NutritionDietaryError):
        profile_for(preferences=(preference, preference))
    with pytest.raises(NutritionDietaryError):
        profile_for(pattern=DietaryPattern.OTHER)
    with pytest.raises(NutritionDietaryError):
        profile_for(pattern=DietaryPattern.VEGAN, description="incorrect")
    with pytest.raises(NutritionDietaryError):
        NutritionPreferenceProfile(DietaryPattern.UNRESTRICTED, FoodSelectionMode.BROAD, [])  # type: ignore[arg-type]
    with pytest.raises(NutritionDietaryError):
        ProteinFlexibilityConfig(difficult_max_usable_categories=True)  # type: ignore[arg-type]


def test_assessment_is_deterministic_immutable_and_preserves_target_provenance(
    target_envelope,
) -> None:
    profile = profile_for(
        mode=FoodSelectionMode.SELECTED,
        preferences=(FoodPreference(FoodCategory.EGGS, FoodPreferenceLevel.LIKE),),
    )
    first = assess_nutrition_preferences(profile, target_envelope)
    assert first == assess_nutrition_preferences(profile, target_envelope)
    assert first.protein_target_range is target_envelope.protein_preferred_range
    assert first.target_range_policy_version == target_envelope.range_policy_version
    assert first.protein_flexibility_policy_version == "protein_flexibility_v1"
    assert isinstance(first.assumptions, tuple)
    assert all(type(item.value) is str for item in first.usable_protein_source_categories)
    with pytest.raises(FrozenInstanceError):
        first.dietary_pattern = DietaryPattern.VEGAN  # type: ignore[misc]


def test_assessment_rejects_invalid_direct_tuple_contents(target_envelope) -> None:
    from dataclasses import replace

    result = assess_nutrition_preferences(profile_for(), target_envelope)
    with pytest.raises(NutritionDietaryError):
        replace(result, accepted_categories=("beef",))
    with pytest.raises(NutritionDietaryError):
        replace(result, assumptions=(None,))


def test_zero_usable_sources_is_actionable(target_envelope) -> None:
    constraints = tuple(
        FoodConstraint(
            category, FoodConstraintType.REQUIRED_EXCLUSION, FoodConstraintAction.EXCLUDE
        )
        for category in (
            FoodCategory.EGGS,
            FoodCategory.SOY,
            FoodCategory.LEGUMES,
            FoodCategory.PROTEIN_SUPPLEMENTS,
            FoodCategory.NUTS,
            FoodCategory.SEEDS,
            FoodCategory.NUT_BUTTERS,
        )
    )
    result = assess_nutrition_preferences(
        profile_for(mode=FoodSelectionMode.SELECTED, constraints=constraints), target_envelope
    )
    assert result.protein_flexibility_status is ProteinFlexibilityStatus.INFEASIBLE
    assert result.actionable_requirements
