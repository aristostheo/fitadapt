# Dietary Preferences And Food Flexibility

Checkpoint 23 adds a framework-independent dietary preference assessment. It works with stable
food categories and never creates individual foods, recipes, meals, or nutrient records.

## Hard Constraints And Soft Preferences

`FoodConstraint` represents a hard rule or an intolerance:

- `allergy` always excludes a category.
- `required_exclusion` always excludes a category.
- `intolerance` may exclude or limit a category.

`FoodPreference` is a soft signal: `dislike`, `neutral`, `like`, or `favorite`. A soft preference
never overrides an allergy, required exclusion, dietary-pattern exclusion, or excluding intolerance.
A contradictory preference is retained in `conflicts` so the user can see the input tension.

The deterministic precedence order is allergy, required exclusion, dietary-pattern exclusion,
excluding intolerance, limiting intolerance, dislike, neutral, like, and favorite. Stronger rules
remain authoritative; weaker inputs are not silently rewritten.

## Patterns And Selection Modes

Supported patterns are `unrestricted`, `vegetarian`, `vegan`, `pescatarian`, `halal`, `kosher`, and
`other`:

- `unrestricted` infers no exclusions.
- `vegetarian` excludes poultry, beef, pork, fish, and shellfish.
- `vegan` applies vegetarian exclusions plus eggs and dairy.
- `pescatarian` excludes poultry, beef, and pork.
- `halal` conservatively excludes pork and requires later ingredient, preparation, and certification verification.
- `kosher` conservatively excludes pork and shellfish and requires the same verification.
- `other` infers no unsupported exclusions and returns a manual-review notice.

`broad` mode treats policy-allowed categories as generally available after hard exclusions and
limits. `selected` mode counts only explicitly neutral, liked, or favorite categories as accepted;
disliked, limited, and unspecified categories do not count as freely usable.

The V1 catalog includes protein-capable categories (poultry, beef, pork, fish, shellfish, eggs,
dairy, soy, legumes, protein supplements, nuts, seeds, and nut butters), carbohydrate/starch
categories (rice, pasta, bread, potatoes, oats, tortillas), produce (fruit, vegetables), and fat
sources (nuts, seeds, nut butters, avocado, cooking oils). A category may have more than one role.
The category policy is versioned as `dietary_categories_v1`.

## Protein Flexibility

The assessment uses the selected protein preferred range from the existing
`nutrition_target_ranges_v1` envelope. It does not recreate macro calculations and does not infer
physiological feasibility. It measures food-choice variety and likely adherence difficulty:

| Usable protein categories | Status       |
| ------------------------: | ------------ |
|                         0 | `infeasible` |
|                         1 | `difficult`  |
|                       2–3 | `limited`    |
|                 4 or more | `supported`  |

These thresholds are the versioned `protein_flexibility_v1` product policy. `infeasible` means that
no usable category was supplied for this assessment, not that a protein target is biologically or
mathematically impossible.

## API Contracts

`POST /v1/nutrition/preferences/assess` accepts a profile, calorie target/source, existing macro
preferences, and a dietary preference profile. The server constructs the exact macro plan and target
envelope first, then assesses the dietary profile against that trusted envelope. Clients cannot
submit a computed envelope.

`POST /v1/profile-intelligence` accepts the optional `dietary_preference_profile` field. Omission
uses an unrestricted/broad profile for backward compatibility. The response adds
`dietary_assessment`, representing the current/latest plan only. Progression snapshots are not
changed or duplicated with dietary assessments.

The assessment records category, pattern, assessment, and protein-flexibility policy versions,
target-envelope provenance, conflicts, verification notices, actionable requirements, and immutable
assumptions. Transport errors use `422`; valid domain conflicts use the stable `nutrition_dietary_error`
`400` code; unexpected failures are opaque `500` responses.

## Limitations And Deferred Work

This checkpoint does not provide frontend onboarding, individual food records, recipes, meal
generation, medical nutrition therapy, micronutrient calculations, persistence, or budget, cuisine,
schedule, and cooking optimization. Halal and kosher outputs are deliberately not certifications.
The category model is a small V1 policy catalog, not a food database or a complete dietary ontology.
