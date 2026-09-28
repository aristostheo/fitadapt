# Plan Outcome Assessment

FitAdapt's plan-outcome assessment describes recorded adherence and observed weight progress
against the existing proposed plan. It is included as `plan_outcome` in
`POST /v1/profile-intelligence` and shown in the Progress stage. It never changes calories, macros,
recommendations, or plan progression.

## Evidence and interpretation

The assessment uses the selected plan's calorie target, the profile's requested weekly weight
change, and a configurable trailing calendar window (28 days by default). Intake adherence is
classified as below, near, or above target using a configurable absolute tolerance (150 kcal/day by
default). Weight-rate evidence reuses the existing calendar-aware trailing weight means, then
compares the observed weekly rate with the requested rate and a configurable tolerance.

Completeness is reported separately for intake and weight. Default sufficiency requires at least
14 intake contributors at 70% completeness, at least 4 weight contributors at 30% completeness,
at least 70% trailing-window coverage, and at least 14 days between weight contributors. Thresholds
and policy version are configurable through `PlanOutcomeConfig`. Missing data remains unknown;
observed zero intake remains a contributor. Sparse or early history is classified as limited, not as
non-adherence. Overall interpretability requires sufficient evidence for both dimensions and
recorded intake near the prescribed target.

By default, the effective date is the latest observation date. The API's optional
`outcome_as_of_date` and the domain function's `as_of_date` exclude later observations. Duplicate
dates and invalid domain inputs use the existing validation boundaries. No meal, clinical, causal,
or medical conclusions are produced.
CP30 may consume this assessment to gate activation, but does not alter its evidence or
interpretation. Activation cooldown and reversal history are separate adaptation policy concerns.

Checkpoint 31 history summaries consume the resulting adaptation events and retain the outcome's
evidence date and structured provenance; they do not reinterpret CP28 evidence.
