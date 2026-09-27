import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PersonalizedMacroPlan, RecommendationDecision } from "../types";
import { RecommendationDecisionCard } from "./RecommendationDecisionCard";

const macroPlan: PersonalizedMacroPlan = {
  calorie_target_kcal_per_day: 2400,
  calorie_source: "baseline",
  strategy: "balanced",
  body_weight_kg: 80,
  protein_g_per_kg: 1.8,
  fat_percentage: 0.25,
  protein_g_per_day: 144,
  fat_g_per_day: 66.67,
  carbohydrate_g_per_day: 276,
  protein_kcal_per_day: 576,
  fat_kcal_per_day: 600,
  carbohydrate_kcal_per_day: 1104,
  macro_policy_version: "preference_macros_v1",
  assumptions: [],
  training_adjustment_available: false,
  training_adjustment_applied: false,
  training_policy_version: null,
  protein_policy_source: "default",
  carbohydrate_policy_source: "default",
  baseline_protein_target_g: null,
  training_aware_protein_target_g: null,
  effective_protein_target_g: null,
  baseline_carbohydrate_target_g: null,
  effective_carbohydrate_target_g: null,
  protein_priority: null,
  carbohydrate_performance_priority: null,
  training_reason_codes: [],
};

const baseDecision: RecommendationDecision = {
  decision: "defer",
  decision_available: true,
  attention_required: false,
  current_calorie_target_kcal_per_day: 2400,
  proposed_calorie_target_kcal_per_day: 2400,
  calorie_delta_kcal_per_day: 0,
  numerical_change_proposed: false,
  goal: "cut",
  requested_weekly_change_kg: -0.4,
  outcome_interpretability: "limited",
  intake_adherence: "above_target",
  weight_trend_status: "available",
  goal_progress: "slower_than_expected",
  limiting_reason: "adherence_not_near_target",
  reason_codes: ["adherence_not_near_target"],
  adaptive_tdee_kcal_per_day: null,
  policy_version: "recommendation_decision_v1",
  assumptions: [],
};

describe("recommendation decision presentation", () => {
  it("explains defer and keeps the current plan active", () => {
    render(
      <RecommendationDecisionCard
        decision={baseDecision}
        currentMacroPlan={macroPlan}
        proposedMacroPlan={null}
      />,
    );

    expect(screen.getByRole("heading", { name: "Defer plan adjustment" })).toBeInTheDocument();
    expect(screen.getByText(/not close enough to target/i)).toBeInTheDocument();
    expect(screen.getByText(/current plan remains active/i)).toBeInTheDocument();
    expect(screen.getByText("Technical decision details").closest("details")).not.toHaveAttribute("open");
  });

  it("shows old and proposed targets and macros for an increase", () => {
    render(
      <RecommendationDecisionCard
        decision={{
          ...baseDecision,
          decision: "increase",
          attention_required: true,
          outcome_interpretability: "interpretable",
          intake_adherence: "near_target",
          goal_progress: "faster_than_expected",
          proposed_calorie_target_kcal_per_day: 2500,
          calorie_delta_kcal_per_day: 100,
          numerical_change_proposed: true,
          reason_codes: ["faster_than_requested"],
        }}
        currentMacroPlan={macroPlan}
        proposedMacroPlan={{ ...macroPlan, calorie_target_kcal_per_day: 2500 }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Propose a calorie increase" })).toBeInTheDocument();
    expect(screen.getByText("Current macros")).toBeInTheDocument();
    expect(screen.getByText("Proposed macros")).toBeInTheDocument();
    expect(screen.getByText(/proposal only/i)).toBeInTheDocument();
  });
});
