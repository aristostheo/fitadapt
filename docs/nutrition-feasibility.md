# Nutrition Feasibility And Practical Guidance

Checkpoint 27 evaluates the practical fit of the existing macro plan against the user's dietary
profile. It does not generate or revise nutrition targets.

## Mathematical And Practical Feasibility

The macro allocator first produces a mathematically feasible plan whose macro calories reconcile to
the selected calorie target. This module then asks whether broad food-category pathways appear
practical given accepted categories, restrictions, dislikes, and training-aware macro provenance.
A mathematically valid plan may still be challenging to follow with a narrow accepted food pool.

Feasibility levels (`easy`, `manageable`, `challenging`, `very_challenging`) are deterministic
product-policy categories, not medical risk or confidence scores. Protein, carbohydrate, fat, and
restriction compatibility are reported separately. Overall feasibility is the most challenging
macro dimension; restriction compatibility is reported alongside it rather than folded into an
opaque score.

## Dietary Evidence

The assessment reuses `NutritionPreferenceProfile` and `NutritionPreferenceAssessment`:

- Hard exclusions and limiting intolerances remove pathways.
- Dislikes are soft signals: they reduce preferred pathways but are not restrictions.
- Neutral, liked, and favorite categories are accepted according to the existing broad/selected
  semantics.
- `broad` means explicitly supplied broad flexibility; it is not inferred from a missing profile.
- Missing dietary information returns `assessment_available: false`.
- An empty selected-food profile is insufficient information; it is not treated as broad acceptance.

No duplicate food taxonomy is created. Existing `FOOD_CATEGORY_ROLES` determines protein,
carbohydrate, and fat category pathways.

## Feasibility Policy

`nutrition_feasibility_v1` uses independent, interpretable category-count and macro-density rules.
Default category-count thresholds are explicit:

| Dimension    |        Very challenging | Challenging | Manageable | Easy |
| ------------ | ----------------------: | ----------: | ---------: | ---: |
| Protein      | 0–1 accepted categories |           2 |        3–5 |   6+ |
| Carbohydrate |                       0 |           1 |        2–3 |   4+ |
| Fat          |                       0 |           1 |          2 |   3+ |

The restriction dimension is `highly_limited` at 5+ hard-excluded/limited categories, `limited` at
2–4, and `compatible` at 0–1. A protein calorie share at or above `32%`
and a carbohydrate share at or above `60%` each move an otherwise easy dimension to manageable or
an otherwise manageable dimension to challenging. Fat at or below `22%` similarly raises its
dimension by one practical-difficulty level. These do not change target values. Restrictions are
separately described as compatible, limited, or highly limited from hard exclusions and limited
intolerances; dislikes do not count as restrictions. These are product-policy thresholds, not
physiological cutoffs.

The result includes the current calorie and macro values as provenance. It never mutates the plan.
When training-aware macro policy was applied, the assessment may explain that the raised protein or
carbohydrate composition adds practical planning demand. Training-aware provenance remains distinct
from feasibility; neither step adds calories. The result preserves the active macro-policy version,
whether CP26 adjustment was applied, protein/carbohydrate policy sources and priorities, and baseline
versus training-aware protein/carbohydrate values where available.

## Practical Guidance

Guidance items are structured by category, priority, action, and stable reason code. Examples include
favoring accepted protein-dense categories, choosing familiar accepted carbohydrate pathways, or
reviewing how restrictions narrow category variety. Guidance stays at broad category level. It does
not name specific foods, quantities, recipes, meals, grocery lists, or meal schedules.

## Unified Flow And Limitations

`POST /v1/profile-intelligence` adds the current `nutrition_feasibility` assessment after the final
macro plan and existing dietary/training assessments. If no dietary profile was provided, the
assessment is explicitly unavailable even though the existing dietary display maintains its
backward-compatible unrestricted/broad default. This distinction prevents missing data from being
mistaken for broad food flexibility.

The assessment does not change calories, macros, target envelopes, recommendations, or progression.
Dietary preferences are self-reported; category counts are not nutrient data, and there is no food
database integration, micronutrient analysis, allergy diagnosis, clinical nutrition, meal generation,
or adherence guarantee. Future meal guidance is a separate checkpoint.
