import type { PlanAdaptationAssessment } from "../types";
import { whole } from "../utils/presentation";
import { MetricCard, Notice } from "./ui";

const actionLabels = {
  activate: "Plan update available",
  hold: "Current plan remains appropriate",
  defer: "Collect more evidence first",
  suppress: "Reversal suppressed",
  review_required: "Decrease requires review",
  reversal_pending: "Reversal pending confirmation",
} as const;

function message(assessment: PlanAdaptationAssessment): string {
  if (assessment.action === "activate") {
    return `Your recent progress supports updating your plan from ${whole(assessment.current_active_target_kcal_per_day, "kcal/day")} to ${whole(assessment.next_active_target_kcal_per_day, "kcal/day")}.`;
  }
  if (assessment.action === "suppress") {
    return "Recent data points in the opposite direction, but there is not enough new evidence to reverse the last adjustment yet.";
  }
  if (assessment.action === "review_required") {
    return "A potential calorie decrease is available for explicit review. FitAdapt cannot distinguish every persistent weight effect or hidden logging bias from a true expenditure change, so the active plan remains unchanged.";
  }
  if (assessment.action === "reversal_pending") {
    if (assessment.review_required) {
      return "FitAdapt is waiting for another evaluation period with new evidence. If the decrease remains supported, it will still need your explicit review before the active plan changes.";
    }
    return "Your recent data points toward reversing the last adjustment. FitAdapt is waiting for another evaluation period with new evidence before making the reversal activation-ready.";
  }
  if (assessment.action === "defer") {
    return "Your plan was adjusted recently or does not have enough fresh evidence. FitAdapt is collecting more data before recommending another activation.";
  }
  return "Your current plan remains appropriate for this evaluation.";
}

export function PlanAdaptationCard({
  assessment,
}: {
  assessment: PlanAdaptationAssessment;
}) {
  return (
    <article className="result-card plan-adaptation">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Longitudinal plan adaptation</p>
          <h2>{actionLabels[assessment.action]}</h2>
        </div>
        <span className="status-badge">
          {assessment.user_attention_required ? "Review" : "No action needed"}
        </span>
      </div>
      <p>{message(assessment)}</p>
      <div className="metric-grid">
        <MetricCard
          label="Current active target"
          value={whole(
            assessment.current_active_target_kcal_per_day,
            "kcal/day",
          )}
        />
        <MetricCard
          label="Proposed target"
          value={whole(assessment.proposed_target_kcal_per_day, "kcal/day")}
        />
        <MetricCard
          label="Next active target"
          value={whole(assessment.next_active_target_kcal_per_day, "kcal/day")}
          detail={
            assessment.activation_available
              ? "Available for activation"
              : "Current plan retained"
          }
        />
      </div>
      {assessment.action === "activate" && (
        <Notice>
          This is activation eligibility only. The caller must accept and
          persist the new plan.
        </Notice>
      )}
      {assessment.action === "suppress" && (
        <Notice tone="warning">
          The current active plan remains unchanged while reversal evidence
          accumulates.
        </Notice>
      )}
      {(assessment.action === "review_required" ||
        assessment.action === "reversal_pending") && (
        <Notice tone="warning">
          {assessment.action === "review_required"
            ? "Review the proposed adjustment before changing your plan."
            : assessment.review_required
              ? "The current active plan remains unchanged while reversal evidence accumulates; explicit decrease review is still required."
              : "The current active plan remains unchanged while reversal evidence accumulates."}
        </Notice>
      )}
      <details>
        <summary>Technical adaptation details</summary>
        <dl className="technical-details">
          <div>
            <dt>Fresh observations</dt>
            <dd>
              {assessment.new_observation_count} total;{" "}
              {assessment.new_weight_contributor_count} weight;{" "}
              {assessment.new_intake_contributor_count} intake
            </dd>
          </div>
          <div>
            <dt>Reason codes</dt>
            <dd>{assessment.reason_codes.join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>History events</dt>
            <dd>{assessment.adaptation_history.length}</dd>
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
