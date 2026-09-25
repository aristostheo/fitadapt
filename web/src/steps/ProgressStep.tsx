import { PlanProgression, TrendChart } from "../components/Results";
import { ActionBar, MetricCard, StepHeader } from "../components/ui";
import type { ProfileIntelligenceResponse } from "../types";
import { whole } from "../utils/presentation";

export function ProgressStep({
  result,
  onBack,
}: {
  result: ProfileIntelligenceResponse | null;
  onBack: () => void;
}) {
  return (
    <>
      <StepHeader
        eyebrow="Step 5 of 5"
        title="See the trend"
        description="Review calendar-aware observations and adaptive evidence without inventing values for missing days."
      />
      {!result ? (
        <article className="empty-state">
          <span aria-hidden="true">05</span>
          <div>
            <h2>No analyzed trend yet</h2>
            <p>
              Analyze your current profile and history first. Charts and
              progression will appear here without clearing your entries.
            </p>
          </div>
        </article>
      ) : (
        <div className="result-stack">
          <article className="result-card">
            <p className="eyebrow">Observed evidence</p>
            <h2>How your history is behaving</h2>
            <div className="metric-grid">
              <MetricCard
                label="Adaptive TDEE"
                value={whole(
                  result.adaptive_tdee.adaptive_tdee_kcal_per_day,
                  "kcal/day",
                )}
              />
              <MetricCard
                label="Eligible estimates"
                value={`${result.adaptive_tdee.eligible_points_used}`}
                detail={`${result.adaptive_tdee.total_eligible_points} eligible across all history`}
              />
              <MetricCard
                label="Observed variability"
                value={whole(
                  result.adaptive_tdee.median_absolute_deviation_kcal_per_day,
                  "kcal/day",
                )}
                detail="A spread in observed estimates, not confidence"
              />
            </div>
          </article>
          <div className="chart-grid">
            <TrendChart
              title="Weight trend"
              points={result.trends.points}
              raw="body_weight_kg"
              trend="trailing_body_weight_mean_kg"
              unit="kg"
              decimals
            />
            <TrendChart
              title="Calorie intake trend"
              points={result.trends.points}
              raw="energy_intake_kcal"
              trend="trailing_energy_intake_mean_kcal"
              unit="kcal"
            />
            <TrendChart
              title="Step trend"
              points={result.trends.points}
              raw="steps"
              trend="trailing_steps_mean"
              unit="steps"
            />
          </div>
          {result.plan_progression ? (
            <PlanProgression result={result} />
          ) : (
            <article className="result-card progress-guidance">
              <p className="eyebrow">Plan history</p>
              <h2>See how your plan changed</h2>
              <p>
                Plan history was not requested for this analysis. Return to
                Plan, enable plan history, and analyze again to compare each
                observation date.
              </p>
              <button className="button-quiet" onClick={onBack}>
                Return to plan
              </button>
            </article>
          )}
        </div>
      )}
      <ActionBar>
        <button className="button-secondary" onClick={onBack}>
          Back to plan
        </button>
      </ActionBar>
    </>
  );
}
