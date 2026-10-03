# Main Fitness App Integration

FitAdapt is a stateless diet-intelligence engine. The main fitness app owns accounts, persistence,
authentication, daily logging, acceptance/storage of active plans, notifications, meal generation,
and workout generation.

## One request path

Use `POST /v1/profile-intelligence` for initial setup, daily reassessment, proposals, activation
eligibility, and explainability. Send the current profile, nutrition/dietary context, training
context, observations, and any caller-owned `adaptation_history`. Newer request fields are optional.

```json
{
  "profile": {
    "age_years": 30,
    "height_cm": 180,
    "weight_kg": 80,
    "sex_for_mifflin_equation": "male",
    "activity_level": "moderately_active",
    "goal": "cut",
    "requested_weekly_change_kg": -0.4
  },
  "observations": [],
  "nutrition_preferences": { "macro_strategy": "balanced" }
}
```

The authoritative active-plan summary is `current_recommendation`. It contains the active calorie
and macro plan, effective date, source, and `is_authoritative: true`. `latest_plan` remains the
backward-compatible detailed calculation view. Do not treat `proposed_macro_plan` or
`next_active_macro_plan` as active until the app accepts and stores the update.

## Normal flows

**Initial/profile recalculation:** send the new profile with no or limited observations. Use
`current_recommendation` for the current plan. Set `adaptation_source` to `profile_recalculation`
when representing a profile-driven recalculation. This does not create a progress-adaptation event.

**Daily reassessment:** resend the same profile and caller-owned active history with updated
observations. FitAdapt returns CP28 outcome evidence, CP29 `recommendation_decision`, CP30
`plan_adaptation`, CP31 `recommendation_history`, and consolidated `integration_status`.

**Proposal:** when `recommendation_decision.numerical_change_proposed` is true, review
`proposed_macro_plan` and `proposed_target_envelope`. This is not an active plan.

For a decrease, `recommendation_decision.activation_readiness` is `review_required`. Keep the
proposal visible and preserve the active plan. If the user explicitly accepts it, send
`review_confirmation` containing the response's exact `effective_date` and
`proposed_target_kcal_per_day`. Confirmation is bound to that evaluation and target; stale or
different values do not count. This requirement is decrease-specific; do not impose it on increases.

**Activation eligibility:** when `integration_status.plan_update_available` is true and
`plan_adaptation.activation_available` is true, the app may present the update for acceptance.
FitAdapt has not activated it.

**Accepted update:** after user acceptance, store the new active plan and append the returned
activation event to the app-owned `adaptation_history`. Include that history on the next request;
FitAdapt then reconstructs the accepted target as `current_recommendation` through the existing macro
pipeline.

**Profile update:** send the updated profile and `adaptation_source: "profile_recalculation"`.
Stale progress-adaptation activation state is not reused for the new profile evaluation. The response
source identifies the recalculation separately.

## Status and notifications

Use `integration_status` without parsing prose:

- `user_attention_required`: the app should consider showing the result.
- `plan_update_available`: a next plan is eligible for review/acceptance.
- `more_data_needed`: no activation should be offered yet.
- `reversal_suppressed`: a contradictory reversal was blocked.
- `proposal_available`: CP29 returned a numerical proposal.
- `proposal_requires_review`: explicit decrease review is outstanding.
- `activation_ready`: CP30 says activation eligibility is satisfied.
- `reversal_pending_confirmation`: a consistent opposite-direction confirmation cycle is underway.
- `current_plan_appropriate`: the current plan is the recommended state.
- `app_status`: one of `plan_remains_appropriate`, `more_data_needed`,
  `deferred_estimator_stabilizing`, `deferred_adaptive_evidence_ambiguous`, `update_available`,
  `proposal_available`, `proposal_requires_review`, or `reversal_pending_confirmation`.
- `reason_codes`: structured CP29 adaptive-evidence and CP30 activation reasons.

`recommendation_history.latest_change`, `actionable_event_available`, source, effective date, old/new
targets, change type, and reason codes are structured notification-ready data. FitAdapt does not send
notifications.

Inspect `target_safety` as well: `eligible` means no safety guardrail constrained the request,
`constrained` means a safer target was applied, and `ineligible` means FitAdapt will not generate an
automated weight-loss target for the current body-size threshold.

Adaptive TDEE responses include `stable`, `stabilizing`, `unstable`, or `insufficient` evidence
status. Treat `stabilizing`, `unstable`, and `insufficient` estimates as context requiring more evidence, not
measured expenditure or an automatic plan change. With weight, logged intake, and dates alone, some
persistent non-energy weight changes cannot be distinguished from true energy-balance change; FitAdapt
may intentionally hold/defer in that case. Do not market adaptive TDEE as measured metabolism.

## Historical safety

For an earlier `outcome_as_of_date`, future observations are excluded from trends, adaptive TDEE,
training assessment, outcome, recommendation, adaptation, history, current recommendation, and
integration status. Replaying the same prefix with additional future records produces the same
results for that date.
