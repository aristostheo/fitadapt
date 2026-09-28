# Unified Profile Intelligence API

`POST /v1/profile-intelligence` is the stateless, latest-profile operation for clients that need
FitAdapt's current baseline and personalized evidence in one response. It avoids a client having to
coordinate several independently valid engine calls. It stores no profile, preference, or observation
data and introduces no fitness formula or policy.

## Request

The endpoint accepts the existing strict `profile`, `observations`, and `nutrition_preferences`
models. `dietary_preference_profile` is optional and `include_plan_progression` is an optional JSON
boolean; omission uses an unrestricted/broad dietary profile and progression defaults to `false`.

```json
{
  "profile": {
    "age_years": 30,
    "height_cm": 180,
    "weight_kg": 80,
    "sex_for_mifflin_equation": "male",
    "activity_level": "moderately_active",
    "goal": "maintain",
    "requested_weekly_change_kg": 0
  },
  "observations": [],
  "nutrition_preferences": { "macro_strategy": "balanced" },
  "dietary_preference_profile": {
    "dietary_pattern": "unrestricted",
    "selection_mode": "broad",
    "constraints": [],
    "preferences": []
  },
  "include_plan_progression": false,
  "outcome_as_of_date": null
}
```

Run this deterministic empty-history example locally:

```bash
curl -X POST http://127.0.0.1:8000/v1/profile-intelligence \
  -H 'content-type: application/json' \
  --data @examples/profile_intelligence_empty_request.json | python -m json.tool
```

The executable API integration test
`tests/integration/api/test_profile_intelligence_api.py::test_profile_intelligence_endpoint_matches_complete_direct_empty_result`
asserts the complete response against the same direct domain call. Its response has an undated
baseline latest plan, empty trend/adaptive collections, `baseline` lifecycle stage, and `null`
`plan_progression`.

## Response Sections

`ProfileIntelligenceResponse` preserves full calculation precision and has these sections:

| Field                      | Existing source                                                                                      |
| -------------------------- | ---------------------------------------------------------------------------------------------------- |
| `baseline`                 | `calculate_calorie_target` output.                                                                   |
| `trends`                   | Calendar-aware trend points and data quality.                                                        |
| `adaptive_tdee`            | Daily eligibility, aggregate TDEE, MAD, and aggregation evidence.                                    |
| `lifecycle`                | Evidence readiness and requirements.                                                                 |
| `recommendation`           | Existing conservative recommendation or ordered insufficiency reasons.                               |
| `latest_plan`              | Current selected calorie basis, exact preference-driven macro plan, and target envelope.             |
| `dietary_assessment`       | Current/latest-plan category constraints, preferences, conflicts, notices, and protein flexibility.  |
| `plan_outcome`             | Current-target intake adherence, observed weight-rate progress, evidence sufficiency, and reasons.   |
| `recommendation_decision`  | Proposal-only hold/increase/decrease/defer decision with target delta, attention state, and reasons. |
| `proposed_macro_plan`      | `null` for hold/defer; otherwise the existing macro pipeline applied to the proposed target.         |
| `proposed_target_envelope` | `null` for hold/defer; otherwise the existing target-envelope pipeline for the proposal.             |
| `plan_adaptation`          | Stateless activate/hold/defer/suppress eligibility with active/proposed/next plans and history.      |
| `recommendation_history`   | Immutable explainability timeline with latest change and actionable-event signals.                   |
| `target_safety`            | BMI eligibility, calorie floor, deficit cap, effective target, and safety reason codes.              |
| `current_recommendation`   | One authoritative active calorie/macro summary for the consuming app.                                |
| `integration_status`       | Consolidated attention, update-available, more-data, reversal, and current-plan signals.             |
| `plan_progression`         | `null` unless requested; otherwise one prefix snapshot per submitted entry.                          |

`target_safety` is structured eligibility information; valid but ineligible weight-loss goals are
returned as data rather than transport errors.
Adaptive TDEE responses additionally expose V2 slope, aligned intake, evidence span/contributors,
method, stability, and reason codes; clients should not interpret stability as a confidence percentage.

Dates serialize as ISO dates, enum fields as stable JSON strings, unavailable values as JSON `null`,
and logged numeric zero as zero. Nutrition preferences affect macro allocation only; they do not
alter baseline calorie estimation, trends, adaptive TDEE, lifecycle evidence, or recommendation policy.
The additive dietary assessment is computed from `latest_plan.target_envelope`; it does not alter
calories, macros, lifecycle, recommendations, or progression snapshots. If omitted, the request
uses an unrestricted/broad dietary profile for backward compatibility.
The additive `plan_outcome` assessment compares recorded calorie intake with the selected current
plan target and compares observed smoothed weight change with the profile's requested rate. It uses
a trailing calendar window, preserves missing values as unknown, and returns contributor counts,
completeness, evidence source, stable reason codes, and an interpretability grade. Early or sparse
history is limited rather than treated as adherence or non-adherence. The optional
`outcome_as_of_date` field filters out later observations; by default the latest observation date is
used. It does not alter any target, recommendation, macro calculation, or progression.
The additive `recommendation_history` is built from caller-supplied adaptation events. It separates
profile recalculation from progress adaptation and distinguishes actual plan changes from
evaluation-only hold, defer, and suppressed entries. `latest_change`, `actionable_event_available`,
and structured target/source fields are notification-ready; summaries are deterministic and reason
codes remain available for technical details.
The additive `nutrition_feasibility` assessment uses only an explicitly supplied dietary profile
and the final effective macro plan. When dietary information is omitted or a selected-food profile
is empty, feasibility is unavailable rather than assumed easy. Practical guidance is category-level
and never modifies calories, macros, or progression. The response distinguishes practical protein,
carbohydrate, fat, and restriction compatibility, carries structured guidance/reason codes, and
preserves any dietary preference conflicts. It also exposes whether training-aware macro policy was
applied and baseline/effective protein and carbohydrate provenance where available. These explain
the single existing macro plan; they are not a second competing plan.
The optional `training_context` contributes only to the additive latest-only `training_assessment`.
When sufficient, it also adds training-aware macro provenance to `latest_plan.macro_plan`; this
changes macro composition only, not calories, TDEE, recommendations, target envelopes, dietary
assessment, or progression snapshots. Insufficient evidence preserves the existing macro policy.
`target_envelope` is additive: all earlier response fields retain their names and semantics. It
contains the exact selected plan plus calorie adherence, protein/fat preferred, and carbohydrate
flexible ranges with policy provenance.
The additive `recommendation_decision` is proposal-only. `latest_plan` remains the current active
plan; hold and defer preserve its target exactly. Increase/decrease proposals use the existing macro
and training-aware macro pipelines and do not alter progression or activate history. CP28 outcome
assessment supplies adherence and progress evidence; CP29 does not duplicate those calculations.
The additive `plan_adaptation` layer accepts optional chronological `adaptation_history` and
evaluates cooldown, fresh contributors, and reversal guards using observation dates. It never
persists or activates a plan. `next_active_macro_plan` indicates the plan eligible for caller
acceptance when action is `activate`.
`current_recommendation` is the authoritative active-plan summary. Proposals and next plans are not
active until the caller accepts and resubmits the resulting adaptation history. See
[app integration](app-integration.md) for normal request and acceptance flows.

## Latest-Only And Progression

Latest-only is the default. It constructs only the current plan and is appropriate for a normal
profile page. With `include_plan_progression: true`, FitAdapt builds the existing chronological
prefix progression: each snapshot contains only entries at or before its date, and no missing-date
snapshots are invented. This can be materially larger and more computationally expensive because
every prefix is recomputed. The final non-empty progression snapshot equals `latest_plan`; an empty
history returns an empty progression tuple and still returns the explicit undated baseline plan.
Each snapshot carries the envelope for its own selected target. Appending or changing future
observations cannot alter earlier snapshots or envelopes.

## Errors And Boundaries

Unknown fields, numeric booleans, numeric strings, non-finite numeric values, and non-boolean
progression flags receive FastAPI's standard `422` validation response. Existing domain errors,
including duplicate observation dates, remain stable documented `400` errors. Unexpected failures
return opaque documented `500` `ErrorResponse` payloads.

The endpoint uses existing defaults and does not expose individual engine configurations as a new
transport policy. It does not persist state, call synthetic ML, perform inference, alter baseline or
adaptive results, or apply recommendations. The standalone Checkpoint 21 React client now uses this
single operation; integration into a separate fitness-app profile page remains future work.

The current standalone client wraps this operation in a five-stage session-only journey: Profile,
Nutrition, History, Plan, and Progress. It sends one unified request after the user chooses analysis.
The Plan stage presents the latest selected target and dietary assessment; Progress presents the
existing trends and only shows plan progression when it was requested. This presentation layer does
not change the endpoint contract or backend calculations.

Target envelopes do not add food selection, allergies/restrictions, medical nutrition therapy,
meal generation, micronutrient analysis, training-day/rest-day targets, or budget, cuisine,
cooking, or schedule optimization.
Dietary assessment remains category-level only. It does not add frontend onboarding, individual
foods, recipes, persistence, or halal/kosher certification.
