# Calorie Recommendations

The recommendation engine composes the baseline target, observation trends, and adaptive TDEE into
a conservative eligibility gate. It returns insufficient data, hold, or a limited explainable
adjustment; it never mutates the profile or replaces the baseline target. This is decision support,
not medical treatment, and remains sensitive to self-reported intake and scale-weight noise.

Eligibility requires at least 21 calendar days, 70% weight and intake completeness, a recent intake
mean and weight change, available adaptive TDEE, and at least four eligible adaptive estimates.
Failures are ordered: history, weight completeness, intake completeness, recent intake, weight
trend, adaptive availability, adaptive count. If any fail, all recommendation calculations are
`None` rather than zero.

After eligibility and limiting, a non-positive proposed target is non-actionable. A positive target
that cannot fund the existing protein-and-fat macro policy is also non-actionable. These follow the
eligibility reasons as `non_positive_proposed_target` then
`macro_policy_infeasible_proposed_target`; no universal calorie floor is introduced.

When eligible, `personalized target = adaptive TDEE + signed weekly-change adjustment`; `raw change
= personalized target - recent intake`. Changes at or within `75 kcal/day` hold. Larger changes are
limited to `+/-150 kcal/day`; proposed intake equals recent intake plus that limited value. Example:
adaptive TDEE 2,000 and gain adjustment 220 gives raw +220, limited +150, proposed 2,150 kcal/day.

Recommendations never overwrite the baseline target, trends, adaptive estimate, or user data. They
are sensitive to logging bias, hydration, glycogen, and measurement noise. Synthetic ML diagnostics
are not used. Real-user validation is required before application integration.
