# Synthetic Data Policy

Synthetic histories support pipeline development and tests when real longitudinal data is not
available. They are not evidence of real-world model performance and must never be reported as
such.

## Truth And Observation

Each simulated day stores hidden truth: start-of-day body weight, intake, expenditure, energy
balance, daily weight change, steps, and exercise. A separate observation may contain noisy scale
weight, noisy logged intake, and noisy steps. Missingness is applied only after truth exists.

An observation field of `None` means the value is missing. Numeric zero remains an observed zero.
When weight, nutrition, and activity are all missing, the day stores no `DailyObservation`.

## Version 1 Assumptions

- Expenditure equals base expenditure plus `0.04 kcal/step`, `6 kcal/strength minute`, and
  `8 kcal/cardio minute`.
- True daily weight change equals energy balance divided by `7,700 kcal/kg`.
- Intake and steps use normal sampling and are clamped at zero.
- Scale weight, logged intake, and observed steps use independent normal noise.
- Observed scale weight is clamped to the supported observation weight range.
- A seeded `numpy.random.default_rng` generator makes each configuration reproducible.

This deliberately simple policy excludes metabolic adaptation, body composition, hormonal cycles,
and nonlinear energy dynamics. It exists to test data handling and estimator recovery against
known simulated values, not to replicate human physiology.
