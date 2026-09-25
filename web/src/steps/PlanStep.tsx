import {
  BaselineAndQuality,
  CurrentPlan,
  DietaryAssessmentCard,
  LifecycleStatus,
  RecommendationPanel,
} from "../components/Results";
import { ActionBar, Notice, SectionCard, StepHeader } from "../components/ui";
import type { ProfileIntelligenceResponse } from "../types";

export function PlanStep({
  result,
  error,
  loading,
  includeProgression,
  canRetry,
  onIncludeProgression,
  onAnalyze,
  onRetry,
  onBack,
  onProgress,
}: {
  result: ProfileIntelligenceResponse | null;
  error: string;
  loading: boolean;
  includeProgression: boolean;
  canRetry: boolean;
  onIncludeProgression: (value: boolean) => void;
  onAnalyze: () => void;
  onRetry: () => void;
  onBack: () => void;
  onProgress: () => void;
}) {
  return (
    <>
      <StepHeader
        eyebrow="Step 4 of 5"
        title="Your current plan"
        description="Baseline guidance is immediate. Personalization appears only when your history supports it."
      />
      <SectionCard className="analysis-control">
        <label className="checkbox">
          <input
            aria-label="Include plan history"
            type="checkbox"
            checked={includeProgression}
            onChange={(event) => onIncludeProgression(event.target.checked)}
          />
          <span>
            Include plan history
            <small>
              Reconstructs one plan per observation prefix and may take longer
              for large histories.
            </small>
          </span>
        </label>
        <button disabled={loading} onClick={onAnalyze}>
          {loading
            ? "Analyzing…"
            : result
              ? "Refresh analysis"
              : "Analyze my profile"}
        </button>
      </SectionCard>
      {error && (
        <Notice tone="danger">
          <div role="alert">
            {error} {canRetry && <button onClick={onRetry}>Retry</button>}
          </div>
        </Notice>
      )}
      {!result && !error && (
        <article className="empty-state">
          <span aria-hidden="true">04</span>
          <div>
            <h2>Ready for analysis</h2>
            <p>
              FitAdapt will calculate a transparent baseline and use any
              suitable history for adaptive evidence. Your entries remain intact
              if the API is unavailable.
            </p>
          </div>
        </article>
      )}
      {result && (
        <div className="result-stack">
          <CurrentPlan plan={result.latest_plan} result={result} />
          <RecommendationPanel result={result} />
          <DietaryAssessmentCard assessment={result.dietary_assessment} />
          <LifecycleStatus result={result} />
          <BaselineAndQuality result={result} />
        </div>
      )}
      <ActionBar>
        <button className="button-secondary" onClick={onBack}>
          Back to history
        </button>
        {result && <button onClick={onProgress}>View progress</button>}
      </ActionBar>
    </>
  );
}
