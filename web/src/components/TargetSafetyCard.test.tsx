import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TargetSafetyAssessment } from "../types";
import { TargetSafetyCard } from "./TargetSafetyCard";

const base: TargetSafetyAssessment = {
  status: "constrained",
  bmi: 22.2,
  minimum_bmi_for_weight_loss: 18.5,
  baseline_tdee_kcal_per_day: 1800,
  requested_target_kcal_per_day: 1000,
  effective_target_kcal_per_day: 1200,
  applied_calorie_floor_kcal_per_day: 1200,
  maximum_permitted_deficit_kcal_per_day: 450,
  requested_deficit_kcal_per_day: 800,
  effective_deficit_kcal_per_day: 600,
  effective_weekly_change_kg: -0.55,
  requested_weekly_change_kg: -0.7,
  goal: "cut",
  reason_codes: ["absolute_calorie_floor_applied"],
  policy_version: "target_safety_v1",
  assumptions: [],
};

describe("target safety presentation", () => {
  it("explains a constrained target", () => {
    render(<TargetSafetyCard assessment={base} />);
    expect(screen.getByText(/more conservative target/i)).toBeInTheDocument();
  });

  it("blocks normal weight-loss messaging when ineligible", () => {
    render(<TargetSafetyCard assessment={{ ...base, status: "ineligible" }} />);
    expect(
      screen.getByText(/does not generate automated weight-loss targets/i),
    ).toBeInTheDocument();
  });
});
