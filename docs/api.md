# FitAdapt HTTP API

## Purpose

The FitAdapt API is a small, stateless FastAPI adapter over the existing domain engine. It exposes
baseline targets, calendar-aware trends, adaptive TDEE, and conservative calorie recommendations.
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

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service, API, and recommendation-policy metadata. |
| `POST` | `/v1/baseline` | REE, baseline TDEE, calorie target, and macro allocation. |
| `POST` | `/v1/trends` | Calendar-day rolling trends and data quality. |
| `POST` | `/v1/adaptive-tdee` | Trend-derived daily and aggregate adaptive TDEE. |
| `POST` | `/v1/recommendations/calories` | Conservative, evidence-gated calorie adjustment. |

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
`adaptive_tdee_error`, `macro_policy_infeasible`, and `recommendation_error`. Unexpected failures
return `500` with `internal_server_error` and no implementation details.

## Non-Goals

There is no persistence, authentication, authorization, CORS policy, database, deployment setup,
or ML inference endpoint in this checkpoint. Future work must validate recommendation behavior with
real-world evidence before use beyond transparent decision support.
