"""CP35 hostile, end-to-end synthetic validation of the frozen FitAdapt product path.

All generated data are in-model synthetic evaluation, not real user records or physiology.
The simulator calls the public profile-intelligence composition and accepts CP30-eligible
events as a caller would. It intentionally makes no production-policy changes.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from statistics import median
from typing import Any

from fitadapt.adaptive.tdee import AdaptiveTdeeConfig, estimate_adaptive_tdee
from fitadapt.analysis.trends import analyze_observation_trends
from fitadapt.baseline.energy import calculate_baseline_energy
from fitadapt.domain.observation import DailyObservation, ObservationValidationError
from fitadapt.domain.profile import (
    ActivityLevel,
    Goal,
    ProfileValidationError,
    SexForMifflinEquation,
    UserProfile,
)
from fitadapt.personalization.adaptation import (
    PlanAdaptationAction,
    PlanAdaptationEvent,
    PlanAdaptationSource,
    ProposalReviewConfirmation,
    evaluate_plan_adaptation,
)
from fitadapt.personalization.decisions import (
    DecisionActivationReadiness,
    RecommendationDecisionConfig,
    RecommendationDecisionType,
    decide_plan_adjustment,
)
from fitadapt.personalization.history import build_recommendation_history
from fitadapt.personalization.integration import IntegrationAppStatus
from fitadapt.personalization.intelligence import (
    _decrease_horizon_disagreement,
    _integration_status,
)
from fitadapt.personalization.macros import (
    MacroCalorieSource,
    MacroStrategy,
    NutritionPreferences,
    calculate_personalized_macro_plan,
)
from fitadapt.personalization.outcomes import assess_plan_outcome
from fitadapt.personalization.safety import (
    TargetEligibilityStatus,
    assess_target_eligibility,
)

CP35_PROTOCOL_VERSION = "cp35a_release_policy_v2"
CP35_DEVELOPMENT_SEEDS = range(140000, 140016)
CP35_HELD_OUT_SEEDS = range(150000, 150016)
CP35_SEED_DESCRIPTION = "development:140000..140015; held_out:150000..150015"
CP35_EVALUATION_DAYS = 84
CP35_CHECKPOINT_INDICES = (27, 34, 41, 48, 55, 62, 69, 76, 83)
CP35_MACRO_PREFERENCES = NutritionPreferences(MacroStrategy.BALANCED)


@dataclass(frozen=True, slots=True)
class FrozenCriterion:
    criterion_id: str
    description: str
    limit: float
    comparator: str


# Frozen before held-out evaluation. Fractions use user-level denominators unless noted.
CP35_FROZEN_CRITERIA = (
    FrozenCriterion(
        "ordinary_false_decrease", "Ordinary false CP29 decrease proposals", 0.10, "max"
    ),
    FrozenCriterion(
        "ordinary_false_increase", "Ordinary false CP29 increase proposals", 0.10, "max"
    ),
    FrozenCriterion(
        "ordinary_false_activation",
        "Ordinary false CP30 activations across stationary controls",
        0.10,
        "max",
    ),
    FrozenCriterion(
        "plus_minus_300_proposal_detection",
        "Correct CP29 proposal by day 56 for each clean +/-300 case",
        0.60,
        "min",
    ),
    FrozenCriterion(
        "opposite_direction_activation",
        "Opposite activation-ready action on clean +/-300 changes",
        0.05,
        "max",
    ),
    FrozenCriterion("proposal_latency", "Median correct +/-300 proposal latency", 56.0, "max_days"),
    FrozenCriterion(
        "activation_reversal",
        "Noisy/transient users with an automatic reversal activation",
        0.10,
        "max",
    ),
    FrozenCriterion(
        "stationary_activation_count",
        "Mean activations per 12 weeks in ordinary stationary cases",
        2.0,
        "max",
    ),
    FrozenCriterion(
        "ambiguous_automatic_decrease",
        "Automatic decrease activations in declared ambiguity scenarios",
        0.0,
        "max",
    ),
    FrozenCriterion(
        "review_ready_decrease",
        "Activation-ready CP29 decreases (decreases require explicit review)",
        0.0,
        "max",
    ),
    FrozenCriterion(
        "review_required_genuine_decrease",
        "Genuine -300 decrease proposals surfaced for explicit review",
        0.60,
        "min",
    ),
    FrozenCriterion(
        "activation_ready_increase",
        "Positive 300 kcal/day change activation-ready by day 56",
        0.60,
        "min",
    ),
    FrozenCriterion(
        "indefinite_inert_proposal",
        "Clean +/-300 cases with no directional proposal by day 84",
        0.20,
        "max",
    ),
    FrozenCriterion(
        "safety_violations", "Safety-bound or ineligible-target activation violations", 0.0, "max"
    ),
    FrozenCriterion(
        "missed_large_change",
        "No CP29 proposal for true +/-300 TDEE cases by day 84",
        0.40,
        "max",
    ),
    FrozenCriterion(
        "indefinite_defer", "True +/-300 cases deferred at every checkpoint", 0.20, "max"
    ),
    FrozenCriterion(
        "transient_recovery", "Median status recovery after transient disturbance", 28.0, "max_days"
    ),
)


@dataclass(frozen=True, slots=True)
class HostileScenario:
    name: str
    category: str
    expected_direction: int | None = None
    tdee_delta: float = 0.0
    change_day: int = 0
    gradual_tdee_days: int = 0
    goal: Goal = Goal.CUT
    requested_weekly_change_kg: float = -0.4
    adherence_offset: float = 0.0
    adherence_drift: float = 0.0
    logging_bias: float = 0.0
    logging_bias_drift: float = 0.0
    bias_start_day: int = 28
    missing_pattern: str = ""
    water_pattern: str = ""
    ambiguous: bool = False
    profile_weight_kg: float = 80.0
    height_cm: float = 180.0


@dataclass(frozen=True, slots=True)
class ScenarioMetrics:
    name: str
    category: str
    users: int
    checks: int
    cp29_hold_rate: float
    cp29_defer_rate: float
    cp29_increase_rate: float
    cp29_decrease_rate: float
    cp30_activate_rate: float
    cp30_defer_rate: float
    cp30_suppress_rate: float
    review_required_decrease_proposal_rate: float
    review_required_decrease_user_rate: float
    activation_ready_decrease_proposal_rate: float
    activation_ready_increase_proposal_rate: float
    automatic_decrease_activation_rate: float
    false_activation_rate: float
    activation_ready_increase_by56_rate: float
    reversal_proposal_rate: float
    reversal_pending_rate: float
    confirmed_reversal_rate: float
    review_accepted_decrease_activation_rate: float
    integration_status_rates: tuple[tuple[str, float], ...]
    false_increase_rate: float
    false_decrease_rate: float
    false_change_rate: float
    correct_direction_rate: float | None
    opposite_direction_rate: float | None
    missed_change_rate: float | None
    median_cp29_proposal_day: float | None
    median_cp30_activation_day: float | None
    median_transient_recovery_days: float | None
    mean_activations_per_user_12_weeks: float
    direction_reversal_rate: float
    repeated_same_direction_rate: float
    indefinitely_inert_rate: float
    all_checkpoint_deferred_rate: float
    ambiguity_decrease_activation_rate: float
    safety_violation_rate: float


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    description: str
    observed: float | None
    limit: float
    comparator: str
    passed: bool


@dataclass(frozen=True, slots=True)
class GateTradeoff:
    scenario: str
    users: int
    proposal_rate_28_day: float
    proposal_rate_42_day: float
    activation_rate_28_day: float
    activation_rate_42_day: float
    median_proposal_day_28_day: float | None
    median_proposal_day_42_day: float | None
    median_activation_day_28_day: float | None
    median_activation_day_42_day: float | None
    false_decreases_prevented: int
    plateau_days_28_day: float | None
    plateau_days_42_day: float | None


@dataclass(frozen=True, slots=True)
class ReviewAcceptanceTradeoff:
    scenario: str
    users: int
    decrease_proposal_rate: float
    review_required_rate: float
    activation_ready_without_review_rate: float
    caller_confirmed_activation_rate: float
    median_proposal_latency_days: float | None
    median_confirmed_activation_latency_days: float | None
    ambiguous_caller_confirmed_activation_rate: float


@dataclass(frozen=True, slots=True)
class CP35Report:
    protocol_version: str
    seed_set: str
    seed_description: str
    seeds: tuple[int, ...]
    evaluation_days: int
    checkpoint_days: tuple[int, ...]
    criteria: tuple[CriterionResult, ...]
    scenarios: tuple[ScenarioMetrics, ...]
    gate_tradeoffs: tuple[GateTradeoff, ...]
    review_acceptance_tradeoffs: tuple[ReviewAcceptanceTradeoff, ...]
    overall_cp29_rates: tuple[tuple[str, float], ...]
    overall_cp30_rates: tuple[tuple[str, float], ...]
    overall_app_status_rates: tuple[tuple[str, float], ...]
    external_audit: tuple[tuple[str, str, bool], ...]
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _UserRun:
    metrics: ScenarioMetrics
    cp29_directions: tuple[int, ...]
    cp30_directions: tuple[int, ...]
    safety_violations: int
    proposal_events: tuple[tuple[int, int], ...]
    activation_events: tuple[tuple[int, int], ...]
    review_required_proposals: int = 0
    ready_decrease_proposals: int = 0
    automatic_decrease_activations: int = 0
    false_activations: int = 0
    ready_increase_proposals: int = 0
    reversal_proposals: int = 0
    pending_reversals: int = 0
    confirmed_reversals: int = 0
    review_accepted_decreases: int = 0


@dataclass(frozen=True, slots=True)
class _Checkpoint:
    adaptive_tdee: object
    target_safety: object
    plan_outcome: object
    recommendation_decision: object
    plan_adaptation: object
    integration_status: object


def cp35_scenarios() -> tuple[HostileScenario, ...]:
    """Return the frozen, named hostile matrix; no random scenario selection is used."""
    base = [
        HostileScenario("stationary_clean", "stationary"),
        HostileScenario("scale_noise", "stationary"),
        HostileScenario("intake_variation", "stationary", adherence_offset=0.0),
        HostileScenario("autocorrelated_water", "water", water_pattern="autocorrelated"),
        HostileScenario("logging_underreport_step", "logging_bias", logging_bias=350),
        HostileScenario("logging_overreport_step", "logging_bias", logging_bias=-350),
        HostileScenario("logging_bias_drift", "logging_bias", logging_bias_drift=300),
        HostileScenario("cut_adherence_drift", "adherence", adherence_drift=350),
        HostileScenario(
            "gain_adherence_drift",
            "adherence",
            goal=Goal.GAIN,
            requested_weekly_change_kg=0.3,
            adherence_drift=-300,
        ),
        HostileScenario("inconsistent_adherence", "adherence", adherence_offset=0),
        HostileScenario("missing_weekends", "missing_data", missing_pattern="weekends"),
        HostileScenario(
            "missing_clustered_weights", "missing_data", missing_pattern="weight_cluster"
        ),
        HostileScenario(
            "missing_after_high_intake",
            "missing_data",
            adherence_offset=300,
            missing_pattern="after_high_intake",
        ),
        HostileScenario(
            "missing_plan_transition", "missing_data", missing_pattern="transition_gap"
        ),
        HostileScenario("sparse_regular", "missing_data", missing_pattern="every_other_day"),
        HostileScenario("water_rebound", "water", water_pattern="rebound"),
        HostileScenario("illness_like_disturbance", "water", water_pattern="illness"),
        HostileScenario("sodium_carb_weight_spike", "water", water_pattern="spike"),
        HostileScenario(
            "persistent_water_drift", "ambiguity", water_pattern="persistent_drift", ambiguous=True
        ),
        HostileScenario("tdee_minus_200", "true_tdee_change", -1, -200, change_day=28),
        HostileScenario("tdee_minus_300", "true_tdee_change", -1, -300, change_day=28),
        HostileScenario("tdee_plus_200", "true_tdee_change", 1, 200, change_day=28),
        HostileScenario("tdee_plus_300", "true_tdee_change", 1, 300, change_day=28),
        HostileScenario(
            "gradual_tdee_minus_300",
            "true_tdee_change",
            -1,
            -300,
            change_day=28,
            gradual_tdee_days=28,
        ),
        HostileScenario(
            "tdee_decline_with_water", "combined", -1, -300, water_pattern="autocorrelated"
        ),
        HostileScenario(
            "tdee_decline_underreporting",
            "combined",
            -1,
            -300,
            adherence_offset=250,
            logging_bias=250,
            ambiguous=True,
        ),
        HostileScenario(
            "poor_adherence_with_water",
            "combined",
            adherence_drift=300,
            water_pattern="autocorrelated",
            ambiguous=True,
        ),
        HostileScenario(
            "intake_regime_change_missing",
            "combined",
            adherence_offset=300,
            bias_start_day=28,
            missing_pattern="transition_gap",
        ),
        HostileScenario(
            "plateau_noise_partial_logs",
            "combined",
            missing_pattern="every_other_day",
            water_pattern="autocorrelated",
        ),
        HostileScenario(
            "repeated_slow_progress_near_floor",
            "safety",
            -1,
            -200,
            requested_weekly_change_kg=-0.39,
            profile_weight_kg=53,
            height_cm=160,
        ),
        HostileScenario(
            "repeated_proposals_near_bmi_band",
            "safety",
            -1,
            -200,
            requested_weekly_change_kg=-0.45,
            profile_weight_kg=62,
            height_cm=180,
        ),
        HostileScenario(
            "profile_update_below_bmi_18_5", "safety", profile_weight_kg=80.0, height_cm=180
        ),
    ]
    return tuple(base)


def run_cp35_hostile_study(seeds: tuple[int, ...] | range, *, seed_set: str) -> CP35Report:
    """Run the complete 12-week pipeline for each frozen scenario and deterministic seed."""
    cohort = tuple(seeds)
    _validate_seeds(cohort, seed_set)
    scenario_runs = tuple(
        (scenario, tuple(_simulate_user(scenario, seed) for seed in cohort))
        for scenario in cp35_scenarios()
    )
    summaries = tuple(_aggregate_scenario(scenario, runs) for scenario, runs in scenario_runs)
    gate_tradeoffs = _run_gate_tradeoffs(cohort)
    review_acceptance_tradeoffs = _run_review_acceptance_tradeoffs(cohort)
    criteria = _evaluate_criteria(summaries)
    app_counts: Counter[str] = Counter()
    total_user_checks = sum(item.checks * item.users for item in summaries)
    for item in summaries:
        for status, rate in item.integration_status_rates:
            app_counts[status] += round(rate * item.checks * item.users)
    # Aggregate enum rates from scenario rows to keep the public report serialization compact.
    cp29_rates = tuple(
        (
            name,
            sum(getattr(row, field) * row.checks * row.users for row in summaries)
            / max(total_user_checks, 1),
        )
        for name, field in (
            ("hold", "cp29_hold_rate"),
            ("defer", "cp29_defer_rate"),
            ("increase", "cp29_increase_rate"),
            ("decrease", "cp29_decrease_rate"),
        )
    )
    cp30_rates = tuple(
        (
            name,
            sum(getattr(row, field) * row.checks * row.users for row in summaries)
            / max(total_user_checks, 1),
        )
        for name, field in (
            ("activate", "cp30_activate_rate"),
            ("defer", "cp30_defer_rate"),
            ("suppress", "cp30_suppress_rate"),
            ("review_required", "review_required_decrease_proposal_rate"),
            ("reversal_pending", "reversal_pending_rate"),
        )
    )
    app_total = sum(app_counts.values())
    app_rates = tuple(sorted((key, value / app_total) for key, value in app_counts.items()))
    return CP35Report(
        CP35_PROTOCOL_VERSION,
        seed_set,
        CP35_SEED_DESCRIPTION,
        cohort,
        CP35_EVALUATION_DAYS,
        tuple(index + 1 for index in CP35_CHECKPOINT_INDICES),
        criteria,
        summaries,
        gate_tradeoffs,
        review_acceptance_tradeoffs,
        cp29_rates,
        cp30_rates,
        app_rates,
        _external_style_audit(),
        (
            "All results are in-model synthetic evaluation; no external or clinical validity "
            "is implied.",
            "Sixteen users per scenario make rates coarse and do not establish population "
            "performance.",
            "An accepted CP30 activation event is replayed as caller-owned history at the next "
            "checkpoint.",
            "The examples directory contains two demonstration rows, not real historical log data.",
            "The 28-day comparison changes only the decrease evidence-span gate in this harness.",
        ),
    )


def report_json(report: CP35Report) -> str:
    """Serialize an aggregate report without exposing per-day synthetic user traces."""
    return json.dumps(asdict(report), indent=2, default=_json_default)


def _json_default(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _simulate_user(
    scenario: HostileScenario,
    seed: int,
    decrease_gate_days: int = 42,
    *,
    confirm_review_required: bool = False,
) -> _UserRun:
    profile = UserProfile(
        30,
        scenario.height_cm,
        scenario.profile_weight_kg,
        SexForMifflinEquation.MALE,
        ActivityLevel.MODERATELY_ACTIVE,
        scenario.goal,
        scenario.requested_weekly_change_kg,
    )
    baseline = calculate_baseline_energy(profile)
    safety = assess_target_eligibility(profile, baseline)
    active_target = safety.effective_target_kcal_per_day or baseline.estimated_tdee_kcal_per_day
    initial_target = active_target
    tissue_weight = scenario.profile_weight_kg
    water = 0.0
    observations: list[DailyObservation] = []
    history: tuple[PlanAdaptationEvent, ...] = ()
    activation_days: list[int] = []
    active_directions: list[int] = []
    proposal_events: list[tuple[int, int]] = []
    activation_events: list[tuple[int, int]] = []
    cp29_directions: list[int] = []
    cp30_directions: list[int] = []
    app_statuses: Counter[str] = Counter()
    safety_violations = ambiguous_decrease_activations = 0
    review_required_proposals = ready_decrease_proposals = 0
    ready_increase_proposals = 0
    automatic_decrease_activations = reversal_proposals = 0
    false_activations = 0
    pending_reversals = confirmed_reversals = review_accepted_decreases = 0
    cp29_days: list[int] = []
    recovery_days: list[int] = []
    transient_end = _transient_end_day(scenario.water_pattern)
    decision_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    last_checkpoint_result: _Checkpoint | None = None

    for day_index in range(CP35_EVALUATION_DAYS):
        day = date(2025, 1, 1) + timedelta(days=day_index)
        actual_tdee = (
            initial_target
            if scenario.name == "plateau_noise_partial_logs"
            else _actual_tdee(scenario, baseline.estimated_tdee_kcal_per_day, day_index)
        )
        adherence = _adherence_delta(scenario, active_target, day_index, seed)
        actual_intake = max(0.0, active_target + adherence)
        bias = _logging_bias(scenario, day_index)
        logged_intake = max(0.0, actual_intake - bias)
        tissue_weight += (actual_intake - actual_tdee) / 7700.0
        water = _water_value(scenario, day_index, water, seed)
        scale_noise = random.Random(
            seed * 1_000_003 + day_index * 31 + _stable_name_code(scenario.name)
        ).gauss(0, 0.25)
        measured_weight = max(20.0, tissue_weight + water + scale_noise)
        record_weight, record_intake = _logging_availability(
            scenario, day_index, actual_intake, active_target, activation_days
        )
        observations.append(
            DailyObservation(
                day,
                measured_weight if record_weight else None,
                logged_intake if record_intake else None,
                steps=7000,
            )
        )
        if scenario.name == "profile_update_below_bmi_18_5" and day_index >= 55:
            profile = replace(profile, weight_kg=18.4 * (profile.height_cm / 100) ** 2)

        if day_index not in CP35_CHECKPOINT_INDICES:
            continue
        result = _evaluate_checkpoint(
            profile,
            observations,
            history,
            active_target,
            decrease_gate_days,
            confirm_review_required=confirm_review_required,
        )
        last_checkpoint_result = result
        decision = result.recommendation_decision.decision.value
        action = result.plan_adaptation.action
        status = result.integration_status.app_status.value
        decision_counts[decision] += 1
        action_counts[action.value] += 1
        app_statuses[status] += 1
        decision_direction = _direction(decision)
        if decision_direction:
            cp29_directions.append(decision_direction)
            proposal_events.append((decision_direction, day_index + 1))
            cp29_days.append(day_index + 1)
            if (
                decision == RecommendationDecisionType.DECREASE.value
                and result.recommendation_decision.activation_readiness
                is DecisionActivationReadiness.REVIEW_REQUIRED
            ):
                review_required_proposals += 1
            if (
                decision == RecommendationDecisionType.DECREASE.value
                and result.recommendation_decision.activation_readiness
                is DecisionActivationReadiness.READY
            ):
                ready_decrease_proposals += 1
            if (
                decision == RecommendationDecisionType.INCREASE.value
                and result.recommendation_decision.activation_readiness
                is DecisionActivationReadiness.READY
            ):
                ready_increase_proposals += 1
            if active_directions and decision_direction != active_directions[-1]:
                reversal_proposals += 1
        if action is PlanAdaptationAction.REVERSAL_PENDING:
            pending_reversals += 1
        if action is PlanAdaptationAction.ACTIVATE and any(
            reason.value == "reversal_confirmed" for reason in result.plan_adaptation.reason_codes
        ):
            confirmed_reversals += 1
        if action is PlanAdaptationAction.ACTIVATE:
            delta = result.plan_adaptation.calorie_delta_kcal_per_day
            direction = 1 if delta > 0 else -1
            active_directions.append(direction)
            cp30_directions.append(direction)
            activation_days.append(day_index)
            activation_events.append((direction, day_index + 1))
            if scenario.expected_direction is not None:
                if (
                    direction != scenario.expected_direction
                    or day_index + 1 <= scenario.change_day + 1
                ):
                    false_activations += 1
            else:
                false_activations += 1
            reviewed = any(
                reason.value == "user_review_accepted"
                for reason in result.plan_adaptation.reason_codes
            )
            if direction < 0 and reviewed:
                review_accepted_decreases += 1
            if direction < 0 and not reviewed:
                automatic_decrease_activations += 1
            if scenario.ambiguous and direction < 0 and not reviewed:
                ambiguous_decrease_activations += 1
            next_target = result.plan_adaptation.next_active_target_kcal_per_day
            safety_now = result.target_safety
            floor = safety_now.applied_calorie_floor_kcal_per_day
            deficit_cap = safety_now.maximum_permitted_deficit_kcal_per_day
            violates = safety_now.status is TargetEligibilityStatus.INELIGIBLE
            violates |= floor is not None and next_target < floor
            violates |= (
                deficit_cap is not None
                and next_target < safety_now.baseline_tdee_kcal_per_day - deficit_cap
            )
            safety_violations += violates
        if transient_end is not None and day_index + 1 > transient_end and not recovery_days:
            if (
                result.integration_status.app_status
                is IntegrationAppStatus.PLAN_REMAINS_APPROPRIATE
            ):
                recovery_days.append(day_index + 1 - transient_end)
        history = result.plan_adaptation.adaptation_history
        active_target = result.plan_adaptation.next_active_target_kcal_per_day

    assert last_checkpoint_result is not None
    directions = active_directions
    reversals = sum(left != right for left, right in zip(directions, directions[1:], strict=False))
    expected = scenario.expected_direction
    correct = expected is None or any(
        direction == expected and 0 <= day - scenario.change_day - 1 <= 56
        for direction, day in proposal_events
    )
    activation_ready_increase_by56 = expected == 1 and any(
        direction == 1 and 0 <= day - scenario.change_day - 1 <= 56
        for direction, day in activation_events
    )
    missed = expected is not None and not any(
        direction == expected and day > scenario.change_day + 1
        for direction, day in proposal_events
    )
    activation_latency = (
        None
        if expected is None
        else min(
            (
                day - scenario.change_day - 1
                for direction, day in activation_events
                if direction == expected and day > scenario.change_day + 1
            ),
            default=None,
        )
    )
    proposal_latency = (
        None
        if expected is None
        else min(
            (
                day - scenario.change_day - 1
                for direction, day in proposal_events
                if direction == expected and day > scenario.change_day + 1
            ),
            default=None,
        )
    )
    checks = len(CP35_CHECKPOINT_INDICES)
    decision_rates = {name: decision_counts[name] / checks for name in RecommendationDecisionType}
    action_rates = {name.value: action_counts[name.value] / checks for name in PlanAdaptationAction}
    false_increases = sum(direction > 0 for direction in cp29_directions) if expected is None else 0
    false_decreases = sum(direction < 0 for direction in cp29_directions) if expected is None else 0
    if expected is not None:
        false_increases = sum(
            direction > 0 and (direction != expected or day <= scenario.change_day + 1)
            for direction, day in proposal_events
        )
        false_decreases = sum(
            direction < 0 and (direction != expected or day <= scenario.change_day + 1)
            for direction, day in proposal_events
        )
    false_changes = false_increases + false_decreases
    app_rates = tuple(
        (item.value, app_statuses[item.value] / checks) for item in IntegrationAppStatus
    )
    metrics = ScenarioMetrics(
        scenario.name,
        scenario.category,
        1,
        checks,
        decision_rates[RecommendationDecisionType.HOLD.value],
        decision_rates[RecommendationDecisionType.DEFER.value],
        decision_rates[RecommendationDecisionType.INCREASE.value],
        decision_rates[RecommendationDecisionType.DECREASE.value],
        action_rates[PlanAdaptationAction.ACTIVATE.value],
        action_rates[PlanAdaptationAction.DEFER.value],
        action_rates[PlanAdaptationAction.SUPPRESS.value],
        review_required_proposals / checks,
        float(review_required_proposals > 0),
        ready_decrease_proposals / checks,
        ready_increase_proposals / checks,
        automatic_decrease_activations / checks,
        false_activations / checks,
        float(activation_ready_increase_by56),
        reversal_proposals / checks,
        pending_reversals / checks,
        confirmed_reversals / checks,
        review_accepted_decreases / checks,
        app_rates,
        false_increases / checks,
        false_decreases / checks,
        false_changes / checks,
        None if expected is None else float(correct),
        None
        if expected is None
        else float(
            any(
                direction != expected or day <= scenario.change_day + 1
                for direction, day in activation_events
            )
        ),
        None if expected is None else float(missed),
        None if proposal_latency is None else float(proposal_latency),
        None if activation_latency is None else float(activation_latency),
        None
        if transient_end is None
        else float(recovery_days[0] if recovery_days else CP35_EVALUATION_DAYS - transient_end + 1),
        float(len(activation_days)),
        float(reversals > 0),
        (
            0.0
            if len(directions) < 2
            else sum(left == right for left, right in zip(directions, directions[1:], strict=False))
            / (len(directions) - 1)
        ),
        float(expected is not None and len(cp29_directions) == 0),
        float(decision_counts[RecommendationDecisionType.DEFER.value] == checks),
        float(ambiguous_decrease_activations > 0),
        float(safety_violations > 0),
    )
    return _UserRun(
        metrics,
        tuple(cp29_directions),
        tuple(cp30_directions),
        safety_violations,
        tuple(proposal_events),
        tuple(activation_events),
        review_required_proposals,
        ready_decrease_proposals,
        automatic_decrease_activations,
        false_activations,
        ready_increase_proposals,
        reversal_proposals,
        pending_reversals,
        confirmed_reversals,
        review_accepted_decreases,
    )


def _evaluate_checkpoint(
    profile: UserProfile,
    observations: list[DailyObservation],
    history: tuple[PlanAdaptationEvent, ...],
    active_target: float,
    decrease_gate_days: int,
    *,
    confirm_review_required: bool = False,
) -> _Checkpoint:
    """Compose the existing public pipeline stages once for a simulation checkpoint."""
    trends = analyze_observation_trends(tuple(observations))
    adaptive = estimate_adaptive_tdee(trends, AdaptiveTdeeConfig())
    baseline = calculate_baseline_energy(profile)
    safety = assess_target_eligibility(profile, baseline)
    active_plan = calculate_personalized_macro_plan(
        profile,
        active_target,
        MacroCalorieSource.BASELINE,
        CP35_MACRO_PREFERENCES,
    )
    outcome = assess_plan_outcome(profile, tuple(observations), active_target)
    config = replace(
        RecommendationDecisionConfig(), minimum_decrease_evidence_span_days=decrease_gate_days
    )
    weight_dates = tuple(
        item.observed_on for item in observations if item.body_weight_kg is not None
    )
    span = 0 if len(weight_dates) < 2 else (max(weight_dates) - min(weight_dates)).days + 1
    decision = decide_plan_adjustment(
        profile,
        active_plan.calorie_target_kcal_per_day,
        active_plan,
        outcome,
        adaptive.adaptive_tdee_kcal_per_day,
        config=config,
        target_safety=safety,
        adaptive_tdee_stability=adaptive.stability,
        adaptive_tdee_reason_codes=adaptive.reason_codes,
        decrease_evidence_span_days=span,
        adaptive_tdee_horizon_disagreement_kcal_per_day=(
            _decrease_horizon_disagreement(trends, adaptive.config)
        ),
    )
    proposed = None
    if decision.numerical_change_proposed:
        proposed = calculate_personalized_macro_plan(
            profile,
            decision.proposed_calorie_target_kcal_per_day,
            active_plan.calorie_source,
            CP35_MACRO_PREFERENCES,
        )
    effective_date = observations[-1].observed_on if observations else None
    review_confirmation = (
        ProposalReviewConfirmation(
            effective_date,
            decision.proposed_calorie_target_kcal_per_day,
        )
        if confirm_review_required
        and effective_date is not None
        and decision.activation_readiness is DecisionActivationReadiness.REVIEW_REQUIRED
        else None
    )
    adaptation = evaluate_plan_adaptation(
        active_plan,
        decision,
        proposed,
        effective_date,
        history,
        observations,
        outcome,
        source=PlanAdaptationSource.PROGRESS_ADAPTATION,
        review_confirmation=review_confirmation,
    )
    integration = _integration_status(
        decision, adaptation, PlanAdaptationSource.PROGRESS_ADAPTATION
    )
    build_recommendation_history(
        history,
        current_active_macro_plan=adaptation.next_active_macro_plan,
        proposed_macro_plan=proposed,
        initial_plan_date=observations[0].observed_on if observations else None,
    )
    return _Checkpoint(adaptive, safety, outcome, decision, adaptation, integration)


def _aggregate_scenario(scenario: HostileScenario, runs: tuple[_UserRun, ...]) -> ScenarioMetrics:
    rows = [run.metrics for run in runs]
    n = len(rows)
    checks = sum(row.checks for row in rows)

    def mean(field: str) -> float:
        return sum(getattr(row, field) for row in rows) / n

    status_keys = tuple(key for key, _ in rows[0].integration_status_rates)
    status_rates = tuple(
        (key, sum(dict(row.integration_status_rates)[key] * row.checks for row in rows) / checks)
        for key in status_keys
    )

    def median_optional(field: str) -> float | None:
        values = [getattr(row, field) for row in rows if getattr(row, field) is not None]
        return None if not values else float(median(values))

    return ScenarioMetrics(
        scenario.name,
        scenario.category,
        n,
        checks,
        *(
            mean(field)
            for field in (
                "cp29_hold_rate",
                "cp29_defer_rate",
                "cp29_increase_rate",
                "cp29_decrease_rate",
                "cp30_activate_rate",
                "cp30_defer_rate",
                "cp30_suppress_rate",
                "review_required_decrease_proposal_rate",
                "review_required_decrease_user_rate",
                "activation_ready_decrease_proposal_rate",
                "activation_ready_increase_proposal_rate",
                "automatic_decrease_activation_rate",
                "false_activation_rate",
                "activation_ready_increase_by56_rate",
                "reversal_proposal_rate",
                "reversal_pending_rate",
                "confirmed_reversal_rate",
                "review_accepted_decrease_activation_rate",
            )
        ),
        status_rates,
        *(
            mean(field)
            for field in ("false_increase_rate", "false_decrease_rate", "false_change_rate")
        ),
        None if scenario.expected_direction is None else mean("correct_direction_rate"),
        None if scenario.expected_direction is None else mean("opposite_direction_rate"),
        None if scenario.expected_direction is None else mean("missed_change_rate"),
        median_optional("median_cp29_proposal_day"),
        median_optional("median_cp30_activation_day"),
        median_optional("median_transient_recovery_days"),
        mean("mean_activations_per_user_12_weeks"),
        mean("direction_reversal_rate"),
        mean("repeated_same_direction_rate"),
        mean("indefinitely_inert_rate"),
        mean("all_checkpoint_deferred_rate"),
        mean("ambiguity_decrease_activation_rate"),
        mean("safety_violation_rate"),
    )


def _run_gate_tradeoffs(seeds: tuple[int, ...]) -> tuple[GateTradeoff, ...]:
    output: list[GateTradeoff] = []
    scenarios = (
        "tdee_minus_200",
        "tdee_minus_300",
        "stationary_clean",
        "autocorrelated_water",
        "persistent_water_drift",
    )
    for name in scenarios:
        spec = next(item for item in cp35_scenarios() if item.name == name)
        runs = {
            gate: tuple(_simulate_user(spec, seed, gate) for seed in seeds) for gate in (28, 42)
        }
        proposal_28 = runs[28]
        proposal_42 = runs[42]

        proposal_days_28 = [
            _first_post_onset(run, "proposal_events", -1, spec.change_day) for run in proposal_28
        ]
        proposal_days_42 = [
            _first_post_onset(run, "proposal_events", -1, spec.change_day) for run in proposal_42
        ]
        activation_days_28 = [
            _first_post_onset(run, "activation_events", -1, spec.change_day) for run in proposal_28
        ]
        activation_days_42 = [
            _first_post_onset(run, "activation_events", -1, spec.change_day) for run in proposal_42
        ]
        plateau_28 = [day for day in activation_days_28 if day is not None]
        plateau_42 = [day for day in activation_days_42 if day is not None]

        output.append(
            GateTradeoff(
                name,
                len(seeds),
                sum(value is not None for value in proposal_days_28) / len(seeds),
                sum(value is not None for value in proposal_days_42) / len(seeds),
                sum(value is not None for value in activation_days_28) / len(seeds),
                sum(value is not None for value in activation_days_42) / len(seeds),
                None
                if not [value for value in proposal_days_28 if value is not None]
                else float(median(value for value in proposal_days_28 if value is not None)),
                None
                if not [value for value in proposal_days_42 if value is not None]
                else float(median(value for value in proposal_days_42 if value is not None)),
                None
                if not [value for value in activation_days_28 if value is not None]
                else float(median(value for value in activation_days_28 if value is not None)),
                None
                if not [value for value in activation_days_42 if value is not None]
                else float(median(value for value in activation_days_42 if value is not None)),
                sum(
                    _has_false_decrease(proposal_28_run, spec)
                    and not _has_false_decrease(proposal_42_run, spec)
                    for proposal_28_run, proposal_42_run in zip(
                        proposal_28, proposal_42, strict=True
                    )
                ),
                None if not plateau_28 else float(median(plateau_28)),
                None if not plateau_42 else float(median(plateau_42)),
            )
        )
    return tuple(output)


def _run_review_acceptance_tradeoffs(
    seeds: tuple[int, ...],
) -> tuple[ReviewAcceptanceTradeoff, ...]:
    scenarios = (
        "tdee_minus_200",
        "tdee_minus_300",
        "persistent_water_drift",
        "poor_adherence_with_water",
    )
    results: list[ReviewAcceptanceTradeoff] = []
    for name in scenarios:
        scenario = next(item for item in cp35_scenarios() if item.name == name)
        runs = tuple(_simulate_user(scenario, seed) for seed in seeds)
        accepted_runs = tuple(
            _simulate_user(scenario, seed, confirm_review_required=True) for seed in seeds
        )
        proposal_count = sum(
            sum(direction < 0 for direction in run.cp29_directions) for run in runs
        )
        review_count = sum(run.review_required_proposals for run in runs)
        ready_count = sum(run.ready_decrease_proposals for run in runs)
        proposal_latencies = [
            min(
                (
                    day - scenario.change_day - 1
                    for direction, day in run.proposal_events
                    if direction < 0 and day > scenario.change_day + 1
                ),
                default=None,
            )
            for run in runs
        ]
        confirmation_latencies = [
            min(
                (
                    day - scenario.change_day - 1
                    for direction, day in run.activation_events
                    if direction < 0
                    and day > scenario.change_day + 1
                    and run.review_accepted_decreases > 0
                ),
                default=None,
            )
            for run in accepted_runs
        ]
        confirmed_users = sum(run.review_accepted_decreases > 0 for run in accepted_runs)
        ambiguous_confirmed = confirmed_users if scenario.ambiguous else 0
        results.append(
            ReviewAcceptanceTradeoff(
                name,
                len(seeds),
                sum(
                    bool(run.review_required_proposals or run.ready_decrease_proposals)
                    for run in runs
                )
                / len(seeds),
                0.0 if proposal_count == 0 else review_count / proposal_count,
                0.0 if proposal_count == 0 else ready_count / proposal_count,
                confirmed_users / len(seeds),
                _median_present(proposal_latencies),
                _median_present(confirmation_latencies),
                ambiguous_confirmed / len(seeds),
            )
        )
    return tuple(results)


def _median_present(values: list[int | None]) -> float | None:
    available = [value for value in values if value is not None]
    return None if not available else float(median(available))


def _evaluate_criteria(scenarios: tuple[ScenarioMetrics, ...]) -> tuple[CriterionResult, ...]:
    by_name = {item.name: item for item in scenarios}
    ordinary = tuple(
        by_name[name] for name in ("stationary_clean", "scale_noise", "intake_variation")
    )
    noisy = tuple(
        by_name[name]
        for name in (
            "scale_noise",
            "autocorrelated_water",
            "water_rebound",
            "illness_like_disturbance",
            "sodium_carb_weight_spike",
        )
    )
    power = tuple(by_name[name] for name in ("tdee_minus_300", "tdee_plus_300"))
    decrease_power = by_name["tdee_minus_300"]
    increase_power = by_name["tdee_plus_300"]
    ambiguity_names = {
        item.name
        for item in cp35_scenarios()
        if item.category == "ambiguity" or (item.category == "combined" and item.ambiguous)
    }
    ambiguity = tuple(item for item in scenarios if item.name in ambiguity_names)
    safety = tuple(item for item in scenarios if item.category == "safety")
    transient = tuple(
        item.median_transient_recovery_days
        for item in scenarios
        if item.category == "water" and item.median_transient_recovery_days is not None
    )
    values: dict[str, float | None] = {
        "ordinary_false_decrease": max(item.false_decrease_rate for item in ordinary),
        "ordinary_false_increase": max(item.false_increase_rate for item in ordinary),
        "ordinary_false_activation": max(item.false_activation_rate for item in ordinary),
        "opposite_direction_activation": max(item.opposite_direction_rate or 0 for item in power),
        "plus_minus_300_proposal_detection": min(
            item.correct_direction_rate or 0 for item in power
        ),
        "proposal_latency": max(
            (
                item.median_cp29_proposal_day
                for item in power
                if item.median_cp29_proposal_day is not None
            ),
            default=None,
        ),
        "activation_reversal": max(item.direction_reversal_rate for item in noisy),
        "stationary_activation_count": max(
            by_name[name].mean_activations_per_user_12_weeks
            for name in ("stationary_clean", "scale_noise", "intake_variation")
        ),
        "ambiguous_automatic_decrease": max(
            (item.ambiguity_decrease_activation_rate for item in ambiguity), default=0.0
        ),
        "review_ready_decrease": max(
            item.activation_ready_decrease_proposal_rate for item in scenarios
        ),
        "review_required_genuine_decrease": decrease_power.review_required_decrease_user_rate,
        "activation_ready_increase": increase_power.activation_ready_increase_by56_rate,
        "indefinite_inert_proposal": max(item.indefinitely_inert_rate for item in power),
        "safety_violations": max((item.safety_violation_rate for item in safety), default=0.0),
        "missed_large_change": max(item.missed_change_rate or 0 for item in power),
        "indefinite_defer": max(item.all_checkpoint_deferred_rate for item in power),
        "transient_recovery": float(median(transient)) if transient else None,
    }
    results: list[CriterionResult] = []
    for criterion in CP35_FROZEN_CRITERIA:
        observed = values[criterion.criterion_id]
        if observed is None:
            passed = False
        elif criterion.comparator == "min":
            passed = observed >= criterion.limit
        else:
            passed = observed <= criterion.limit
        results.append(
            CriterionResult(
                criterion.criterion_id,
                criterion.description,
                observed,
                criterion.limit,
                criterion.comparator,
                passed,
            )
        )
    return tuple(results)


def _actual_tdee(scenario: HostileScenario, baseline_tdee: float, day: int) -> float:
    if not scenario.tdee_delta:
        return baseline_tdee
    fraction = (
        min(1.0, (day - scenario.change_day + 1) / scenario.gradual_tdee_days)
        if scenario.gradual_tdee_days and day >= scenario.change_day
        else float(day >= scenario.change_day)
    )
    return baseline_tdee + scenario.tdee_delta * fraction


def _adherence_delta(scenario: HostileScenario, target: float, day: int, seed: int) -> float:
    if (
        scenario.name in ("logging_underreport_step", "logging_overreport_step")
        and day < scenario.bias_start_day
    ):
        return 0.0
    if scenario.name == "intake_regime_change_missing" and day < scenario.bias_start_day:
        return 0.0
    drift_progress = max(0.0, min(1.0, (day - scenario.bias_start_day + 1) / 56.0))
    if scenario.name == "inconsistent_adherence":
        return random.Random(seed * 101 + day).choice((-300.0, 300.0, 0.0, 0.0))
    noise = (
        random.Random(seed * 313 + day).gauss(0.0, 75.0)
        if scenario.name == "intake_variation"
        else 0.0
    )
    return scenario.adherence_offset + scenario.adherence_drift * drift_progress + noise


def _logging_bias(scenario: HostileScenario, day: int) -> float:
    if scenario.logging_bias_drift:
        progress = max(0.0, min(1.0, (day - scenario.bias_start_day + 1) / 56.0))
        return scenario.logging_bias_drift * progress
    if day >= scenario.bias_start_day:
        return scenario.logging_bias
    return 0.0


def _logging_availability(scenario, day, actual_intake, target, activation_days):
    weekday = (date(2025, 1, 1) + timedelta(days=day)).weekday()
    if scenario.missing_pattern == "weekends" and weekday >= 5:
        return False, False
    if scenario.missing_pattern == "weight_cluster" and 35 <= day <= 48:
        return False, True
    if scenario.missing_pattern == "after_high_intake" and actual_intake > target + 150:
        return True, False
    if scenario.missing_pattern == "transition_gap" and any(
        abs(day - event_day) <= 3 for event_day in activation_days
    ):
        return False, False
    if scenario.missing_pattern == "every_other_day" and day % 2:
        return False, False
    if scenario.name == "plateau_noise_partial_logs" and day % 3:
        return False, False
    if scenario.name == "intake_regime_change_missing" and 28 <= day <= 41 and day % 2:
        return True, False
    return True, True


def _water_value(scenario: HostileScenario, day: int, water: float, seed: int) -> float:
    rng = random.Random(seed * 991 + day)
    pattern = scenario.water_pattern
    if pattern == "autocorrelated":
        return 0.85 * water + rng.gauss(0.0, 0.40)
    if pattern == "persistent_drift":
        return -200.0 / 7700.0 * day
    if pattern == "rebound":
        if 28 <= day <= 34:
            return -1.2 * (day - 27) / 7
        if 35 <= day <= 48:
            return -1.2 * max(0.0, 1 - (day - 34) / 14)
        return 0.0
    if pattern == "illness":
        if 35 <= day <= 45:
            return 1.6
        if 45 < day <= 63:
            return 1.6 * max(0, 1 - (day - 45) / 18)
        return 0.0
    if pattern == "spike":
        return 1.3 if 35 <= day <= 40 else 0.0
    return 0.0


def _transient_end_day(pattern: str) -> int | None:
    return {"rebound": 48, "illness": 63, "spike": 40}.get(pattern)


def _relative_day(day: int | None, change_day: int) -> int | None:
    return None if day is None else day - change_day - 1


def _first_post_onset(run: _UserRun, field: str, direction: int, change_day: int) -> int | None:
    events = getattr(run, field)
    event_day = min(
        (
            day
            for event_direction, day in events
            if event_direction == direction and day > change_day + 1
        ),
        default=None,
    )
    return _relative_day(event_day, change_day)


def _has_false_decrease(run: _UserRun, scenario: HostileScenario) -> bool:
    return any(
        direction < 0
        and (
            scenario.expected_direction is None
            or scenario.expected_direction != direction
            or day <= scenario.change_day + 1
        )
        for direction, day in run.activation_events
    )


def _external_style_audit() -> tuple[tuple[str, str, bool], ...]:
    audit: list[tuple[str, str, bool]] = []
    try:
        UserProfile(
            30,
            180,
            80,
            SexForMifflinEquation.MALE,
            ActivityLevel.MODERATELY_ACTIVE,
            Goal.CUT,
            -1.0,
        )
    except ProfileValidationError:
        audit.append(("oversized_cut_request", "rejected_at_profile_boundary", True))
    else:
        audit.append(("oversized_cut_request", "accepted", False))
    try:
        DailyObservation(date(2025, 1, 1), energy_intake_kcal=10_001)
    except ObservationValidationError:
        audit.append(("absurd_intake", "rejected_at_observation_boundary", True))
    else:
        audit.append(("absurd_intake", "accepted", False))

    def make_profile(weight: float, height: float, requested: float) -> UserProfile:
        return UserProfile(
            30,
            height,
            weight,
            SexForMifflinEquation.MALE,
            ActivityLevel.MODERATELY_ACTIVE,
            Goal.CUT,
            requested,
        )

    for name, profile, expected in (
        ("low_bmi_below_18_5", make_profile(55, 180, -0.2), TargetEligibilityStatus.INELIGIBLE),
        (
            "near_underweight_bmi_band",
            make_profile(62, 180, -0.4),
            TargetEligibilityStatus.CONSTRAINED,
        ),
        (
            "normal_bmi_aggressive_cut",
            replace(make_profile(80, 180, -0.6), activity_level=ActivityLevel.SEDENTARY),
            TargetEligibilityStatus.CONSTRAINED,
        ),
    ):
        result = assess_target_eligibility(profile, calculate_baseline_energy(profile))
        safe_target = result.effective_target_kcal_per_day
        within_cap = expected is TargetEligibilityStatus.INELIGIBLE or (
            safe_target is not None
            and result.maximum_permitted_deficit_kcal_per_day is not None
            and safe_target
            >= result.baseline_tdee_kcal_per_day - result.maximum_permitted_deficit_kcal_per_day
        )
        passed = result.status is expected and within_cap
        audit.append((name, result.status.value, passed))
    return tuple(audit)


def _direction(value: str, delta: float = 0.0) -> int:
    if value in (RecommendationDecisionType.INCREASE.value, PlanAdaptationAction.ACTIVATE.value):
        return 1 if delta >= 0 else -1
    if value == RecommendationDecisionType.DECREASE.value:
        return -1
    return 0


def _stable_name_code(value: str) -> int:
    return sum((position + 1) * ord(char) for position, char in enumerate(value))


def _validate_seeds(seeds: tuple[int, ...], seed_set: str) -> None:
    bounds = {"development": (140000, 140015), "held_out": (150000, 150015)}
    if seed_set not in bounds:
        raise ValueError("seed_set must be 'development' or 'held_out'.")
    low, high = bounds[seed_set]
    if (
        not seeds
        or len(seeds) != len(set(seeds))
        or any(
            isinstance(seed, bool) or not isinstance(seed, int) or not low <= seed <= high
            for seed in seeds
        )
    ):
        raise ValueError(f"seeds must be unique integers in {seed_set} range {low}..{high}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-set", choices=("development", "held_out"), required=True)
    parser.add_argument("--count", type=int, default=16)
    args = parser.parse_args()
    available = CP35_DEVELOPMENT_SEEDS if args.seed_set == "development" else CP35_HELD_OUT_SEEDS
    if not 1 <= args.count <= len(available):
        parser.error(f"--count must be between 1 and {len(available)}")
    selected = tuple(available)[: args.count]
    print(report_json(run_cp35_hostile_study(selected, seed_set=args.seed_set)))


if __name__ == "__main__":
    main()
