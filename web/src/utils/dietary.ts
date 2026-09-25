import type {
  DietaryPattern,
  FoodCategory,
  FoodConstraintAction,
  FoodConstraintType,
  FoodPreferenceLevel,
  FoodSelectionMode,
  NutritionPreferenceProfile,
  ProteinFlexibilityStatus,
} from "../types";

export const dietaryPatternLabels: Record<DietaryPattern, string> = {
  unrestricted: "Unrestricted",
  vegetarian: "Vegetarian",
  vegan: "Vegan",
  pescatarian: "Pescatarian",
  halal: "Halal",
  kosher: "Kosher",
  other: "Other",
};

export const dietaryPatterns: readonly DietaryPattern[] = [
  "unrestricted",
  "vegetarian",
  "vegan",
  "pescatarian",
  "halal",
  "kosher",
  "other",
];

export const foodCategoryLabels: Record<FoodCategory, string> = {
  poultry: "Poultry",
  beef: "Beef",
  pork: "Pork",
  fish: "Fish",
  shellfish: "Shellfish",
  eggs: "Eggs",
  dairy: "Dairy",
  soy: "Soy",
  legumes: "Legumes",
  protein_supplements: "Protein supplements",
  rice: "Rice",
  pasta: "Pasta",
  bread: "Bread",
  potatoes: "Potatoes",
  oats: "Oats",
  tortillas: "Tortillas",
  fruit: "Fruit",
  vegetables: "Vegetables",
  nuts: "Nuts",
  seeds: "Seeds",
  nut_butters: "Nut butters",
  avocado: "Avocado",
  cooking_oils: "Cooking oils",
};

export const constraintTypeLabels: Record<FoodConstraintType, string> = {
  allergy: "Allergy",
  required_exclusion: "Required exclusion",
  intolerance: "Intolerance",
};
export const constraintTypes: readonly FoodConstraintType[] = [
  "allergy",
  "required_exclusion",
  "intolerance",
];

export const constraintActionLabels: Record<FoodConstraintAction, string> = {
  exclude: "Exclude",
  limit: "Limit",
};
export const constraintActions: readonly FoodConstraintAction[] = [
  "exclude",
  "limit",
];

export const preferenceLevelLabels: Record<FoodPreferenceLevel, string> = {
  dislike: "Dislike",
  neutral: "Okay",
  like: "Like",
  favorite: "Favorite",
};
export const preferenceLevels: readonly FoodPreferenceLevel[] = [
  "dislike",
  "neutral",
  "like",
  "favorite",
];

export const flexibilityLabels: Record<ProteinFlexibilityStatus, string> = {
  supported: "Supported",
  limited: "Limited",
  difficult: "Difficult",
  infeasible: "Infeasible",
};

export const foodCategoryGroups: readonly {
  label: string;
  categories: readonly FoodCategory[];
}[] = [
  {
    label: "Protein sources",
    categories: [
      "poultry",
      "beef",
      "pork",
      "fish",
      "shellfish",
      "eggs",
      "dairy",
      "soy",
      "legumes",
      "protein_supplements",
    ],
  },
  {
    label: "Carbohydrate sources",
    categories: ["rice", "pasta", "bread", "potatoes", "oats", "tortillas"],
  },
  { label: "Produce", categories: ["fruit", "vegetables"] },
  {
    label: "Fat sources",
    categories: ["nuts", "seeds", "nut_butters", "avocado", "cooking_oils"],
  },
];

export const allFoodCategories = foodCategoryGroups.flatMap(
  (group) => group.categories,
);

export const initialDietaryProfile: NutritionPreferenceProfile = {
  dietary_pattern: "unrestricted",
  selection_mode: "broad",
  constraints: [],
  preferences: [],
};

const patternValues: Record<string, DietaryPattern | undefined> = {
  unrestricted: "unrestricted",
  vegetarian: "vegetarian",
  vegan: "vegan",
  pescatarian: "pescatarian",
  halal: "halal",
  kosher: "kosher",
  other: "other",
};
const selectionValues: Record<string, FoodSelectionMode | undefined> = {
  broad: "broad",
  selected: "selected",
};
const categoryValues: Record<string, FoodCategory | undefined> = {
  poultry: "poultry",
  beef: "beef",
  pork: "pork",
  fish: "fish",
  shellfish: "shellfish",
  eggs: "eggs",
  dairy: "dairy",
  soy: "soy",
  legumes: "legumes",
  protein_supplements: "protein_supplements",
  rice: "rice",
  pasta: "pasta",
  bread: "bread",
  potatoes: "potatoes",
  oats: "oats",
  tortillas: "tortillas",
  fruit: "fruit",
  vegetables: "vegetables",
  nuts: "nuts",
  seeds: "seeds",
  nut_butters: "nut_butters",
  avocado: "avocado",
  cooking_oils: "cooking_oils",
};
const constraintTypeValues: Record<string, FoodConstraintType | undefined> = {
  allergy: "allergy",
  required_exclusion: "required_exclusion",
  intolerance: "intolerance",
};
const constraintActionValues: Record<string, FoodConstraintAction | undefined> =
  { exclude: "exclude", limit: "limit" };
const preferenceValues: Record<string, FoodPreferenceLevel | undefined> = {
  dislike: "dislike",
  neutral: "neutral",
  like: "like",
  favorite: "favorite",
};

function parsed<T>(
  value: string,
  values: Record<string, T | undefined>,
  field: string,
): T {
  const result = values[value];
  if (result === undefined) throw new Error(`Unsupported ${field}: ${value}`);
  return result;
}

export const parseDietaryPattern = (value: string) =>
  parsed(value, patternValues, "dietary pattern");
export const parseSelectionMode = (value: string) =>
  parsed(value, selectionValues, "selection mode");
export const parseFoodCategory = (value: string) =>
  parsed(value, categoryValues, "food category");
export const parseConstraintType = (value: string) =>
  parsed(value, constraintTypeValues, "constraint type");
export const parseConstraintAction = (value: string) =>
  parsed(value, constraintActionValues, "constraint action");
export const parsePreferenceLevel = (value: string) =>
  parsed(value, preferenceValues, "preference level");

export function humanizeDietaryText(value: string): string {
  return [...allFoodCategories]
    .sort((left, right) => right.length - left.length)
    .reduce(
      (text, category) =>
        text.replace(
          new RegExp(`\\b${category}\\b`, "g"),
          foodCategoryLabels[category],
        ),
      value,
    );
}

export function dietaryProfileErrors(
  profile: NutritionPreferenceProfile | undefined,
): string[] {
  if (profile == null) return [];
  const errors: string[] = [];
  if (
    profile.dietary_pattern === "other" &&
    !profile.other_description?.trim()
  ) {
    errors.push("Describe your dietary pattern before continuing.");
  }
  if (
    profile.dietary_pattern !== "other" &&
    profile.other_description != null
  ) {
    errors.push(
      "The custom dietary-pattern description is only valid for Other.",
    );
  }
  const keys = profile.constraints.map(
    (item) => `${item.category}:${item.constraint_type}`,
  );
  if (new Set(keys).size !== keys.length)
    errors.push("Each category and constraint type may be added only once.");
  if (
    profile.constraints.some(
      (item) =>
        item.constraint_type !== "intolerance" && item.action !== "exclude",
    )
  ) {
    errors.push("Allergies and required exclusions must use Exclude.");
  }
  if (
    profile.constraints.some((item) => item.note != null && !item.note.trim())
  ) {
    errors.push("Constraint notes must contain text or be left absent.");
  }
  if (
    profile.selection_mode === "selected" &&
    !profile.preferences.some((item) => item.level !== "dislike")
  ) {
    errors.push(
      "Select at least one food category as Okay, Like, or Favorite.",
    );
  }
  return errors;
}
