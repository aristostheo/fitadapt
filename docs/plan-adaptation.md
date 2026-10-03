# Longitudinal Plan Adaptation

Checkpoint 30 adds a deterministic, stateless activation gate around CP29 proposals. It distinguishes
the current active plan, the CP29 proposed plan, and the next active plan that is eligible for
activation. The evaluator does not persist or activate anything; the caller owns acceptance and
future storage.

## Actions

`activate` means the proposal is eligible to become the next active plan. `hold` means evidence is
valid but no change is needed. `defer` means the proposal cannot be reconsidered yet because the
cooldown, fresh-evidence, effective-date, or CP29 decision gate is not satisfied. `suppress` means a
reversal is likely to be noise or oscillation and needs stronger evidence.

CP30 trusts CP29's decision contract. If CP29 returns `defer` because adaptive evidence is
`insufficient`, `stabilizing`, `unstable`, or sensitivity-ambiguous, CP30 cannot activate a calorie
decrease and carries the structured reason codes into its evaluation event. CP30 does not duplicate
or reinterpret estimator logic.

The default `PlanAdaptationConfig` requires:

- 14 calendar days between activated changes
- 7 new observations after the last activation
- 4 new weight contributors
- 7 new intake contributors
- 28 days before a reversal
- 7 new weight contributors for a reversal
- 14 new intake contributors for a reversal

Fresh contributors are counted only after the last activated event and on or before the evaluation
date. Repeated calls over the same observations therefore cannot ratchet the active plan.
Same-direction proposals can activate after the standard cooldown and fresh-evidence requirements.
Opposite-direction proposals are suppressed until both the reversal interval and stronger fresh
weight/intake requirements are met.

## CP35A Review and Reversal Confirmation

CP29 decreases remain visible proposals but are marked `review_required`; without confirmation, CP30
returns `review_required` (or `reversal_pending` when a reversal cycle is active) and preserves the
current plan. The caller can submit `review_confirmation` with the exact current `effective_date` and
`proposed_target_kcal_per_day`. A mismatch does not accept the proposal. This review-only gate does
not apply to increases.

The first eligible opposite-direction proposal starts `reversal_pending`. A later evaluation must
retain the same direction and include at least 14 days after that first signal, 7 distinct observation
dates, 4 weight contributors, and 7 intake contributors strictly after the signal, plus the existing
reversal interval and fresh-evidence requirements. Two consistent pending evaluations are required.
If the direction disappears or changes, the cycle clears and a future signal starts a new interval.
This is derived from caller-owned history; no state is persisted, and overlapping rolling estimator
windows are not treated as independent proof. A decrease still requires exact user review after the
reversal evidence passes.

## History and isolation

`PlanAdaptationEvent` is an immutable record containing effective date, previous/new active targets,
calorie delta, originating CP29 decision, action, source, reason codes, evidence date, fresh counts,
and policy version. The evaluator accepts a chronological tuple/list and returns a new tuple; it does
not mutate the input. Duplicate dates, out-of-order events, invalid targets, and invalid counts are
rejected.

An optional source distinguishes `progress_adaptation` from `profile_recalculation`. Profile
recalculation is represented as metadata only and is not silently converted into progress history.
As-of evaluations filter future observations before counting fresh evidence. Earlier adaptation events
and plan versions cannot be rewritten by later observations.

## Unified response and UI

`POST /v1/profile-intelligence` accepts optional `adaptation_history` and `adaptation_source`, and
returns `plan_adaptation`. The response includes the current active macro plan, proposed macro plan,
next active macro plan, action, activation/user-attention signals, target values, fresh evidence
counts, reason codes, and resulting history. `latest_plan` and progression remain unchanged.

The Progress screen shows whether a plan update is available, whether more evidence is needed, or
whether a reversal was suppressed. It can distinguish estimator stabilization from broader ambiguous
adaptive evidence through structured status/reason fields. Activation is eligibility only; no notification, persistence,
or active-plan mutation occurs. Checkpoint 31 or the main application may store accepted events and
active-plan transitions.

The structured integration status distinguishes an available proposal, a proposal requiring review,
and a reversal pending confirmation. `activation_ready` remains false until CP30 allows activation;
`proposal_available` does not imply readiness.

The main app should treat `current_recommendation` as the authoritative active plan. Acceptance is a
caller action: send the accepted activation event in `adaptation_history` on the next request so the
engine can reconstruct that active target. A returned proposal or activation eligibility alone does
not mean the plan became active.

Safety guardrails remain authoritative during adaptation: repeated decreases cannot cross the
configured calorie floor or deficit cap, and an ineligible weight-loss profile cannot activate an
automated loss target.

Checkpoint 31 converts the supplied adaptation-event tuple into a separate explainability history.
It does not change activation eligibility. Activated changes, profile recalculations, holds, defers,
and suppressed reversals remain distinguishable, and evaluation-only entries do not imply that the
active plan changed.
