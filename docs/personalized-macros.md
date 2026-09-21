# Personalized Macro Plans

## Purpose

`preference_macros_v1` is a separate macro-planning contract. It combines an explicit user
strategy with a caller-supplied calorie target; it does not infer food preferences from weight
change, adaptive TDEE, or the synthetic ML experiments. Existing V0.1 baseline macros remain
unchanged for backward compatibility.

## Strategies

| Strategy | Protein | Fat | Carbohydrates |
| --- | ---: | ---: | --- |
| Balanced | 1.8 g/kg/day | 25% of calories | Remaining calories |
| Higher carb | 1.6 g/kg/day | 20% of calories | Remaining calories |
| Higher fat | 1.6 g/kg/day | 35% of calories | Remaining calories |
| Higher protein | 2.0 g/kg/day | 25% of calories | Remaining calories |
| Custom | 1.2-2.4 g/kg/day | 20-40% of calories | Remaining calories |

No strategy is universally superior. Protein is allocated first from total body weight, fat is
allocated from target calories, and carbohydrates receive the remaining calories. This keeps the
V1 result transparent and exactly energy-reconcilable, but is not individualized nutrition care.

## Calorie Sources

The caller explicitly supplies both a calorie value and its source: `baseline` or `personalized`.
For example, `calculate_calorie_target(profile).target_calories_kcal_per_day` may be supplied as a
baseline target, while an eligible recommendation's personalized target may be supplied as a
personalized target. The macro allocator never calls adaptive TDEE itself.

## Custom Limits And Safety

The custom bounds are general-adult product-policy limits for a fitness decision-support product,
not universal medical requirements. Plans reject a non-positive or non-finite calorie target and
raise an explicit infeasibility error when protein plus fat cannot fit. Carbohydrates never become
materially negative; negligible floating-point remainders are treated as zero.

Medical-condition-specific nutrition planning is out of scope. The system does not yet learn
macro preference automatically, account for training/rest days, or use adherence feedback. Those
are future extensions requiring evaluation before recommendation use.
