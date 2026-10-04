import type {
  RecommendationHistory,
  RecommendationHistoryEntry,
} from "../types";
import { whole } from "../utils/presentation";
import { Notice } from "./ui";

function entryTitle(entry: RecommendationHistoryEntry): string {
  if (entry.change_type === "initial_plan") return "Initial active plan";
  if (entry.change_type === "profile_update") return "Profile update";
  if (entry.change_type === "calorie_increase") return "Calories increased";
  if (entry.change_type === "calorie_decrease") return "Calories decreased";
  if (entry.change_type === "hold") return "Plan held";
  if (entry.change_type === "defer") return "Adjustment deferred";
  if (entry.change_type === "review_required")
    return "Decrease requires review";
  if (entry.change_type === "reversal_pending")
    return "Reversal pending confirmation";
  return "Reversal suppressed";
}

export function RecommendationHistoryCard({
  history,
}: {
  history: RecommendationHistory;
}) {
  const latest = history.latest_change;
  return (
    <article className="result-card recommendation-history">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Recommendation history</p>
          <h2>
            {latest ? entryTitle(latest) : "No recommendation events yet"}
          </h2>
        </div>
        <span className="status-badge">
          {history.actionable_event_available
            ? "Review available"
            : "Audit trail"}
        </span>
      </div>
      {latest ? (
        <p>
          {latest.user_summary} Effective {latest.effective_date}.
        </p>
      ) : (
        <p>
          Recommendation evaluations will appear here as caller-supplied history
          is provided.
        </p>
      )}
      {latest?.is_plan_change && (
        <Notice>
          {whole(latest.previous_calorie_target_kcal_per_day, "kcal/day")} to{" "}
          {whole(
            latest.resulting_or_proposed_calorie_target_kcal_per_day,
            "kcal/day",
          )}
          . This entry represents a plan change.
        </Notice>
      )}
      {latest?.is_evaluation_only && (
        <Notice tone="warning">
          This entry records an evaluation only. It did not change the active
          plan.
        </Notice>
      )}
      <ol className="recommendation-timeline">
        {history.entries
          .slice()
          .reverse()
          .map((entry) => (
            <li key={`${entry.effective_date}-${entry.change_type}`}>
              <time dateTime={entry.effective_date}>{entry.effective_date}</time>
              <div><strong>{entryTitle(entry)}</strong>
              <p>{entry.user_summary}</p>
              <small>{entry.source.replaceAll("_", " ")} · {entry.is_plan_change ? `${whole(entry.previous_calorie_target_kcal_per_day, "kcal/day")} → ${whole(entry.resulting_or_proposed_calorie_target_kcal_per_day, "kcal/day")} · Active plan changed` : "Evaluation only · active plan unchanged"}</small>
              {entry.is_current_active_plan && <span className="status-badge success">Current active plan</span>}</div>
            </li>
          ))}
      </ol>
      <details>
        <summary>Technical history details</summary>
        <p>
          Events: <code>{history.entries.length}</code> · Policy:{" "}
          <code>{history.policy_version}</code>
        </p>
        {latest && (
          <p>
            Source: <code>{latest.source}</code> · Reason codes:{" "}
            <code>{latest.reason_codes.join(", ") || "None"}</code>
          </p>
        )}
      </details>
    </article>
  );
}
