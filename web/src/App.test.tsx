import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { ApiError, getProfileIntelligence } from "./api";
import { createFictionalSample } from "./sample-history";
import type {
  MacroCalorieSource,
  NutritionTargetEnvelope,
  PersonalizedMacroPlan,
  PersonalizedPlanSnapshot,
  ProfileIntelligenceResponse,
} from "./types";

const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label, { exact: true }), {
    target: { value },
  });

const navigate = (step: string) => {
  const button = document.getElementById(`journey-${step}`);
  if (!(button instanceof HTMLButtonElement))
    throw new Error(`Missing ${step} journey button`);
  fireEvent.click(button);
  return button;
};

function macroPlan(source: MacroCalorieSource): PersonalizedMacroPlan {
  return {
    calorie_target_kcal_per_day: 2450,
    calorie_source: source,
    strategy: "higher_protein",
    body_weight_kg: 80,
    protein_g_per_kg: 2,
    fat_percentage: 0.25,
    protein_g_per_day: 160,
    fat_g_per_day: 68,
    carbohydrate_g_per_day: 298,
    protein_kcal_per_day: 640,
    fat_kcal_per_day: 613,
    carbohydrate_kcal_per_day: 1192,
    macro_policy_version: "preference_macros_v1",
    assumptions: [],
  };
}

function targetEnvelope(source: MacroCalorieSource): NutritionTargetEnvelope {
  return {
    selected_calorie_target_kcal_per_day: 2450,
    calorie_adherence_range: {
      lower_bound: 2350.4,
      selected_value: 2450,
      upper_bound: 2549.6,
      unit: "kcal/day",
      interpretation: "Daily adherence range",
      range_kind: "adherence",
    },
    protein_preferred_range: {
      lower_bound: 144.2,
      selected_value: 160,
      upper_bound: 175.8,
      unit: "g/day",
      interpretation: "Preferred protein range",
      range_kind: "preferred",
    },
    fat_preferred_range: {
      lower_bound: 54.4,
      selected_value: 68,
      upper_bound: 81.6,
      unit: "g/day",
      interpretation: "Preferred fat range",
      range_kind: "preferred",
    },
    carbohydrate_flexible_range: {
      lower_bound: 239.6,
      selected_value: 298,
      upper_bound: 356.4,
      unit: "g/day",
      interpretation: "Flexible carbohydrate range",
      range_kind: "flexible_remainder",
    },
    macro_plan: macroPlan(source),
    macro_strategy: "higher_protein",
    calorie_source: source,
    policy_floors: ["protein_floor", "fat_floor"],
    range_policy_version: "nutrition_target_ranges_v1",
    macro_policy_version: "preference_macros_v1",
    assumptions: ["Ranges are flexible policy bounds."],
  };
}

function response(
  stage:
    | "baseline"
    | "calibrating"
    | "early_personalized"
    | "personalized" = "personalized",
  progression = false,
): ProfileIntelligenceResponse {
  const source: MacroCalorieSource =
    stage === "personalized" ? "personalized" : "baseline";
  const envelope = targetEnvelope(source);
  const plan: PersonalizedPlanSnapshot = {
    as_of_date: "2026-01-14",
    lifecycle_stage: stage,
    lifecycle_requirements: [],
    calorie_basis: source,
    baseline_calorie_target_kcal_per_day: 2300,
    selected_calorie_target_kcal_per_day: 2450,
    previous_selected_calorie_target_kcal_per_day: 2400,
    change_from_previous_snapshot_kcal_per_day: 50,
    adaptive_tdee_kcal_per_day: 2450,
    adaptive_median_absolute_deviation_kcal_per_day: 6,
    eligible_adaptive_estimate_count: 8,
    recommendation_status: "increase_calories",
    recommendation_reasons: ["adjustment_recommended"],
    raw_recommendation_adjustment_kcal_per_day: 160,
    limited_recommendation_adjustment_kcal_per_day: 150,
    macro_plan: macroPlan(source),
    planning_policy_version: "personalized_planning_v1",
    baseline_energy_formula_version: "mifflin",
    baseline_activity_policy_version: "activity",
    baseline_energy_equivalent_policy_version: "energy",
    baseline_macro_policy_version: "baseline",
    lifecycle_policy_version: "lifecycle",
    trend_policy_version: "trends",
    adaptive_policy_version: "adaptive",
    recommendation_policy_version: "recommendation",
    personalized_macro_policy_version: "preference_macros_v1",
    assumptions: [],
    target_envelope: envelope,
  };
  return {
    policy_version: "profile_intelligence_v1",
    baseline: {
      baseline_energy: {
        estimated_ree_kcal_per_day: 1700,
        activity_level: "moderately_active",
        activity_multiplier: 1.55,
        estimated_tdee_kcal_per_day: 2400,
        ree_formula_version: "mifflin",
        activity_policy_version: "activity",
      },
      goal: "maintain",
      requested_weekly_change_kg: 0,
      daily_calorie_adjustment_kcal: 0,
      target_calories_kcal_per_day: 2400,
      protein_g_per_day: 128,
      fat_g_per_day: 48,
      carbohydrate_g_per_day: 300,
      energy_equivalent_policy_version: "energy",
      macro_policy_version: "baseline",
      assumptions: [],
    },
    trends: {
      policy_version: "trends",
      config: { window_size_days: 7, minimum_observations: 4 },
      points: [
        {
          observed_on: "2026-01-14",
          observation_present: true,
          body_weight_kg: 79.94,
          energy_intake_kcal: 2400,
          steps: 8000,
          trailing_body_weight_mean_kg: 79.97,
          trailing_energy_intake_mean_kcal: 2380,
          trailing_steps_mean: 7800,
          body_weight_contributor_count: 7,
          energy_intake_contributor_count: 7,
          steps_contributor_count: 7,
          window_weight_change_kg: -0.2,
        },
      ],
      data_quality: {
        first_date: "2026-01-01",
        last_date: "2026-01-14",
        total_calendar_days: 14,
        submitted_observation_records: 14,
        missing_calendar_days: 0,
        present_body_weight_values: 14,
        missing_body_weight_values: 0,
        body_weight_completeness_ratio: 1,
        present_energy_intake_values: 14,
        missing_energy_intake_values: 0,
        energy_intake_completeness_ratio: 1,
        present_step_values: 14,
        missing_step_values: 0,
        step_completeness_ratio: 1,
      },
      assumptions: [],
    },
    adaptive_tdee: {
      policy_version: "adaptive",
      config: {
        energy_equivalent_kcal_per_kg: 7700,
        aggregation_window_days: 14,
        minimum_estimate_points: 4,
      },
      daily_estimates: [],
      adaptive_tdee_kcal_per_day: 2450,
      median_absolute_deviation_kcal_per_day: 6,
      eligible_points_used: 4,
      total_eligible_points: 8,
      aggregation_start_date: "2026-01-01",
      aggregation_end_date: "2026-01-14",
      assumptions: [],
    },
    lifecycle: {
      stage,
      requirements:
        stage === "baseline"
          ? ["add_history", "log_body_weight", "log_energy_intake"]
          : [],
      calendar_history_days: 14,
      weight_observation_count: 14,
      intake_observation_count: 14,
      weight_completeness: 1,
      intake_completeness: 1,
      eligible_adaptive_estimate_count: 8,
      required_eligible_estimate_count: 4,
      adaptive_tdee_kcal_per_day: 2450,
      median_absolute_deviation_kcal_per_day: 6,
      lifecycle_policy_version: "lifecycle",
      trend_policy_version: "trends",
      adaptive_policy_version: "adaptive",
      assumptions: [],
    },
    recommendation: {
      status: "increase_calories",
      reasons: ["adjustment_recommended"],
      goal: "maintain",
      requested_weekly_change_kg: 0,
      observed_window_weight_change_kg: -0.2,
      baseline_estimated_tdee_kcal_per_day: 2400,
      baseline_calorie_target_kcal_per_day: 2400,
      adaptive_tdee_kcal_per_day: 2450,
      recent_mean_intake_kcal_per_day: 2300,
      personalized_goal_target_kcal_per_day: 2450,
      raw_adjustment_kcal_per_day: 150,
      recommended_adjustment_kcal_per_day: 150,
      proposed_intake_target_kcal_per_day: 2450,
      calendar_history_days: 14,
      weight_completeness: 1,
      intake_completeness: 1,
      adaptive_estimate_count: 4,
      recommendation_policy_version: "recommendation",
      trend_policy_version: "trends",
      adaptive_policy_version: "adaptive",
      energy_equivalent_policy_version: "energy",
      assumptions: [],
    },
    latest_plan: plan,
    dietary_assessment: {
      dietary_pattern: "unrestricted",
      selection_mode: "broad",
      protein_target_range: envelope.protein_preferred_range,
      protein_target_provenance: "nutrition_target_envelope",
      inferred_hard_excluded_categories: [],
      explicit_hard_excluded_categories: [],
      limited_categories: [],
      disliked_categories: [],
      accepted_categories: [],
      preferred_categories: [],
      favorite_categories: [],
      usable_protein_source_categories: [
        "poultry",
        "fish",
        "eggs",
        "dairy",
        "soy",
        "legumes",
      ],
      usable_protein_source_count: 6,
      protein_flexibility_status: "supported",
      conflicts: [],
      verification_notices: [],
      actionable_requirements: [],
      category_policy_version: "dietary_categories_v1",
      pattern_policy_version: "dietary_patterns_v1",
      assessment_policy_version: "dietary_assessment_v1",
      protein_flexibility_policy_version: "protein_flexibility_v1",
      target_range_policy_version: "nutrition_target_ranges_v1",
      assumptions: [],
    },
    plan_progression: progression
      ? {
          snapshots: [plan],
          submitted_observation_count: 1,
          planning_policy_version: "planning",
          assumptions: [],
        }
      : null,
    assumptions: [],
  };
}

function mockApi(value = response()) {
  const fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: true, status: 200, json: async () => value });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("guided FitAdapt journey", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders five accessible stages and supports click and keyboard navigation", () => {
    render(<App />);
    const profile = document.getElementById("journey-profile");
    expect(profile).toHaveAttribute("aria-current", "step");
    expect(
      ["profile", "nutrition", "history", "plan", "progress"].map((id) =>
        document.getElementById(`journey-${id}`),
      ),
    ).not.toContain(null);

    fireEvent.keyDown(profile as HTMLButtonElement, { key: "ArrowRight" });
    expect(document.getElementById("journey-nutrition")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Shape your nutrition plan",
      }),
    ).toBeInTheDocument();

    navigate("history");
    expect(document.getElementById("journey-history")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Build your evidence" }),
    ).toBeInTheDocument();
  });

  it("retains profile and nutrition values while moving between stages", () => {
    render(<App />);
    fill("Age", "041");
    fill("Weight (kg)", "91.4");
    navigate("nutrition");
    fill("Macro strategy", "higher_fat");
    navigate("profile");
    expect(screen.getByLabelText("Age")).toHaveValue(41);
    expect(screen.getByLabelText("Weight (kg)")).toHaveValue(91.4);
    navigate("nutrition");
    expect(screen.getByLabelText("Macro strategy")).toHaveValue("higher_fat");
  });

  it("preserves observation state, zero values, editing, deletion, and history errors", () => {
    render(<App />);
    navigate("history");
    fill("Date", "2026-01-02");
    fill("Calories (kcal)", "0");
    fireEvent.click(screen.getByRole("button", { name: "Add observation" }));
    expect(screen.getByText("0 kcal")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
    navigate("profile");
    navigate("history");
    expect(
      screen.getByRole("heading", { name: /Daily observations 1/ }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit 2026-01-02" }));
    fill("Calories (kcal)", "2200");
    fireEvent.click(screen.getByRole("button", { name: "Save observation" }));
    expect(screen.getByText("2,200 kcal")).toBeInTheDocument();

    fill("Date", "2026-01-02");
    fill("Steps", "5000");
    fireEvent.click(screen.getByRole("button", { name: "Add observation" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Duplicate observation dates",
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete 2026-01-02" }));
    expect(
      screen.getByRole("heading", { name: /Daily observations 0/ }),
    ).toBeInTheDocument();
  });

  it("loads deterministic fictional history around the active profile and clears it", () => {
    render(<App />);
    fill("Weight (kg)", "91");
    fireEvent.click(screen.getByRole("button", { name: "Load demo" }));
    expect(document.getElementById("journey-history")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(
      screen.getByRole("heading", { name: /Daily observations 28/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("90.64 kg")).toBeInTheDocument();
    expect(screen.getByText(/Fictional sample data/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear data" }));
    expect(
      screen.getByRole("heading", { name: /Daily observations 0/ }),
    ).toBeInTheDocument();
  });

  it("generates complete, deterministic fictional variation without personal data", () => {
    const profile = {
      age_years: 30,
      height_cm: 180,
      weight_kg: 91,
      sex_for_mifflin_equation: "male",
      activity_level: "moderately_active",
      goal: "maintain",
      requested_weekly_change_kg: 0,
    } as const;
    const first = createFictionalSample(profile);
    expect(first).toEqual(createFictionalSample(profile));
    expect(first).toHaveLength(28);
    expect(
      first.every(
        (item) =>
          item.body_weight_kg != null &&
          item.energy_intake_kcal != null &&
          item.steps != null,
      ),
    ).toBe(true);
    expect(
      new Set(first.map((item) => item.body_weight_kg)).size,
    ).toBeGreaterThan(10);
    expect(
      new Set(first.map((item) => item.energy_intake_kcal)).size,
    ).toBeGreaterThan(10);
    expect(new Set(first.map((item) => item.steps)).size).toBeGreaterThan(10);
  });

  it("previews JSON imports before mutation and preserves conflict policy behavior", () => {
    render(<App />);
    navigate("history");
    fill("Date", "2026-01-01");
    fill("Steps", "10");
    fireEvent.click(screen.getByRole("button", { name: "Add observation" }));
    fireEvent.click(screen.getByRole("button", { name: "Import history" }));
    expect(
      screen.getByRole("button", { name: "Import history" }),
    ).toHaveAttribute("aria-expanded", "true");
    fill(
      "Import observations",
      '[{"observed_on":"2026-01-01","steps":20},{"observed_on":"2026-01-02","steps":0}]',
    );
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(screen.getByText(/conflicts: 1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Resolve date conflicts",
    );
    fill("Conflict policy", "keep_existing");
    fireEvent.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(
      screen.getByRole("heading", { name: /Daily observations 2/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("0 steps")).toBeInTheDocument();
  });

  it("submits one unified request and moves successful analysis to Plan", async () => {
    const fetchMock = mockApi();
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(document.getElementById("journey-plan")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(options.body));
    expect(url).toContain("/v1/profile-intelligence");
    expect(body).toMatchObject({
      nutrition_preferences: { macro_strategy: "balanced" },
      include_plan_progression: false,
    });
    expect(body.dietary_preference_profile).toEqual({
      dietary_pattern: "unrestricted",
      selection_mode: "broad",
      constraints: [],
      preferences: [],
    });
  });

  it("renders macro ranges, readable recommendation copy, charts, and progression", async () => {
    mockApi(response("personalized", true));
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByLabelText("Include plan history"));
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(screen.getByText("2,350–2,550 kcal/day")).toBeInTheDocument();
    expect(
      screen.getByText("Preferred range: 144–176 g/day"),
    ).toBeInTheDocument();
    expect(screen.getByText("Higher protein")).toBeInTheDocument();
    expect(
      screen.getAllByText(
        "Your recent intake differs meaningfully from the personalized target.",
      ),
    ).toHaveLength(2);
    expect(
      screen.getByText("adjustment_recommended").closest("details"),
    ).not.toHaveAttribute("open");

    fireEvent.click(screen.getByRole("button", { name: "View progress" }));
    expect(document.getElementById("journey-progress")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(
      screen.getByRole("heading", { name: "Weight trend" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Calorie intake trend" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Step trend" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show plan history" }));
    expect(
      screen.getByText(
        "Each point uses only observations available up to that date.",
      ),
    ).toBeInTheDocument();
  });

  it("clears stale results when profile, nutrition, history, or progression inputs change", async () => {
    mockApi();
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");

    navigate("profile");
    fill("Age", "42");
    navigate("plan");
    expect(screen.queryByText("Current proposed plan")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Ready for analysis" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    fireEvent.click(screen.getByLabelText("Include plan history"));
    expect(screen.queryByText("Current proposed plan")).not.toBeInTheDocument();
  });

  it("prevents duplicate analysis while loading", async () => {
    let resolveResponse: ((value: unknown) => void) | undefined;
    const pending = new Promise((resolve) => {
      resolveResponse = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    const loadingButton = screen.getByRole("button", { name: "Analyzing…" });
    expect(loadingButton).toBeDisabled();
    fireEvent.click(loadingButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveResponse?.({ ok: true, status: 200, json: async () => response() });
    await screen.findByText("Current proposed plan");
  });

  it("preserves entered inputs across a structured API error and exact-request retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          error: {
            message: "Profile is inconsistent.",
            code: "PROFILE_INVALID",
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => response(),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fill("Age", "44");
    navigate("nutrition");
    fireEvent.click(screen.getByRole("radio", { name: /^Vegan/ }));
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Profile is inconsistent.",
    );
    navigate("profile");
    expect(screen.getByLabelText("Age")).toHaveValue(44);
    navigate("nutrition");
    expect(screen.getByRole("radio", { name: /^Vegan/ })).toBeChecked();
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("Current proposed plan");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]?.body).toBe(
      fetchMock.mock.calls[0][1]?.body,
    );
  });

  it("retains session-only privacy and explicit accessible labels and headings", () => {
    render(<App />);
    expect(screen.getByText("Session only")).toBeInTheDocument();
    expect(
      screen.getByText(/Nothing is saved remotely by this client/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Build your profile" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Sex used for REE estimate"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Desired weekly change (kg)"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Activity level")).toBeInTheDocument();
  });

  it("maps domain, validation, server, network, and unexpected failures to typed API errors", async () => {
    const cases = [
      [400, "domain"],
      [422, "validation"],
      [500, "server"],
      [503, "unexpected"],
    ] as const;
    for (const [status, kind] of cases) {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue({
            ok: false,
            status,
            json: async () => ({ error: { message: "invalid", code: "BAD" } }),
          }),
      );
      await expect(getProfileIntelligence({} as never)).rejects.toMatchObject({
        kind,
      });
      vi.unstubAllGlobals();
    }
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getProfileIntelligence({} as never)).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("keeps custom strategy controls and blocks invalid custom values before the API call", async () => {
    const fetchMock = mockApi();
    render(<App />);
    navigate("nutrition");
    expect(
      screen.queryByLabelText("Protein grams per kilogram"),
    ).not.toBeInTheDocument();
    fill("Macro strategy", "custom");
    fill("Protein grams per kilogram", "3");
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Custom protein");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders readable baseline requirements without raw lifecycle codes", async () => {
    mockApi(response("baseline"));
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(
      screen.getByText("Add your first weight and calorie entries."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Log body weight consistently."),
    ).toBeInTheDocument();
    expect(screen.queryByText("add_history")).not.toBeInTheDocument();
  });

  it("keeps technical plan identifiers out of primary copy", async () => {
    mockApi(response("personalized"));
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(
      screen.getByText("Based on your observed history"),
    ).toBeInTheDocument();
    expect(screen.queryByText("personalized basis")).not.toBeInTheDocument();
    expect(
      screen.queryByText("personalized calorie source"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Technical plan details").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("guides users back to Plan when progression was not requested", async () => {
    mockApi(response("personalized", false));
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    fireEvent.click(screen.getByRole("button", { name: "View progress" }));
    expect(
      screen.getByRole("heading", { name: "See how your plan changed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Return to plan" }),
    ).toBeInTheDocument();
  });

  it("moves through forward actions without losing form values", () => {
    render(<App />);
    fill("Height (cm)", "176");
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to nutrition" }),
    );
    expect(document.getElementById("journey-nutrition")).toHaveAttribute(
      "aria-current",
      "step",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to history" }),
    );
    expect(document.getElementById("journey-history")).toHaveAttribute(
      "aria-current",
      "step",
    );
    fireEvent.click(screen.getByRole("button", { name: "Back to nutrition" }));
    fireEvent.click(screen.getByRole("button", { name: "Back to profile" }));
    expect(screen.getByLabelText("Height (cm)")).toHaveValue(176);
  });

  it.each([
    ["unrestricted", "Unrestricted"],
    ["vegetarian", "Vegetarian"],
    ["vegan", "Vegan"],
    ["pescatarian", "Pescatarian"],
    ["halal", "Halal"],
    ["kosher", "Kosher"],
    ["other", "Other"],
  ] as const)(
    "supports and retains the %s dietary pattern",
    (pattern, label) => {
      render(<App />);
      navigate("nutrition");
      const radio = screen.getByRole("radio", {
        name: new RegExp(`^${label}`),
      });
      fireEvent.click(radio);
      if (pattern === "other")
        fill("Other dietary pattern description", "Cultural household pattern");
      navigate("profile");
      navigate("nutrition");
      expect(
        screen.getByRole("radio", { name: new RegExp(`^${label}`) }),
      ).toBeChecked();
    },
  );

  it("requires a description for Other and marks selected mode without accepted foods incomplete", () => {
    render(<App />);
    navigate("nutrition");
    fireEvent.click(screen.getByRole("radio", { name: /^Other/ }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Describe your dietary pattern",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to history" }),
    );
    expect(document.getElementById("journey-nutrition")).toHaveAttribute(
      "aria-current",
      "step",
    );
    fill("Other dietary pattern description", "A documented household pattern");
    fireEvent.click(
      screen.getByRole("radio", { name: /^Let me choose foods/ }),
    );
    expect(screen.getByText(/No accepted categories yet/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Select at least one food category",
    );
    fill("Soy preference", "neutral");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to history" }),
    );
    expect(document.getElementById("journey-history")).toHaveAttribute(
      "aria-current",
      "step",
    );
  });

  it.each(["Halal", "Kosher"])(
    "uses conservative %s verification copy without claiming certification",
    (pattern) => {
      render(<App />);
      navigate("nutrition");
      fireEvent.click(
        screen.getByRole("radio", { name: new RegExp(`^${pattern}`) }),
      );
      expect(
        screen.getByText(
          /does not verify ingredients, preparation methods, facilities, or certification/,
        ),
      ).toBeInTheDocument();
    },
  );

  it("defaults to broad mode and presents neutral as Okay in selected mode", () => {
    render(<App />);
    navigate("nutrition");
    expect(
      screen.getByRole("radio", { name: /^I eat most foods/ }),
    ).toBeChecked();
    expect(screen.getByText("Fine-tune preferences")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("radio", { name: /^Let me choose foods/ }),
    );
    expect(screen.getAllByRole("option", { name: "Okay" })[0]).toHaveValue(
      "neutral",
    );
    fill("Soy preference", "neutral");
    expect(
      screen.getByText("1 categories currently count as accepted."),
    ).toBeInTheDocument();
  });

  it("prevents duplicate constraints and supports accessible constraint removal", () => {
    render(<App />);
    navigate("nutrition");
    expect(screen.getByLabelText("Constraint action")).toBeDisabled();
    expect(screen.getByLabelText("Constraint action")).toHaveValue("exclude");
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Poultry already has this constraint type",
    );
    const remove = screen.getByRole("button", {
      name: "Remove Poultry Allergy constraint",
    });
    fireEvent.click(remove);
    expect(
      screen.queryByRole("button", {
        name: "Remove Poultry Allergy constraint",
      }),
    ).not.toBeInTheDocument();
  });

  it("forces required exclusions to exclude and lets intolerances exclude or limit", () => {
    render(<App />);
    navigate("nutrition");
    fill("Constraint food category", "beef");
    fill("Constraint type", "required_exclusion");
    expect(screen.getByLabelText("Constraint action")).toBeDisabled();
    expect(screen.getByLabelText("Constraint action")).toHaveValue("exclude");
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    fill("Constraint food category", "dairy");
    fill("Constraint type", "intolerance");
    expect(screen.getByLabelText("Constraint action")).toBeEnabled();
    fill("Constraint action", "limit");
    fill("Constraint note", "Small servings only");
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    expect(
      screen.getByText(/Required exclusion · Exclude/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Intolerance · Limit · Small servings only/),
    ).toBeInTheDocument();
  });

  it("serializes raw dietary enums, preferences, constraints, and notes in the unified request", async () => {
    const value = response();
    value.dietary_assessment.conflicts = [
      "Preference for dairy conflicts with a stronger exclusion.",
    ];
    const fetchMock = mockApi(value);
    render(<App />);
    navigate("nutrition");
    fireEvent.click(screen.getByRole("radio", { name: /^Vegan/ }));
    fireEvent.click(
      screen.getByRole("radio", { name: /^Let me choose foods/ }),
    );
    fill("Soy preference", "neutral");
    fill("Eggs preference", "favorite");
    fill("Constraint food category", "dairy");
    fill("Constraint type", "intolerance");
    fill("Constraint action", "limit");
    fill("Constraint note", "Lactose");
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    const body = JSON.parse(
      String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body),
    );
    expect(body.dietary_preference_profile).toEqual({
      dietary_pattern: "vegan",
      selection_mode: "selected",
      constraints: [
        {
          category: "dairy",
          constraint_type: "intolerance",
          action: "limit",
          note: "Lactose",
        },
      ],
      preferences: [
        { category: "soy", level: "neutral" },
        { category: "eggs", level: "favorite" },
      ],
    });
    expect(
      screen.getByText(/Preference for Dairy conflicts/),
    ).toBeInTheDocument();
    navigate("nutrition");
    expect(screen.getByRole("radio", { name: /^Vegan/ })).toBeChecked();
    expect(screen.getByLabelText("Soy preference")).toHaveValue("neutral");
    expect(screen.getByLabelText("Eggs preference")).toHaveValue("favorite");
  });

  it.each([
    ["balanced", undefined],
    ["higher_carb", undefined],
    ["higher_fat", undefined],
    ["higher_protein", undefined],
    ["custom", { custom_protein_g_per_kg: 1.8, custom_fat_percentage: 0.25 }],
  ] as const)(
    "preserves %s macro strategy serialization",
    async (strategy, custom) => {
      const fetchMock = mockApi();
      render(<App />);
      navigate("nutrition");
      fill("Macro strategy", strategy);
      navigate("plan");
      fireEvent.click(
        screen.getByRole("button", { name: "Analyze my profile" }),
      );
      await screen.findByText("Current proposed plan");
      const body = JSON.parse(
        String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body),
      );
      expect(body.nutrition_preferences).toEqual({
        macro_strategy: strategy,
        ...custom,
      });
    },
  );

  it("clears stale analysis after a dietary change without erasing the dietary input", async () => {
    mockApi();
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    navigate("nutrition");
    fireEvent.click(screen.getByRole("radio", { name: /^Vegetarian/ }));
    navigate("plan");
    expect(screen.queryByText("Current proposed plan")).not.toBeInTheDocument();
    navigate("nutrition");
    expect(screen.getByRole("radio", { name: /^Vegetarian/ })).toBeChecked();
  });

  it.each([
    ["supported", "Supported", /several usable protein-source categories/],
    ["limited", "Limited", /limited protein-source variety/],
    ["difficult", "Difficult", /Only one usable protein-source category/],
    [
      "infeasible",
      "Infeasible",
      /does not currently provide a usable protein-source category/,
    ],
  ] as const)(
    "renders the %s food-flexibility assessment without medical overclaiming",
    async (status, heading, copy) => {
      const value = response();
      value.dietary_assessment.protein_flexibility_status = status;
      value.dietary_assessment.usable_protein_source_count =
        status === "infeasible"
          ? 0
          : status === "difficult"
            ? 1
            : status === "limited"
              ? 2
              : 6;
      mockApi(value);
      render(<App />);
      navigate("plan");
      fireEvent.click(
        screen.getByRole("button", { name: "Analyze my profile" }),
      );
      await screen.findByText("Current proposed plan");
      expect(
        screen.getByRole("heading", { name: heading }),
      ).toBeInTheDocument();
      expect(screen.getByText(copy)).toBeInTheDocument();
    },
  );

  it("renders categorized assessment evidence, conflicts, notices, requirements, and technical provenance", async () => {
    const value = response();
    Object.assign(value.dietary_assessment, {
      dietary_pattern: "halal",
      selection_mode: "selected",
      accepted_categories: ["soy", "legumes"],
      preferred_categories: ["soy"],
      favorite_categories: ["eggs"],
      limited_categories: ["dairy"],
      inferred_hard_excluded_categories: ["pork"],
      explicit_hard_excluded_categories: ["shellfish"],
      conflicts: [
        "Preference for shellfish conflicts with a stronger exclusion.",
      ],
      verification_notices: [
        "halal categories require ingredient and certification verification.",
      ],
      actionable_requirements: ["Review the single usable protein source."],
    });
    mockApi(value);
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(screen.getByText("Soy, Legumes")).toBeInTheDocument();
    expect(screen.getByText("Favorite categories")).toBeInTheDocument();
    expect(screen.getAllByText("Eggs")).not.toHaveLength(0);
    expect(screen.getByText("Limited categories")).toBeInTheDocument();
    expect(screen.getAllByText("Dairy")).not.toHaveLength(0);
    expect(screen.getByText("Pork, Shellfish")).toBeInTheDocument();
    expect(
      screen.getByText(/Preference for Shellfish conflicts/),
    ).toBeInTheDocument();
    expect(screen.getByText(/certification verification/)).toBeInTheDocument();
    expect(
      screen.getByText("Review the single usable protein source."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("Technical dietary-assessment details"));
    expect(screen.getByText("dietary_assessment_v1")).toBeInTheDocument();
    expect(screen.getByText("protein_flexibility_v1")).toBeInTheDocument();
  });

  it("explains when personalized evidence retains the baseline safety fallback", async () => {
    const value = response();
    value.latest_plan.calorie_basis = "baseline";
    value.latest_plan.macro_plan.calorie_source = "baseline";
    value.latest_plan.target_envelope = targetEnvelope("baseline");
    mockApi(value);
    render(<App />);
    navigate("plan");
    fireEvent.click(screen.getByRole("button", { name: "Analyze my profile" }));
    await screen.findByText("Current proposed plan");
    expect(
      screen.getByText(
        /recommendation safety gate retained your baseline target/,
      ),
    ).toBeInTheDocument();
  });

  it("supports replace-existing and replace-all imports after explicit preview", () => {
    render(<App />);
    navigate("history");
    fill("Date", "2026-01-01");
    fill("Steps", "10");
    fireEvent.click(screen.getByRole("button", { name: "Add observation" }));
    fireEvent.click(screen.getByRole("button", { name: "Import history" }));
    fill(
      "Import observations",
      '[{"observed_on":"2026-01-01","steps":20},{"observed_on":"2026-01-02","steps":30}]',
    );
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    fill("Conflict policy", "replace_existing");
    fireEvent.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(screen.getByText("20 steps")).toBeInTheDocument();
    fill("Import observations", '[{"observed_on":"2026-02-01","steps":40}]');
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    fill("Import mode", "replace_all");
    fireEvent.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(
      screen.getByRole("heading", { name: /Daily observations 1/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("2026-02-01")).toBeInTheDocument();
  });
});
