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

## End-to-End Request Cycle

1. **Initial user:** send profile, training/dietary context, and any existing observations to
  `POST /v1/profile-intelligence`. Use `current_recommendation` as the authoritative plan. With no
  history, FitAdapt still returns a complete baseline response.
2. **Daily use:** resend the profile, caller-owned `adaptation_history`, and updated dated
  observations. FitAdapt recomputes trends, adaptive evidence, adherence/outcome, safety, and status.
3. **No change:** a `hold` or `defer` leaves `current_recommendation` unchanged. Keep the stored plan;
  use `more_data_needed` and reason codes to decide whether to wait or collect better evidence.
4. **Proposed update:** if `recommendation_decision.numerical_change_proposed` is true, review the
  `proposed_macro_plan` and `proposed_target_envelope`. These and `next_active_macro_plan` are not
  active merely because FitAdapt returned them.
5. **Review-required decrease:** keep the proposal visible and leave the active plan unchanged. Only
  after the user explicitly accepts that exact proposal, resend the response's exact date and target:

  ```json
  {
    "review_confirmation": {
     "effective_date": "2026-01-28",
     "proposed_target_kcal_per_day": 2300
    }
  }
  ```

  A stale date or different target does not confirm it. This decrease-specific requirement does not
  apply to increases. CP30's other cooldown and evidence gates still apply.
6. **Accepted update:** when CP30 returns activation eligibility and the user accepts, store the new
  active plan and returned activation event in the app. Resend the event in caller-owned
  `adaptation_history` so the next `current_recommendation` reconstructs the accepted target. FitAdapt
  does not persist or activate the plan on the app's behalf.
7. **Profile update:** send the changed profile with `adaptation_source: "profile_recalculation"`.
  Do not reuse stale progress-adaptation events as current-profile activation state. The response
  source identifies profile recalculation separately.

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
