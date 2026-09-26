export type SexForMifflinEquation = "female" | "male";
export type ActivityLevel =
  | "sedentary"
  | "lightly_active"
  | "moderately_active"
  | "very_active"
  | "extra_active";
export type Goal = "cut" | "maintain" | "gain";
export type MacroStrategy =
  | "balanced"
  | "higher_carb"
  | "higher_fat"
  | "higher_protein"
  | "custom";
export type MacroCalorieSource = "baseline" | "personalized";
export type PlanCalorieBasis = "baseline" | "personalized";
export type PersonalizationStage =
  | "baseline"
  | "calibrating"
  | "early_personalized"
  | "personalized";
export type PersonalizationRequirement =
  | "add_history"
  | "log_body_weight"
  | "log_energy_intake"
  | "build_weight_trend"
  | "build_intake_trend"
  | "collect_more_eligible_estimates";
export type RecommendationStatus =
  | "insufficient_data"
  | "hold"
  | "increase_calories"
  | "decrease_calories";
export type RecommendationReason =
  | "insufficient_history"
  | "insufficient_weight_completeness"
  | "insufficient_intake_completeness"
  | "missing_recent_intake"
  | "missing_weight_trend"
  | "adaptive_tdee_unavailable"
  | "insufficient_adaptive_estimates"
  | "non_positive_proposed_target"
  | "macro_policy_infeasible_proposed_target"
  | "within_hold_threshold"
  | "limited_by_maximum_adjustment"
  | "adjustment_recommended";
export type TdeeEligibility =
  | "available"
  | "missing_intake_trend"
  | "missing_weight_change"
  | "non_finite_result";
export type NutritionRangeKind =
  | "adherence"
  | "preferred"
  | "flexible_remainder";
export type NutritionTargetUnit = "kcal/day" | "g/day";
export type DietaryPattern =
  | "unrestricted"
  | "vegetarian"
  | "vegan"
  | "pescatarian"
  | "halal"
  | "kosher"
  | "other";
export type FoodSelectionMode = "broad" | "selected";
export type FoodCategory =
  | "poultry"
  | "beef"
  | "pork"
  | "fish"
  | "shellfish"
  | "eggs"
  | "dairy"
  | "soy"
  | "legumes"
  | "protein_supplements"
  | "rice"
  | "pasta"
  | "bread"
  | "potatoes"
  | "oats"
  | "tortillas"
  | "fruit"
  | "vegetables"
  | "nuts"
  | "seeds"
  | "nut_butters"
  | "avocado"
  | "cooking_oils";
export type FoodConstraintType =
  | "allergy"
  | "required_exclusion"
  | "intolerance";
export type FoodConstraintAction = "exclude" | "limit";
export type FoodPreferenceLevel = "dislike" | "neutral" | "like" | "favorite";
export type ProteinFlexibilityStatus =
  | "supported"
  | "limited"
  | "difficult"
  | "infeasible";
export type OccupationActivity =
  | "mostly_seated"
  | "mixed"
  | "mostly_on_feet"
  | "physically_demanding";
export type TrainingIntensity = "low" | "moderate" | "vigorous";
export type PrimaryTrainingFocus =
  | "general"
  | "resistance"
  | "endurance"
  | "intermittent_sport"
  | "mixed";
export type TrainingDemandLevel = "low" | "moderate" | "high" | "very_high";
export type TrainingPriority = "low" | "moderate" | "high";
export type TrainingEvidenceSource =
  | "questionnaire"
  | "observations"
  | "combined"
  | "insufficient";

export interface Profile {
  age_years: number;
  height_cm: number;
  weight_kg: number;
  sex_for_mifflin_equation: SexForMifflinEquation;
  activity_level: ActivityLevel;
  goal: Goal;
  requested_weekly_change_kg: number;
}
export interface Observation {
  observed_on: string;
  body_weight_kg?: number | null;
  energy_intake_kcal?: number | null;
  protein_g?: number | null;
  carbohydrate_g?: number | null;
  fat_g?: number | null;
  steps?: number | null;
  strength_training_minutes?: number | null;
  cardio_minutes?: number | null;
  sleep_hours?: number | null;
  hunger_rating?: number | null;
  energy_rating?: number | null;
}
export interface NutritionPreferences {
  macro_strategy: MacroStrategy;
  custom_protein_g_per_kg?: number | null;
  custom_fat_percentage?: number | null;
}
export interface FoodConstraint {
  category: FoodCategory;
  constraint_type: FoodConstraintType;
  action: FoodConstraintAction;
  note?: string | null;
}
export interface FoodPreference {
  category: FoodCategory;
  level: FoodPreferenceLevel;
}
export interface NutritionPreferenceProfile {
  dietary_pattern: DietaryPattern;
  selection_mode: FoodSelectionMode;
  constraints: FoodConstraint[];
  preferences: FoodPreference[];
  other_description?: string | null;
}
export interface TrainingContext {
  occupation_activity: OccupationActivity;
  resistance_days_per_week: number;
  resistance_minutes_per_week: number;
  cardio_days_per_week: number;
  cardio_minutes_per_week: number;
  cardio_intensity?: TrainingIntensity | null;
  sport_days_per_week: number;
  sport_minutes_per_week: number;
  sport_intensity?: TrainingIntensity | null;
  primary_training_focus: PrimaryTrainingFocus;
  typical_daily_steps?: number | null;
}
export interface ProfileIntelligenceRequest {
  profile: Profile;
  observations: Observation[];
  nutrition_preferences: NutritionPreferences;
  dietary_preference_profile?: NutritionPreferenceProfile;
  training_context?: TrainingContext;
  include_plan_progression: boolean;
}

export interface BaselineEnergy {
  estimated_ree_kcal_per_day: number;
  activity_level: ActivityLevel;
  activity_multiplier: number;
  estimated_tdee_kcal_per_day: number;
  ree_formula_version: string;
  activity_policy_version: string;
}
export interface BaselineResult {
  baseline_energy: BaselineEnergy;
  goal: Goal;
  requested_weekly_change_kg: number;
  daily_calorie_adjustment_kcal: number;
  target_calories_kcal_per_day: number;
  protein_g_per_day: number;
  fat_g_per_day: number;
  carbohydrate_g_per_day: number;
  energy_equivalent_policy_version: string;
  macro_policy_version: string;
  assumptions: string[];
}
export interface TrendPoint {
  observed_on: string;
  observation_present: boolean;
  body_weight_kg: number | null;
  energy_intake_kcal: number | null;
  steps: number | null;
  trailing_body_weight_mean_kg: number | null;
  trailing_energy_intake_mean_kcal: number | null;
  trailing_steps_mean: number | null;
  body_weight_contributor_count: number;
  energy_intake_contributor_count: number;
  steps_contributor_count: number;
  window_weight_change_kg: number | null;
}
export interface TrendsResult {
  policy_version: string;
  config: { window_size_days: number; minimum_observations: number };
  points: TrendPoint[];
  data_quality: {
    first_date: string | null;
    last_date: string | null;
    total_calendar_days: number;
    submitted_observation_records: number;
    missing_calendar_days: number;
    present_body_weight_values: number;
    missing_body_weight_values: number;
    body_weight_completeness_ratio: number;
    present_energy_intake_values: number;
    missing_energy_intake_values: number;
    energy_intake_completeness_ratio: number;
    present_step_values: number;
    missing_step_values: number;
    step_completeness_ratio: number;
  };
  assumptions: string[];
}
export interface AdaptiveResult {
  policy_version: string;
  config: {
    energy_equivalent_kcal_per_kg: number;
    aggregation_window_days: number;
    minimum_estimate_points: number;
  };
  daily_estimates: {
    observed_on: string;
    trailing_energy_intake_mean_kcal: number | null;
    window_weight_change_kg: number | null;
    estimated_daily_energy_balance_kcal: number | null;
    estimated_tdee_kcal_per_day: number | null;
    eligibility: TdeeEligibility;
  }[];
  adaptive_tdee_kcal_per_day: number | null;
  median_absolute_deviation_kcal_per_day: number | null;
  eligible_points_used: number;
  total_eligible_points: number;
  aggregation_start_date: string | null;
  aggregation_end_date: string | null;
  assumptions: string[];
}
export interface LifecycleResult {
  stage: PersonalizationStage;
  requirements: PersonalizationRequirement[];
  calendar_history_days: number;
  weight_observation_count: number;
  intake_observation_count: number;
  weight_completeness: number;
  intake_completeness: number;
  eligible_adaptive_estimate_count: number;
  required_eligible_estimate_count: number;
  adaptive_tdee_kcal_per_day: number | null;
  median_absolute_deviation_kcal_per_day: number | null;
  lifecycle_policy_version: string;
  trend_policy_version: string;
  adaptive_policy_version: string;
  assumptions: string[];
}
export interface RecommendationResult {
  status: RecommendationStatus;
  reasons: RecommendationReason[];
  goal: Goal;
  requested_weekly_change_kg: number;
  observed_window_weight_change_kg: number | null;
  baseline_estimated_tdee_kcal_per_day: number;
  baseline_calorie_target_kcal_per_day: number;
  adaptive_tdee_kcal_per_day: number | null;
  recent_mean_intake_kcal_per_day: number | null;
  personalized_goal_target_kcal_per_day: number | null;
  raw_adjustment_kcal_per_day: number | null;
  recommended_adjustment_kcal_per_day: number | null;
  proposed_intake_target_kcal_per_day: number | null;
  calendar_history_days: number;
  weight_completeness: number;
  intake_completeness: number;
  adaptive_estimate_count: number;
  recommendation_policy_version: string;
  trend_policy_version: string;
  adaptive_policy_version: string;
  energy_equivalent_policy_version: string;
  assumptions: string[];
}
export interface PersonalizedMacroPlan {
  calorie_target_kcal_per_day: number;
  calorie_source: MacroCalorieSource;
  strategy: MacroStrategy;
  body_weight_kg: number;
  protein_g_per_kg: number;
  fat_percentage: number;
  protein_g_per_day: number;
  fat_g_per_day: number;
  carbohydrate_g_per_day: number;
  protein_kcal_per_day: number;
  fat_kcal_per_day: number;
  carbohydrate_kcal_per_day: number;
  macro_policy_version: string;
  assumptions: string[];
  training_adjustment_available?: boolean;
  training_adjustment_applied?: boolean;
  training_policy_version?: string | null;
  protein_policy_source?: string;
  carbohydrate_policy_source?: string;
  baseline_protein_target_g?: number | null;
  training_aware_protein_target_g?: number | null;
  effective_protein_target_g?: number | null;
  baseline_carbohydrate_target_g?: number | null;
  effective_carbohydrate_target_g?: number | null;
  protein_priority?: string | null;
  carbohydrate_performance_priority?: string | null;
  training_reason_codes?: string[];
}
export interface NutritionTargetRange {
  lower_bound: number;
  selected_value: number;
  upper_bound: number;
  unit: NutritionTargetUnit;
  interpretation: string;
  range_kind: NutritionRangeKind;
}
export interface NutritionTargetEnvelope {
  selected_calorie_target_kcal_per_day: number;
  calorie_adherence_range: NutritionTargetRange;
  protein_preferred_range: NutritionTargetRange;
  fat_preferred_range: NutritionTargetRange;
  carbohydrate_flexible_range: NutritionTargetRange;
  macro_plan: PersonalizedMacroPlan;
  macro_strategy: MacroStrategy;
  calorie_source: MacroCalorieSource;
  policy_floors: string[];
  range_policy_version: string;
  macro_policy_version: string;
  assumptions: string[];
}
export interface DietaryPreferenceAssessment {
  dietary_pattern: DietaryPattern;
  selection_mode: FoodSelectionMode;
  protein_target_range: NutritionTargetRange;
  protein_target_provenance: string;
  inferred_hard_excluded_categories: FoodCategory[];
  explicit_hard_excluded_categories: FoodCategory[];
  limited_categories: FoodCategory[];
  disliked_categories: FoodCategory[];
  accepted_categories: FoodCategory[];
  preferred_categories: FoodCategory[];
  favorite_categories: FoodCategory[];
  usable_protein_source_categories: FoodCategory[];
  usable_protein_source_count: number;
  protein_flexibility_status: ProteinFlexibilityStatus;
  conflicts: string[];
  verification_notices: string[];
  actionable_requirements: string[];
  category_policy_version: string;
  pattern_policy_version: string;
  assessment_policy_version: string;
  protein_flexibility_policy_version: string;
  target_range_policy_version: string;
  assumptions: string[];
}
export interface TrainingStreamEvidence {
  eligible_calendar_days: number;
  observation_records: number;
  contributor_count: number;
  completeness: number;
  mean_value: number | null;
  weekly_equivalent: number | null;
  evidence_available: boolean;
}
export interface TrainingDemandAssessment {
  assessment_available: boolean;
  effective_date: string | null;
  overall_demand: TrainingDemandLevel | null;
  resistance_demand: TrainingDemandLevel | null;
  aerobic_sport_demand: TrainingDemandLevel | null;
  protein_priority: TrainingPriority | null;
  carbohydrate_performance_priority: TrainingPriority | null;
  evidence_source: TrainingEvidenceSource;
  questionnaire_summary: string[];
  step_evidence: TrainingStreamEvidence;
  strength_evidence: TrainingStreamEvidence;
  cardio_evidence: TrainingStreamEvidence;
  reason_codes: string[];
  policy_version: string;
  assumptions: string[];
}
export interface PersonalizedPlanSnapshot {
  as_of_date: string | null;
  lifecycle_stage: PersonalizationStage;
  lifecycle_requirements: PersonalizationRequirement[];
  calorie_basis: PlanCalorieBasis;
  baseline_calorie_target_kcal_per_day: number;
  selected_calorie_target_kcal_per_day: number;
  previous_selected_calorie_target_kcal_per_day: number | null;
  change_from_previous_snapshot_kcal_per_day: number | null;
  adaptive_tdee_kcal_per_day: number | null;
  adaptive_median_absolute_deviation_kcal_per_day: number | null;
  eligible_adaptive_estimate_count: number;
  recommendation_status: RecommendationStatus;
  recommendation_reasons: RecommendationReason[];
  raw_recommendation_adjustment_kcal_per_day: number | null;
  limited_recommendation_adjustment_kcal_per_day: number | null;
  macro_plan: PersonalizedMacroPlan;
  planning_policy_version: string;
  baseline_energy_formula_version: string;
  baseline_activity_policy_version: string;
  baseline_energy_equivalent_policy_version: string;
  baseline_macro_policy_version: string;
  lifecycle_policy_version: string;
  trend_policy_version: string;
  adaptive_policy_version: string;
  recommendation_policy_version: string;
  personalized_macro_policy_version: string;
  assumptions: string[];
  target_envelope: NutritionTargetEnvelope | null;
}
export interface PlanProgression {
  snapshots: PersonalizedPlanSnapshot[];
  submitted_observation_count: number;
  planning_policy_version: string;
  assumptions: string[];
}
export interface ProfileIntelligenceResponse {
  policy_version: string;
  baseline: BaselineResult;
  trends: TrendsResult;
  adaptive_tdee: AdaptiveResult;
  lifecycle: LifecycleResult;
  recommendation: RecommendationResult;
  latest_plan: PersonalizedPlanSnapshot;
  dietary_assessment: DietaryPreferenceAssessment;
  training_assessment?: TrainingDemandAssessment;
  plan_progression: PlanProgression | null;
  assumptions: string[];
}
