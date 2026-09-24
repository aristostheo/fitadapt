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
