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
The next checkpoints will add pure functions for BMR, activity adjustment, calorie targets,
and macro targets. Those functions will preserve unrounded values while calculating and round
only public results.

Future adaptive estimation, predictive models, recommendation policy, storage, and an API
will remain separate layers. They must consume the core through typed inputs and outputs,
not embed calculation rules themselves.

## Data and privacy boundary

No personal fitness or health-adjacent data belongs in this repository. Future local datasets
will be ignored under `data/private/`; synthetic data will be explicitly labelled as synthetic.
