import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RecommendationHistory } from "../types";
import { RecommendationHistoryCard } from "./RecommendationHistoryCard";

const history: RecommendationHistory = {
  entries: [
    {
      effective_date: "2026-01-28",
      source: "progress_adaptation",
      action: "activate",
      change_type: "calorie_decrease",
      is_plan_change: true,
      is_evaluation_only: false,
      is_current_active_plan: true,
      previous_calorie_target_kcal_per_day: 2400,
      resulting_or_proposed_calorie_target_kcal_per_day: 2300,
      calorie_delta_kcal_per_day: -100,
      previous_macro_summary: null,
      resulting_or_proposed_macro_summary: null,
      recommendation_decision: "decrease",
      evidence_as_of_date: "2026-01-28",
      observation_window_days: 28,
      high_level_reason: "progress_adaptation",
      reason_codes: ["proposal_activated"],
      user_summary:
        "Your calorie target decreased based on recent progress evidence.",
      policy_versions: ["recommendation_history_v1"],
      assumptions: [],
    },
    {
      effective_date: "2026-02-01",
      source: "progress_adaptation",
      action: "suppress",
      change_type: "suppressed",
      is_plan_change: false,
      is_evaluation_only: true,
      is_current_active_plan: false,
      previous_calorie_target_kcal_per_day: 2300,
      resulting_or_proposed_calorie_target_kcal_per_day: 2300,
      calorie_delta_kcal_per_day: 0,
      previous_macro_summary: null,
      resulting_or_proposed_macro_summary: null,
      recommendation_decision: "increase",
      evidence_as_of_date: "2026-02-01",
      observation_window_days: 28,
      high_level_reason: "reversal_suppressed",
      reason_codes: ["reversal_needs_more_evidence"],
      user_summary:
        "A reversal was suppressed because your plan was adjusted recently.",
      policy_versions: ["recommendation_history_v1"],
      assumptions: [],
    },
  ],
  latest_change: null,
  has_new_recommendation_event: true,
  actionable_event_available: true,
  current_active_target_kcal_per_day: 2300,
  policy_version: "recommendation_history_v1",
  assumptions: [],
};
history.latest_change = history.entries[0];

describe("recommendation history presentation", () => {
  it("shows the latest change and current-plan marker", () => {
    render(<RecommendationHistoryCard history={history} />);

    expect(
      screen.getByRole("heading", { name: "Calories decreased" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/This entry represents a plan change/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Current active plan")).toBeInTheDocument();
    expect(screen.getByText(/reversal was suppressed/i)).toBeInTheDocument();
    expect(
      screen.getByText("Technical history details").closest("details"),
    ).not.toHaveAttribute("open");
  });
});
