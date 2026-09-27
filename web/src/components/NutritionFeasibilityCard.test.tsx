import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NutritionFeasibilityCard } from "./NutritionFeasibilityCard";
import type { NutritionFeasibilityAssessment } from "../types";

const available: NutritionFeasibilityAssessment = {
  assessment_available: true,
  overall_feasibility: "challenging",
  protein_feasibility: "challenging",
  carbohydrate_feasibility: "manageable",
  fat_feasibility: "manageable",
  restriction_compatibility: "limited",
  macro_policy_version: "training_aware_macros_v1",
  training_adjustment_applied: true,
  protein_target_g_per_day: 176,
  carbohydrate_target_g_per_day: 274,
  fat_target_g_per_day: 53,
  calorie_target_kcal_per_day: 2400,
  accepted_protein_categories: ["soy"],
  accepted_carbohydrate_categories: ["rice", "potatoes"],
  accepted_fat_categories: ["nuts", "cooking_oils"],
  disliked_categories: [],
  limiting_categories: ["dairy", "eggs"],
  dietary_conflicts: [],
  guidance: [
    {
      category: "protein",
      priority: "high",
      reason_code: "limited_accepted_protein_categories",
      action: "plan_deliberately",
      message: "Use familiar accepted protein categories deliberately.",
    },
  ],
  reason_codes: ["limited_accepted_protein_categories"],
  policy_version: "nutrition_feasibility_v1",
  assumptions: ["Category-level assessment."],
  training_policy_version: "training_aware_macros_v1",
  protein_policy_source: "training_aware",
  carbohydrate_policy_source: "default",
  baseline_protein_target_g_per_day: 144,
  training_aware_protein_target_g_per_day: 176,
  baseline_carbohydrate_target_g_per_day: 306,
  protein_priority: "high",
  carbohydrate_performance_priority: "low",
};

describe("nutrition feasibility presentation", () => {
  it("shows dimensions, category guidance, and unchanged-target messaging", () => {
    render(<NutritionFeasibilityCard assessment={available} />);
    expect(
      screen.getByRole("heading", { name: "Challenging" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Use familiar accepted protein categories deliberately.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/did not change calories or macros/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Technical feasibility details").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("explains unavailable dietary evidence without inferring broad flexibility", () => {
    render(
      <NutritionFeasibilityCard
        assessment={{
          ...available,
          assessment_available: false,
          overall_feasibility: null,
          protein_feasibility: null,
          carbohydrate_feasibility: null,
          fat_feasibility: null,
          restriction_compatibility: null,
          guidance: [],
          reason_codes: ["dietary_profile_unavailable"],
        }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "More dietary information needed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not imply broad flexibility/i),
    ).toBeInTheDocument();
  });
});
