import type { PersonalizedMacroPlan, RecommendationDecision } from "../types";
import { whole } from "../utils/presentation";
import { MetricCard, Notice } from "./ui";

const decisionLabels = {
  hold: "Keep the current plan",
  increase: "Propose a calorie increase",
  decrease: "Propose a calorie decrease",
  defer: "Defer plan adjustment",
} as const;

function explanation(decision: RecommendationDecision): string {
  if (decision.decision === "defer") {
    if (decision.intake_adherence !== "near_target") {
      return "Your recent intake is not close enough to target to judge the plan reliably, so FitAdapt is holding off on changing it.";
    }
    return "There is not enough reliable evidence to adjust your plan yet.";
  }
  if (decision.decision === "hold") {
    return "Your recent progress supports keeping the current plan.";
  }
  if (decision.decision === "increase") {
    return "Your recent progress is faster than intended or weight is drifting downward. FitAdapt proposes increasing your calorie target.";
  }
  return "Your recent progress is slower than expected despite intake being close to target. FitAdapt proposes reducing your calorie target.";
}

function MacroSummary({
  label,
  plan,
}: {
  label: string;
  plan: PersonalizedMacroPlan;
}) {
  return (
    <div className="category-summary">
      <strong>{label}</strong>
      <span>
        {whole(plan.protein_g_per_day, "g protein")} /{" "}
        {whole(plan.carbohydrate_g_per_day, "g carbs")} /{" "}
        {whole(plan.fat_g_per_day, "g fat")}
      </span>
    </div>
  );
}

export function RecommendationDecisionCard({
  decision,
  currentMacroPlan,
  proposedMacroPlan,
}: {
  decision: RecommendationDecision;
  currentMacroPlan: PersonalizedMacroPlan;
  proposedMacroPlan: PersonalizedMacroPlan | null;
}) {
  return (
    <article className="result-card recommendation-decision">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Recommendation decision</p>
          <h2>{decisionLabels[decision.decision]}</h2>
        </div>
        <span className="status-badge">
          {decision.attention_required ? "Review proposed change" : "Informational"}
        </span>
      </div>
      <p>{explanation(decision)}</p>
      <div className="metric-grid">
        <MetricCard
          label="Current calories"
          value={whole(decision.current_calorie_target_kcal_per_day, "kcal/day")}
        />
        <MetricCard
          label="Proposed calories"
          value={whole(decision.proposed_calorie_target_kcal_per_day, "kcal/day")}
          detail={
            decision.calorie_delta_kcal_per_day === 0
              ? "No numerical change"
              : whole(decision.calorie_delta_kcal_per_day, "kcal/day")
          }
        />
        <MetricCard
          label="Outcome evidence"
          value={decision.outcome_interpretability}
          detail={`Adherence: ${decision.intake_adherence.replaceAll("_", " ")}`}
        />
      </div>
      {decision.numerical_change_proposed && proposedMacroPlan ? (
        <div className="category-summary-grid">
          <MacroSummary label="Current macros" plan={currentMacroPlan} />
          <MacroSummary label="Proposed macros" plan={proposedMacroPlan} />
        </div>
      ) : null}
      {decision.decision === "defer" && (
        <Notice tone="warning">The current plan remains active while more reliable evidence is collected.</Notice>
      )}
      {decision.decision !== "defer" && decision.decision !== "hold" && (
        <Notice>This is a proposal only. FitAdapt has not activated a new plan or changed plan history.</Notice>
      )}
      <details>
        <summary>Technical decision details</summary>
        <dl className="technical-details">
          <div>
            <dt>Reason codes</dt>
            <dd>{decision.reason_codes.join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Adaptive TDEE context</dt>
            <dd>{whole(decision.adaptive_tdee_kcal_per_day, "kcal/day")}</dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>{decision.policy_version}</dd>
          </div>
        </dl>
      </details>
    </article>
  );
}
