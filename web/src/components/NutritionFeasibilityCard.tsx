import type { FoodCategory, NutritionFeasibilityAssessment } from "../types";
import { foodCategoryLabels } from "../utils/dietary";
import { MetricCard, Notice } from "./ui";

const levelLabels = {
  easy: "Easy",
  manageable: "Manageable",
  challenging: "Challenging",
  very_challenging: "Very challenging",
} as const;

function categories(values: readonly FoodCategory[]): string {
  return values.length
    ? values.map((value) => foodCategoryLabels[value]).join(", ")
    : "None recorded";
}

export function NutritionFeasibilityCard({
  assessment,
}: {
  assessment?: NutritionFeasibilityAssessment;
}) {
  if (!assessment) return null;
  if (!assessment.assessment_available || !assessment.overall_feasibility) {
    return (
      <article
        className="result-card nutrition-feasibility"
        aria-labelledby="nutrition-feasibility-title"
      >
        <p className="eyebrow">Nutrition feasibility</p>
        <h2 id="nutrition-feasibility-title">
          More dietary information needed
        </h2>
        <p>
          Add food preferences or restrictions to assess how practical the
          current plan may be for your choices. Missing information does not
          imply broad flexibility.
        </p>
        <p className="supporting-copy">
          The current calorie and macro targets are unchanged. No meals or exact
          food quantities are generated.
        </p>
        <details>
          <summary>Technical feasibility details</summary>
          <p>
            Reason codes: <code>{assessment.reason_codes.join(", ")}</code>
          </p>
          <p>
            Policy: <code>{assessment.policy_version}</code>
          </p>
          <div>
            <dt>Protein policy source / priority</dt>
            <dd>
              {assessment.protein_policy_source} /{" "}
              {assessment.protein_priority ?? "unavailable"}
            </dd>
          </div>
          <div>
            <dt>Carbohydrate policy source / priority</dt>
            <dd>
              {assessment.carbohydrate_policy_source} /{" "}
              {assessment.carbohydrate_performance_priority ?? "unavailable"}
            </dd>
          </div>
          <div>
            <dt>Standard protein / effective protein</dt>
            <dd>
              {Math.round(assessment.baseline_protein_target_g_per_day)} g /{" "}
              {Math.round(assessment.protein_target_g_per_day)} g
            </dd>
          </div>
        </details>
      </article>
    );
  }
  return (
    <article
      className="result-card nutrition-feasibility"
      aria-labelledby="nutrition-feasibility-title"
    >
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Nutrition feasibility</p>
          <h2 id="nutrition-feasibility-title">
            {levelLabels[assessment.overall_feasibility]}
          </h2>
        </div>
        <span className="status-badge">Current plan</span>
      </div>
      <p>
        This is a practical-fit assessment of the existing macro plan, not a new
        target calculation.
      </p>
      <div className="metric-grid">
        <MetricCard
          label="Protein"
          value={
            assessment.protein_feasibility
              ? levelLabels[assessment.protein_feasibility]
              : "Unavailable"
          }
        />
        <MetricCard
          label="Carbohydrates"
          value={
            assessment.carbohydrate_feasibility
              ? levelLabels[assessment.carbohydrate_feasibility]
              : "Unavailable"
          }
        />
        <MetricCard
          label="Fat"
          value={
            assessment.fat_feasibility
              ? levelLabels[assessment.fat_feasibility]
              : "Unavailable"
          }
        />
        <MetricCard
          label="Restrictions"
          value={
            assessment.restriction_compatibility?.replace("_", " ") ??
            "Unavailable"
          }
        />
      </div>
      <div className="category-summary-grid">
        <div className="category-summary">
          <strong>Accepted protein options</strong>
          <span>{categories(assessment.accepted_protein_categories)}</span>
        </div>
        <div className="category-summary">
          <strong>Accepted carbohydrate options</strong>
          <span>{categories(assessment.accepted_carbohydrate_categories)}</span>
        </div>
        <div className="category-summary">
          <strong>Accepted fat options</strong>
          <span>{categories(assessment.accepted_fat_categories)}</span>
        </div>
        {assessment.limiting_categories.length > 0 && (
          <div className="category-summary">
            <strong>Limited by restrictions/preferences</strong>
            <span>{categories(assessment.limiting_categories)}</span>
          </div>
        )}
      </div>
      {assessment.guidance.length > 0 && (
        <section aria-label="Practical guidance">
          <h3>Practical ideas</h3>
          <ul className="action-list">
            {assessment.guidance.slice(0, 4).map((item, index) => (
              <li key={`${item.reason_code}-${index}`}>{item.message}</li>
            ))}
          </ul>
        </section>
      )}
      {assessment.dietary_conflicts.length > 0 && (
        <Notice tone="warning">
          <strong>Preference conflicts to review</strong>
          <ul>
            {assessment.dietary_conflicts.map((conflict, index) => (
              <li key={`${index}-${conflict}`}>{conflict}</li>
            ))}
          </ul>
        </Notice>
      )}
      <Notice>
        The assessment did not change calories or macros. Training-aware policy
        may have shaped the macro mix first; calories still come from
        baseline/adaptive TDEE.
      </Notice>
      <details>
        <summary>Technical feasibility details</summary>
        <dl className="technical-details">
          <div>
            <dt>Macro policy</dt>
            <dd>{assessment.macro_policy_version}</dd>
          </div>
          <div>
            <dt>Feasibility policy</dt>
            <dd>{assessment.policy_version}</dd>
          </div>
          <div>
            <dt>Training adjustment applied</dt>
            <dd>{assessment.training_adjustment_applied ? "yes" : "no"}</dd>
          </div>
          <div>
            <dt>Accepted category counts</dt>
            <dd>
              Protein {assessment.accepted_protein_categories.length};
              carbohydrate {assessment.accepted_carbohydrate_categories.length};
              fat {assessment.accepted_fat_categories.length}
            </dd>
          </div>
        </dl>
        {assessment.dietary_conflicts.length > 0 && (
          <ul>
            {assessment.dietary_conflicts.map((conflict, index) => (
              <li key={`${index}-${conflict}`}>{conflict}</li>
            ))}
          </ul>
        )}
        <ul>
          {assessment.reason_codes.map((code) => (
            <li key={code}>
              <code>{code}</code>
            </li>
          ))}
        </ul>
        <ul>
          {assessment.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
    </article>
  );
}
