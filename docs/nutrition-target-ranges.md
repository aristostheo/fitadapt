# Nutrition Target Ranges

`nutrition_target_ranges_v1` wraps one exact, feasible `preference_macros_v1` plan in transparent
product-policy bands. The envelope is decision support, not a second energy calculation and not a
medical prescription.

## Energy And Macro Separation

The caller first supplies a calorie target and identifies its source as `baseline` or
`personalized`. FitAdapt then runs the existing preference-driven macro allocator to obtain one
exact energy-reconciling plan. Only after that selected plan succeeds does the range policy add
adherence and flexibility bands:

```text
selected baseline or safe personalized calories
    -> exact preference_macros_v1 plan
    -> nutrition_target_ranges_v1 envelope
```

The envelope never changes the selected calorie target, macro strategy, or exact macro plan. A
planning snapshot uses the baseline calorie source while evidence is baseline, calibrating, or
early-personalized. A personalized snapshot uses the existing safe recommendation target; if that
recommendation is unavailable or unsafe, its established baseline fallback and reason codes remain
unchanged.

## V1 Policy Bands

All calculations preserve full precision. Display rounding is a client concern.

| Target | V1 rule |
| --- | --- |
| Calories | Selected target plus or minus `100 kcal/day`; the lower bound is clamped to zero. |
| Protein | Selected `g/kg/day` plus or minus `0.2`, multiplied by total body weight; clamped to the supported `1.2–2.4 g/kg/day` limits. |
| Fat | Selected calorie fraction plus or minus `0.05` (five percentage points), converted with `9 kcal/g`; clamped to the supported `20–40%` limits. |
| Carbohydrate | Flexible energy remainder after applying the calorie, protein, and fat bounds, converted with `4 kcal/g` and clamped to zero. |

The carbohydrate lower bound uses lower-bound calories with upper-bound protein and fat. The upper
bound uses upper-bound calories with lower-bound protein and fat:

```text
carbohydrate lower = max(0, (calorie lower - 4 * protein upper - 9 * fat upper) / 4)
carbohydrate upper = max(0, (calorie upper - 4 * protein lower - 9 * fat lower) / 4)
```

Balanced, higher-carbohydrate, higher-fat, and higher-protein strategies use their existing selected
protein and fat values. Custom values remain subject to the existing inclusive `1.2–2.4 g/kg/day`
protein and `20–40%` fat boundaries. Preferred ranges narrow at those limits rather than extending
beyond them.

The exact selected plan is one feasible, energy-reconciling point. Range endpoints express separate
policy bounds; arbitrary combinations of calorie, protein, fat, and carbohydrate endpoints are not
guaranteed to reconcile. Users do not need to hit exact grams perfectly, but the envelope is not a
license to combine every extreme simultaneously.

## Hand-Calculated Example

For an 80 kg profile, `2,400 kcal/day`, baseline calorie source, and the balanced strategy:

- Selected protein: `1.8 * 80 = 144 g/day` (`576 kcal/day`).
- Selected fat: `25% * 2,400 / 9 = 66.666... g/day` (`600 kcal/day`).
- Selected carbohydrate: `(2,400 - 576 - 600) / 4 = 306 g/day`.
- Calorie adherence range: `2,300–2,500 kcal/day`.
- Protein preferred range: `(1.8 +/- 0.2) * 80 = 128–160 g/day`.
- Fat preferred range: `(20–30%) * 2,400 / 9 = 53.333...–80 g/day`.
- Carbohydrate flexible range: `235–377 g/day`, derived from the cross-bounds above.

The selected `144 g` protein, `66.666... g` fat, and `306 g` carbohydrate still reconcile exactly
to `2,400 kcal/day`; the range endpoints are not one combined menu.

## Validation, Feasibility, And Provenance

Inputs use the existing strict profile, nutrition-preference, calorie-source, and finite-number
contracts. Range tolerances must be finite and non-negative. If the selected calorie target cannot
fund the strategy's protein and fat allocation, the existing feasibility failure is surfaced as a
`NutritionTargetEnvelopeError`; FitAdapt does not silently reduce macros or invent negative
carbohydrates.

Every envelope records `nutrition_target_ranges_v1`, the underlying macro-policy version, calorie
source, strategy, policy floors, assumptions, and the complete exact macro plan. Domain models are
frozen and slotted. `POST /v1/nutrition/targets` exposes the same contract, and each current or
progression plan in `POST /v1/profile-intelligence` carries its prefix-specific envelope.

## Limitations

These bands are product-policy assumptions for transparent general-adult decision support, not
medical requirements or evidence that a range is optimal for an individual. They use total body
weight, fixed macro energy factors, a fixed calorie tolerance, and the selected V1 strategy. They do
not yet implement food selection, allergies or restrictions, medical nutrition therapy, meal
generation, micronutrient analysis, training-day/rest-day targets, or budget, cuisine, cooking, or
schedule optimization. Real-world validation is required before broader use.
