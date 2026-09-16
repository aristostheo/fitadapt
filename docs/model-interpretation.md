# Weight-Change Model Interpretation

The selected validation winner is interpreted with standardized linear coefficients, validation-set
permutation importance, and held-out test residual diagnostics. Coefficients describe one-standard-
deviation transformed-feature associations, not causal effects. Missingness indicators are separate
transformed features. Permutation importance is measured as validation MAE increase and can be
negative when permutation happens to improve a correlated feature's validation performance.

Test residuals use `prediction - actual`; positive values overpredict. Diagnostics group held-out
records by synthetic history and loss/stable/gain target direction. These synthetic-only diagnostics
do not alter recommendations or targets and cannot establish clinical or real-world validity.

The default deterministic run selects `linear`. Its largest standardized coefficients and validation
permutation importances are descriptive of this synthetic cohort only; correlated trend features can
split or obscure importance. No fitted artifact is exposed or persisted, and real longitudinal data
is required before any real-world performance claim.
