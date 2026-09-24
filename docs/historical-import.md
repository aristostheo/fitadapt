# Historical Observation Import

The standalone FitAdapt client imports history only in the browser. Nothing is uploaded through a
file endpoint or persisted by FitAdapt; an imported history is sent to the stateless API only when
the user later selects **Analyze my profile**.

## Formats And Fields

JSON accepts either an array of observations or an object with an `observations` array. CSV accepts
these canonical headers:

```text
observed_on,body_weight_kg,energy_intake_kcal,protein_g,carbohydrate_g,fat_g,
steps,strength_training_minutes,cardio_minutes,sleep_hours,hunger_rating,energy_rating
```

The browser supports a small deterministic alias set: `date`, `weight_kg`, `calories`, and
`calorie_intake_kcal`. Unknown JSON fields and CSV headers are rejected rather than guessed.

`observed_on` is an ISO calendar date without a time component. Blank CSV measurements become
`null`; `0` is retained as observed numeric zero. JSON numeric strings are rejected because the
API transport contract requires JSON numbers. The same UI validates finite values, domain ranges,
integer-only steps/ratings, and at least one measurement per row.

## Preview And Confirmation

Every import shows its format, total/valid/invalid row count, earliest/latest date, duplicate dates,
conflicts with current observations, compact date preview, and row-numbered errors. The maximum is
`5,000` rows. Canceling a preview changes nothing.

Invalid rows are never silently discarded. Correct them, or explicitly choose **Import valid rows
only** and review the accurate import summary. Duplicate dates inside an import require correction.

Choose one mode:

| Mode | Behavior |
| --- | --- |
| `merge` | Combine valid import rows with session history. |
| `replace_all` | Replace all current session observations with valid import rows. |

For merge conflicts, choose `reject_conflicts` (recommended), `keep_existing`, or
`replace_existing`. Confirmed results are sorted chronologically, clear stale analysis output, and
remain session-only. Use **Download CSV template** for `fitadapt-observations-template.csv`, which
contains canonical headers and one fictional row.

## Limitations

Import validates observation-shaped data, not medical plausibility or nutrition consistency. The
browser does not provide persistence, authentication, cloud upload, or file storage. Duplicate-date
and calculation policies remain enforced by the API when analysis is requested.
