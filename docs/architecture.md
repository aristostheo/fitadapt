# V0.1 Architecture

V0.1 keeps the scientific core independent of databases, frameworks, and user interfaces.
The initial execution path is intentionally small:

```text
Validated user profile
        |
        v
Versioned deterministic baseline calculations
        |
        v
Transparent baseline estimate and assumptions
```

The `UserProfile` domain model validates its inputs before they reach any calculation code.
The baseline package now performs a pure, versioned calculation:

```text
UserProfile -> Mifflin-St Jeor REE -> activity multiplier -> BaselineEnergyEstimate
```

`BaselineEnergyEstimate` preserves full calculation precision and records both formula and
activity-policy versions. REE is an estimate of resting energy expenditure; TDEE is that estimate
adjusted by a rough population-level activity multiplier. Goal and requested weekly change are
validated profile inputs but do not affect energy estimates until the calorie-target checkpoint.

The activity multipliers are intentionally isolated from the REE formula because they represent
a separate, weaker static assumption. The adaptive-estimation layer is intended to improve on
these population-level assumptions using reliable longitudinal observations.

The target layer composes, rather than copies, `BaselineEnergyEstimate`:

```text
Validated profile
    -> estimated REE and baseline TDEE
    -> signed daily calorie adjustment
    -> daily calorie target
    -> protein and fat allocation
    -> remaining calories assigned to carbohydrates
    -> CalorieTargetEstimate
```

It uses a versioned `7,700 kcal/kg` planning approximation and a separate, versioned macro
policy. These deterministic outputs are distinct from personalized/adaptive estimates and
recommendations. If protein and fat cannot fit within a target, the policy raises an explicit error
instead of producing negative carbohydrates or silently changing inputs.

## Daily Observation Boundary

`UserProfile` represents relatively stable user settings and a selected goal. `DailyObservation`
represents partial measurements captured for one calendar date. Its optional fields preserve the
distinction between missing (`None`) and an observed zero; it does not fill, infer, or derive
values.

Daily observations remain upstream of trend, data-quality, adaptive-estimation, and modelling
layers. They do not reconcile nutrition totals or reject future dates, because those behaviours
would introduce assumptions about logging and the current clock into the domain model.

## Calendar Trend Boundary

The analysis layer reindexes observations onto continuous calendar dates, calculates trailing-only
rolling features, and reports completeness with all calendar days as denominators. It does not
impute values, predict outcomes, or personalize estimates.

## Current Calculation Paths

```text
UserProfile
    -> baseline REE/TDEE
    -> baseline calorie and macro targets

DailyObservation history
    -> calendar-aware trends
    -> adaptive TDEE estimate
```

The adaptive result is an observed-data estimate only. It does not overwrite the baseline estimate
or change baseline calorie or macro targets. The recommendation layer composes baseline, trend, and
adaptive outputs behind an eligibility gate without mutating any of them.

## Personalization Lifecycle Boundary

The lifecycle is a separate readiness/status composition. It recalculates existing calendar trends
and adaptive estimates from the complete supplied history, then reports `baseline`, `calibrating`,
`early_personalized`, or `personalized` evidence without adding a new calculation formula:

```text
UserProfile + DailyObservation history
    -> calendar trends + adaptive TDEE
    -> lifecycle readiness, requirements, and evidence counts
```

It does not manufacture an early aggregate, assign a confidence score, change macro preferences,
or mutate the baseline, trends, adaptive result, recommendation, profile, or observation history.
The FastAPI lifecycle route remains stateless; callers resupply their history for each assessment.

## Entry-By-Entry Planning Boundary

The planning layer composes existing output for every chronological submitted-observation prefix:

```text
UserProfile + observations through one entry + NutritionPreferences
    -> baseline target + lifecycle + recommendation
    -> selected baseline or actionable personalized target
    -> preference-driven macro plan
```

It creates no new REE, TDEE, calorie-adjustment, lifecycle, smoothing, or macro formulas. Before
an existing adaptive aggregate can responsibly support an actionable recommendation, planning uses
the baseline target. A personalized lifecycle with an unavailable or unsafe recommendation also
falls back explicitly to baseline while retaining recommendation reasons. Future observations cannot
change earlier snapshots, and the layer remains stateless. The standalone web client renders this
contract; integration into external products remains a separate future boundary.

## Unified Profile Intelligence Boundary

The unified application orchestration collects existing outputs without changing their contracts:

```text
UserProfile + DailyObservation history + NutritionPreferences
    -> baseline + trends + adaptive TDEE + lifecycle + recommendation
    -> latest proposed plan
    -> optional chronological plan progression
    -> explicit HTTP response schemas
```

`POST /v1/profile-intelligence` uses the documented existing defaults and is stateless. Its
latest-only response avoids constructing progression by default; requesting progression recomputes
every chronological prefix and is intentionally more expensive. The orchestration does not add
formulas, caches, synthetic truth, ML inference, persistence, or mutation. The standalone React
client consumes this operation rather than duplicating calculations. It keeps profile, preferences,
and imported observations only in session memory; browser CSV/JSON import is previewed locally and
never adds an upload or persistence boundary.

## Preference Macro Boundary

`NutritionPreferences` is separate from `UserProfile`: equation inputs and goals remain in the
profile, while explicit strategy choices remain in the personalization package. The macro allocator
accepts a caller-supplied calorie target and an explicit `baseline` or `personalized` source:

```text
UserProfile + NutritionPreferences + supplied calorie target
    -> preference_macros_v1
    -> PersonalizedMacroPlan
```

It does not call adaptive TDEE, overwrite V0.1 baseline macros, infer preferences from physiology,
or mutate recommendation outputs. The existing baseline macro contract is retained unchanged.

## Nutrition Target Envelope Boundary

The range layer is additive and downstream of the exact preference-driven macro plan:

```text
selected baseline or safe personalized calorie target
    -> exact preference_macros_v1 allocation
    -> nutrition_target_ranges_v1 policy envelope
    -> domain, API, and standalone-client representations
```

It does not select energy, alter a recommendation, or replace exact macros. It adds a fixed calorie
adherence band, bounded protein/fat preferred bands, and a carbohydrate flexible remainder with
explicit versions and assumptions. Baseline and pre-personalized plans keep baseline-source
envelopes. Safe personalized plans keep the existing recommendation target; safety fallback keeps
its baseline target and reason codes. Prefix progression constructs each envelope from only the
observations available at that snapshot, so future entries cannot alter earlier envelopes.

The bands are product policy, not medical requirements. Their endpoints are independent and are not
arbitrary jointly energy-reconciling combinations. This boundary does not provide food selection,
allergies/restrictions, medical nutrition therapy, meal generation, micronutrient analysis,
training-day/rest-day targets, or budget, cuisine, cooking, or schedule optimization.

## Dietary Preference Assessment Boundary

Dietary assessment is a downstream composition over an existing target envelope:

```text
profile + calorie target + macro preferences
    -> exact macro plan -> nutrition target envelope
    -> dietary pattern + hard constraints + soft preferences
    -> conflicts, verification notices, and protein-source flexibility
```

The `dietary_categories_v1`, `dietary_patterns_v1`, `dietary_assessment_v1`, and
`protein_flexibility_v1` policies are framework-independent. Allergies, required exclusions,
pattern exclusions, and excluding intolerances override limiting intolerances and soft preferences.
The assessment measures food-choice variety and adherence difficulty, not biological impossibility.
The unified endpoint adds the current/latest assessment only; progression snapshots are unchanged.
This boundary does not add frontend onboarding, individual foods, recipes, meals, medical nutrition
therapy, micronutrients, persistence, or budget/cuisine/schedule/cooking logic.

## HTTP Adapter Boundary

Checkpoint 13 adds a stateless adapter outside the domain packages:

```text
HTTP JSON
   -> Pydantic transport schemas
   -> domain objects and existing engine functions
   -> explicit response schemas
   -> HTTP JSON
```

FastAPI contains no fitness formulas and stores no profile or observation data. Domain packages do
not depend on FastAPI or Pydantic, and API failures do not mutate engine state. The synthetic ML
benchmark and interpretation modules are not called by any API endpoint.

```text
React browser client -> FastAPI JSON adapter -> typed domain engine
```

The standalone React client keeps session-only form state and never duplicates calculations. It
renders exact selected targets and server-provided ranges from `/v1/profile-intelligence`; the API
remains the validation and calculation boundary.

## Guided Web Experience Boundary

The standalone web client organizes these contracts into a five-stage journey:

```text
Profile -> Nutrition -> History -> Plan -> Progress
```

Profile and Nutrition collect session-only inputs, History supports direct entry and browser-only
CSV/JSON preview/import, Plan presents the current selected target before explanations and food
flexibility, and Progress presents existing trends and optional chronological plan history. The
client adds no formulas, persistence, authentication, or backend endpoints. Technical identifiers
and reason codes remain available through secondary disclosures while primary cards use
consumer-facing explanations. Responsive layouts, keyboard navigation, visible focus, ARIA stage
state, labeled actions, and reduced-motion support remain presentation concerns.

## Synthetic Evaluation Boundary

The evaluation layer is the only non-test layer permitted to compare production estimates with
synthetic hidden truth. It builds trends and adaptive estimates from `DailyObservation` values
only, then aligns eligible adaptive estimates to hidden truth by exact `datetime.date` afterward.

```text
Profile -> static baseline -----------------+
                                             +-> evaluation metrics
Observations -> trends -> adaptive TDEE -----+
                                             |
Synthetic hidden truth ----------------------+
```

Hidden truth must never enter production trend or adaptive estimation. Baseline-all-days metrics
use every synthetic truth date; paired baseline and adaptive metrics use the same adaptive-eligible
dates. This boundary supports controlled synthetic evaluation, not real-world validation.

## Synthetic ML Boundary

```text
Synthetic histories
    -> observation-only feature construction
    -> grouped train / validation / test split
    -> train-only preprocessing
    -> baseline and ML model comparison
    -> held-out test evaluation
```

Hidden truth supplies future labels and evaluation targets only. It is never a feature.

```text
Selected validation winner
    -> standardized coefficient extraction
    -> validation permutation importance
    -> held-out test residual diagnostics
```

Validation supports selection and permutation diagnostics; held-out test data supports residual
diagnostics only. Interpretation never changes recommendations or user targets.

```text
profile + observations
        -> baseline + trends + adaptive estimate
        -> eligibility gate
        -> hold / small explainable adjustment / insufficient evidence
```

Recommendations compose upstream outputs and never mutate or replace them.

## Synthetic Data Boundary

Synthetic generation is an in-memory test/development layer, not a source of real-world evidence:

```text
Simulation configuration
          -> hidden daily truth
          -> noise and missingness
          -> DailyObservation or no observation
```

`SyntheticHistory` retains hidden truth for evaluation, while future estimators must consume only
the noisy observations. A seed-scoped NumPy generator makes results reproducible. The simulator is
deliberately linear and does not model metabolic adaptation, body composition, or other complex
physiology.

Future predictive models, storage, authentication, and client-integration layers must remain
separate and consume the core through typed inputs and outputs, not embed calculation rules.

## Data and privacy boundary

No personal fitness or health-adjacent data belongs in this repository. Future local datasets
will be ignored under `data/private/`; synthetic data will be explicitly labelled as synthetic.
