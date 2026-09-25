import type {
  MacroStrategy,
  NutritionTargetRange,
  RecommendationReason,
  RecommendationStatus,
} from "../types";

export const strategyLabels: Record<MacroStrategy, string> = {
  balanced: "Balanced",
  higher_carb: "Higher carbohydrate",
  higher_fat: "Higher fat",
  higher_protein: "Higher protein",
  custom: "Custom",
};

export const macroStrategies: readonly MacroStrategy[] = [
  "balanced",
  "higher_carb",
  "higher_fat",
  "higher_protein",
  "custom",
];

const macroStrategyValues: Record<string, MacroStrategy | undefined> = {
  balanced: "balanced",
  higher_carb: "higher_carb",
  higher_fat: "higher_fat",
  higher_protein: "higher_protein",
  custom: "custom",
};

export function parseMacroStrategy(value: string): MacroStrategy {
  const strategy = macroStrategyValues[value];
  if (strategy === undefined)
    throw new Error(`Unsupported macro strategy: ${value}`);
  return strategy;
}

export const strategyCopy: Record<MacroStrategy, string> = {
  balanced:
    "Moderate protein and fat, with carbohydrates using the remaining calories.",
  higher_carb:
    "More calories available for carbohydrate-focused training preferences.",
  higher_fat:
    "A larger fat allocation with remaining calories assigned to carbohydrates.",
  higher_protein: "Higher protein while retaining a moderate fat allocation.",
  custom: "Choose protein per kilogram and fat as a percentage of calories.",
};

export const reasonCopy: Record<RecommendationReason, string> = {
  insufficient_history:
    "Add more calendar days of history before using a recommendation.",
  insufficient_weight_completeness:
    "Log weight more consistently so the trend is reliable.",
  insufficient_intake_completeness:
    "Log calorie intake more consistently to compare it with your trend.",
  missing_recent_intake:
    "Add recent calorie entries before adjusting your intake target.",
  missing_weight_trend:
    "Add enough weight entries to establish a calendar-based trend.",
  adaptive_tdee_unavailable:
    "More consistent weight and calorie history is needed to estimate your personal TDEE.",
  insufficient_adaptive_estimates:
    "More eligible days are needed before your adaptive estimate is stable enough.",
  non_positive_proposed_target: "The proposed intake target is not actionable.",
  macro_policy_infeasible_proposed_target:
    "The proposed intake target cannot support the current macro policy.",
  within_hold_threshold:
    "Your recent intake is already close to the personalized target.",
  limited_by_maximum_adjustment:
    "The suggested change is capped for a gradual adjustment.",
  adjustment_recommended:
    "Your recent intake differs meaningfully from the personalized target.",
};

export const statusCopy: Record<RecommendationStatus, string> = {
  insufficient_data: "Recommendation unavailable",
  hold: "Hold current intake",
  increase_calories: "Increase daily intake",
  decrease_calories: "Decrease daily intake",
};

export const planBasisCopy = {
  baseline: "Baseline estimate for comparison",
  personalized: "Based on your observed history",
} as const;

export const lifecycleLabels = {
  baseline: "Starting point",
  calibrating: "Building evidence",
  early_personalized: "Early personalization",
  personalized: "Personalized",
} as const;

export const whole = (value: number | null | undefined, unit: string) =>
  value == null
    ? "Unavailable"
    : `${Math.round(value).toLocaleString()} ${unit}`;
export const decimal = (value: number | null | undefined, unit: string) =>
  value == null
    ? "Unavailable"
    : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value)} ${unit}`;
export const targetRange = (range: NutritionTargetRange) =>
  `${Math.round(range.lower_bound).toLocaleString()}–${Math.round(range.upper_bound).toLocaleString()} ${range.unit}`;
export const percent = (value: number) => `${Math.round(value * 100)}%`;
export const numericInput = (value: number) =>
  Number.isFinite(value) ? String(value) : "";
