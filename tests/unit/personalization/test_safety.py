"""Target safety guardrail contracts and adversarial profiles."""

from dataclasses import replace

import pytest

from fitadapt.baseline.energy import calculate_baseline_energy
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.personalization.safety import (
    TargetEligibilityStatus,
    TargetSafetyConfig,
    TargetSafetyReason,
    assess_target_eligibility,
)


def _profile(
    sex: SexForMifflinEquation = SexForMifflinEquation.FEMALE,
    weight: float = 50,
    height: float = 150,
    goal: Goal = Goal.CUT,
    rate: float = -0.2,
) -> UserProfile:
    return UserProfile(30, height, weight, sex, ActivityLevel.MODERATELY_ACTIVE, goal, rate)


def test_bmi_boundaries_are_deterministic() -> None:
    below = _profile(weight=41.6, height=150)
    exact = _profile(weight=41.625, height=150)
    above = _profile(weight=41.7, height=150)

    assert (
        assess_target_eligibility(below, calculate_baseline_energy(below)).status
        is TargetEligibilityStatus.INELIGIBLE
    )
    assert (
        assess_target_eligibility(exact, calculate_baseline_energy(exact)).status
        is not TargetEligibilityStatus.INELIGIBLE
    )
    assert (
        assess_target_eligibility(above, calculate_baseline_energy(above)).status
        is not TargetEligibilityStatus.INELIGIBLE
    )


def test_near_underweight_protection_band_boundaries() -> None:
    lower_band = _profile(weight=44.9, height=150, rate=-0.3)
    upper_edge = _profile(weight=45.0, height=150, rate=-0.3)
    lower_result = assess_target_eligibility(lower_band, calculate_baseline_energy(lower_band))
    edge_result = assess_target_eligibility(upper_edge, calculate_baseline_energy(upper_edge))

    assert lower_result.bmi < 20.0
    assert TargetSafetyReason.NEAR_UNDERWEIGHT_PROTECTION_APPLIED in lower_result.reason_codes
    assert edge_result.bmi == pytest.approx(20.0)
    assert TargetSafetyReason.NEAR_UNDERWEIGHT_PROTECTION_APPLIED not in edge_result.reason_codes


def test_underweight_cut_is_ineligible_but_maintenance_and_gain_work() -> None:
    cut = _profile(weight=45, height=180)
    maintenance = replace(cut, goal=Goal.MAINTAIN, requested_weekly_change_kg=0)
    gain = replace(cut, goal=Goal.GAIN, requested_weekly_change_kg=0.2)

    assert (
        assess_target_eligibility(cut, calculate_baseline_energy(cut)).status
        is TargetEligibilityStatus.INELIGIBLE
    )
    assert (
        assess_target_eligibility(maintenance, calculate_baseline_energy(maintenance)).status
        is TargetEligibilityStatus.ELIGIBLE
    )
    assert (
        assess_target_eligibility(gain, calculate_baseline_energy(gain)).status
        is TargetEligibilityStatus.ELIGIBLE
    )


def test_adversarial_normal_bmi_case_never_returns_extreme_target() -> None:
    profile = _profile(weight=50, height=150, rate=-0.375)
    result = assess_target_eligibility(profile, calculate_baseline_energy(profile))

    assert result.status in (
        TargetEligibilityStatus.ELIGIBLE,
        TargetEligibilityStatus.CONSTRAINED,
    )
    assert result.effective_target_kcal_per_day is not None
    assert result.effective_target_kcal_per_day >= 1200


def test_female_and_male_floors_are_explicit() -> None:
    female = assess_target_eligibility(_profile(), calculate_baseline_energy(_profile()))
    male_profile = _profile(SexForMifflinEquation.MALE)
    male = assess_target_eligibility(male_profile, calculate_baseline_energy(male_profile))

    assert female.applied_calorie_floor_kcal_per_day == 1200
    assert male.applied_calorie_floor_kcal_per_day == 1500


def test_deficit_cap_can_bind_before_floor() -> None:
    profile = _profile(weight=70, height=170, rate=-0.5)
    result = assess_target_eligibility(
        profile,
        calculate_baseline_energy(profile),
        TargetSafetyConfig(maximum_deficit_fraction_of_tdee=0.2),
    )

    assert result.status is TargetEligibilityStatus.CONSTRAINED
    assert result.effective_deficit_kcal_per_day == pytest.approx(
        result.maximum_permitted_deficit_kcal_per_day
    )
    assert TargetSafetyReason.DEFICIT_LIMIT_APPLIED in result.reason_codes


def test_requested_target_exactly_at_floor_is_not_constrained_by_floor() -> None:
    profile = _profile(weight=70, height=170, rate=-0.2)
    baseline = calculate_baseline_energy(profile)
    config = TargetSafetyConfig(
        female_minimum_calories_kcal_per_day=baseline.estimated_tdee_kcal_per_day
        + profile.requested_weekly_change_kg * 7700 / 7
    )
    result = assess_target_eligibility(profile, baseline, config)

    assert result.effective_target_kcal_per_day == config.female_minimum_calories_kcal_per_day


def test_custom_configuration_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        TargetSafetyConfig(maximum_deficit_fraction_of_tdee=1)


def test_safety_rejects_invalid_inputs() -> None:
    profile = _profile()
    with pytest.raises(ValueError):
        assess_target_eligibility(object(), calculate_baseline_energy(profile))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assess_target_eligibility(profile, object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assess_target_eligibility(profile, calculate_baseline_energy(profile), object())  # type: ignore[arg-type]
