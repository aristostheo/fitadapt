# Recommendation History

Checkpoint 31 adds a deterministic, immutable explainability stream over caller-supplied CP30
adaptation events. It answers what changed, when it changed, why it changed, and whether the entry
actually changed the active plan. FitAdapt still does not persist history.

## Entries

`RecommendationHistoryEntry` contains effective date, source, action, change type, plan-change versus
evaluation-only flags, previous/resulting targets, calorie delta, compact macro summaries, CP29
decision, evidence date, reason category, ordered reason codes, deterministic user summary, policy
versions, and assumptions. Macro summaries contain protein, carbohydrate, fat, calories, and macro
policy version rather than duplicating full nested plans.

Sources are `progress_adaptation` and `profile_recalculation`. Change types are `initial_plan`,
`profile_update`, `calorie_increase`, `calorie_decrease`, `hold`, `defer`, and `suppressed`.
Activated calorie changes and non-zero profile recalculations are plan-change entries. Hold, defer,
and suppressed reversal entries remain visible for technical auditing but are marked evaluation-only.

Summaries are derived from structured source/action/delta/reason data. Examples include:

- `Your calorie target decreased based on recent progress evidence.`
- `Your plan stayed the same because progress was broadly on track.`
- `FitAdapt is collecting more data before making another change.`
- `A reversal was suppressed because your plan was adjusted recently.`
- `Your profile update recalculated your plan.`

## API and isolation

`POST /v1/profile-intelligence` returns `recommendation_history`, including `latest_change`,
`has_new_recommendation_event`, `actionable_event_available`, and the current active target. History
is constructed from caller-supplied `adaptation_history`; no database or background process is added.
Entries are sorted by effective date, duplicate dates are rejected, and older entries are never
rewritten by newer events or observations. The main application can use the structured actionable
fields for future notifications without parsing prose.

The Progress screen shows the latest change prominently and renders a compact timeline. Actual plan
changes are distinguished from evaluation-only entries, and current active-plan context is explicit.
Technical policy identifiers and reason codes remain collapsed.

For app integration, `current_recommendation` is authoritative. History describes caller-supplied
events and does not itself activate a proposal; `integration_status` consolidates attention,
more-data, update-available, and reversal-suppressed signals.
