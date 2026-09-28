# Adaptive TDEE

Daily balance equals configured-window weight change times the energy equivalent divided by the
trend window length. Adaptive TDEE equals trailing logged intake minus that balance. The estimator
uses only eligible trend points, then takes the median of eligible values in its trailing aggregation
window; MAD in kcal/day describes spread only. It does not overwrite baseline or calorie targets.

FitAdapt V2 estimates observed TDEE from one aligned trailing calendar window. The default window is
28 days, with at least 5 valid weigh-ins, 14 intake contributors, and 14 calendar days between the
first and last valid weigh-in. Raw intake and weight observations come from the same effective
start/end dates; missing values are not imputed and zero intake remains observed data.

## Robust estimator

The weight trend uses a deterministic Theil-Sen slope over valid weigh-ins and actual calendar-day
spacing. A single outlier weigh-in therefore has limited influence. The transparent energy-balance
relationship remains:

`TDEE ~= aligned mean intake - (weight slope kg/day * 7,700 kcal/kg)`

The 7,700 kcal/kg conversion is an approximation, not measured physiology. V2 reports the aligned
intake, slope, contributor counts, calendar span, method version, and reason codes.

## Stability

Stability is categorical rather than a fake confidence percentage:

- `insufficient`: contributor, intake, or calendar-span requirements are not met.
- `unstable`: median absolute slope residual dispersion exceeds the configured threshold.
- `stable`: sufficient evidence with residual dispersion within the threshold.

Unstable estimates do not strengthen CP29 plan-change decisions. The estimator remains observational
decision support and does not independently generate a target.

## Noise and limitations

The estimator is designed to reduce sensitivity to short-window scale noise, outlier weigh-ins, and
misaligned intake windows. Water, glycogen, sodium, illness, medication, logging bias, and abrupt
behavior changes can still distort the result. Synthetic stress benchmarks are evaluation tools, not
clinical validation. Missing intake or weight evidence returns insufficient output rather than a
fabricated TDEE.

The current default is 28 days. A 21-day candidate remains available through configuration for
evaluation comparisons; the longer default was selected to provide more robust slope evidence before
downstream decisions.
