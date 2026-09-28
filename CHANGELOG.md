# Changelog

## 0.1.0

Initial development release: validated profiles and observations, REE/TDEE and macro policies, calendar trends, adaptive TDEE, evidence-based personalization lifecycle status, entry-by-entry proposed personalized planning, a unified stateless profile-intelligence API, synthetic evaluation, leakage-safe ML diagnostics, conservative recommendations, a stateless FastAPI adapter, a session-only React profile-intelligence client with browser-only CSV/JSON historical import, separate V1 preference-driven macro plans, versioned nutrition target envelopes exposed through domain, API, progression, and frontend contracts, and deterministic category-level dietary preference assessment exposed through standalone and unified backend APIs.

Nutrition target envelopes remain policy-based decision support. They do not implement food selection, allergies/restrictions, medical nutrition therapy, meal generation, micronutrient analysis, training-day/rest-day targets, or budget, cuisine, cooking, or schedule optimization.

Dietary assessment remains category-level decision support. Frontend onboarding, individual food records,
recipes, meal generation, medical nutrition therapy, micronutrient analysis, persistence, and
budget/cuisine/schedule/cooking optimization are deferred.

Checkpoint 24 client polish adds the five-stage guided journey, clearer Plan and Progress hierarchy,
technical-detail disclosures, responsive/accessibility refinements, and explicit empty states without
changing backend behavior or API contracts.

Checkpoint 25 adds versioned informational training-demand context with questionnaire and observed
evidence, missing-versus-zero handling, contributor completeness, conservative demand levels, and
future-facing protein/carbohydrate priorities. It does not change current nutrition calculations.
Checkpoint 26 adds a fixed-calorie training-aware macro policy with explicit protein/carbohydrate
provenance, feasibility constraints, and latest-plan-only integration.

Checkpoint 27 adds informational nutrition feasibility and deterministic category-level guidance
based on the explicit dietary profile and final macro plan. Targets remain unchanged; no meals or
recipes are generated.

Checkpoint 28 adds deterministic current-plan adherence and observed-outcome assessment with
trailing-window evidence thresholds, missing-versus-zero preservation, optional as-of filtering,
and a Progress-stage summary. It is informational and does not change targets or recommendations.

Checkpoint 29 adds a deterministic proposal-only recommendation decision layer with explicit
hold/increase/decrease/defer outcomes, conservative goal-aware adjustment sizes, adherence gates,
target-floor constraints, adaptive-TDEE context, and proposed macro/envelope recalculation. It does
not activate plans, retain adaptation history, or change progression.

Checkpoint 30 adds stateless longitudinal plan adaptation with immutable events, cooldown and fresh
evidence requirements, anti-oscillation reversal suppression, activate/hold/defer/suppress actions,
caller-owned history, and Progress/API activation eligibility. It does not persist or automatically
activate plans.

Checkpoint 31 adds immutable recommendation history and explainability derived from caller-supplied
adaptation events. It distinguishes profile recalculation, progress adaptation, actual plan changes,
and evaluation-only hold/defer/suppression events, with deterministic summaries and notification-ready
latest-change fields. It does not add persistence or notification delivery.

Checkpoint 32 hardens engine integration with an authoritative `current_recommendation`, consolidated
`integration_status`, accepted-plan handoff behavior, profile-recalculation isolation, end-to-end
prefix safety, and an app integration guide. It does not add persistence or notification delivery.

Checkpoint 33 adds deterministic target-safety guardrails: BMI eligibility, sex-equation calorie
floors, a 25% baseline-TDEE deficit cap, constrained/ineligible statuses, observation bounds, and
CP29/CP30 safety enforcement. These are product guardrails, not individualized medical advice.

Checkpoint 34 replaces the production adaptive-TDEE aggregate with an aligned 28-day Theil-Sen
estimate, explicit evidence span/contributors, categorical stability, and V2 reason/provenance
fields. It does not change the adaptive-TDEE formula family or add product features.
