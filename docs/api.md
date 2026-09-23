# FitAdapt HTTP API

## Purpose

The FitAdapt API is a small, stateless FastAPI adapter over the existing domain engine. It exposes
baseline targets, calendar-aware trends, adaptive TDEE, lifecycle readiness, conservative calorie recommendations,
and a unified profile-intelligence response.
It stores no submitted profile or observation data, contains no fitness formulas, and is not a
clinical, medical, or nutritional treatment service. Synthetic ML benchmarks and model
interpretation are not used by recommendation endpoints.

## Run Locally

```bash
uv sync
uv run uvicorn fitadapt.api.app:app --reload
```

Swagger UI is at `http://127.0.0.1:8000/docs`; OpenAPI JSON is at
`http://127.0.0.1:8000/openapi.json`.

The API and health version are read from installed `fitadapt` package metadata. A direct,
uninstalled source-tree import uses the deterministic fallback `0+uninstalled`.

`fastapi` and `uvicorn` are runtime dependencies because the latter serves the application.
`httpx` is a development dependency used only by the FastAPI integration-test client.

## Browser CORS

The local standalone client is allowed from `http://localhost:5173` and `http://127.0.0.1:5173` only. Set `FITADAPT_CORS_ORIGINS` to a comma-separated explicit allowlist for another environment. Wildcard origins and credentials are not enabled.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service, API, and recommendation-policy metadata. |
| `POST` | `/v1/baseline` | REE, baseline TDEE, calorie target, and macro allocation. |
| `POST` | `/v1/trends` | Calendar-day rolling trends and data quality. |
| `POST` | `/v1/adaptive-tdee` | Trend-derived daily and aggregate adaptive TDEE. |
| `POST` | `/v1/recommendations/calories` | Conservative, evidence-gated calorie adjustment. |
| `POST` | `/v1/macros/personalized` | Explicit V1 macro plan for supplied baseline or personalized calories. |
| `POST` | `/v1/personalization/status` | Recomputed evidence stage and next data-logging requirements. |
| `POST` | `/v1/profile-intelligence` | Complete stateless baseline, evidence, recommendation, and latest-plan response. |

All `POST` routes use explicit JSON schemas. Unknown fields, numeric booleans, `NaN`, and infinity
are rejected at the transport boundary. ISO dates use `YYYY-MM-DD`; omitted optional measurements
are `null`. Numeric zero is an observed value, not missing data.

Profile enums are `female`/`male`, `sedentary`/`lightly_active`/`moderately_active`/
`very_active`/`extra_active`, and `cut`/`maintain`/`gain`. Recommendation statuses and reasons are
returned as their stable string enum values. All unavailable engine outputs are JSON `null`.

## Example

```bash
curl -X POST http://127.0.0.1:8000/v1/baseline \
  -H 'content-type: application/json' \
  -d '{
    "profile": {
      "age_years": 30,
      "height_cm": 180,
      "weight_kg": 80,
      "sex_for_mifflin_equation": "male",
      "activity_level": "moderately_active",
      "goal": "maintain",
      "requested_weekly_change_kg": 0
    }
  }'
```

The response has an explicit schema containing the unrounded baseline energy values, signed daily
adjustment, macro targets, formula/policy versions, and assumptions. The trend response contains
calendar-day points and quality metrics. The adaptive response contains daily eligibility values,
aggregate TDEE, MAD, and assumptions. The recommendation response contains the full public
recommendation contract, including ordered reasons and `null` actionable outputs when evidence or
safety gates fail.

`POST /v1/macros/personalized` accepts a profile, `calorie_target_kcal_per_day`, `calorie_source`
(`baseline` or `personalized`), and explicit nutrition preferences. Strategy values are `balanced`,
`higher_carb`, `higher_fat`, `higher_protein`, and `custom`; custom plans require both protein
g/kg/day and fat-percentage fields. Its result records full-precision macro energy reconciliation,
the strategy/source, `preference_macros_v1`, and assumptions. It does not change existing V0.1
baseline macros or infer preferences from adaptive estimates or ML.

`POST /v1/personalization/status` accepts the same strict profile and observation transport models
as the analysis endpoints, with optional `trend_config`, `adaptive_config`, and
`lifecycle_config`. It reports one of `baseline`, `calibrating`, `early_personalized`, or
`personalized`; ordered requirements; calendar/count/completeness evidence; eligible and required
adaptive-estimate counts; optional aggregate adaptive TDEE and MAD; policy versions; and
assumptions. It recomputes status from the full submitted history, does not create a confidence
score or premature TDEE estimate, and does not alter recommendations, macro plans, or stored data.

`POST /v1/profile-intelligence` accepts `profile`, `observations`, `nutrition_preferences`, and
an optional strict boolean `include_plan_progression` (default `false`). It returns explicit
baseline, trends/data quality, adaptive TDEE, lifecycle, recommendation, latest-plan, and optional
progression sections using the same full-precision schemas as existing routes. Nutrition strategy
changes only the nested macro allocation. When progression is requested, it returns one
chronological prefix plan per submitted observation; this is larger and more expensive than the
latest-only default. Empty history remains a complete undated baseline response. See
[profile-intelligence API](profile-intelligence-api.md) for the executable request example.

Run the supplied non-identifying recommendation example with:

```bash
curl -X POST http://127.0.0.1:8000/v1/recommendations/calories \
  -H 'content-type: application/json' \
  --data @examples/recommendation_request.json
```

## Errors

Malformed JSON and transport-schema failures use FastAPI's standard deterministic `422` validation
response. Valid JSON that violates a FitAdapt domain contract uses a documented `400`
`ErrorResponse`; unexpected failures use the same schema with `500`:

```json
{"error": {"code": "trend_analysis_error", "message": "Duplicate observed_on dates are not allowed."}}
```

Codes are `profile_validation_error`, `observation_validation_error`, `trend_analysis_error`,
`adaptive_tdee_error`, `macro_policy_infeasible`, `nutrition_preferences_error`,
`macro_plan_infeasible`, `recommendation_error`, and `personalization_lifecycle_error`. Unexpected failures
return `500` with `internal_server_error` and no implementation details. The unified endpoint also
uses `personalized_planning_error` and `profile_intelligence_error` for its applicable domain
contract failures.

## Non-Goals

There is no persistence, authentication, authorization, database, deployment setup, or ML inference
endpoint in this checkpoint. Future work must validate recommendation behavior with
real-world evidence before use beyond transparent decision support.
