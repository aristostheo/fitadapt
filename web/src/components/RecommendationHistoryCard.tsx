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
      <ol className="action-list">
        {history.entries
          .slice()
          .reverse()
          .map((entry) => (
            <li key={`${entry.effective_date}-${entry.change_type}`}>
              <strong>
                {entry.effective_date} · {entryTitle(entry)}
              </strong>
              <span>{entry.user_summary}</span>
              {entry.is_current_active_plan && <span>Current active plan</span>}
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
