"""Practical dietary fit assessment tests; macro targets remain authoritative."""

from dataclasses import FrozenInstanceError, astuple, replace
from math import inf, nan

import pytest

from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.dietary import (
    DietaryPattern,
    FoodCategory,
    FoodConstraint,
    FoodConstraintAction,
    FoodConstraintType,
    FoodPreference,
    FoodPreferenceLevel,
    FoodSelectionMode,
    NutritionPreferenceProfile,
    assess_nutrition_preferences,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.nutrition_feasibility import (
    FeasibilityLevel,
    GuidanceAction,
    GuidanceCategory,
    GuidancePriority,
    NutritionFeasibilityConfig,
    NutritionFeasibilityError,
    NutritionGuidanceItem,
    RestrictionCompatibility,
    assess_nutrition_feasibility,
)
from fitadapt.personalization.targets import calculate_nutrition_target_envelope
from fitadapt.personalization.training import (
    OccupationActivity,
    PrimaryTrainingFocus,
    TrainingContext,
    TrainingIntensity,
    assess_training_demand,
)


def profile() -> UserProfile:
    return UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.MAINTAIN, 0
    )


def envelope(training=None):
    return calculate_nutrition_target_envelope(
        profile(),
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
        training_assessment=training,
    )


def broad_profile(constraints=(), preferences=()):
    return NutritionPreferenceProfile(
        DietaryPattern.UNRESTRICTED,
        FoodSelectionMode.BROAD,
        tuple(constraints),
        tuple(preferences),
    )


def assess(dietary, macro=None):
    macro = macro or envelope().macro_plan
    target = calculate_nutrition_target_envelope(
        profile(),
        macro.calorie_target_kcal_per_day,
        macro.calorie_source,
        NutritionPreferences(macro.strategy),
    )
    dietary_result = assess_nutrition_preferences(dietary, target)
    return assess_nutrition_feasibility(dietary, dietary_result, macro)


def test_missing_and_empty_selected_context_are_unavailable_but_explicit_broad_is_assessable() -> (
    None
):
    macro = envelope().macro_plan
    broad = broad_profile()
    assert (
        assess_nutrition_feasibility(
            None, assess_nutrition_preferences(broad, envelope()), macro
        ).assessment_available
        is False
    )
    empty_selected = NutritionPreferenceProfile(
        DietaryPattern.UNRESTRICTED, FoodSelectionMode.SELECTED
    )
    assert assess(empty_selected).assessment_available is False
    result = assess(broad)
    assert result.assessment_available is True
    assert result.overall_feasibility in (FeasibilityLevel.EASY, FeasibilityLevel.MANAGEABLE)


def test_narrow_protein_pool_and_training_aware_plan_add_deliberate_guidance() -> None:
    context = NutritionPreferenceProfile(
        DietaryPattern.VEGAN,
        FoodSelectionMode.SELECTED,
        (),
        (FoodPreference(FoodCategory.SOY, FoodPreferenceLevel.LIKE),),
    )
    training = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            4,
            240,
            primary_training_focus=PrimaryTrainingFocus.RESISTANCE,
        )
    )
    macro = envelope(training).macro_plan
    result = assess(context, macro)
    assert result.protein_feasibility in (
        FeasibilityLevel.CHALLENGING,
        FeasibilityLevel.VERY_CHALLENGING,
    )
    assert result.training_adjustment_applied
    assert "training_aware_protein_increased_feasibility_demand" in result.reason_codes
    assert any(item.category is GuidanceCategory.PROTEIN for item in result.guidance)


def test_dislikes_are_not_restrictions_and_guidance_uses_only_accepted_categories() -> None:
    dietary = broad_profile(
        preferences=(FoodPreference(FoodCategory.DAIRY, FoodPreferenceLevel.DISLIKE),)
    )
    result = assess(dietary)
    assert FoodCategory.DAIRY in result.disliked_categories
    assert FoodCategory.DAIRY not in result.accepted_protein_categories
    assert result.restriction_compatibility is RestrictionCompatibility.COMPATIBLE
    assert "guidance_based_on_preferences_not_restrictions" in result.reason_codes
    assert any("preferences, not hard exclusions" in item.message for item in result.guidance)


def test_restrictions_are_reported_and_targets_are_not_modified() -> None:
    constraints = tuple(
        FoodConstraint(
            category, FoodConstraintType.REQUIRED_EXCLUSION, FoodConstraintAction.EXCLUDE
        )
        for category in (
            FoodCategory.EGGS,
            FoodCategory.DAIRY,
            FoodCategory.SOY,
            FoodCategory.LEGUMES,
            FoodCategory.PROTEIN_SUPPLEMENTS,
        )
    )
    dietary = broad_profile(constraints=constraints)
    macro = envelope().macro_plan
    before = astuple(macro)
    result = assess(dietary, macro)
    assert result.restriction_compatibility is RestrictionCompatibility.HIGHLY_LIMITED
    assert result.calorie_target_kcal_per_day == macro.calorie_target_kcal_per_day
    assert result.protein_target_g_per_day == macro.protein_g_per_day
    assert astuple(macro) == before


def test_high_carbohydrate_training_priority_is_explained_without_target_change() -> None:
    training = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            cardio_days_per_week=5,
            cardio_minutes_per_week=360,
            cardio_intensity=TrainingIntensity.VIGOROUS,
            primary_training_focus=PrimaryTrainingFocus.ENDURANCE,
        )
    )
    macro = envelope(training).macro_plan
    result = assess(broad_profile(), macro)
    assert result.training_adjustment_applied
    assert result.carbohydrate_target_g_per_day == macro.carbohydrate_g_per_day
    assert "training_aware_carbohydrate_increased_feasibility_demand" in result.reason_codes


def test_macro_density_and_fat_floor_adjust_dimensions_even_with_broad_categories() -> None:
    training = assess_training_demand(
        TrainingContext(
            OccupationActivity.MOSTLY_SEATED,
            5,
            360,
            cardio_days_per_week=5,
            cardio_minutes_per_week=360,
            cardio_intensity=TrainingIntensity.VIGOROUS,
            primary_training_focus=PrimaryTrainingFocus.MIXED,
        )
    )
    macro = calculate_personalized_macro_plan(
        profile(),
        2400,
        MacroCalorieSource.BASELINE,
        NutritionPreferences(MacroStrategy.BALANCED),
        training,
    )
    result = assess(broad_profile(), macro)
    assert result.protein_feasibility is FeasibilityLevel.MANAGEABLE
    assert result.fat_feasibility is FeasibilityLevel.MANAGEABLE
    assert result.carbohydrate_feasibility is FeasibilityLevel.EASY


def test_explicit_broad_profile_can_be_easy_while_missing_profile_is_unavailable() -> None:
    macro = envelope().macro_plan
    broad = broad_profile()
    dietary_result = assess_nutrition_preferences(broad, envelope())
    available = assess_nutrition_feasibility(broad, dietary_result, macro)
    missing = assess_nutrition_feasibility(None, dietary_result, macro)
    assert available.assessment_available is True
    assert available.overall_feasibility is FeasibilityLevel.EASY
    assert missing.assessment_available is False


def test_restriction_and_favorite_conflict_remains_in_feasibility_diagnostics() -> None:
    dietary = NutritionPreferenceProfile(
        DietaryPattern.UNRESTRICTED,
        FoodSelectionMode.BROAD,
        (
            FoodConstraint(
                FoodCategory.DAIRY, FoodConstraintType.ALLERGY, FoodConstraintAction.EXCLUDE
            ),
        ),
        (FoodPreference(FoodCategory.DAIRY, FoodPreferenceLevel.FAVORITE),),
    )
    result = assess(dietary)
    assert result.dietary_conflicts
    assert FoodCategory.DAIRY in result.limiting_categories
    assert "dietary_preference_conflicts_present" in result.reason_codes


def test_config_and_results_are_immutable_and_deterministic() -> None:
    config = NutritionFeasibilityConfig()
    with pytest.raises(FrozenInstanceError):
        config.policy_version = "new"  # type: ignore[misc]
    with pytest.raises(NutritionFeasibilityError):
        NutritionFeasibilityConfig(high_protein_calorie_share=1.2)
    dietary = broad_profile()
    first = assess_nutrition_feasibility(
        dietary, assess_nutrition_preferences(dietary, envelope()), envelope().macro_plan
    )
    again = assess_nutrition_feasibility(
        dietary, assess_nutrition_preferences(dietary, envelope()), envelope().macro_plan
    )
    assert first == again
    assert isinstance(first.guidance, tuple)
    assert all(type(item.message) is str for item in first.guidance)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"protein_easy_categories": True},
        {"protein_easy_categories": -1},
        {"protein_easy_categories": 2},
        {"restriction_highly_limited_categories": 1},
        {"high_protein_calorie_share": True},
        {"high_protein_calorie_share": "0.3"},
        {"high_protein_calorie_share": nan},
        {"high_protein_calorie_share": inf},
        {"fat_floor_proximity_percentage": -0.1},
    ],
)
def test_config_rejects_invalid_threshold_contracts(kwargs: dict[str, object]) -> None:
    with pytest.raises(NutritionFeasibilityError):
        NutritionFeasibilityConfig(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"overall_feasibility": "easy"},
        {"macro_policy_version": ""},
        {"protein_target_g_per_day": True},
        {"protein_target_g_per_day": nan},
        {"protein_target_g_per_day": inf},
        {"protein_target_g_per_day": -1.0},
        {"accepted_protein_categories": [FoodCategory.SOY]},
        {"accepted_protein_categories": ("soy",)},
        {"reason_codes": ["mutable"]},
        {"guidance": ["mutable"]},
    ],
)
def test_result_runtime_validation_rejects_invalid_public_values(
    changes: dict[str, object],
) -> None:
    result = assess(broad_profile())
    with pytest.raises(NutritionFeasibilityError):
        replace(result, **changes)


def test_guidance_item_rejects_invalid_enum_and_empty_text() -> None:
    with pytest.raises(NutritionFeasibilityError):
        NutritionGuidanceItem(
            "protein", GuidancePriority.HIGH, "reason", GuidanceAction.PLAN_DELIBERATELY, "message"
        )  # type: ignore[arg-type]
    with pytest.raises(NutritionFeasibilityError):
        NutritionGuidanceItem(
            GuidanceCategory.PROTEIN,
            GuidancePriority.HIGH,
            "",
            GuidanceAction.PLAN_DELIBERATELY,
            "message",
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"policy_version": ""},
        {"protein_easy_categories": True},
        {"protein_very_challenging_categories": 4, "protein_challenging_categories": 2},
        {"restriction_limited_categories": 5, "restriction_highly_limited_categories": 3},
        {"high_protein_calorie_share": True},
        {"high_protein_calorie_share": "0.3"},
        {"high_protein_calorie_share": nan},
        {"fat_floor_proximity_percentage": inf},
        {"high_carbohydrate_calorie_share": -0.1},
    ],
)
def test_config_rejects_invalid_policy_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(NutritionFeasibilityError):
        NutritionFeasibilityConfig(**kwargs)  # type: ignore[arg-type]


def test_result_rejects_mutable_or_inconsistent_public_values() -> None:
    result = assess(broad_profile())
    with pytest.raises(NutritionFeasibilityError):
        replace(result, guidance=list(result.guidance))
    with pytest.raises(NutritionFeasibilityError):
        replace(result, protein_target_g_per_day=True)
    with pytest.raises(NutritionFeasibilityError):
        replace(result, assessment_available=False)


@pytest.mark.parametrize(
    "changes",
    [
        {"assessment_available": 1},
        {"training_adjustment_applied": 1},
        {"overall_feasibility": "easy"},
        {"macro_policy_version": ""},
        {"policy_version": ""},
        {"calorie_target_kcal_per_day": nan},
        {"fat_target_g_per_day": -1},
        {"accepted_fat_categories": ("nuts",)},
        {"dietary_conflicts": ["conflict"]},
        {"baseline_protein_target_g_per_day": inf},
        {"training_aware_protein_target_g_per_day": True},
        {"protein_policy_source": ""},
        {"protein_priority": 2},
    ],
)
def test_result_rejects_invalid_scalar_enum_and_tuple_values(
    changes: dict[str, object],
) -> None:
    result = assess(broad_profile())
    with pytest.raises(NutritionFeasibilityError):
        replace(result, **changes)


def test_selected_protein_category_counts_resolve_feasibility_thresholds() -> None:
    cases = [
        (1, FeasibilityLevel.VERY_CHALLENGING),
        (2, FeasibilityLevel.CHALLENGING),
        (4, FeasibilityLevel.MANAGEABLE),
        (6, FeasibilityLevel.EASY),
    ]
    protein_categories = (
        FoodCategory.EGGS,
        FoodCategory.SOY,
        FoodCategory.LEGUMES,
        FoodCategory.NUTS,
        FoodCategory.SEEDS,
        FoodCategory.NUT_BUTTERS,
    )
    for count, expected in cases:
        dietary = NutritionPreferenceProfile(
            DietaryPattern.UNRESTRICTED,
            FoodSelectionMode.SELECTED,
            (),
            tuple(
                FoodPreference(category, FoodPreferenceLevel.NEUTRAL)
                for category in protein_categories[:count]
            ),
        )
        assert assess(dietary).protein_feasibility is expected
