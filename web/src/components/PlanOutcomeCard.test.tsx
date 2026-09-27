import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PlanOutcomeAssessment } from "../types";
import { PlanOutcomeCard } from "./PlanOutcomeCard";

const assessment: PlanOutcomeAssessment = {
  assessment_available: true,
  effective_date: "2026-01-28",
  observation_window_days: 28,
  overall_interpretability: "interpretable",
  intake_adherence: "near_target",
  weight_trend_status: "available",
  goal_progress: "broadly_on_track",
  observed_mean_intake_kcal_per_day: 2400,
  prescribed_calorie_target_kcal_per_day: 2400,
  intake_deviation_kcal_per_day: 0,
  observed_weight_change_kg_per_week: -0.02,
  intended_weight_change_kg_per_week: 0,
  intake_observation_records: 28,
  intake_contributor_count: 28,
  intake_completeness: 1,
  weight_observation_records: 28,
  weight_contributor_count: 28,
  weight_completeness: 1,
  weight_span_days: 27,
  evidence_source: "intake_and_weight",
  reason_codes: ["outcome_interpretable_for_review"],
  policy_version: "plan_outcome_assessment_v1",
  assumptions: [],
};

describe("plan outcome presentation", () => {
  it("shows adherence, weight progress, and the interpretability boundary", () => {
    render(<PlanOutcomeCard assessment={assessment} />);

    expect(
      screen.getByRole("heading", { name: "Interpretable" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Near target")).toBeInTheDocument();
    expect(screen.getByText("Broadly on track")).toBeInTheDocument();
    expect(screen.getByText(/does not change the plan/i)).toBeInTheDocument();
    expect(
      screen.getByText("Technical outcome details").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("does not label unavailable evidence as non-adherence", () => {
    render(
      <PlanOutcomeCard
        assessment={{
          ...assessment,
          assessment_available: false,
          overall_interpretability: "insufficient",
          intake_adherence: "insufficient_evidence",
          weight_trend_status: "insufficient_evidence",
          goal_progress: "insufficient_evidence",
          observed_mean_intake_kcal_per_day: null,
          intake_deviation_kcal_per_day: null,
          observed_weight_change_kg_per_week: null,
          intake_contributor_count: 0,
          weight_contributor_count: 0,
          reason_codes: ["no_observations_in_effective_window"],
          evidence_source: "insufficient",
        }}
      />,
    );

    expect(
      screen.getByText(
        "There is not enough relevant intake or weight history to assess plan outcomes. Missing entries do not imply non-adherence.",
      ),
    ).toBeInTheDocument();
  });
});
