# Recommendation Decisions

Checkpoint 29 adds a deterministic, proposal-only decision layer on top of the CP28 plan-outcome
assessment. It returns `hold`, `increase`, `decrease`, or `defer` for the current latest plan. It
never activates a new plan, stores adaptation history, applies cooldowns, or changes historical
progression. Those stateful workflows belong to Checkpoint 30.

## CP28 versus CP29

CP28 describes evidence: recorded intake adherence, smoothed weight progress, completeness, and
interpretability. CP29 decides whether that evidence justifies a conservative proposal. A decision
never re-derives trend, adherence, training, or TDEE calculations.

`defer` is distinct from `hold`. Hold means evidence is interpretable and no change is justified.
Defer means the engine ran, but evidence or adherence is not strong enough to judge the plan. Both
preserve the current target exactly.

## Policy

The default `RecommendationDecisionConfig` uses:

- minimum adjustment: 50 kcal/day
- standard adjustment: 100 kcal/day
- maximum adjustment per decision: 150 kcal/day
- optional absolute maximum target: unset by default; proposals are clamped when supplied
- minimum interpretable weight span: 14 days
- adaptive-TDEE supporting threshold: 150 kcal/day

The decision defers when the CP28 assessment is unavailable or not interpretable, intake adherence
is not near target, weight evidence is unavailable, the weight span is too short, or the outcome
reports a direction mismatch requiring review. This prevents changing calories because of sparse logs,
short history, or materially off-target intake.

When evidence is interpretable and adherence is near target, the goal-aware rules are:

- cut: slower loss proposes a decrease; faster loss proposes an increase
- gain: slower gain proposes an increase; faster gain proposes a decrease
- maintain: stable weight holds; sustained loss proposes an increase; sustained gain proposes a decrease

The standard change is 100 kcal/day and is bounded by the configured maximum. Changes smaller than
the minimum are held. Decreases are clamped to the established `minimum_macro_calories_kcal_per_day`
safety floor with an explicit reason code. A current target already below that floor defers rather
than reversing direction. An optional absolute maximum target similarly clamps increases with an
explicit reason code. Adaptive TDEE is supporting context only: it may add a supporting or
conflicting reason, but never becomes a second target generator.

## CP34B conservative adaptive-evidence policy

Adaptive TDEE is an observational estimate, not measured expenditure. CP29 now exposes categorical
adaptive evidence status and structured reason codes. `insufficient`, `stabilizing`, `unstable`,
recent intake-regime changes, or material 28/35/42-day horizon disagreement are ambiguous evidence.

A calorie decrease requires interpretable CP28 outcome evidence, near-target adherence, adequate weight
and intake data/span, safety eligibility, stable adaptive evidence, a sufficiently long decrease
evidence span, and acceptable cross-horizon agreement. Otherwise CP29 returns `defer` with reasons
such as `adaptive_evidence_ambiguous`, `estimator_stabilizing`,
`estimator_sensitivity_disagreement`, `persistent_weight_drift_unidentifiable`, and
`conservative_decrease_withheld`.

Increases intentionally use a different bar: interpretable outcome, near-target adherence, direction
and safety evidence remain required, but ambiguous adaptive TDEE is contextual and does not by itself
block a CP28-supported increase. This asymmetry is proposal-only and is not an assertion that TDEE
changed.

No probability or confidence score is invented. A hold/defer is an intentional safety behavior when
the available inputs cannot distinguish persistent non-energy weight drift from a true deficit.

## CP35A Decrease Review Readiness

A numerically supported calorie decrease remains visible as a CP29 `decrease` proposal with its
proposed target, but its `activation_readiness` is `review_required`. This conservative rule applies
even when the observed estimator evidence looks stable: weight and logged intake alone cannot rule
out hidden adherence/logging effects or persistent non-energy weight drift. CP29 therefore does not
claim a decrease is automatically activation-ready. CP30 leaves the current plan unchanged until a
caller submits an explicit review confirmation for the exact effective date and proposed target.

This additional review condition applies to decreases only. Increases retain the existing evidence,
safety, and readiness rules; ambiguous adaptive TDEE alone does not block a CP28-supported increase.

## Proposed plans

The unified response keeps `latest_plan` as the active current plan. `recommendation_decision`
contains old target, proposed target, delta, direction, attention state, adherence/evidence summary,
and ordered reason codes. For numerical proposals only, `proposed_macro_plan` and
`proposed_target_envelope` are calculated through the existing macro and training-aware pipelines.
CP27 feasibility remains assessment-only. No plan is activated and no notification is sent.

The optional `outcome_as_of_date` is honored by the decision's CP28 input. Later observations cannot
influence an earlier decision. Existing progression snapshots remain unchanged and do not receive
historical decisions.

CP30 adds a separate activation gate after this decision. It may defer or suppress an otherwise
valid proposal because of cooldown, insufficient fresh contributors, or reversal risk. It does not
alter CP29 direction or magnitude logic.

Checkpoint 31 presents CP30 events as an immutable audit stream. The history layer derives summaries
and change types from structured source/action/reason fields; it does not alter decisions or create
new recommendation logic.

CP33 safety is evaluated before this decision. Underweight loss is ineligible; otherwise the
configured calorie floor and maximum TDEE-deficit cap prevent a decrease from crossing a safe
target boundary.

CP34 adaptive-TDEE evidence is aligned, robust, and categorical in stability. Unstable estimates do
not strengthen plan-change decisions; adaptive TDEE remains supporting context rather than a target
generator.
