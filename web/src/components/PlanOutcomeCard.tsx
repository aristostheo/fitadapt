import type { PlanOutcomeAssessment } from "../types";
import { whole } from "../utils/presentation";
import { MetricCard, Notice } from "./ui";

const interpretationLabels = {
  insufficient: "Not enough evidence",
  limited: "Limited evidence",
  interpretable: "Interpretable",
} as const;

const adherenceLabels = {
  insufficient_evidence: "Unavailable",
  below_target: "Below target",
  near_target: "Near target",
  above_target: "Above target",
} as const;

const progressLabels = {
  insufficient_evidence: "Unavailable",
  slower_than_expected: "Slower than requested",
  broadly_on_track: "Broadly on track",
  faster_than_expected: "Faster than requested",
  direction_mismatch: "Different direction",
  outside_maintenance_range: "Outside maintenance range",
  not_applicable: "Not applicable",
} as const;

export function PlanOutcomeCard({
  assessment,
}: {
  assessment: PlanOutcomeAssessment;
}) {
  return (
    <article className="result-card plan-outcome">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Current plan outcome</p>
          <h2>{interpretationLabels[assessment.overall_interpretability]}</h2>
        </div>
        <span className="status-badge">
          {assessment.effective_date ?? "No dated evidence"}
        </span>
      </div>
      <p>
        Recorded intake is compared with the current{" "}
        {whole(assessment.prescribed_calorie_target_kcal_per_day, "kcal/day")}{" "}
        target. This review does not change the plan.
      </p>
      {assessment.assessment_available ? (
        <div className="metric-grid">
          <MetricCard
            label="Intake adherence"
            value={adherenceLabels[assessment.intake_adherence]}
            detail={whole(
              assessment.observed_mean_intake_kcal_per_day,
              "kcal/day recorded",
            )}
          />
          <MetricCard
            label="Weight progress"
            value={progressLabels[assessment.goal_progress]}
            detail={whole(
              assessment.observed_weight_change_kg_per_week,
              "kg/week observed",
            )}
          />
          <MetricCard
            label="Interpretability"
            value={interpretationLabels[assessment.overall_interpretability]}
            detail={`${assessment.observation_window_days}-day trailing window`}
          />
        </div>
      ) : (
        <Notice>
          There is not enough relevant intake or weight history to assess plan
          outcomes. Missing entries do not imply non-adherence.
        </Notice>
      )}
      {assessment.overall_interpretability === "limited" && (
        <Notice>
          Some relevant entries are available, but the configured evidence
          thresholds are not met. Treat these signals as preliminary.
        </Notice>
      )}
      <details>
        <summary>Technical outcome details</summary>
        <dl className="technical-details">
          <div>
            <dt>Intake evidence</dt>
            <dd>
              {assessment.intake_contributor_count} entries;{" "}
              {Math.round(assessment.intake_completeness * 100)}% complete
            </dd>
          </div>
          <div>
            <dt>Weight evidence</dt>
            <dd>
              {assessment.weight_contributor_count} entries across{" "}
              {assessment.weight_span_days} days;{" "}
              {Math.round(assessment.weight_completeness * 100)}% complete
            </dd>
          </div>
          <div>
            <dt>Reason codes</dt>
            <dd>{assessment.reason_codes.join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>{assessment.policy_version}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}
