# Adaptive TDEE

Daily balance equals configured-window weight change times the energy equivalent divided by the
trend window length. Adaptive TDEE equals trailing logged intake minus that balance. The estimator
uses only eligible trend points, then takes the median of eligible values in its trailing aggregation
window; MAD in kcal/day describes spread only. It does not overwrite baseline or calorie targets.

Food logging bias, water, glycogen, sodium, digestion, medication, illness, and overlapping rolling
windows limit the result. It is not measured TDEE, medical advice, or proof of clinical validity.
