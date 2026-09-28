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
whether a reversal was suppressed. Activation is eligibility only; no notification, persistence,
or active-plan mutation occurs. Checkpoint 31 or the main application may store accepted events and
active-plan transitions.
