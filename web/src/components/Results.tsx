import { useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { paddedDomain } from "../chart-domain";
import type {
  DietaryPreferenceAssessment,
  FoodCategory,
  PersonalizedPlanSnapshot,
  ProfileIntelligenceResponse,
  TrendPoint,
} from "../types";
import {
  flexibilityLabels,
  foodCategoryLabels,
  humanizeDietaryText,
} from "../utils/dietary";
import {
  lifecycleLabels,
  percent,
  planBasisCopy,
  reasonCopy,
  statusCopy,
  strategyLabels,
  targetRange,
  whole,
} from "../utils/presentation";
import { MetricCard, Notice, StatusBadge } from "./ui";

const stageCopy = {
  baseline:
    "Using profile-based estimates because there is not enough relevant history.",
  calibrating: "FitAdapt is building usable weight and intake trends.",
  early_personalized:
    "Individual evidence exists, but the full adaptive aggregate is not ready.",
  personalized:
    "The adaptive aggregate is available and used where recommendation safety allows.",
};
const requirementCopy = {
  add_history: "Add your first weight and calorie entries.",
  log_body_weight: "Log body weight consistently.",
  log_energy_intake: "Log calorie intake consistently.",
  build_weight_trend: "Continue logging to build a usable weight trend.",
  build_intake_trend:
    "Continue logging to build a usable calorie-intake trend.",
  collect_more_eligible_estimates:
    "Continue logging until more adaptive estimates are eligible.",
};

export function LifecycleStatus({
  result,
}: {
  result: ProfileIntelligenceResponse;
}) {
  const lifecycle = result.lifecycle;
  const stages = [
    "baseline",
    "calibrating",
    "early_personalized",
    "personalized",
  ] as const;
  return (
    <article className="result-card lifecycle-card">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Personalization status</p>
          <h2>{lifecycleLabels[lifecycle.stage]}</h2>
        </div>
        <StatusBadge
          tone={lifecycle.stage === "personalized" ? "success" : "warning"}
        >
          {lifecycle.eligible_adaptive_estimate_count} /{" "}
          {lifecycle.required_eligible_estimate_count} estimates
        </StatusBadge>
      </div>
      <ol className="lifecycle-steps">
        {stages.map((stage, index) => (
          <li
            key={stage}
            className={
              stage === lifecycle.stage
                ? "current"
                : stages.indexOf(lifecycle.stage) > index
                  ? "complete"
                  : ""
            }
          >
            <span>{index + 1}</span>
            <strong>{lifecycleLabels[stage]}</strong>
          </li>
        ))}
      </ol>
      <p>{stageCopy[lifecycle.stage]}</p>
      <div className="evidence-grid">
        <span>
          History <strong>{lifecycle.calendar_history_days} days</strong>
        </span>
        <span>
          Weight <strong>{lifecycle.weight_observation_count}</strong>
        </span>
        <span>
          Intake <strong>{lifecycle.intake_observation_count}</strong>
        </span>
        <span>
          Weight completeness{" "}
          <strong>{percent(lifecycle.weight_completeness)}</strong>
        </span>
        <span>
          Intake completeness{" "}
          <strong>{percent(lifecycle.intake_completeness)}</strong>
        </span>
      </div>
      {lifecycle.requirements.length > 0 && (
        <ul className="action-list">
          {lifecycle.requirements.map((item) => (
            <li key={item}>{requirementCopy[item]}</li>
          ))}
        </ul>
      )}
      <details>
        <summary>Technical lifecycle details</summary>
        <p>
          Current stage code: <code>{lifecycle.stage}</code>
        </p>
      </details>
    </article>
  );
}

export function CurrentPlan({
  plan,
  result,
}: {
  plan: PersonalizedPlanSnapshot;
  result: ProfileIntelligenceResponse;
}) {
  const envelope = plan.target_envelope;
  const fallback =
    result.lifecycle.stage === "personalized" &&
    plan.calorie_basis === "baseline";
  return (
    <article className="result-card current-plan">
      <div className="plan-heading">
        <div>
          <p className="eyebrow">Current proposed plan</p>
          <p className="plan-label">What to do now</p>
          <h2>
            {whole(plan.selected_calorie_target_kcal_per_day, "kcal/day")}
          </h2>
          {envelope && (
            <p className="range-summary">
              Adherence range:{" "}
              <strong>{targetRange(envelope.calorie_adherence_range)}</strong>
            </p>
          )}
          <p>As of {plan.as_of_date || "your profile setup"}</p>
        </div>
        <StatusBadge
          tone={plan.calorie_basis === "personalized" ? "success" : "neutral"}
        >
          {planBasisCopy[plan.calorie_basis]}
        </StatusBadge>
      </div>
      {fallback && (
        <Notice tone="warning">
          Personalized evidence exists, but the current recommendation safety
          gate retained your baseline target.
        </Notice>
      )}
      {envelope ? (
        <>
          <div
            className="metric-grid target-ranges"
            aria-label="Nutrition target ranges"
          >
            <MetricCard
              label="Selected protein"
              value={whole(
                envelope.protein_preferred_range.selected_value,
                "g/day",
              )}
              detail={`Preferred range: ${targetRange(envelope.protein_preferred_range)}`}
            />
            <MetricCard
              label="Selected fat"
              value={whole(
                envelope.fat_preferred_range.selected_value,
                "g/day",
              )}
              detail={`Preferred range: ${targetRange(envelope.fat_preferred_range)}`}
            />
            <MetricCard
              label="Selected carbohydrates"
              value={whole(
                envelope.carbohydrate_flexible_range.selected_value,
                "g/day",
              )}
              detail={`Flexible range: ${targetRange(envelope.carbohydrate_flexible_range)}`}
            />
            <MetricCard
              label="Strategy"
              value={strategyLabels[envelope.macro_strategy]}
              detail="Selected macro approach"
            />
          </div>
          <p className="range-explanation">
            The selected calories and macros are one feasible point within
            flexible policy ranges. You do not need to hit exact grams
            perfectly. Range endpoints are separate bounds, so arbitrary
            combinations of every endpoint may not reconcile exactly to the
            calorie target.
          </p>
          <details>
            <summary>Technical plan details</summary>
            <p>
              Calorie source: <code>{envelope.calorie_source}</code>
            </p>
            <p>
              Policy versions: <code>{envelope.range_policy_version}</code>,{" "}
              <code>{envelope.macro_policy_version}</code>
            </p>
          </details>
        </>
      ) : (
        <Notice tone="warning">
          Target ranges are unavailable for this plan response.
        </Notice>
      )}
      {plan.change_from_previous_snapshot_kcal_per_day != null && (
        <p>
          Change from previous plan:{" "}
          {whole(plan.change_from_previous_snapshot_kcal_per_day, "kcal/day")}
        </p>
      )}
      <p className="supporting-copy">
        FitAdapt caps the next step to move gradually toward the calculated goal
        intake. Your macro strategy is explicitly selected, not inferred.
      </p>
    </article>
  );
}

export function RecommendationPanel({
  result,
}: {
  result: ProfileIntelligenceResponse;
}) {
  return (
    <article className="result-card">
      <p className="eyebrow">Why this plan</p>
      <h2>{statusCopy[result.recommendation.status]}</h2>
      <p className="primary-reason">
        {reasonCopy[result.recommendation.reasons[0]] ||
          "Review your logged evidence before changing intake."}
      </p>
      <div className="evidence-grid">
        <span>
          Observed history{" "}
          <strong>
            {whole(result.adaptive_tdee.adaptive_tdee_kcal_per_day, "kcal/day")}
          </strong>
        </span>
        <span>
          Observed variability{" "}
          <strong>
            {whole(
              result.adaptive_tdee.median_absolute_deviation_kcal_per_day,
              "kcal/day",
            )}
          </strong>
        </span>
        <span>
          Recent intake{" "}
          <strong>
            {whole(
              result.recommendation.recent_mean_intake_kcal_per_day,
              "kcal/day",
            )}
          </strong>
        </span>
        <span>
          Calculated goal intake{" "}
          <strong>
            {whole(
              result.recommendation.personalized_goal_target_kcal_per_day,
              "kcal/day",
            )}
          </strong>
        </span>
        <span>
          Recommended adjustment{" "}
          <strong>
            {whole(
              result.recommendation.recommended_adjustment_kcal_per_day,
              "kcal/day",
            )}
          </strong>
        </span>
      </div>
      <p className="supporting-copy">
        Adjustments are deliberately gradual and are never applied
        automatically.
      </p>
      <details>
        <summary>Technical recommendation details</summary>
        <ul>
          {result.recommendation.reasons.map((reason) => (
            <li key={reason}>
              {reasonCopy[reason]} <code>{reason}</code>
            </li>
          ))}
        </ul>
        {result.recommendation.raw_adjustment_kcal_per_day != null && (
          <p>
            Raw adjustment:{" "}
            {whole(
              result.recommendation.raw_adjustment_kcal_per_day,
              "kcal/day",
            )}
          </p>
        )}
      </details>
    </article>
  );
}

const flexibilityCopy = {
  supported:
    "Your selected food pool includes several usable protein-source categories. This describes choice flexibility, not nutritional adequacy.",
  limited:
    "Your selected food pool has limited protein-source variety. Review whether these categories are practical for you.",
  difficult:
    "Only one usable protein-source category is currently available, which may make adherence difficult.",
  infeasible:
    "The selected food pool does not currently provide a usable protein-source category. This is a category-selection issue, not a claim of biological impossibility.",
};

function CategorySummary({
  label,
  categories,
}: {
  label: string;
  categories: readonly FoodCategory[];
}) {
  return (
    <div className="category-summary">
      <strong>{label}</strong>
      <span>
        {categories.length > 0
          ? categories
              .map((category) => foodCategoryLabels[category])
              .join(", ")
          : "None"}
      </span>
    </div>
  );
}

export function DietaryAssessmentCard({
  assessment,
}: {
  assessment: DietaryPreferenceAssessment;
}) {
  const status = assessment.protein_flexibility_status;
  const excluded = [
    ...new Set([
      ...assessment.inferred_hard_excluded_categories,
      ...assessment.explicit_hard_excluded_categories,
    ]),
  ];
  return (
    <article className="result-card dietary-assessment" aria-live="polite">
      <div className="result-card-heading">
        <div>
          <p className="eyebrow">Food flexibility</p>
          <h2>{flexibilityLabels[status]}</h2>
        </div>
        <StatusBadge
          tone={
            status === "supported"
              ? "success"
              : status === "infeasible"
                ? "danger"
                : "warning"
          }
        >
          {assessment.usable_protein_source_count} usable protein{" "}
          {assessment.usable_protein_source_count === 1 ? "source" : "sources"}
        </StatusBadge>
      </div>
      <p>{flexibilityCopy[status]}</p>
      <div className="metric-grid">
        <MetricCard
          label="Protein range assessed"
          value={targetRange(assessment.protein_target_range)}
          detail={assessment.protein_target_provenance}
        />
        <MetricCard
          label="Pattern"
          value={
            assessment.dietary_pattern === "other"
              ? "Other"
              : assessment.dietary_pattern.charAt(0).toUpperCase() +
                assessment.dietary_pattern.slice(1)
          }
          detail={
            assessment.selection_mode === "broad"
              ? "Broad food pool"
              : "Selected food pool"
          }
        />
      </div>
      <div className="category-summary-grid">
        <CategorySummary
          label="Accepted categories"
          categories={assessment.accepted_categories}
        />
        <CategorySummary
          label="Preferred categories"
          categories={assessment.preferred_categories}
        />
        <CategorySummary
          label="Favorite categories"
          categories={assessment.favorite_categories}
        />
        <CategorySummary
          label="Limited categories"
          categories={assessment.limited_categories}
        />
        <CategorySummary label="Excluded categories" categories={excluded} />
      </div>
      {assessment.conflicts.length > 0 && (
        <Notice tone="warning">
          <strong>Preference conflicts</strong>
          <ul>
            {assessment.conflicts.map((item) => (
              <li key={item}>{humanizeDietaryText(item)}</li>
            ))}
          </ul>
        </Notice>
      )}
      {assessment.verification_notices.length > 0 && (
        <Notice tone="warning">
          <strong>Verification still needed</strong>
          <ul>
            {assessment.verification_notices.map((item) => (
              <li key={item}>{humanizeDietaryText(item)}</li>
            ))}
          </ul>
        </Notice>
      )}
      {assessment.actionable_requirements.length > 0 && (
        <Notice>
          <strong>What to review next</strong>
          <ul>
            {assessment.actionable_requirements.map((item) => (
              <li key={item}>{humanizeDietaryText(item)}</li>
            ))}
          </ul>
        </Notice>
      )}
      <details>
        <summary>Technical dietary-assessment details</summary>
        <dl className="technical-details">
          <div>
            <dt>Category policy</dt>
            <dd>{assessment.category_policy_version}</dd>
          </div>
          <div>
            <dt>Pattern policy</dt>
            <dd>{assessment.pattern_policy_version}</dd>
          </div>
          <div>
            <dt>Assessment policy</dt>
            <dd>{assessment.assessment_policy_version}</dd>
          </div>
          <div>
            <dt>Flexibility policy</dt>
            <dd>{assessment.protein_flexibility_policy_version}</dd>
          </div>
          <div>
            <dt>Target-range policy</dt>
            <dd>{assessment.target_range_policy_version}</dd>
          </div>
        </dl>
        <ul>
          {assessment.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </details>
    </article>
  );
}

export function BaselineAndQuality({
  result,
}: {
  result: ProfileIntelligenceResponse;
}) {
  return (
    <div className="two-column-results">
      <article className="result-card secondary-result">
        <p className="eyebrow">Baseline reference</p>
        <h2>Starting estimate</h2>
        <div className="metric-grid">
          <MetricCard
            label="REE"
            value={whole(
              result.baseline.baseline_energy.estimated_ree_kcal_per_day,
              "kcal/day",
            )}
          />
          <MetricCard
            label="Baseline TDEE"
            value={whole(
              result.baseline.baseline_energy.estimated_tdee_kcal_per_day,
              "kcal/day",
            )}
          />
          <MetricCard
            label="Calorie target"
            value={whole(
              result.baseline.target_calories_kcal_per_day,
              "kcal/day",
            )}
          />
        </div>
        <p className="supporting-copy">
          This is your starting estimate for comparison. The current plan uses
          your selected macro approach.
        </p>
        <details>
          <summary>Technical baseline details</summary>
          <p>
            Formula:{" "}
            <code>{result.baseline.baseline_energy.ree_formula_version}</code>
          </p>
          <p>
            Policy versions:{" "}
            <code>{result.baseline.energy_equivalent_policy_version}</code>,{" "}
            <code>{result.baseline.macro_policy_version}</code>
          </p>
        </details>
      </article>
      <article className="result-card">
        <p className="eyebrow">History quality</p>
        <h2>Logging coverage</h2>
        <div className="evidence-grid">
          <span>
            Weight{" "}
            <strong>
              {percent(
                result.trends.data_quality.body_weight_completeness_ratio,
              )}
            </strong>
          </span>
          <span>
            Calories{" "}
            <strong>
              {percent(
                result.trends.data_quality.energy_intake_completeness_ratio,
              )}
            </strong>
          </span>
          <span>
            Steps{" "}
            <strong>
              {percent(result.trends.data_quality.step_completeness_ratio)}
            </strong>
          </span>
        </div>
      </article>
    </div>
  );
}

export function TrendChart({
  title,
  points,
  raw,
  trend,
  unit,
  decimals = false,
}: {
  title: string;
  points: TrendPoint[];
  raw: keyof TrendPoint;
  trend: keyof TrendPoint;
  unit: string;
  decimals?: boolean;
}) {
  const format = (value: number) =>
    decimals
      ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
          value,
        )
      : Math.round(value).toLocaleString();
  if (!points.some((point) => point[raw] != null))
    return (
      <article className="empty-card compact">
        <h2>{title}</h2>
        <p>No recorded {unit} values yet. Add entries to see this chart.</p>
      </article>
    );
  return (
    <article className="chart-card">
      <h2>{title}</h2>
      <p className="chart-key">Coral: recorded value · teal: trailing mean</p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={points}>
          <XAxis dataKey="observed_on" hide />
          <YAxis
            domain={paddedDomain(points, String(raw), String(trend))}
            tickFormatter={(value) => format(Number(value))}
            width={56}
          />
          <Tooltip formatter={(value) => `${format(Number(value))} ${unit}`} />
          <Line
            type="linear"
            connectNulls={false}
            dataKey={String(raw)}
            stroke="#dc6849"
            dot={false}
            name={`Recorded (${unit})`}
          />
          <Line
            type="linear"
            connectNulls={false}
            dataKey={String(trend)}
            stroke="#0f5960"
            dot={false}
            name={`Trailing mean (${unit})`}
          />
        </LineChart>
      </ResponsiveContainer>
    </article>
  );
}

export function PlanProgression({
  result,
}: {
  result: ProfileIntelligenceResponse;
}) {
  const [open, setOpen] = useState(false);
  const progression = result.plan_progression;
  if (!progression) return null;
  const snapshots = [...progression.snapshots].reverse();
  return (
    <article className="result-card progression">
      <button
        className="button-quiet"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {open ? "Hide plan history" : "Show plan history"}
      </button>
      {open &&
        (progression.snapshots.length === 0 ? (
          <p>No entries yet, so there is no plan history to reconstruct.</p>
        ) : (
          <>
            <p>Each point uses only observations available up to that date.</p>
            <ResponsiveContainer width="100%" height={210}>
              <LineChart data={progression.snapshots}>
                <XAxis dataKey="as_of_date" hide />
                <YAxis
                  domain={paddedDomain(
                    progression.snapshots,
                    "selected_calorie_target_kcal_per_day",
                  )}
                />
                <Tooltip />
                <Line
                  dataKey="selected_calorie_target_kcal_per_day"
                  stroke="#dc6849"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
            <div className="history-table-wrap progression-table">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Stage</th>
                    <th>Basis</th>
                    <th>Target / range</th>
                    <th>Change</th>
                    <th>Strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((item) => (
                    <tr key={item.as_of_date}>
                      <td>{item.as_of_date}</td>
                      <td>{item.lifecycle_stage.replace("_", " ")}</td>
                      <td>{item.calorie_basis}</td>
                      <td className="progression-target">
                        <strong>
                          {whole(
                            item.selected_calorie_target_kcal_per_day,
                            "kcal/day",
                          )}
                        </strong>
                        <small>
                          {item.target_envelope
                            ? targetRange(
                                item.target_envelope.calorie_adherence_range,
                              )
                            : "Range unavailable"}
                        </small>
                      </td>
                      <td>
                        {item.change_from_previous_snapshot_kcal_per_day == null
                          ? "—"
                          : whole(
                              item.change_from_previous_snapshot_kcal_per_day,
                              "kcal/day",
                            )}
                      </td>
                      <td>{strategyLabels[item.macro_plan.strategy]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ))}
    </article>
  );
}
