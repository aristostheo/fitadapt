"""Deterministic target-safety and weight-loss eligibility guardrails."""

from dataclasses import dataclass
from enum import StrEnum

from fitadapt.baseline.energy import BaselineEnergyEstimate
from fitadapt.baseline.targets import calculate_daily_calorie_adjustment
from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.profile import Goal, SexForMifflinEquation, UserProfile

TARGET_SAFETY_POLICY_VERSION = "target_safety_v1"
MINIMUM_BMI_FOR_WEIGHT_LOSS = 18.5


class TargetSafetyError(ValueError):
    """Raised when target-safety inputs or configuration are invalid."""


class TargetEligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    CONSTRAINED = "constrained"
    INELIGIBLE = "ineligible"


class TargetSafetyReason(StrEnum):
    BMI_BELOW_WEIGHT_LOSS_THRESHOLD = "bmi_below_weight_loss_threshold"
    DEFICIT_LIMIT_APPLIED = "maximum_deficit_limit_applied"
    CALORIE_FLOOR_APPLIED = "absolute_calorie_floor_applied"
    REQUESTED_RATE_REDUCED = "requested_rate_reduced"
    WEIGHT_LOSS_NOT_REQUESTED = "weight_loss_not_requested"
    SAFETY_TARGET_UNAVAILABLE = "safety_target_unavailable"
    NEAR_UNDERWEIGHT_PROTECTION_APPLIED = "near_underweight_protection_applied"


@dataclass(frozen=True, slots=True)
class TargetSafetyConfig:
    """Conservative product guardrails, not individualized medical prescriptions."""

    policy_version: str = TARGET_SAFETY_POLICY_VERSION
    minimum_bmi_for_weight_loss: float = MINIMUM_BMI_FOR_WEIGHT_LOSS
    female_minimum_calories_kcal_per_day: float = 1200.0
    male_minimum_calories_kcal_per_day: float = 1500.0
    maximum_deficit_fraction_of_tdee: float = 0.25
    near_underweight_bmi_upper_bound: float = 20.0
    near_underweight_maximum_deficit_fraction_of_tdee: float = 0.10

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise TargetSafetyError("policy_version must be a non-empty string.")
        for name in (
            "minimum_bmi_for_weight_loss",
            "female_minimum_calories_kcal_per_day",
            "male_minimum_calories_kcal_per_day",
            "maximum_deficit_fraction_of_tdee",
            "near_underweight_bmi_upper_bound",
            "near_underweight_maximum_deficit_fraction_of_tdee",
        ):
            value = validate_finite_number(
                getattr(self, name), field_name=name, error_type=TargetSafetyError
            )
            if value <= 0:
                raise TargetSafetyError(f"{name} must be positive.")
            object.__setattr__(self, name, value)
        if self.maximum_deficit_fraction_of_tdee >= 1:
            raise TargetSafetyError("maximum_deficit_fraction_of_tdee must be below 1.")
        if self.near_underweight_bmi_upper_bound <= self.minimum_bmi_for_weight_loss:
            raise TargetSafetyError(
                "near_underweight_bmi_upper_bound must exceed minimum_bmi_for_weight_loss."
            )
        if self.near_underweight_maximum_deficit_fraction_of_tdee >= 1:
            raise TargetSafetyError(
                "near_underweight_maximum_deficit_fraction_of_tdee must be below 1."
            )


@dataclass(frozen=True, slots=True)
class TargetEligibilityAssessment:
    status: TargetEligibilityStatus
    bmi: float
    minimum_bmi_for_weight_loss: float
    near_underweight_bmi_upper_bound: float
    near_underweight_maximum_deficit_fraction_of_tdee: float
    baseline_tdee_kcal_per_day: float
    requested_target_kcal_per_day: float
    effective_target_kcal_per_day: float | None
    applied_calorie_floor_kcal_per_day: float | None
    maximum_permitted_deficit_kcal_per_day: float | None
    requested_deficit_kcal_per_day: float
    effective_deficit_kcal_per_day: float | None
    effective_weekly_change_kg: float | None
    requested_weekly_change_kg: float
    goal: Goal
    reason_codes: tuple[TargetSafetyReason, ...]
    policy_version: str
    assumptions: tuple[str, ...]

    @property
    def weight_loss_target_available(self) -> bool:
        return self.status is not TargetEligibilityStatus.INELIGIBLE


def assess_target_eligibility(
    profile: UserProfile,
    baseline_energy: BaselineEnergyEstimate,
    config: TargetSafetyConfig | None = None,
) -> TargetEligibilityAssessment:
    """Assess and, when possible, constrain the requested calorie target."""
    if not isinstance(profile, UserProfile):
        raise TargetSafetyError("profile must be a UserProfile.")
    if not isinstance(baseline_energy, BaselineEnergyEstimate):
        raise TargetSafetyError("baseline_energy must be a BaselineEnergyEstimate.")
    effective = config or TargetSafetyConfig()
    if not isinstance(effective, TargetSafetyConfig):
        raise TargetSafetyError("config must be a TargetSafetyConfig or None.")
    height_m = profile.height_cm / 100.0
    bmi = profile.weight_kg / (height_m * height_m)
    tdee = float(baseline_energy.estimated_tdee_kcal_per_day)
    requested_target = tdee + calculate_daily_calorie_adjustment(profile)
    requested_deficit = max(0.0, tdee - requested_target)
    if profile.goal is not Goal.CUT:
        return _assessment(
            effective,
            profile,
            bmi,
            tdee,
            requested_target,
            requested_target,
            None,
            None,
            requested_deficit,
            max(0.0, requested_target - tdee),
            (TargetSafetyReason.WEIGHT_LOSS_NOT_REQUESTED,),
        )
    floor = (
        effective.female_minimum_calories_kcal_per_day
        if profile.sex_for_mifflin_equation is SexForMifflinEquation.FEMALE
        else effective.male_minimum_calories_kcal_per_day
    )
    near_underweight = bmi < effective.near_underweight_bmi_upper_bound
    deficit_fraction = (
        effective.near_underweight_maximum_deficit_fraction_of_tdee
        if near_underweight
        else effective.maximum_deficit_fraction_of_tdee
    )
    maximum_deficit = tdee * deficit_fraction
    if bmi < effective.minimum_bmi_for_weight_loss:
        return _assessment(
            effective,
            profile,
            bmi,
            tdee,
            requested_target,
            None,
            floor,
            maximum_deficit,
            requested_deficit,
            None,
            (
                TargetSafetyReason.BMI_BELOW_WEIGHT_LOSS_THRESHOLD,
                TargetSafetyReason.SAFETY_TARGET_UNAVAILABLE,
            ),
            status=TargetEligibilityStatus.INELIGIBLE,
        )
    effective_target = max(requested_target, tdee - maximum_deficit, floor)
    reasons: list[TargetSafetyReason] = []
    if effective_target > requested_target:
        reasons.append(TargetSafetyReason.REQUESTED_RATE_REDUCED)
    if requested_target < tdee - maximum_deficit:
        reasons.append(TargetSafetyReason.DEFICIT_LIMIT_APPLIED)
    if near_underweight and requested_target < tdee - maximum_deficit:
        reasons.append(TargetSafetyReason.NEAR_UNDERWEIGHT_PROTECTION_APPLIED)
    if requested_target < floor:
        reasons.append(TargetSafetyReason.CALORIE_FLOOR_APPLIED)
    status = TargetEligibilityStatus.CONSTRAINED if reasons else TargetEligibilityStatus.ELIGIBLE
    effective_deficit = max(0.0, tdee - effective_target)
    effective_weekly = effective_deficit * 7.0 / 7700.0
    return _assessment(
        effective,
        profile,
        bmi,
        tdee,
        requested_target,
        effective_target,
        floor,
        maximum_deficit,
        requested_deficit,
        effective_deficit,
        tuple(reasons),
        status=status,
        effective_weekly_change_kg=-effective_weekly,
    )


def _assessment(
    config: TargetSafetyConfig,
    profile: UserProfile,
    bmi: float,
    tdee: float,
    requested_target: float,
    effective_target: float | None,
    floor: float | None,
    maximum_deficit: float | None,
    requested_deficit: float,
    effective_deficit: float | None,
    reasons: tuple[TargetSafetyReason, ...],
    *,
    status: TargetEligibilityStatus = TargetEligibilityStatus.ELIGIBLE,
    effective_weekly_change_kg: float | None = None,
) -> TargetEligibilityAssessment:
    if effective_target is not None and effective_weekly_change_kg is None:
        effective_weekly_change_kg = (effective_target - tdee) * 7.0 / 7700.0
    return TargetEligibilityAssessment(
        status=status,
        bmi=float(bmi),
        minimum_bmi_for_weight_loss=config.minimum_bmi_for_weight_loss,
        near_underweight_bmi_upper_bound=config.near_underweight_bmi_upper_bound,
        near_underweight_maximum_deficit_fraction_of_tdee=(
            config.near_underweight_maximum_deficit_fraction_of_tdee
        ),
        baseline_tdee_kcal_per_day=tdee,
        requested_target_kcal_per_day=float(requested_target),
        effective_target_kcal_per_day=(
            None if effective_target is None else float(effective_target)
        ),
        applied_calorie_floor_kcal_per_day=floor,
        maximum_permitted_deficit_kcal_per_day=maximum_deficit,
        requested_deficit_kcal_per_day=float(requested_deficit),
        effective_deficit_kcal_per_day=(
            None if effective_deficit is None else float(effective_deficit)
        ),
        effective_weekly_change_kg=effective_weekly_change_kg,
        requested_weekly_change_kg=profile.requested_weekly_change_kg,
        goal=profile.goal,
        reason_codes=reasons,
        policy_version=config.policy_version,
        assumptions=(
            "Safety thresholds are conservative FitAdapt product guardrails, not individualized "
            "medical advice.",
            "BMI is a screening calculation and is not a diagnosis.",
            "Weight-loss eligibility is assessed before target and macro feasibility composition.",
        ),
    )
