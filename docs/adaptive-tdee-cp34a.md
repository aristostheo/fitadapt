# CP34A Adaptive-TDEE Validation

Every result here is **in-model synthetic evaluation**. It is not clinical, real-world, or prospective
validation. CP34A evaluates the existing V2 estimator and evaluation-only candidates; it does not
replace V2 or change CP29 production policy.

## Frozen Protocol

- Development/calibration seeds: `0..299`.
- Untouched held-out seeds: `10000..10299`.
- V1 is the exact pre-V2 implementation from the parent of commit `ee94a50`: 7-day trend estimates,
  then the median of eligible estimates whose dates fall in the trailing 14 calendar days, requiring
  four points.
- Candidates are V1, 21-day Theil-Sen, 28-day Theil-Sen, and an evaluation-only cumulative-energy
  OLS slope. V2's `0.50 kg` residual-MAD stability boundary remains fixed.
- Decision uncertainty multipliers are `1.5`, `2.0`, and `2.5`, with a `75 kcal/day` minimum
  threshold. The comparison uncertainty is `7700 * weight_residual_MAD_kg / evidence_span_days`; this
  is only a diagnostic proxy, not a confidence interval.
- The V2 public `median_absolute_deviation_kcal_per_day` remains unset for the raw-observation
  estimator. Its residual MAD is reported in the separate `weight_residual_mad_kg` field.

Date convention: same-date intake and weight observations are date-aligned, without inferring
within-day timing. The cumulative candidate sums intake on dates `[previous weigh-in, next weigh-in)`.
This is an explicit synthetic convention, not a claim about measurement timing in real users.

Synthetic inputs use true TDEE `2000 kcal/day`, logged intake variation with standard deviation
`150 kcal/day` where enabled, scale noise `0.4 kg`, and autocorrelated water noise with coefficient
`0.85` and innovation standard deviation `0.45 kg`. The missing-data case independently omits 20% of
weights and 15% of intakes. A transition changes intake by `-500 kcal/day`; its water variant adds a
temporary `-1.5 kg` shift over seven days followed by a 14-day return. Day 1 is the first calendar
date on which the changed intake is observed. Density mismatch uses `6160` and `9240 kcal/kg` while
the estimator retains `7700 kcal/kg`, during a `-300 kcal/day` deficit.

## Frozen Acceptance Criteria

- Stationary false recommendation rate (increase or decrease after gates): at most 10% in each
  stationary scenario.
- Stable coverage: at least 40% for both scale-noise and scale-plus-intake-variation scenarios.
- Conditional absolute error: stable MAE below unstable MAE when each group has at least 30 users.
- For both `+300` and `-300 kcal/day` TDEE shifts, correct-direction gated detection by day 28 is at
  least 60%, and opposite-direction recommendations are at most 10%.
- Abrupt intake-only transition signed mean error at day 28 is within `±150 kcal/day`.
- After the transient water shift has returned to baseline, stable false changes beyond
  `±150 kcal/day` occur in at most 10% of users.
- A candidate cannot qualify by marking fewer than 40% of ordinary scale-noise users stable.

Selection rule, applied only to development seeds and only to the existing 28-day V2 path: choose
among multipliers meeting all criteria by highest combined `±300` day-28 detection, then lowest
overall stationary false-change rate, then the smaller multiplier. If none meet every criterion,
choose among multipliers with at least 40% stable coverage by lowest overall stationary false-change
rate, then highest day-28 detection, then the smaller multiplier; explicitly report that no multiplier
passed. The 21-day and cumulative estimators are comparisons only and cannot replace V2. Do not retune
from held-out results. If held-out evidence exposes a code defect, repair it and reserve a new
untouched seed range.

## Development Calibration

For V2 at multiplier `2.5`, stationary false-change rates were `5.0%` scale-only, `5.7%` scale plus
intake variation, `30.3%` autocorrelated water, and `8.0%` missing-data. At `1.5`, those rates were
`19.0%`, `19.3%`, `43.7%`, and `26.3%`; at `2.0`, `11.0%`, `10.3%`, `37.7%`, and `15.3%`. No
multiplier met the 10% cap in every stationary scenario. All had 100% stable coverage for the two
ordinary scenarios and `67.3%` for water; stable MAE was not lower than unstable MAE in the water
scenario (`285.8` vs `291.7 kcal/day`). The frozen fallback therefore selects `2.5` for held-out
evaluation: it has the lowest aggregate stationary false-change rate among eligible multipliers.

At multiplier `2.5`, correct-direction detection for `+300/-300 kcal/day` was `99.3%/91.0%` by day
21 and `95.3%/91.0%` by day 28, with zero opposite-direction recommendations. Median detection was
day 21 for both. The abrupt intake-only day-28 signed mean bias was `-5.5 kcal/day`, and its regime
signal appeared by day 7 in all users. The combined intake/water scenario had `98.3%` persistent
stable false change beyond `±150 kcal/day` at day 28; the water transition therefore fails its frozen
criterion. With true TDEE `2000`, density-mismatch mean bias was `+64.2 kcal/day` at `6160` and
`-59.8 kcal/day` at `9240 kcal/kg` (both MAE below `85 kcal/day`).

## Held-Out Evaluation

The single development-selected multiplier `2.5` was evaluated once on seeds `10000..10299`.
Stationary results were:

| Scenario                 | Stable coverage |   MAE | Stable MAE | Unstable MAE |  HOLD | False increase | False decrease | False change |
| ------------------------ | --------------: | ----: | ---------: | -----------: | ----: | -------------: | -------------: | -----------: |
| Scale noise              |          100.0% |  57.4 |       57.4 |          N/A | 97.3% |           1.7% |           1.0% |         2.7% |
| Scale + intake variation |          100.0% |  57.1 |       57.1 |          N/A | 97.7% |           1.7% |           0.7% |         2.3% |
| Autocorrelated water     |           65.3% | 292.9 |      296.8 |        285.5 | 67.0% |          17.7% |          15.3% |        33.0% |
| Missing data             |           98.3% |  68.3 |       68.5 |         23.0 | 91.7% |           4.0% |           4.3% |         8.3% |

The `±300 kcal/day` power results had zero opposite-direction recommendations. Correct detections
were `92.7%` for `+300` and `94.0%` for `-300` by day 28; median detection was day 21 for both.
Detection by day 35 was `98.3%` and `97.7%`, respectively.

For abrupt intake-only change, day-28 signed mean error was `+0.3 kcal/day`, and the intake-regime
signal appeared by day 7 for all users. For abrupt intake plus water shift, the day-28 signed mean
error was `-369.2 kcal/day`; `98.7%` had a stable false change beyond `±150 kcal/day` at day 28.
That water-transition criterion fails on held-out seeds too. Density-mismatch signed mean errors
were `+75.7 kcal/day` at `6160` and `-50.2 kcal/day` at `9240 kcal/kg` (MAE `86.4` and `71.4`).

Verdict: the frozen V2 configuration and decision multiplier meet the stated false-change cap on
scale-only, scale-plus-intake-variation, and missing-data scenarios, and meet the power and
intake-only transition criteria. The autocorrelated-water stationary false-change criterion and
stable-versus-unstable error criterion fail, as does the combined intake/water transition criterion.
These failures are reported, not tuned away. The selected evaluation multiplier remains `2.5`; CP29
production policy is unchanged. Earlier exploratory aggregates are excluded because their generator
and V1 emulation were not verified against this protocol.

## CP34A2 Frozen Protocol

All CP34A2 results remain **in-model synthetic evaluation**. CP34A held-out seeds above are frozen
historical reference and will not be used to tune CP34A2.

- New development seeds: `20000..20299`.
- New untouched held-out seeds: `30000..30299`.
- The disturbance-aware 28-day V2 remains the reference. CP34A3 evaluates 28/35/42-day horizons
  without changing production behavior; cumulative energy remains comparison-only.
- Intake transition policy starts with a `250 kcal/day` minimum robust median shift, at least 7
  observed calendar days supporting each regime, a 42-day lookback, and 14 additional stabilization
  days after the final supporting new-regime day; CP34A2 fallback uses 28 stabilization days.
- Weight disturbance candidate guard compares early/late sub-window implied TDEE, not raw slopes;
  the selected development threshold is `585 kcal/day`. Existing residual MAD threshold remains
  `0.50 kg`; CP34A2 fallback disagreement threshold is `585 kcal/day`.
- Decision multiplier remains at the previously development-selected `2.5` for the frozen reference
  candidate comparisons. CP29 is not modified.

Frozen CP34A2 acceptance criteria for the new held-out set:

- Scale-only false-change rate at most `4.7%` (historical 2.7% plus 2 percentage points).
- Scale-plus-intake-variation false-change rate at most `4.3%` (historical 2.3% plus 2 points).
- Missing-data false-change rate at most `10.3%` (historical 8.3% plus 2 points).
- Both `+300` and `-300 kcal/day` day-28 detection at least `85%`; opposite direction at most `1%`;
  stable coverage at least `90%`.
- Autocorrelated-water stationary false-change rate at most `15%` and at least 50% relative reduction
  from the historical `33.0%`.
- For both intake-plus-water transition directions, stable false-change beyond `±150 kcal/day` by
  day 28 at most `20%`; stabilizing classification must not be counted as a recommendation.
- In water disturbance scenarios, stable MAE must be at least 20% lower than combined
  stabilizing/unstable MAE when both groups have at least 30 users.
- The intake-only step must enter stabilizing within 14 days and return to stable after the configured
  guard expires if post-change sub-window slopes agree.
- Select policy on development seeds only: among policies meeting every criterion, choose the
  shortest stabilization period. If none meet every criterion, choose among fallbacks meeting the
  ordinary-noise, power, water-rate, and transition-rate gates by the lowest mean of stationary water
  false-change and both water-transition persistent-false-change rates; report other failed gates and
  do not call the fallback passing. If no fallback meets those gates, do not open a held-out set.
  Freeze the config before opening held-out results.

Development comparison selected the fallback `intake_regime_stabilization_days=28` and
`subwindow_slope_disagreement_kcal_per_day=585`. At the frozen decision multiplier `2.5`, V2
development false-change rates were `3.3%` scale-only, `3.3%` scale plus intake variation, `6.0%`
missing-data, and `14.0%` autocorrelated water. Stable coverage was `96.7%`, `87.7%`, `80.3%`, and
`25.3%`, respectively. Stationary-water stable MAE was `318.7` versus `288.0 kcal/day` combined
stabilizing/unstable MAE, so the mandatory stability-quality gate failed.

The fallback's `+300/-300` day-28 power was `86.7%/87.7%`, opposite recommendations `0.7%`/`0%`,
and stable coverage `98%`. Intake-only regime signal median was day 7; day-28 signed bias was
`-4.7 kcal/day`. Water-loss and water-gain day-28 false recommendation rates were `4.7%` each, with
`4.7%` classified stable at that checkpoint and no persistent stable false-change acceptance rate
above `±150 kcal/day`. The cumulative candidate had `14.0%` stationary water false changes, similar
transition errors/guard classifications, `88.3%/85.3%` `±300` power, and only `2.7%` estimate
coverage with missing intake, so it is not selected.

The development fallback does not pass all criteria because stationary-water stable estimates were
not materially more accurate than non-stable estimates. Its config was frozen before evaluating the
new held-out set.

## CP34A2 Held-Out Results

The frozen `28-day` V2 candidate at multiplier `2.5`, regime threshold `250 kcal/day`, seven-day
support per regime, 28-day additional stabilization, and `585 kcal/day` early/late implied-TDEE
disagreement threshold was evaluated once on untouched seeds `30000..30299`. Every result below is
**in-model synthetic evaluation**.

| Candidate | Scenario                 | Estimate coverage | Stable | Stabilizing | Unstable |   MAE | Stable MAE | Non-stable MAE |  HOLD | False increase | False decrease | False change |
| --------- | ------------------------ | ----------------: | -----: | ----------: | -------: | ----: | ---------: | -------------: | ----: | -------------: | -------------: | -----------: |
| V2        | Scale noise              |            100.0% |  95.0% |        5.0% |     0.0% |  57.5 |       57.0 |           67.1 | 97.0% |           0.7% |           2.3% |         3.0% |
| V2        | Scale + intake variation |            100.0% |  84.3% |       15.7% |     0.0% |  58.5 |       58.0 |           61.2 | 97.0% |           0.7% |           2.3% |         3.0% |
| V2        | Autocorrelated water     |            100.0% |  30.0% |       64.7% |     5.3% | 289.3 |      302.0 |          283.9 | 85.0% |           6.0% |           9.0% |        15.0% |
| V2        | Missing data             |             98.3% |  80.7% |       17.7% |     0.0% |  73.5 |       71.6 |           81.7 | 91.3% |           6.0% |           2.7% |         8.7% |

Water stable MAE (`302.0`) exceeds combined stabilizing/unstable MAE (`283.9 kcal/day`), so the
stability-quality requirement fails. The cumulative candidate had the same `15.0%` stationary-water
false-change rate and almost identical water error separation (`302.3` stable vs `283.9` non-stable).
It produced `82.7%/82.3%` `±300` day-28 detection, zero opposite recommendations, and only `1.0%`
estimate coverage under missing-intake requirements. It does not improve the key failure and is not
selected.

| Candidate  | True TDEE shift | Correct by day 14 | Correct by day 21 | Correct by day 28 | Correct by day 35 | Median detection day | Opposite direction | Stable coverage |
| ---------- | --------------- | ----------------: | ----------------: | ----------------: | ----------------: | -------------------: | -----------------: | --------------: |
| V2 28-day  | +300 kcal/day   |             25.0% |             60.7% |             86.7% |             93.0% |                   21 |               0.7% |           98.7% |
| V2 28-day  | -300 kcal/day   |             23.0% |             60.0% |             85.0% |             93.3% |                   21 |               0.7% |           98.7% |
| Cumulative | +300 kcal/day   |              0.0% |              0.0% |             82.7% |             90.3% |                   28 |               0.0% |           93.3% |
| Cumulative | -300 kcal/day   |              0.0% |              0.0% |             82.3% |             91.3% |                   28 |               0.0% |           93.3% |

Transition checkpoints report signed mean TDEE error and peak absolute error across all 56 post-change
days. The regime signal occurred at median day 7 in every scenario.

| Candidate  | Scenario                     | Day 7 bias | Day 14 bias | Day 21 bias | Day 28 bias | Peak MAE | Stable by day 28 | Median stable recovery | Stable false change by day 28 |
| ---------- | ---------------------------- | ---------: | ----------: | ----------: | ----------: | -------: | ---------------: | ---------------------: | ----------------------------: |
| V2         | Intake drop only             |      -60.0 |       -20.9 |       +45.4 |        +8.2 |    172.1 |             0.0% |                 day 36 |                          0.7% |
| Cumulative | Intake drop only             |       -1.0 |        -4.7 |        +7.1 |        +6.9 |    154.7 |             0.0% |                 day 36 |                          0.3% |
| V2         | Intake drop + water loss     |     +225.1 |      +433.5 |      +148.0 |      -365.0 |    638.0 |             0.0% |                 day 40 |                          2.7% |
| Cumulative | Intake drop + water loss     |     +280.4 |      +441.6 |      +140.9 |      -334.6 |    647.5 |             0.0% |                 day 40 |                          2.7% |
| V2         | Intake increase + water gain |     -250.9 |      -417.3 |      -110.4 |      +381.1 |    630.5 |             0.0% |                 day 39 |                          4.7% |
| Cumulative | Intake increase + water gain |     -301.2 |      -424.5 |      -102.5 |      +351.3 |    638.5 |             0.0% |                 day 39 |                          4.7% |

All candidates met the `±100` and `±150 kcal/day` recovery criterion at least once within 56 days,
but this is not equivalent to a stable state: the water transitions remained non-stable at day 28 and
needed 39–40 days for median stable recovery. Peak transient error remains high, and cumulative energy
does not remove water bias. The cumulative method also requires near-complete interval intake and
therefore has impractically low coverage in the configured missing-data scenario.

### Frozen Criterion Verdicts

- Scale-only false-change cap `<=4.7%`: **PASS**, V2 `3.0%`.
- Scale plus intake-variation cap `<=4.3%`: **PASS**, V2 `3.0%`.
- Missing-data cap `<=10.3%`: **PASS**, V2 `8.7%`.
- `+300` day-28 detection `>=85%`: **PASS**, V2 `86.7%`.
- `-300` day-28 detection `>=85%`: **PASS**, V2 `85.0%`.
- Opposite-direction rate `<=1%`: **PASS**, V2 `0.7%` for each direction.
- Power stable coverage `>=90%`: **PASS**, V2 `98.7%`.
- Autocorrelated-water false-change cap `<=15%` and at least 50% relative reduction: **PASS at the
  boundary**, V2 `15.0%` (54.5% reduction from 33.0%).
- Water transition stable false-change beyond `±150` by day 28 `<=20%`: **PASS**, V2 `2.7%` water loss
  and `4.7%` water gain.
- Water stable MAE at least 20% lower than combined stabilizing/unstable MAE: **FAIL**, `302.0` vs
  `283.9 kcal/day`.
- Intake-only state enters stabilizing within 14 days and later recovers: **PASS**, median signal day
  7 and median stable recovery day 36.

## Estimator Decision

**Continue investigation because no candidate passes all frozen criteria.** Keep 28-day Theil-Sen as
the baseline estimator for further offline work; the guard meaningfully reduces water false changes
without collapsing `±300` detection. Do not switch to cumulative energy: it has similar water
performance, lower power, and severe missing-intake coverage loss. CP29 and other product behavior
remain unchanged. CP34A2 does not establish real-world or clinical performance.

## CP34A3 Frozen Protocol

CP34A3 is a new **in-model synthetic evaluation**. CP34A and CP34A2 held-out seeds are frozen
historical references and are not available for tuning.

- Development seeds: `40000..40299`.
- Untouched CP34A3 held-out seeds: `50000..50299`.
- Transition recovery is sampled at seven-day post-change checkpoints through day 56; reported
  recovery latency is therefore weekly resolution.
- Compare trailing horizons of `28`, `35`, and `42` days using matched generated users per seed.
- Keep the disturbance-aware 28-day V2 as the reference candidate. Candidate stability warnings use
  leave-first-week-out, leave-last-week-out, leave-one-seven-day-block-out and adjacent overlapping
  horizon agreement; these are sensitivity warnings, not independent observations and are not
  averaged into TDEE.
- Development threshold grid for each warning is `200`, `300`, `400`, and `500 kcal/day`; selected
  offline block and adjacent-horizon warning thresholds are both `200 kcal/day`.
- Decrease-action study compares the symmetric `75 kcal/day` minimum / `2.5x` diagnostic uncertainty
  gate with an evaluation-only decrease gate `max(150 kcal/day, 3x uncertainty)`. Neither policy is
  wired to product recommendations.
- Persistent water drift is `-270/7700 kg/day` added to scale weight with stable logged intake and
  true TDEE `2000`. Its matched true-energy-deficit scenario uses true TDEE `2270`, logged intake
  `2000`, and the same scale-noise stream. Their scale/intake/date inputs should be identical up to
  floating-point precision; this is the predeclared information-limit control.

Held-out acceptance criteria, frozen before CP34A3 evaluation:

- Ordinary scale false changes `<=5%`, scale-plus-intake `<=5%`, and missing-data `<=10.7%`.
- For both `±300 kcal/day`, day-28 correct detection `>=80%`, opposite direction `<=1%`, median
  latency `<=35` days, and stable coverage `>=85%`.
- Persistent-water false changes improve materially from the CP34A2 `15%`: target `<=10%`.
- Persistent-water false-decrease recommendations are at most `10%`; report this separately from
  autocorrelated, zero-drift water noise because it tests the available-input identifiability limit.
- Water evidence quality passes if either (a) stable MAE is at least 20% below non-stable MAE with
  at least 20% of water users stable, or (b) at most 20% of water users are classified stable while
  ordinary stable coverage remains at least 70% and power coverage at least 85%.
- Transition stable recovery median `<=42` days for the three directional transition scenarios,
  without day-28 false recommendations above 10%.
- Horizon selection first excludes any horizon failing ordinary or power criteria. Among remaining
  horizons, select the shortest that passes the water criterion; otherwise report no passing horizon.
- Sensitivity thresholds are selected on development users only using the same exclusions; choose
  the least aggressive thresholds that pass water while preserving ordinary/power requirements. If
  no sensitivity configuration passes, select none and report that result.
- Asymmetric decreases qualify for CP34B consideration only if they reduce false decreases by at
  least 25% on stationary-noise scenarios, retain at least 75% of symmetric `-300` decrease power,
  keep median latency `<=42` days, and do not increase false increases. No product behavior changes
  in CP34A3.

Development threshold sweep evaluated `200`, `300`, `400`, and `500 kcal/day` on seeds
`40000..40049`; the full development cohort was then measured with `200 kcal/day` sensitivity limits.
The provisional 42-day horizon and both 200 kcal/day warning thresholds are frozen for CP34A3
held-out evaluation. All three horizons remain reported as predeclared comparisons. The 42-day choice
is a usefulness choice (ordinary stable coverage and water false-change rate), not a fully passing
candidate because its stable-water error separation fails. The CP34A2 asymmetry candidate gate is
frozen as written. Held-out results will not be used to select windows or alter thresholds.

Development cohort results on seeds `40000..40299` favored the `42-day` candidate among the tested
horizons: at the frozen `200 kcal/day` sensitivity thresholds, autocorrelated-water false changes
were `1.7%` at 28 days, `3.0%` at 35 days, and `7.0%` at 42 days; scale-only false changes were
`3.0%`, `2.7%`, and `1.7%`, while scale-plus-intake false changes were `3.0%`, `2.0%`, and `2.3%`.
Stable coverage for ordinary operation was `59.7%/56.3%`, `82.7%/78.7%`, and `93.3%/89.0%` at
28/35/42 days. At 42 days, autocorrelated-water stable MAE was `162.7` versus non-stable MAE `173.1`
(`6.0%` relative improvement), short of the required 20% separation. The persistent water-drift
control had a `93.3%` false-decrease rate at 42 days.

The ±300 day-28 detections with sensitivity warnings were `98.3%/99.0%` at 28 days, `100%/100%` at
35 days, and `100%/100%` at 42 days, with zero opposite-direction detections and median latency 28
days. Transition stable-recovery medians at 42 days were 28 days for intake-only, 42 days for
intake-plus-water-loss, and 42 days for intake-plus-water-gain.

At 28 days, median leave-first/leave-last-week differences were `60.7/58.2 kcal/day` for ordinary
scale noise and `225.5/218.3` for autocorrelated water; leave-one-week-block range P90 was `250.4` vs
`1073.2 kcal/day`. At 42 days, these were `25.1/21.7`, with block range P90 `110.3`; water multi-horizon
warning rate dropped from `79.7%` at 28 days to `15.7%` at 42 days. These overlapping horizons are
treated as correlated sensitivity checks, not independent evidence.

The stronger decrease gate reduced stationary false decreases from `1.3%` to `0.7–1.0%`, preserved
`97.7%` of symmetric -300 detection on development users, and had median latency 28 days. It did not
reduce the `53.3%` false increases in the persistent-drift scenario. The matched persistent-drift and
true-energy-deficit pairs differed in observed values by at most `2e-13` and their 28-day estimates by
`2e-11 kcal/day`, despite true TDEE differing by `270 kcal/day`.

### CP34A3 Held-Out Results

The frozen `200 kcal/day` sensitivity thresholds were evaluated once on untouched seeds `50000..50299`.
These are **in-model synthetic evaluation** results.

| Scenario               | Days | Stable | Stabilizing | Unstable | False increase | False decrease | False change |   MAE | Stable MAE | Non-stable MAE |
| ---------------------- | ---: | -----: | ----------: | -------: | -------------: | -------------: | -----------: | ----: | ---------: | -------------: |
| Scale noise            |   28 |  61.7% |       38.3% |     0.0% |           2.0% |           0.3% |         2.3% |  60.9 |       59.6 |           62.9 |
| Scale noise            |   35 |  83.0% |       17.0% |     0.0% |           1.3% |           0.3% |         1.7% |  44.1 |       44.7 |           41.0 |
| Scale noise            |   42 |  95.0% |        5.0% |     0.0% |           1.7% |           0.0% |         1.7% |  32.9 |       33.0 |           30.9 |
| Scale + intake         |   28 |  57.7% |       42.3% |     0.0% |           1.7% |           0.3% |         2.0% |  60.9 |       59.5 |           62.9 |
| Scale + intake         |   35 |  76.3% |       23.7% |     0.0% |           2.0% |           0.3% |         2.3% |  46.2 |       45.9 |           47.0 |
| Scale + intake         |   42 |  89.0% |       11.0% |     0.0% |           1.3% |           0.3% |         1.7% |  34.8 |       34.1 |           40.2 |
| Missing data           |   28 |   2.7% |       96.7% |     0.0% |           0.0% |           0.0% |         0.0% |  71.9 |       70.1 |           71.9 |
| Missing data           |   35 |  13.3% |       86.7% |     0.0% |           0.0% |           0.0% |         0.0% |  51.0 |       50.5 |           51.1 |
| Missing data           |   42 |  27.7% |       72.0% |     0.0% |           1.0% |           1.0% |         2.0% |  41.6 |       43.8 |           40.8 |
| Autocorrelated water   |   28 |   3.3% |       91.7% |     5.0% |           0.7% |           2.0% |         2.7% | 305.1 |      329.2 |          304.2 |
| Autocorrelated water   |   35 |   4.7% |       88.7% |     6.7% |           0.3% |           2.0% |         2.3% | 231.9 |      223.3 |          232.3 |
| Autocorrelated water   |   42 |  12.7% |       78.7% |     8.7% |           3.0% |           5.7% |         8.7% | 181.0 |      242.1 |          172.1 |
| Persistent water drift |   28 |  61.7% |       38.3% |     0.0% |          53.7% |           0.0% |        53.7% | 273.7 |      274.7 |          272.1 |
| Persistent water drift |   35 |  83.0% |       17.0% |     0.0% |          81.0% |           0.0% |        81.0% | 272.0 |      271.7 |          273.4 |
| Persistent water drift |   42 |  95.0% |        5.0% |     0.0% |          94.7% |           0.0% |        94.7% | 272.3 |      272.0 |          277.7 |

At 42 days, `+300/-300 kcal/day` day-28 detection was `100%/100%`, median latency 28 days,
opposite-direction rate 0%, and stable coverage 89.0%. At 28 and 35 days detection was `98.7%/98.0%`
and `100%/100%`; median latency was 28 days with zero opposite-direction errors.

Leave-first/leave-last-week median shifts at 28/35/42 days were `60.7/58.2`, `35.8/32.8`, and
`25.1/21.7 kcal/day` for scale-only noise, and `225.5/218.3`, `163.3/154.3`, and `99.0/97.2` for
autocorrelated water. Leave-one-week-block range P90 fell from `1073.2` to `703.9` to `453.1 kcal/day`
for water across these horizons. At 42 days, water block warnings were 64.0% and adjacent-horizon
warnings 17.7%. Missing-data leave-block refits were unavailable in 94.7%/82.0%/68.0%; these are
counted as warnings, not stable evidence.

The decrease guard reduced stationary false decreases to 0.0% for scale noise, 0.0% for scale plus
intake noise, and 2.0% for autocorrelated water, from symmetric rates of 0.3%, 0.3%, and 2.0%. It
retained 97.3% of symmetric `-300` power with median latency 28 days. For persistent water drift it
did not help: false increases remained 53.7%/81.0%/94.7% at 28/35/42 days. The matched drift/deficit
streams had maximum input difference `2e-13`, median paired-estimate difference `2.1e-11 kcal/day`,
and identical stability classifications for all 300 users while true TDEE differed by `270 kcal/day`.

### CP34A3 Frozen Criterion Verdicts

- Ordinary scale and scale-plus-intake false changes <=5%: **PASS** at every horizon; at 42 days the
  rates were 1.7% and 1.7%.
- Missing-data false changes <=10.7%: **PASS**; 2.0% at 42 days with 99.7% estimate coverage.
- Both `±300` detections >=80%, opposite <=1%, latency <=35 days, stable coverage >=85%: **PASS** at
  42 days (`100%/100%`, 0%, day 28, 89.0% stable coverage).
- Persistent-water false change <=10%: **PASS** at 42 days, 8.7%.
- Water evidence-quality criterion: **FAIL**. Stable MAE (242.1) is worse than non-stable MAE
  (172.1 kcal/day); stable classification is 78.7%, above the alternative <=20% rare-stable bound.
- Water-transition recovery <=42 days and day-28 false changes <=10%: **PASS at 42 days**; median
  stable recovery was day 42 for both water directions, with false changes 4.0%/5.3%.
- Persistent-drift false-decrease <=10%: **FAIL**, 94.7% at 42 days.
- Asymmetric decrease gate: stationary false-decrease and `-300` power subcriteria **PASS**, but it
  does not address persistent drift and is not a production candidate.
- Identifiability: **FAIL by construction**; the permitted inputs contain no distinguishing signal.

offline candidate for ordinary operation: it provides 89-95% stable coverage in ordinary scenarios,

## CP34B Product Integration

No horizon or sensitivity policy passes every frozen criterion. The 42-day option remains useful
offline, but it cannot distinguish matched persistent water drift from a real deficit. Theil-Sen V2
therefore remains the estimator baseline; CP34B does not redesign or promote a new estimator.

CP29 now applies the conservative product contract: adaptive TDEE is observational supporting
evidence, not measured expenditure; decreases require stable categorical evidence, a long evidence
span, and 28/35/42-day agreement; and `HOLD`/`DEFER` with reason codes is preferred when evidence is
compatible with both persistent drift and real energy change. Increases may proceed from strong CP28
outcome/adherence evidence while treating ambiguous TDEE as contextual only. CP30 trusts CP29 and
cannot activate a deferred decrease. The current baseline/safety plan remains active until the caller
accepts an activation event. These are product-policy changes, not estimator claims.
