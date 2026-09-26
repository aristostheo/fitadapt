# Training-Aware Nutrition Policy

Checkpoint 26 uses the reviewed Checkpoint 25 training assessment to refine macro composition while
keeping the selected calorie target unchanged. This is deterministic FitAdapt product policy, not a
medical prescription or a claim of universal optimality.

## Calories And Macros Stay Separate

Baseline or adaptive TDEE determines the supplied calorie target. Training-aware nutrition does not
add workout calories, estimate exercise expenditure, create training/rest-day cycling, or change
recommendations. It redistributes the same calorie budget between protein, fat, and carbohydrates.

The existing preference-driven macro allocator remains the foundation. Training-aware composition is
an additive layer around that feasible plan.

## Protein Policy

Structured resistance demand is the primary protein signal. The default preferred resistance values
are:

| Resistance demand | Preferred protein |
| ----------------- | ----------------: |
| Low               |      1.8 g/kg/day |
| Moderate          |      2.0 g/kg/day |
| High              |      2.2 g/kg/day |
| Very high         |      2.4 g/kg/day |

The effective value is never lower than the existing selected strategy value and remains bounded by
the existing macro policy. Endurance/cardio alone does not receive the same resistance protein uplift.
These are product-policy preferences, not medical requirements or universal optimal targets.

## Carbohydrate And Performance Policy

High or very-high aerobic/sport performance priority prefers a 20% fat floor, allowing more of the
same calorie budget to become carbohydrate. Protein is applied first, the established fat floor is
preserved, and carbohydrates receive the remainder. Moderate priority uses the same conservative
redistribution rule when the selected strategy has a higher fat share.

Intermittent sport uses the Checkpoint 25 sport/performance signal and remains distinct from resistance
protein policy. Mixed training can elevate both priorities, but both are resolved inside the fixed
calorie budget rather than maximized independently.

## Feasibility And Provenance

If the preferred training-aware protein target cannot fit with the established fat floor, the policy
caps protein at the largest feasible value and records `calorie_budget_limited_preferred_protein_target`.
It never returns negative carbohydrates or breaks calorie equality. The effective plan records:

- Whether training-aware adjustment was available and applied
- Default and training-aware protein/carbohydrate values
- Effective policy sources
- Protein and carbohydrate priorities
- Ordered, deduplicated reason codes
- `training_aware_macros_v1`

If training assessment is absent or insufficient, the existing macro plan is returned unchanged and
training-aware adjustment is not applied.

## Unified And Historical Behavior

`POST /v1/profile-intelligence` assesses training first, calculates the existing calorie target, then
applies training-aware macro composition only to the current/latest plan. Existing historical
progression snapshots remain unchanged and do not receive current training evidence. Existing clients
without `training_context` retain the default macro behavior unless sufficient observed training
signals provide an explicit resistance or performance priority.

## Limitations And Deferred Work

This policy does not estimate calorie burn, prescribe workouts, implement nutrient timing, recommend
supplements, provide clinical nutrition, guarantee performance, or activate training/rest-day cycling.
Training thresholds are deterministic FitAdapt product policy. Individual needs may vary, and the
system does not measure glycogen needs or diagnose deficiencies. Later work may review training-aware
protein and carbohydrate policy further, but this checkpoint does not add meals or workouts.
