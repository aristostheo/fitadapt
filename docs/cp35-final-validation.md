# CP35 Final Hostile Validation Protocol

This document records CP35 protocol v1 and freezes corrected protocol v2 before its held-out
evaluation. Every generated result is
**in-model synthetic evaluation**. The scenario generator is a stress harness, not a physiological
model, prospective trial, or real-world validation study. CP29, CP30, CP32, CP33, and CP34B
production policies are unchanged by this checkpoint.

## Cohorts and Runs

- Protocol v2 development seeds: `80000..80015` (16 deterministic users per scenario).
- Protocol v2 untouched held-out seeds: `90000..90015` (16 deterministic users per scenario).
- Protocol v2 ranges are disjoint from CP34A/CP34A2/CP34A3 and CP35 v1
  (`60000..60015`, `70000..70015`) cohorts.
- CP35 v1 reports were opened and failed some criteria before a test exposed that its “gradual TDEE”
  scenario had no pre-change baseline. Those v1 figures are retained for auditability but are not
  release evidence; v2 uses the same frozen thresholds on new cohorts.
- Each scenario spans 84 days.
- Weekly checkpoints occur on days 28, 35, 42, 49, 56, 63, 70, 77, and 84. At each checkpoint the
  caller accepts an eligible CP30 activation event into caller-owned history; the next simulation
  interval uses that active calorie target.
- The 28-day counterfactual changes only CP29's minimum decrease evidence span. Other decision,
  adaptation, safety, estimator, and app-status policies remain fixed.
- Protocol v2 corrects `gradual_tdee_minus_300`: baseline expenditure applies for 28 days, then
  true TDEE decreases by `300 kcal/day` linearly over the next 28 days. CP35 v1 had `change_day=0`,
  causing the ramp to finish before the first 28-day checkpoint; its gradual-change result is
  superseded and is not evidence for gradual adaptation behavior.
- Run command: `uv run python -m fitadapt.evaluation.cp35_hostile_validation --seed-set development`
  and repeat with `--seed-set held_out` only after freezing this protocol and recording development.

The matrix includes stationary scale noise and intake variation; step and drifting intake-logging
bias; adherence drift and inconsistency; weekend, clustered, transition-gap, high-intake-conditioned,
and sparse regular missingness; autocorrelated water, rebound, illness-like, sodium/carbohydrate-like,
and persistent weight disturbances; abrupt and gradual `±200/±300 kcal/day` TDEE changes; combined
water/logging/adherence/missingness cases; and near-floor/BMI safety cases. Scenario disturbances
are deliberately stylized and are not claims about exact physiology.

## Frozen Acceptance Criteria

Rates are user-level or user-check-level as explicitly labelled in the report. A proportion is
computed over the named scenarios and users, not over synthetic days. CP29 false-change rates count
proposal decisions contrary to the scenario's known direction; for a no-mismatch stationary case any
directional proposal is false. A proposal or activation before the first changed TDEE observation is
counted as false for that future mismatch, not as detection. `change_day` is zero-based; its first
changed observation is calendar day `change_day + 1`. CP30 detection is a correct-direction accepted
activation by 56 days after that first changed observation. A missed change is no correct-direction
activation after onset by day 84.

| Criterion                                                             | Frozen threshold |
| --------------------------------------------------------------------- | ---------------: |
| Ordinary false CP29 decrease proposal, worst of stationary controls   |         `<= 10%` |
| Ordinary false CP29 increase proposal, worst of stationary controls   |         `<= 10%` |
| Opposite CP30 activation on true `±300` mismatch                      |          `<= 5%` |
| Correct CP30 activation for each true `±300` mismatch by day 56       |         `>= 60%` |
| Median correct CP30 activation latency for `±300` mismatch            |     `<= 56 days` |
| Noisy stationary users with a direction reversal                      |         `<= 10%` |
| Mean activation count in each stationary control over 12 weeks        |           `<= 2` |
| CP30 decrease activation under declared ambiguity                     |              `0` |
| Safety-bound/ineligible-target activation violations                  |              `0` |
| Missed true `±300` mismatch by day 84                                 |         `<= 40%` |
| True `±300` mismatch deferred at every checkpoint                     |         `<= 20%` |
| Median recovery to `plan_remains_appropriate` after modeled transient |     `<= 28 days` |

All criteria apply unchanged to held-out results. A held-out failure remains a failure; no thresholds,
scenario definitions, or estimator/product thresholds are retuned from those results.

## Protocol v1 Results (Superseded)

Both CP35 v1 cohorts ran 32 scenarios with 16 users each and nine weekly decision checkpoints.
Their results below are **in-model synthetic evaluation**, retained as historical evidence only.
The full v1 reports are `evaluation/cp35-results/protocol-v1-development.json` and
`evaluation/cp35-results/protocol-v1-held_out.json`. Corrected v2 results will be saved as
`evaluation/cp35-results/development-v2.json` and
`evaluation/cp35-results/held_out-v2.json`.

### Protocol v1 Results (Superseded Scenario Matrix)

| Frozen criterion                                     | Development |  Held out | Verdict     |
| ---------------------------------------------------- | ----------: | --------: | ----------- |
| Worst ordinary false CP29 decrease proposal          |     `0.69%` |   `0.69%` | PASS / PASS |
| Worst ordinary false CP29 increase proposal          |     `0.69%` |   `0.69%` | PASS / PASS |
| Opposite activation on `±300` changes                |        `0%` |      `0%` | PASS / PASS |
| Correct activation by day 56 for each `±300`         |      `100%` |    `100%` | PASS / PASS |
| Median `±300` activation latency                     |   `20 days` | `27 days` | PASS / PASS |
| Users with a direction reversal in noisy/water cases |    `18.75%` |     `50%` | FAIL / FAIL |
| Maximum mean activations in a stationary control     |     `0.125` |   `0.125` | PASS / PASS |
| Decrease activation in declared ambiguous cases      |     `12.5%` |   `6.25%` | FAIL / FAIL |
| Safety-bound/ineligible activation violations        |        `0%` |      `0%` | PASS / PASS |
| Missed clean `±300` changes by day 84                |        `0%` |      `0%` | PASS / PASS |
| Clean `±300` changes deferred at all checkpoints     |        `0%` |      `0%` | PASS / PASS |
| Median status recovery after modeled transient       |    `9 days` |  `9 days` | PASS / PASS |

The reversal criterion's frozen description says “noisy stationary users,” while its implementation
uses scale-noise, autocorrelated-water, rebound, illness-like, and sodium/carbohydrate-like transient
scenarios. The reported value is the maximum across that broader set, not stationary-only. This
scope-label discrepancy is retained and disclosed; the criterion and threshold were not changed
after held-out results were opened. The broader metric fails in both cohorts.

At the final checkpoints, weighted decision rates across the whole scenario matrix were:

| Cohort      | CP29 hold | CP29 defer | CP29 increase | CP29 decrease | CP30 activate | CP30 defer | CP30 suppress |
| ----------- | --------: | ---------: | ------------: | ------------: | ------------: | ---------: | ------------: |
| Development |  `45.10%` |   `42.60%` |       `8.42%` |       `3.88%` |       `8.22%` |   `46.53%` |       `0.15%` |
| Held out    |  `44.73%` |   `42.86%` |       `8.40%` |       `4.01%` |       `8.33%` |   `46.88%` |       `0.07%` |

App-facing statuses were mostly `plan_remains_appropriate`, `more_data_needed`, or
`deferred_estimator_stabilizing`; `update_available` matched CP30 activation eligibility. Ambiguous
adaptive status was rare because CP29 often deferred earlier on CP28 adherence/completeness grounds.
Exact status rates by cohort are in the JSON reports.

Scenario highlights:

- Step and gradual logging-bias cases deferred `63.4%` of development checkpoints and `64.1%` of
  held-out checkpoints on average, with no false CP29 direction changes in these named cases.
- Weekend and clustered missingness produced occasional false changes (`0.7%` to `2.1%` of
  checkpoints); missing logs after high-intake days and sparse every-other-day logging deferred at
  every checkpoint. Gaps around plan transitions did not trigger a consistent false direction.
- Water-like disturbances caused many false changes: average CP29 false-change rate across the four
  water cases was about `25.0%` development and `24.8%` held out. Water rebound also produced user-level
  reversals of `18.75%` and `50%`, respectively. Median first `plan_remains_appropriate` checkpoint
  recovery was 1 day for rebound, 22 days for illness-like disturbance, and 9 days for a weight spike.
- Clean true `±200` and `±300` changes and gradual `-300` changes were detected in the majority of
  cases; each clean held-out `±300` scenario had 100% correct activation within 56 days. The combined
  true decline plus water case was detected in `6.25%` development and `0%` held out; true decline
  plus under-reporting was detected in `0%` in both cohorts and deferred throughout.
- The declared poor-adherence-plus-water ambiguity case activated decreases in `12.5%` of development
  users and `6.25%` held-out users. CP34B blocks categorical estimator ambiguity, but it cannot
  identify hidden logging/adherence bias when the observed evidence appears stable and near-target.
- Profile updates below BMI `18.5`, repeated near-underweight loss proposals, and calorie-floor/cap
  interactions produced zero measured safety violations. The external-style input/safety audit passed
  all five cases in both cohorts.

### 42-Day Decrease Gate Tradeoff

The 28/42 comparison changed only the minimum CP29 decrease evidence span, but accepted plans feed
subsequent simulated observations. Therefore gate runs are path-dependent, not paired fixed-data
one-shot decisions. Median days below are measured from true TDEE-change onset to first post-onset
proposal/activation; the plateau-duration field is that same latency proxy, not an independently
measured physiological plateau.

| Scenario             | Cohort      | Proposal rate 28 / 42 | Activation rate 28 / 42 | Median activation latency 28 / 42 | False decreases prevented by 42-day gate |
| -------------------- | ----------- | --------------------: | ----------------------: | --------------------------------: | ---------------------------------------: |
| `-200` TDEE          | Development |          `100 / 100%` |            `100 / 100%` |                  `23.5 / 20 days` |                                 `2 / 16` |
| `-200` TDEE          | Held out    |          `100 / 100%` |            `100 / 100%` |                    `20 / 20 days` |                                 `0 / 16` |
| `-300` TDEE          | Development |          `100 / 100%` |            `100 / 100%` |                    `20 / 20 days` |                                 `1 / 16` |
| `-300` TDEE          | Held out    |          `100 / 100%` |            `100 / 100%` |                    `27 / 27 days` |                                 `1 / 16` |
| Autocorrelated water | Development |         `25 / 18.75%` |           `25 / 18.75%` |                  `58.5 / 62 days` |                                 `1 / 16` |
| Autocorrelated water | Held out    |              `0 / 0%` |                `0 / 0%` |                      Not detected |                                 `0 / 16` |

The gate did not reduce clean `±300` detection in these small cohorts, but it did not eliminate
false decreases under all water/logging/adherence ambiguities. Legitimate `-200`/`-300` decrease
latencies were not uniformly longer under the 42-day path because the 28-day path sometimes accepted
a pre-onset decrease and thereby changed later weight trajectories. No product threshold was changed.

### External-Style Audit And Real Data

Oversized cut requests and intake above the `10000 kcal/day` transport/domain bound were rejected;
BMI below `18.5` was ineligible; the near-underweight band and an aggressive normal-BMI cut were
constrained. All five synthetic audit assertions passed in both cohorts. No meaningful historic
before/after comparison was available for CP29/CP30; the external-style cases are current invariant
checks, not a replay of an independent reviewer's data.

No usable real historical log exists in the repository. The two rows in `examples/observations.json`
are demonstrative only and lack active target/diet-phase provenance. No real-data evaluation or
claim about a person's true TDEE was made.

## Protocol v2 Results

Protocol v2 reran all 32 scenarios, 16 users each, and nine weekly checkpoints using development
seeds `80000..80015` and untouched held-out seeds `90000..90015`. The estimator, CP29/CP30/CP33
policies, scenario list, and frozen criteria were unchanged from v1 except for the corrected gradual
TDEE scenario onset and the new, disjoint seed cohorts. These are **in-model synthetic evaluation**
results, not real-world validation. Full reports are in `evaluation/cp35-results/development-v2.json`
and `evaluation/cp35-results/held_out-v2.json`.

| Frozen criterion                                   | Development v2 | Held out v2 | Verdict     |
| -------------------------------------------------- | -------------: | ----------: | ----------- |
| Worst ordinary false CP29 decrease                 |        `1.39%` |     `1.39%` | PASS / PASS |
| Worst ordinary false CP29 increase                 |        `0.69%` |     `1.39%` | PASS / PASS |
| Opposite CP30 activation on clean `±300`           |        `6.25%` |        `0%` | FAIL / PASS |
| Correct clean `±300` activation by day 56          |         `100%` |      `100%` | PASS / PASS |
| Median clean `±300` activation latency             |    `23.5 days` |   `27 days` | PASS / PASS |
| Noisy/transient users with a reversal              |          `50%` |     `37.5%` | FAIL / FAIL |
| Maximum stationary-control mean activations / user |       `0.1875` |    `0.1875` | PASS / PASS |
| Decrease activation in declared ambiguity cases    |        `6.25%` |     `6.25%` | FAIL / FAIL |
| Safety-bound/ineligible activation violations      |           `0%` |        `0%` | PASS / PASS |
| Missed clean `±300` by day 84                      |           `0%` |        `0%` | PASS / PASS |
| Clean `±300` deferred at every checkpoint          |           `0%` |        `0%` | PASS / PASS |
| Median transient status-recovery latency           |       `9 days` |    `9 days` | PASS / PASS |

The noisy/transient reversal measure retains the disclosed scope mismatch: it takes the maximum across
the noise and water/transient scenarios, not stationary scale-noise cases only. A release gate should
not pass until its naming and intended scenario set are reconciled in a future explicitly versioned
validation protocol. The hidden poor-adherence-plus-water case remains a failure of the no-decrease
under unresolved ambiguity criterion in both cohorts.

Overall v2 final-checkpoint decision rates:

| Cohort      | CP29 hold | CP29 defer | CP29 increase | CP29 decrease | CP30 activate | CP30 defer | CP30 suppress |
| ----------- | --------: | ---------: | ------------: | ------------: | ------------: | ---------: | ------------: |
| Development |  `46.05%` |   `41.21%` |       `8.96%` |       `3.78%` |       `8.49%` |   `45.44%` |       `0.02%` |
| Held out    |  `45.55%` |   `41.71%` |       `8.77%` |       `3.97%` |       `8.57%` |   `45.79%` |       `0.09%` |

Key v2 scenario outcomes:

- Step under-reporting, over-reporting, and gradually increasing logging bias produced zero CP29
  increase/decrease proposals. Their defer-check fractions were roughly `78%/78%/34%` in both
  cohorts. The high-intake-conditioned missing-intake, sparse-regular, and combined intake-regime
  change with missing logs cases deferred at every checkpoint.
- Weekend and clustered weigh-in gaps usually held but occasionally produced proposals; their false
  directional CP29 rates were at most `2.1%` of checks. Missingness therefore reduced evidence but
  did not guarantee defer in every structured pattern.
- Water remains the largest failure family. CP29 false changes across the four named water cases were
  approximately `26.6%` development and `24.8%` held out. Transient spikes/rebound triggered
  direction reversals: the rebound user reversal rate was `50%` development and `37.5%` held out.
  Recovery to `plan_remains_appropriate` was observed at weekly resolution: rebound `1 day`, illness
  `22 days`, sodium/carbohydrate-style spike `9 days` (medians are grid-rounded by checkpoint).
- Clean abrupt true `±200` and `±300` shifts were detected with high rates. Corrected gradual `-300`
  TDEE change detected in `93.75%` of development users by day 56 and `100%` held out; median latency
  was `34` and `27 days`, respectively.
- Combined decline plus water was missed in `100%` held out and almost all development cases. The
  decline-plus-under-reporting combination was missed in all development users and `93.75%` of
  held-out users; only one held-out trace activated after the combined logged evidence became
  interpretable. Poor adherence plus water also produced unresolved-ambiguity decreases in `6.25%`
  of users in both cohorts.
- The safety audit passed all five boundary cases in both cohorts. Across repeated near-floor and
  near-underweight adaptation scenarios, measured safety violations remained `0%`; near-underweight
  repeated decrease proposals were deferred rather than activated.

### V2 42-Day Gate Comparison

The v2 counterfactual has the same path-dependence limitation described above. Clean `-200` and `-300`
activation rates remained `100%` for both evidence-span gates in each cohort, with median onset
latencies `23.5/27 days` for `-300` in development/held out. In the autocorrelated-water case, the
development proposal/activation rates were `31.25%` at 28 days versus `12.5%` at 42 days; held out
they were `0%` versus `0%`. The gate prevented three of 16 development false-decrease activations in
that water case and none held out. Stationary clean/scale cases had very low proposal/activation
rates at either gate. Persistent drift had `6.25%` activation at both gates in both cohorts, showing
that a 42-day span is not an identifiability solution.

The 42-day threshold did not materially delay clean true `-300` changes on these synthetic paths,
but it also did not eliminate all water or persistent-drift decreases. No production threshold was
changed. Historical CP34 estimator validation remains estimator-focused; CP35 exposed product-path
failures that those estimator-only experiments could not measure.

## CP35A Release-Policy Protocol (Frozen Before Held Out)

CP35A changes only CP29/CP30 release policy and caller-facing contracts; the adaptive estimator and
its thresholds are unchanged. It addresses v2's noisy reversal activation and ambiguous-decrease
activation failures. Every result remains **in-model synthetic evaluation**.

- Development seeds: `120000..120015`; untouched held-out seeds: `130000..130015`. Both ranges are
  disjoint from CP34A/CP34A2/CP34A3 and CP35 v1/v2.
- The same named 32-scenario, 84-day matrix and nine weekly checkpoints are used. CP35A does not
  change scenario definitions, observation generation, estimator behavior, or the 28/42-day
  decrease-span counterfactual.
- Run development first with `uv run python -m fitadapt.evaluation.cp35_hostile_validation
--seed-set development`. Record the complete report and protocol version before running
  `--seed-set held_out`; no threshold, scenario, or policy tuning is allowed after held-out is opened.
- Main-cohort metrics never submit review confirmations. A CP29 decrease remains a visible numerical
  proposal with `review_required` readiness and cannot change the active plan. The separate
  review-acceptance counterfactual submits exact date-and-target confirmation at each eligible
  decrease; its rates describe caller-confirmed behavior and are not automatic-readiness or release
  evidence.
- Reversal confirmation is stateless and reconstructed from caller-owned events. The first opposite
  proposal is pending. A later evaluation must preserve direction and include at least 14 days after
  the first pending signal, 7 distinct post-signal observation dates, 4 post-signal weight
  contributors, and 7 post-signal intake contributors, in addition to the existing 28-day reversal,
  7-weight/14-intake and activation cooldown/fresh-evidence requirements. Two same-direction pending
  evaluations are required. Rolling estimator windows are not counted as independent evidence.
- A decrease is still review-required after reversal evidence passes; activation additionally requires
  a caller confirmation matching the current evaluation date and exact proposed target. Increases keep
  the existing readiness rule.

### Frozen CP35A Acceptance Criteria

The harness emits CP29 proposal rates, activation-readiness rates, CP30 actions, and the explicit
review counterfactual separately. User-level criteria use 16 users per scenario; ordinary false
activation uses the maximum user rate among `stationary_clean`, `scale_noise`, and `intake_variation`.
The noisy/transient reversal metric uses the maximum across scale noise, autocorrelated water,
rebound, illness-like, and sodium/carbohydrate-like cases. Ambiguity includes persistent water drift,
decline plus under-reporting, and poor adherence plus water.

| Criterion ID                        |                                                      Frozen threshold |
| ----------------------------------- | --------------------------------------------------------------------: |
| `ordinary_false_decrease`           |                                                              `<= 10%` |
| `ordinary_false_increase`           |                                                              `<= 10%` |
| `ordinary_false_activation`         |                                                              `<= 10%` |
| `plus_minus_300_proposal_detection` |                                                              `>= 60%` |
| `opposite_direction_activation`     |                                                               `<= 5%` |
| `proposal_latency`                  |                                                          `<= 56 days` |
| `activation_reversal`               |                                                              `<= 10%` |
| `stationary_activation_count`       |                                 `<= 2` mean activations/user/12 weeks |
| `ambiguous_automatic_decrease`      |                                                                   `0` |
| `review_ready_decrease`             |                                   `0` activation-ready CP29 decreases |
| `review_required_genuine_decrease`  | `>= 60%` of `tdee_minus_300` users surface a review-required proposal |
| `activation_ready_increase`         |                           `>= 60%` of `tdee_plus_300` users by day 56 |
| `indefinite_inert_proposal`         |                                                              `<= 20%` |
| `safety_violations`                 |                                                                   `0` |
| `missed_large_change`               |                                                              `<= 40%` |
| `indefinite_defer`                  |                                                              `<= 20%` |
| `transient_recovery`                |                                                   `<= 28 days` median |

These thresholds are frozen for both CP35A cohorts. The explicit-review counterfactual is reported
separately and does not relax the zero automatic-decrease criteria. A failed criterion remains a
failure; no results are described as real-world, clinical, or physiological validation.

### CP35A Development Results

The development cohort completed all 32 scenarios with 16 users each and nine checkpoints. All frozen
criteria passed; the full report is `evaluation/cp35-results/development-v3.json`. Results are
**in-model synthetic evaluation** only.

| Frozen criterion                                         | Development observed | Verdict |
| -------------------------------------------------------- | -------------------: | ------- |
| Worst ordinary false decrease proposal                   |              `2.78%` | PASS    |
| Worst ordinary false increase proposal                   |              `0.69%` | PASS    |
| Worst ordinary false activation                          |              `0.69%` | PASS    |
| Correct clean `+/-300` proposal by day 56                |               `100%` | PASS    |
| Opposite activation on clean `+/-300`                    |                 `0%` | PASS    |
| Median correct proposal latency, clean `+/-300`          |          `16.5 days` | PASS    |
| Noisy/transient users with automatic reversal activation |                 `0%` | PASS    |
| Maximum ordinary stationary mean activations/user        |             `0.0625` | PASS    |
| Automatic decrease activation in ambiguity cases         |                 `0%` | PASS    |
| Activation-ready CP29 decreases                          |                 `0%` | PASS    |
| Clean `-300` users with review-required proposal         |               `100%` | PASS    |
| Clean `+300` users activation-ready by day 56            |               `100%` | PASS    |
| Clean `+/-300` users with no proposal by day 84          |                 `0%` | PASS    |
| Safety violations                                        |                 `0%` | PASS    |
| Missed clean `+/-300` proposal by day 84                 |                 `0%` | PASS    |
| Clean `+/-300` users deferred at every checkpoint        |                 `0%` | PASS    |
| Median transient recovery                                |             `9 days` | PASS    |

The separate review-acceptance counterfactual assumes the caller confirms each eligible decrease with
the exact date and target. It produced `100%` confirmed activation for clean `-200` and `-300` cases,
with `0%` activation-ready decreases without review. In the deliberately ambiguous
`poor_adherence_with_water` scenario, `93.75%` of users received a decrease proposal requiring review;
`56.25%` activated only in this explicit-confirmation counterfactual. This is not automatic activation
and is not evidence that the ambiguity was resolved. Persistent-water-drift users received no decrease
proposal in this cohort. Full tradeoff values are in the JSON report.

### CP35A Held-Out Results

After the protocol and development report were frozen, the untouched held-out cohort completed the
same 32 scenarios, 16 users per scenario, and nine checkpoints. All frozen criteria passed; the full
report is `evaluation/cp35-results/held_out-v3.json`. Results remain **in-model synthetic evaluation**.

| Frozen criterion                                         | Held-out observed | Verdict |
| -------------------------------------------------------- | ----------------: | ------- |
| Worst ordinary false decrease proposal                   |           `1.39%` | PASS    |
| Worst ordinary false increase proposal                   |           `0.69%` | PASS    |
| Worst ordinary false activation                          |           `0.69%` | PASS    |
| Correct clean `+/-300` proposal by day 56                |            `100%` | PASS    |
| Opposite activation on clean `+/-300`                    |              `0%` | PASS    |
| Median correct proposal latency, clean `+/-300`          |         `13 days` | PASS    |
| Noisy/transient users with automatic reversal activation |              `0%` | PASS    |
| Maximum ordinary stationary mean activations/user        |          `0.0625` | PASS    |
| Automatic decrease activation in ambiguity cases         |              `0%` | PASS    |
| Activation-ready CP29 decreases                          |              `0%` | PASS    |
| Clean `-300` users with review-required proposal         |            `100%` | PASS    |
| Clean `+300` users activation-ready by day 56            |            `100%` | PASS    |
| Clean `+/-300` users with no proposal by day 84          |              `0%` | PASS    |
| Safety violations                                        |              `0%` | PASS    |
| Missed clean `+/-300` proposal by day 84                 |              `0%` | PASS    |
| Clean `+/-300` users deferred at every checkpoint        |              `0%` | PASS    |
| Median transient recovery                                |          `9 days` | PASS    |

The held-out explicit-review counterfactual produced `100%` caller-confirmed activations for clean
`-200` and `-300` cases, and `81.25%` caller-confirmed activations in `poor_adherence_with_water`.
Those ambiguous activations only occur in the counterfactual that supplies exact user confirmation;
they do not alter the `0%` automatic ambiguous-decrease result and do not establish that hidden
adherence or weight effects have been identified. Persistent-water-drift proposals occurred for
`6.25%` of users but none activated, even in the explicit-confirmation counterfactual. The combined
`tdee_decline_underreporting` case remained difficult: `93.75%` of held-out users had no CP29 proposal
by day 84. This is a proposal-availability limitation, distinct from unsafe automatic activation.

### CP35A v1 Supersession and Corrected Protocol v2

CP35A v1 reports are preserved in `evaluation/cp35-results/development-v3.json` and
`evaluation/cp35-results/held_out-v3.json`. A post-run edge-case review found that direct callers of
CP30 could submit repeated records with the same observation date and have them counted as multiple
new reversal contributors. The integrated trend path rejects duplicate dates, but the standalone
activation evaluator did not enforce distinct-date counting. The v1 synthetic cohorts contained no
such duplicate records; their results remain historical evidence, but are superseded for final
release evidence by the corrected v2 protocol.

CP35A v2 counts distinct observation dates, distinct weight-contributor dates, and distinct
intake-contributor dates for both ordinary freshness and post-reversal confirmation. No threshold,
scenario, estimator, or decision rule changed. The frozen CP35A acceptance criteria above remain
identical.

- Development seeds: `140000..140015`; untouched held-out seeds: `150000..150015`, disjoint from all
  earlier CP34/CP35/CP35A cohorts.
- The scenario matrix remains 32 scenarios over 84 days with nine weekly checkpoints.
- Run and record `uv run python -m fitadapt.evaluation.cp35_hostile_validation --seed-set
development` before `--seed-set held_out`. V2 held-out is not opened until the corrected v2
  development report is saved.
- Corrected reports will be `evaluation/cp35-results/development-v4.json` and
  `evaluation/cp35-results/held_out-v4.json`. Do not overwrite the v1 report artifacts.

#### CP35A v2 Development Results

Development seeds `140000..140015` completed after the distinct-date correction. All 17 unchanged
frozen criteria passed; the full report is `evaluation/cp35-results/development-v4.json`.

| Frozen criterion                                   | Development v2 observed | Verdict |
| -------------------------------------------------- | ----------------------: | ------- |
| Worst ordinary false decrease proposal             |                 `2.08%` | PASS    |
| Worst ordinary false increase proposal             |                 `0.69%` | PASS    |
| Worst ordinary false activation                    |                 `0.69%` | PASS    |
| Correct clean `+/-300` proposal by day 56          |                  `100%` | PASS    |
| Opposite activation on clean `+/-300`              |                    `0%` | PASS    |
| Median correct proposal latency                    |               `13 days` | PASS    |
| Noisy/transient automatic reversal activation      |                    `0%` | PASS    |
| Maximum ordinary stationary mean activations/user  |                `0.0625` | PASS    |
| Automatic ambiguous decrease activation            |                    `0%` | PASS    |
| Activation-ready CP29 decreases                    |                    `0%` | PASS    |
| Clean `-300` review-required proposal availability |                  `100%` | PASS    |
| Clean `+300` activation readiness by day 56        |                  `100%` | PASS    |
| Clean `+/-300` users without proposal by day 84    |                    `0%` | PASS    |
| Safety violations                                  |                    `0%` | PASS    |
| Missed clean `+/-300` proposal by day 84           |                    `0%` | PASS    |
| Clean `+/-300` users deferred at every checkpoint  |                    `0%` | PASS    |
| Median transient recovery                          |                `9 days` | PASS    |

The v2 review-acceptance counterfactual surfaced review-required decreases for `93.75%` of
`poor_adherence_with_water` users; `56.25%` activated only when the synthetic caller explicitly
confirmed the exact proposal. This remains a user-confirmed tradeoff, not automatic readiness or
proof that ambiguity was resolved. The full proposal/readiness/activation breakdown is in the JSON.

#### CP35A v2 Held-Out Results

Held-out seeds `150000..150015` completed after the v2 development report was recorded. Sixteen of
the 17 frozen criteria passed; `opposite_direction_activation` failed narrowly at `6.25%` against a
`5%` maximum. The complete report is `evaluation/cp35-results/held_out-v4.json`.

| Frozen criterion                                   | Held-out v2 observed | Verdict |
| -------------------------------------------------- | -------------------: | ------- |
| Worst ordinary false decrease proposal             |              `2.08%` | PASS    |
| Worst ordinary false increase proposal             |                 `0%` | PASS    |
| Worst ordinary false activation                    |                 `0%` | PASS    |
| Correct clean `+/-300` proposal by day 56          |               `100%` | PASS    |
| Opposite or pre-onset activation on clean `+/-300` |              `6.25%` | FAIL    |
| Median correct proposal latency                    |          `16.5 days` | PASS    |
| Noisy/transient automatic reversal activation      |                 `0%` | PASS    |
| Maximum ordinary stationary mean activations/user  |                  `0` | PASS    |
| Automatic ambiguous decrease activation            |                 `0%` | PASS    |
| Activation-ready CP29 decreases                    |                 `0%` | PASS    |
| Clean `-300` review-required proposal availability |               `100%` | PASS    |
| Clean `+300` activation readiness by day 56        |               `100%` | PASS    |
| Clean `+/-300` users without proposal by day 84    |                 `0%` | PASS    |
| Safety violations                                  |                 `0%` | PASS    |
| Missed clean `+/-300` proposal by day 84           |                 `0%` | PASS    |
| Clean `+/-300` users deferred at every checkpoint  |                 `0%` | PASS    |
| Median transient recovery                          |             `9 days` | PASS    |

The held-out opposite/pre-onset failure is one of 16 users in `tdee_plus_300` (seed `150011`). The
activation trace was direction-matched but began at day 28, before the first changed observation on
day 29; later activations occurred on days 49 and 63. The frozen definition counts any activation
before onset as false/opposite for that future mismatch, so the gate remains failed. No threshold or
classification was changed after seeing this result.

The separate held-out review counterfactual reported `100%` caller-confirmed activation for clean
`-200` and `-300` cases, with no decreases activation-ready without review. In `poor_adherence_with_water`,
`100%` of users received a review-required decrease proposal and `43.75%` activated only under exact
caller confirmation. These confirmations do not resolve the synthetic ambiguity or change the `0%`
automatic ambiguous-decrease result. The combined `tdee_decline_underreporting` case remained
unresolved: all held-out users deferred throughout with no proposal by day 84.

## CP35B Final Statistical Confirmation Protocol

### Seed 150011 Leakage Audit

The CP35A v2 held-out `tdee_plus_300` activation for seed `150011` was reproduced from its exact
simulation prefix. At the first checkpoint, the model received only 28 observations dated
`2025-01-01` through `2025-01-28`, with the initial active target `2319 kcal/day` and no prior
adaptation events. For this scenario `change_day=28` is a zero-based observation index: `_actual_tdee`
returns baseline TDEE at index 27 (`2759 kcal/day`) and baseline plus `300` at index 28, calendar
day 29. The prefix therefore contains no changed-TDEE observation.

On that prefix the observed-data estimator returned `2928.9 kcal/day`, CP28 classified progress as
`faster_than_expected`, CP29 proposed an increase of `100 kcal/day`, and CP30 activated it on calendar
day 28. The deterministic trace was `((+1, 28), (+1, 49), (+1, 63))`; the first event is counted as
false for the future mismatch. The initial target generated all 28 prefix records. The new target
applies only to subsequent intake generation after the checkpoint. `expected_direction` is used only
for metric classification after evaluation; it is not passed into CP29/CP30. The checkpoint receives
the current observation list, and the TDEE generator does not apply the configured change until index
28. No future observation, target, or change-state leakage was found. This is a genuine pre-onset false
positive caused by the observed pre-change outcome and is not grounds for tuning to seed `150011`.

### Frozen Confirmatory Cohort

The CP35B cohort is evaluation-only and does not alter the estimator, CP29 thresholds, CP30 rules,
CP35A review policy, scenarios, or frozen criteria. It reruns the unchanged 17 CP35A criteria on 15
preselected scenarios, 100 users per scenario, and nine weekly checkpoints. The selected set contains
all named scenario rows needed by the frozen criterion evaluator, including ordinary controls,
all noisy/transient reversal cases, all declared ambiguity cases, and all safety cases.

Each scenario receives a unique contiguous 100-seed block. The first block starts at `200000`; the
last ends at `201499`. These seeds are disjoint from documented CP34A/CP34A2/CP34A3, CP35, and CP35A
cohorts. The scenario-to-seed mapping is emitted in the JSON report. The cohort runs once with
`uv run python -m fitadapt.evaluation.cp35b_confirmatory --workers 4`; no development-based tuning or
mid-cohort threshold changes are permitted. The report path is
`evaluation/cp35-results/confirmatory-v1.json`.

The JSON reports the original CP35A criteria with identical identifiers, scope, thresholds, and
comparators. Per-scenario reports separately include pre-onset activations, direction-opposite
activations, the frozen composite opposite-or-pre-onset measure, correct activation by day 56,
activation latency, ambiguous automatic decreases, automatic reversal activations, review-required
decrease proposals, no activation within 84 days, all-checkpoint CP29 deferral, and safety violations.
Pre-onset counts use calendar activation days strictly before onset (`day <= change_day`); the frozen
composite retains CP35's `day <= change_day + 1` rule. Correct-activation latency and by-day-56
classification retain the CP35 report convention. Main-cohort runs never submit review confirmation.

User-level proportions include 95% Wilson score intervals. Repeated-checkpoint rates are descriptive
counts/rates without treating checkpoints as independent users. All results are **in-model synthetic
evaluation**, not real-world or clinical validation. The CP35A held-out failure remains preserved and
visible; the new cohort does not erase or relabel earlier reports. No release-readiness recommendation
will be made unless the unchanged frozen criteria pass on the confirmatory cohort and earlier evidence
is reconciled without post-result threshold revision.

### CP35B Confirmatory Results

All 15 scenarios completed for 100 users each. The full result, including the deterministic
scenario-to-seed map and user-level confidence intervals, is
`evaluation/cp35-results/confirmatory-v1.json`. All 17 frozen criteria pass on this cohort.

| Frozen criterion | CP35B observed | Threshold | Verdict |
| --- | ---: | ---: | --- |
| Worst ordinary false decrease proposal | `1.44%` | `<= 10%` | PASS |
| Worst ordinary false increase proposal | `0.78%` | `<= 10%` | PASS |
| Worst ordinary false activation | `0.78%` | `<= 10%` | PASS |
| Correct clean `+/-300` proposal by day 56 | `100%` | `>= 60%` | PASS |
| Opposite/pre-onset activation on clean `+/-300` | `0%` | `<= 5%` | PASS |
| Median correct clean `+/-300` proposal latency | `13 days` | `<= 56 days` | PASS |
| Noisy/transient users with automatic reversal activation | `0%` | `<= 10%` | PASS |
| Maximum ordinary stationary mean activations/user | `0.07` | `<= 2` | PASS |
| Automatic decrease activation in ambiguity cases | `0%` | `0` | PASS |
| Activation-ready CP29 decreases | `0%` | `0` | PASS |
| Clean `-300` users with review-required proposals | `100%` | `>= 60%` | PASS |
| Clean `+300` users activation-ready by day 56 | `100%` | `>= 60%` | PASS |
| Clean `+/-300` users with no directional proposal by day 84 | `0%` | `<= 20%` | PASS |
| Safety-bound/ineligible activation violations | `0%` | `0` | PASS |
| Missed clean `+/-300` proposal by day 84 | `0%` | `<= 40%` | PASS |
| Clean `+/-300` users deferred at every checkpoint | `0%` | `<= 20%` | PASS |
| Median recovery after modeled transient | `9 days` | `<= 28 days` | PASS |

#### Activation Outcomes

User rates below are `successes/100` with Wilson 95% intervals. `Opposite/frozen` gives strict
post-onset wrong-direction activations followed by the unchanged CP35 composite, which also counts
activations on or before `change_day + 1`. `Correct by 56d` and latency use the existing CP35 onset
convention. `No activation` means no CP30 activation during 84 simulated days; it is not synonymous
with CP29 deferring at every checkpoint.

| Scenario | Pre-onset | Opposite / frozen | Correct by 56d | Correct activation latency, median [P25, P75] | No activation | CP29 deferred all 9 checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stationary_clean` | N/A | N/A | N/A | N/A | `99/100 (99%; 94.55-99.82%)` | `0/100` |
| `scale_noise` | N/A | N/A | N/A | N/A | `93/100 (93%; 86.25-96.57%)` | `0/100` |
| `intake_variation` (scale + intake noise) | N/A | N/A | N/A | N/A | `98/100 (98%; 93.00-99.45%)` | `0/100` |
| `tdee_plus_300` | `0/100 (0%; 0-3.70%)` | `0/100 / 0/100` | `100/100 (100%; 96.30-100%)` | `13 [13, 20] days`, n=100 | `0/100` | `0/100` |
| `tdee_minus_300` | `0/100 (0%; 0-3.70%)` | `0/100 / 0/100` | `0/100 (0%; 0-3.70%)` | No activation, n=0 | `100/100` | `0/100` |
| `autocorrelated_water` | N/A | N/A | N/A | N/A | `4/100 (4%; 1.57-9.84%)` | `0/100` |
| `water_rebound` | N/A | N/A | N/A | N/A | `0/100` | `0/100` |
| `illness_like_disturbance` | N/A | N/A | N/A | N/A | `0/100` | `0/100` |
| `sodium_carb_weight_spike` | N/A | N/A | N/A | N/A | `0/100` | `0/100` |
| `persistent_water_drift` | N/A | N/A | N/A | N/A | `0/100` | `0/100` |
| `poor_adherence_with_water` | N/A | N/A | N/A | N/A | `24/100 (24%; 16.69-33.23%)` | `0/100` |
| `tdee_decline_underreporting` | `0/100 (0%; 0-3.70%)` | `0/100 / 0/100` | `0/100 (0%; 0-3.70%)` | No activation, n=0 | `100/100` | `99/100 (99%; 94.55-99.82%)` |
| `repeated_slow_progress_near_floor` | `0/100 (0%; 0-3.70%)` | `0/100 / 0/100` | `0/100 (0%; 0-3.70%)` | No activation, n=0 | `100/100` | `0/100` |
| `repeated_proposals_near_bmi_band` | N/A | N/A | N/A | N/A | `100/100` | `100/100 (100%; 96.30-100%)` |
| `profile_update_below_bmi_18_5` | N/A | N/A | N/A | N/A | `97/100 (97%; 91.55-98.97%)` | `0/100` |

For clean `-300`, all 100 users received a review-required proposal, but the main cohort supplies no
review confirmation; therefore no plan activated. This is a review-gated state, not all-checkpoint
CP29 deferral. In `tdee_decline_underreporting`, 99 users deferred at every CP29 checkpoint and one
received a review-required proposal; none activated.

#### Review, Ambiguity, Reversal, and Safety

Review-required decrease user incidence and checkpoint frequency are separate; the latter denominator
is 900 evaluations per scenario. User rates include Wilson 95% intervals.

| Scenario | Users with review-required decrease | Review-required checkpoints / 900 |
| --- | ---: | ---: |
| `stationary_clean` | `9/100 (9%; 4.81-16.23%)` | `10/900` |
| `scale_noise` | `10/100 (10%; 5.52-17.44%)` | `13/900` |
| `intake_variation` | `11/100 (11%; 6.25-18.63%)` | `12/900` |
| `tdee_plus_300` | `8/100 (8%; 4.11-15.00%)` | `8/900` |
| `tdee_minus_300` | `100/100 (100%; 96.30-100%)` | `662/900` |
| `autocorrelated_water` | `99/100 (99%; 94.55-99.82%)` | `308/900` |
| `water_rebound` | `100/100 (100%; 96.30-100%)` | `352/900` |
| `illness_like_disturbance` | `100/100 (100%; 96.30-100%)` | `193/900` |
| `sodium_carb_weight_spike` | `100/100 (100%; 96.30-100%)` | `113/900` |
| `persistent_water_drift` | `6/100 (6%; 2.78-12.48%)` | `7/900` |
| `poor_adherence_with_water` | `91/100 (91%; 83.77-95.19%)` | `225/900` |
| `tdee_decline_underreporting` | `1/100 (1%; 0.18-5.45%)` | `1/900` |
| `repeated_slow_progress_near_floor` | `100/100 (100%; 96.30-100%)` | `886/900` |
| `repeated_proposals_near_bmi_band` | `0/100 (0%; 0-3.70%)` | `0/900` |
| `profile_update_below_bmi_18_5` | `6/100 (6%; 2.78-12.48%)` | `6/900` |

Automatic ambiguous decrease activation was `0/300` users across `persistent_water_drift`,
`poor_adherence_with_water`, and `tdee_decline_underreporting` (95% Wilson interval `0-1.26%`).
Automatic reversal activation was `0/500` users across the five noisy/transient criterion scenarios
(95% Wilson interval `0-0.76%`). Safety violations were `0/300` across the three safety cases
(95% Wilson interval `0-1.26%`); total measured violation events were zero.

The CP35A v2 held-out cohort's one pre-onset activation remains a genuine observed false positive and
its original `6.25%` failure is unchanged in `held_out-v4.json`. Its 95% Wilson interval is
`1.11-28.33%`; the independent CP35B estimate is `0/100`, with a 95% Wilson interval of `0-3.70%`.
These intervals overlap, so the larger confirmatory cohort is consistent with the earlier small-sample
observation while its point estimate and upper interval bound remain below the unchanged `5%` gate.
The independent CP35B cohort had no pre-onset or opposite activation in its 100-user clean `+300` and
clean `-300` scenarios. No result was relabeled, pooled post hoc, or used to revise a threshold.

**Recommendation:** CP35B supports release readiness with respect to the unchanged in-model synthetic
criteria: all 17 pass on the predeclared 1,500-user confirmatory cohort. This is not a claim of
real-world or clinical validation; the reproduced day-28 false positive remains an observed behavior,
not a leakage defect, and the earlier CP35A failure remains part of the release record.

## Report Semantics and Limits

The report separates CP29 decisions, CP30 activation actions, and final integration status rates. It
also reports false/correct/opposite direction, proposal/activation latency, transient recovery,
reversals, repeated same-direction activations, inert/deferred cases, and the 28/42-day decrease-gate
tradeoff. “Indefinitely inert” is operationally “no activation during the 84-day simulation,” not a
claim about behavior after observation ends. Cohort size is intentionally small for bounded
execution: a rate increment is `6.25`
percentage points per user, so results are directional stress evidence, not population estimates.

`examples/observations.json` contains only two demonstration records and has no active-target or diet
phase provenance. No usable real historical weight/intake log is present in the repository; no real
data evaluation is claimed. True TDEE labels exist only in the synthetic generator. They are not
observable in real user records without independent measurement.

The external-style audit repeats input rejection for oversized goal requests and absurd intake, plus
low-BMI ineligibility, near-underweight deficit constraints, and normal-BMI aggressive-deficit
constraints. Historical CP34 estimator reports remain comparisons only; their cohorts and criteria
are not merged with CP35.

## Release Hygiene

The repository does not contain a `LICENSE` file. No license is inferred or added. License selection
remains release work. This checkpoint does not add product behavior, data persistence, or a frontend
feature. Synthetic outcomes must not be described as accurate, clinically validated, or
real-world-validated.
