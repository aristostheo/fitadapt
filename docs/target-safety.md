# Target Safety Guardrails

Checkpoint 33 adds a deterministic safety assessment before automated weight-loss targets are used.
These are conservative FitAdapt product guardrails, not individualized medical advice.

## Policy

The precedence is:

1. Existing profile validation
2. BMI eligibility
3. Baseline TDEE
4. Requested rate calculation
5. Existing weekly-rate cap
6. Maximum deficit as a fraction of baseline TDEE
7. Absolute calorie floor
8. Existing macro feasibility

The minimum BMI for automated weight loss is `18.5 kg/m2`. Below it, the status is `ineligible` and
FitAdapt does not generate an automated loss target. Maintenance and gain goals remain eligible when
otherwise valid.

Automated weight-loss floors are product policy values:

- female-equation profiles: `1200 kcal/day`
- male-equation profiles: `1500 kcal/day`

The maximum automated deficit is `25%` of baseline TDEE. A representative 600-case grid across sex
equation, height, weight, activity, BMI-valid profiles, and allowed loss rates produced these primary
binding counts:

| Candidate cap | Weekly-rate cap | TDEE deficit cap | Calorie floor | BMI policy |
| --- | ---: | ---: | ---: | ---: |
| 20% | 20 | 174 | 19 | 0 |
| 25% | 76 | 106 | 26 | 0 |

The remaining cases were already safe without a guardrail binding. The default remains `25%`: it
allows the existing profile/rate policy to remain active in more ordinary cases while the absolute
floor and near-underweight band protect the lower end. This grid is a policy calibration aid, not a
clinical validation study.

The final loss target is the most
conservative of the requested rate, this deficit cap, and the applicable calorie floor. A target can
therefore be `constrained` while weight loss remains eligible. The response exposes requested and
effective targets, BMI, floor, maximum permitted deficit, effective deficit/rate, and ordered reason
codes. Existing macro feasibility remains a separate downstream constraint.

Profiles with BMI from `18.5` up to but not including `20.0` are in a near-underweight protection
band. Their maximum deficit is tightened to `10%` of baseline TDEE. BMI `20.0` is outside the band;
BMI below `18.5` remains ineligible for automated weight loss.

## Integration behavior

`target_safety` is included in unified profile intelligence. CP29 defers ineligible weight-loss
profiles and will not propose a decrease below the safety floor or deficit boundary. CP30 cannot ratchet
an accepted plan below those boundaries. Profile recalculation reruns the assessment, so a changed
height or weight can move a profile from eligible to constrained or ineligible.

Normal maintenance and gain targets are not subjected to weight-loss floors. Underweight users receive
neutral messaging and no diagnosis. The frontend explains constrained targets without alarm and does
not present a normal automated cut plan for ineligible profiles.

Daily energy intake observations are bounded at `10000 kcal/day`, and the unified request accepts at
most `1095` observations. These are validation/resource guardrails; values are not silently truncated.
Synthetic histories clamp generated stress values to this public ceiling, so public validation is not
weakened to accommodate extreme synthetic noise.

All safety decisions depend on self-reported height and weight. A stateless API cannot prevent
deliberate misreporting or bypass of eligibility guardrails; the consuming app is responsible for
appropriate product and user safeguards.
