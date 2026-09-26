import type { TrainingDemandAssessment } from "../types";
import { Notice, MetricCard } from "./ui";

const labels = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  very_high: "Very high",
} as const;
const sources = {
  questionnaire: "Questionnaire",
  observations: "Observed history",
  combined: "Questionnaire and observed history",
  insufficient: "Insufficient evidence",
} as const;

export function TrainingAssessmentCard({
  assessment,
}: {
  assessment?: TrainingDemandAssessment;
}) {
  if (!assessment) return null;
  return (
    <article className="result-card training-assessment">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Training and performance context</p>
          <h2>
            {assessment.assessment_available && assessment.overall_demand
              ? labels[assessment.overall_demand]
              : "More evidence needed"}
          </h2>
        </div>
        <span className="status-badge">
          {sources[assessment.evidence_source]}
        </span>
      </div>
      <p>
        This assessment describes training demand and performance context. It
        has not changed your current plan or estimated energy needs.
      </p>
      {assessment.assessment_available ? (
        <div className="metric-grid">
          <MetricCard
            label="Resistance demand"
            value={
              assessment.resistance_demand
                ? labels[assessment.resistance_demand]
                : "Unavailable"
            }
          />
          <MetricCard
            label="Aerobic / sport demand"
            value={
              assessment.aerobic_sport_demand
                ? labels[assessment.aerobic_sport_demand]
                : "Unavailable"
            }
          />
          <MetricCard
            label="Protein priority"
            value={
              assessment.protein_priority
                ? labels[assessment.protein_priority]
                : "Unavailable"
            }
          />
          <MetricCard
            label="Carbohydrate / performance priority"
            value={
              assessment.carbohydrate_performance_priority
                ? labels[assessment.carbohydrate_performance_priority]
                : "Unavailable"
            }
          />
        </div>
      ) : (
        <Notice>
          Keep logging steps and training minutes when available. Missing logs
          are treated as unknown, not zero activity.
        </Notice>
      )}
      <p className="supporting-copy">
        Energy needs still come from baseline and adaptive TDEE. Training-aware
        macro adjustments are future policy work; no workout calories are
        estimated.
      </p>
      <details>
        <summary>Technical training details</summary>
        <p>
          Effective date: {assessment.effective_date ?? "Questionnaire only"}
        </p>
        <p>
          Reason codes:{" "}
          <code>{assessment.reason_codes.join(", ") || "None"}</code>
        </p>
        <p>
          Policy: <code>{assessment.policy_version}</code>
        </p>
        <p>
          Steps: {assessment.step_evidence.contributor_count} contributors at{" "}
          {Math.round(assessment.step_evidence.completeness * 100)}%
          completeness. Strength:{" "}
          {assessment.strength_evidence.contributor_count}. Cardio:{" "}
          {assessment.cardio_evidence.contributor_count}.
        </p>
      </details>
    </article>
  );
}
