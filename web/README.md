# FitAdapt Web Client

The standalone React/Vite client is a session-only view over the stateless FitAdapt API. It sends
profile, preferences, and observations only when the user chooses **Analyze my profile**; it has no
local storage, accounts, cookies, persistence, or browser-side fitness formulas.

## Run Locally

Terminal 1 starts the API:

```bash
uv sync
uv run uvicorn fitadapt.api.app:app --reload
```

Terminal 2 starts the client:

```bash
cd web
npm ci
npm run dev
```

`VITE_FITADAPT_API_URL` defaults to `http://127.0.0.1:8000`. Use `npm run lint`,
`npm run test -- --run`, and `npm run build` for validation.

## Profile Intelligence

The primary action sends one `POST /v1/profile-intelligence` request. It includes the profile,
daily observations, nutrition preferences, and optional plan-history flag. The browser does not
call legacy calculation endpoints as part of its analysis flow.

Users select balanced, higher-carb, higher-fat, higher-protein, or custom macro allocation.
Custom protein is limited to `1.2–2.4 g/kg`; custom fat is limited to `20–40%` of calories. This
preference changes macro allocation, not TDEE estimation. Lifecycle stages explain whether results
are baseline, calibrating, early-personalized, or personalized. Optional plan history reconstructs
one plan per historical observation prefix and can be slower for larger histories.

## Guided Journey

The client presents five session-only stages: Profile, Nutrition, History, Plan, and Progress.
Nutrition includes dietary pattern, broad or selected food mode, soft preferences, and hard
constraints. The Plan stage leads with the next action, explains the recommendation, shows flexible
targets and food-choice flexibility, then keeps lifecycle evidence and the baseline comparison
secondary. Technical policy identifiers and reason codes are available in expandable details.
Profile also includes an optional Training and Performance context section. It records occupation,
training frequency, optional duration/intensity, focus, and optional steps without estimating workout
calories or changing the current plan. The Plan assessment is informational; future checkpoints may
use it for training-aware macro policy.
The Progress stage shows weight, calorie, and step trends, observed variability, and optional plan
history. Missing values remain gaps; no browser-side formulas or interpolation are added.

The interface uses keyboard-navigable journey stages, visible focus states, labeled controls,
responsive cards and tables, and reduced-motion support. The browser keeps profile, dietary inputs,
observations, and results in session memory only. It does not provide accounts, persistence, food
records, recipes, meal generation, medical guidance, micronutrient analysis, or budget, cuisine,
cooking, or schedule optimization.

The current-plan panel keeps the selected next-step calorie and macro plan primary, then displays
its calorie adherence, protein and fat preferred, and carbohydrate flexible ranges from the unified
response. The selected plan is one exactly feasible point. Range endpoints are independent policy
bounds and arbitrary endpoint combinations may not reconcile; users do not need perfect daily gram
precision. The browser does not calculate or default these ranges.

## Historical Import

Imports are browser-only previews until confirmation. JSON accepts an array or an
`{"observations": [...]}` wrapper; CSV uses canonical headers. The client uses Papa Parse for
quoted CSV handling and rejects unknown headers, invalid rows, duplicates, and more than 5,000 rows.
Blank CSV cells become missing `null`; CSV `0` remains numeric zero.

Choose merge or replace-all. Merge supports rejecting date conflicts (default), keeping existing
records, or replacing existing records. The generated CSV template is fictional and contains all
canonical fields. See [historical import documentation](../docs/historical-import.md).

Sample history is fictional and deterministically generated around the currently displayed profile
weight, with varied calories and steps. It is complete enough to demonstrate personalization but is
not personal, clinical, or real-world evidence. Do not commit personal fitness data or use an
untrusted browser for sensitive data. FitAdapt is transparent decision support, not medical or
clinical guidance.

The client does not implement food selection, allergies/restrictions, medical nutrition therapy,
meal generation, micronutrient analysis, training-day/rest-day targets, or budget, cuisine,
cooking, or schedule optimization.
