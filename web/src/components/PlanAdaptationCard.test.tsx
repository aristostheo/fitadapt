import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PlanAdaptationAssessment, PersonalizedMacroPlan } from "../types";
import { PlanAdaptationCard } from "./PlanAdaptationCard";

const macro: PersonalizedMacroPlan = {
  calorie_target_kcal_per_day: 2400,
  calorie_source: "baseline",
  strategy: "balanced",
  body_weight_kg: 80,
  protein_g_per_kg: 1.8,
  fat_percentage: 0.25,
  protein_g_per_day: 144,
  fat_g_per_day: 66,
  carbohydrate_g_per_day: 276,
  protein_kcal_per_day: 576,
  fat_kcal_per_day: 594,
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

const assessment: PlanAdaptationAssessment = {
  action: "activate",
  activation_available: true,
  activation_ready: true,
  review_required: false,
  user_attention_required: true,
  current_active_macro_plan: macro,
  proposed_macro_plan: { ...macro, calorie_target_kcal_per_day: 2300 },
  next_active_macro_plan: { ...macro, calorie_target_kcal_per_day: 2300 },
  current_active_target_kcal_per_day: 2400,
  proposed_target_kcal_per_day: 2300,
  next_active_target_kcal_per_day: 2300,
  calorie_delta_kcal_per_day: -100,
  effective_date: "2026-01-28",
  recommendation_decision: "decrease",
  reason_codes: ["proposal_activated"],
  new_observation_count: 28,
  new_weight_contributor_count: 28,
  new_intake_contributor_count: 28,
  adaptation_history: [],
  policy_version: "plan_adaptation_v1",
  assumptions: [],
};

describe("plan adaptation presentation", () => {
  it("shows activation eligibility and current/proposed/next targets", () => {
    render(<PlanAdaptationCard assessment={assessment} />);

    expect(
      screen.getByRole("heading", { name: "Plan update available" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/updating your plan from/i)).toBeInTheDocument();
    expect(screen.getByText("Available for activation")).toBeInTheDocument();
    expect(
      screen.getByText("Technical adaptation details").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("explains reversal suppression without implying activation", () => {
    render(
      <PlanAdaptationCard
        assessment={{
          ...assessment,
          action: "suppress",
          activation_available: false,
          user_attention_required: false,
          next_active_target_kcal_per_day: 2400,
          reason_codes: ["reversal_needs_more_evidence"],
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Reversal suppressed" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not enough new evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/remains unchanged/i)).toBeInTheDocument();
  });

  it("distinguishes review-required decreases from activation-ready updates", () => {
    render(
      <PlanAdaptationCard
        assessment={{
          ...assessment,
          action: "review_required",
          activation_available: false,
          activation_ready: false,
          review_required: true,
          user_attention_required: true,
          next_active_target_kcal_per_day: 2400,
          next_active_macro_plan: macro,
          reason_codes: ["decrease_requires_review"],
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Decrease requires review" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/active plan remains unchanged/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Current plan retained")).toBeInTheDocument();
  });

  it("explains a reversal confirmation cycle", () => {
    render(
      <PlanAdaptationCard
        assessment={{
          ...assessment,
          action: "reversal_pending",
          activation_available: false,
          activation_ready: false,
          review_required: false,
          next_active_target_kcal_per_day: 2400,
          next_active_macro_plan: macro,
          reason_codes: ["reversal_pending_confirmation"],
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Reversal pending confirmation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/another evaluation period with new evidence/i),
    ).toBeInTheDocument();
  });

  it("keeps decrease review visible during a reversal confirmation cycle", () => {
    render(
      <PlanAdaptationCard
        assessment={{
          ...assessment,
          action: "reversal_pending",
          activation_available: false,
          activation_ready: false,
          review_required: true,
          next_active_target_kcal_per_day: 2400,
          next_active_macro_plan: macro,
          reason_codes: [
            "reversal_pending_confirmation",
            "decrease_requires_review",
          ],
        }}
      />,
    );

    expect(
      screen.getByText(/still need your explicit review/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/explicit decrease review is still required/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Current plan retained")).toBeInTheDocument();
  });
});
