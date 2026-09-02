# V0.1 Architecture

V0.1 keeps the scientific core independent of databases, frameworks, and user interfaces.
The initial execution path is intentionally small:

```text
Validated user profile
        |
        v
Versioned deterministic baseline calculations
        |
        v
Transparent baseline estimate and assumptions
```

The `UserProfile` domain model validates its inputs before they reach any calculation code.
The baseline package now performs a pure, versioned calculation:

```text
UserProfile -> Mifflin-St Jeor REE -> activity multiplier -> BaselineEnergyEstimate
```

`BaselineEnergyEstimate` preserves full calculation precision and records both formula and
activity-policy versions. REE is an estimate of resting energy expenditure; TDEE is that estimate
adjusted by a rough population-level activity multiplier. Goal and requested weekly change are
validated profile inputs but do not affect energy estimates until the calorie-target checkpoint.

The activity multipliers are intentionally isolated from the REE formula because they represent
a separate, weaker static assumption. Future adaptive estimation should improve on these
population-level assumptions using reliable longitudinal observations.

Future adaptive estimation, predictive models, recommendation policy, storage, and an API
will remain separate layers. They must consume the core through typed inputs and outputs,
not embed calculation rules themselves.

## Data and privacy boundary

No personal fitness or health-adjacent data belongs in this repository. Future local datasets
will be ignored under `data/private/`; synthetic data will be explicitly labelled as synthetic.
