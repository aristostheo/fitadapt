import type { Profile, ProfileIntelligenceResponse } from '../types'
import { strategyLabels, whole } from '../utils/presentation'
import { MetricCard, StatusBadge } from './ui'

type Result = ProfileIntelligenceResponse
type OverviewProps = {
  result: Result | null
  profile: Profile
  observationCount: number
  loading: boolean
  error: string
  onProfile: () => void
  onHistory: () => void
  onAnalyze: () => void
  onRetry: () => void
  onPlan: () => void
  onProgress: () => void
}

const statusPresentation = {
  plan_remains_appropriate: { label: 'Current plan on track', tone: 'success' },
  more_data_needed: { label: 'More data needed', tone: 'warning' },
  deferred_estimator_stabilizing: { label: 'Stabilizing', tone: 'purple' },
  deferred_adaptive_evidence_ambiguous: { label: 'Evidence ambiguous', tone: 'warning' },
  proposal_available: { label: 'Proposed update', tone: 'purple' },
  proposal_requires_review: { label: 'Review required', tone: 'warning' },
  reversal_pending_confirmation: { label: 'Reversal pending', tone: 'warning' },
  update_available: { label: 'Activation ready', tone: 'success' },
} as const

const stabilityCopy = {
  stable: 'Enough consistent evidence is available to support planning.',
  stabilizing: 'Recent intake or weight patterns changed. FitAdapt is collecting more evidence.',
  unstable: 'Recent weight data is too variable to treat this estimate as settled.',
  insufficient: 'More recent weight and intake data is needed.',
} as const

const goalCopy = { cut: 'Weight loss', maintain: 'Maintenance', gain: 'Weight gain' } as const

function EmptyOverview({ observationCount, loading, error, onHistory, onProfile, onAnalyze, onRetry }: OverviewProps) {
  return (
    <div className="overview-page">
      <header className="overview-hero">
        <div>
          <p className="eyebrow">FitAdapt / Engine overview</p>
          <h1>Adaptive diet intelligence, without the black box.</h1>
          <p>
            Profile-based energy estimates meet longitudinal evidence, training
            context, dietary fit and conservative plan adaptation. Every change
            has a reason, a safety boundary and an activation state.
          </p>
          <div className="hero-actions">
            <button disabled={loading} onClick={onHistory}>
              {loading ? 'Analyzing…' : 'Explore with fictional data'}
            </button>
            <button className="button-quiet" onClick={onProfile}>Set up profile</button>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <span>PROFILE</span><i /><span>EVIDENCE</span><i /><strong>PLAN</strong>
          <small>Deterministic · explainable · stateless</small>
        </div>
      </header>
      {error && (
        <div className="notice-card danger" role="alert">
          {error} <button className="button-quiet" onClick={onRetry}>Retry analysis</button>
        </div>
      )}
      <div className="overview-intro">
        <div>
          <p className="eyebrow">Current workspace</p>
          <h2>{loading ? 'Analyzing evidence' : 'No analysis yet'}</h2>
          <p>{observationCount > 0
            ? `${observationCount} observations are ready. Analyze to see a current plan and evidence.`
            : 'Start with your profile or load fictional sample history. The dashboard never invents a recommendation.'}</p>
        </div>
        <button className="button-secondary" disabled={loading} onClick={onAnalyze}>
          Analyze profile
        </button>
      </div>
      <section className="overview-modules" aria-label="Engine capabilities">
        <article><span>01 / ESTIMATE</span><h3>Energy & safety</h3><p>REE, activity-adjusted TDEE and explicit calorie guardrails.</p></article>
        <article><span>02 / INTERPRET</span><h3>Adaptive evidence</h3><p>Calendar-aware weight and intake trends with stability signals.</p></article>
        <article><span>03 / PERSONALIZE</span><h3>Nutrition & training</h3><p>Preference-driven macros, demand context and practical food flexibility.</p></article>
        <article><span>04 / ADAPT</span><h3>Plan decisions</h3><p>Conservative proposals, review gates and anti-oscillation history.</p></article>
      </section>
      <p className="demo-disclaimer">
        Decision-support demo, not medical advice. Fictional sample data is
        clearly labeled and no result appears until the API evaluates it.
      </p>
    </div>
  )
}

function ActivePlanCard({ result }: { result: Result }) {
  const active = result.current_recommendation
  const target = active?.calorie_target_kcal_per_day ?? result.latest_plan.selected_calorie_target_kcal_per_day
  const macros = active?.macro_plan ?? result.latest_plan.macro_plan

  return (
    <section className="dashboard-active" aria-label="Current active plan">
      <div className="dashboard-card-top">
        <span className="dashboard-kicker">Current active plan</span>
        <StatusBadge tone="success">Active</StatusBadge>
      </div>
      <strong className="dashboard-calories">{whole(target, 'kcal/day')}</strong>
      <p className="dashboard-sub">
        {active?.effective_date ? `Effective ${active.effective_date}` : 'Profile-based starting plan'}
        {' · '}{active?.source?.replaceAll('_', ' ') ?? result.latest_plan.calorie_basis} source
      </p>
      <div className="dashboard-macros">
        <MetricCard label="Protein" value={whole(macros.protein_g_per_day, 'g/day')} />
        <MetricCard label="Carbohydrates" value={whole(macros.carbohydrate_g_per_day, 'g/day')} />
        <MetricCard label="Fat" value={whole(macros.fat_g_per_day, 'g/day')} />
      </div>
      <p className="dashboard-foot">
        {strategyLabels[macros.strategy]} macro strategy · The selected target
        is one feasible point in a flexible range.
      </p>
    </section>
  )
}

function ProposalCard({ result, onPlan }: { result: Result; onPlan: () => void }) {
  const activeTarget = result.current_recommendation?.calorie_target_kcal_per_day
    ?? result.latest_plan.selected_calorie_target_kcal_per_day
  const decision = result.recommendation_decision
  const adaptation = result.plan_adaptation
  const integration = result.integration_status
  const proposed = decision?.numerical_change_proposed
    && decision.proposed_calorie_target_kcal_per_day !== activeTarget
  const review = adaptation?.review_required
    || decision?.activation_readiness === 'review_required'
    || integration?.proposal_requires_review

  return (
    <section className={`dashboard-proposal ${proposed ? 'has-proposal' : ''}`} aria-label="Proposed plan status">
      <div className="dashboard-card-top">
        <span className="dashboard-kicker">Proposed plan</span>
        <StatusBadge tone={review ? 'warning' : proposed ? 'purple' : 'neutral'}>
          {review ? 'Review required' : proposed ? 'Not active' : 'No change'}
        </StatusBadge>
      </div>
      {proposed ? (
        <>
          <div className="proposal-flow">
            <span>{whole(activeTarget, 'kcal/day')}</span>
            <b aria-hidden="true">→</b>
            <strong>{whole(decision.proposed_calorie_target_kcal_per_day, 'kcal/day')}</strong>
          </div>
          <p className="proposal-delta">
            {whole(decision.calorie_delta_kcal_per_day, 'kcal/day')} proposed change
          </p>
          <p>{review
            ? 'FitAdapt sees evidence that may support a lower target, but short-term weight effects and intake bias cannot be fully separated. Review this proposal before any plan update.'
            : adaptation?.activation_ready
              ? 'Eligible for activation, but not active until the caller accepts it.'
              : 'A proposal is under evaluation. Your active plan has not changed.'}</p>
        </>
      ) : (
        <>
          <h2>{decision?.decision === 'defer' ? 'Adjustment deferred' : 'Keep the current plan'}</h2>
          <p>{integration?.summary ?? 'There is no numerical plan change ready to review.'}</p>
        </>
      )}
      {adaptation && (
        <p className="next-active-note">
          <strong>Next active plan:</strong> {whole(adaptation.next_active_target_kcal_per_day, 'kcal/day')}
          {' · '}{adaptation.activation_ready
            ? 'activation eligible, awaiting caller acceptance'
            : 'current target retained'}
        </p>
      )}
      <button className="button-quiet" onClick={onPlan}>Inspect plan details</button>
    </section>
  )
}

function InsightCards({ result, profile }: { result: Result; profile: Profile }) {
  const stability = result.adaptive_tdee.stability ?? 'insufficient'
  const decision = result.recommendation_decision
  const adaptation = result.plan_adaptation
  const review = adaptation?.review_required || decision?.activation_readiness === 'review_required'

  return (
    <div className="overview-insights">
      <section className="dashboard-insight">
        <p className="dashboard-kicker">Adaptive energy estimate</p>
        <h2>{whole(result.adaptive_tdee.adaptive_tdee_kcal_per_day, 'kcal/day')}</h2>
        <StatusBadge tone={stability === 'stable' ? 'success' : stability === 'insufficient' ? 'neutral' : 'warning'}>
          {stability === 'insufficient' ? 'Insufficient evidence' : stability}
        </StatusBadge>
        <p>{stabilityCopy[stability]}</p>
        <small>{result.adaptive_tdee.eligible_points_used} eligible estimates used · Observational, not measured expenditure</small>
      </section>
      <section className="dashboard-insight">
        <p className="dashboard-kicker">Goal progress</p>
        <h2>{goalCopy[profile.goal]}</h2>
        <p>{profile.requested_weekly_change_kg === 0
          ? 'Maintenance pace'
          : `${profile.requested_weekly_change_kg > 0 ? '+' : ''}${profile.requested_weekly_change_kg} kg/week requested`}</p>
        <StatusBadge tone={result.plan_outcome?.goal_progress === 'broadly_on_track' ? 'success' : 'neutral'}>
          {result.plan_outcome?.goal_progress?.replaceAll('_', ' ') ?? 'Awaiting outcome evidence'}
        </StatusBadge>
        <small>{result.lifecycle.calendar_history_days} calendar days of history</small>
      </section>
      <section className="dashboard-insight">
        <p className="dashboard-kicker">Decision & adaptation</p>
        <h2>{decision
          ? decision.decision.charAt(0).toUpperCase() + decision.decision.slice(1)
          : 'Not evaluated'}</h2>
        <p>{result.integration_status?.summary ?? 'No integration decision is available yet.'}</p>
        <StatusBadge tone={review ? 'warning' : adaptation?.activation_ready ? 'success' : 'neutral'}>
          {review ? 'Review required' : adaptation?.activation_ready
            ? 'Activation ready' : adaptation?.action?.replaceAll('_', ' ') ?? 'Current'}
        </StatusBadge>
      </section>
    </div>
  )
}

function IntelligenceModules({ result }: { result: Result }) {
  const training = result.training_assessment
  const feasibility = result.nutrition_feasibility
  return (
    <div className="overview-bottom-grid">
      <section className="dashboard-module">
        <p className="dashboard-kicker">Training intelligence</p>
        <h2>{training?.overall_demand?.replaceAll('_', ' ') ?? 'More evidence needed'}</h2>
        <p>Resistance {training?.resistance_demand?.replaceAll('_', ' ') ?? 'unknown'}
          {' · '}Aerobic / sport {training?.aerobic_sport_demand?.replaceAll('_', ' ') ?? 'unknown'}</p>
        <small>Protein priority: {training?.protein_priority?.replaceAll('_', ' ') ?? 'unavailable'}
          {' · '}Carbohydrate priority: {training?.carbohydrate_performance_priority?.replaceAll('_', ' ') ?? 'unavailable'}</small>
      </section>
      <section className="dashboard-module">
        <p className="dashboard-kicker">Nutrition feasibility</p>
        <h2>{feasibility?.overall_feasibility?.replaceAll('_', ' ') ?? 'More context needed'}</h2>
        <p>{feasibility?.guidance[0]?.message
          ?? 'Food preferences help assess how practical the current plan may be.'}</p>
        <small>Assessment only; it does not change the target.</small>
      </section>
    </div>
  )
}

function RecentHistory({ result, onProgress }: { result: Result; onProgress: () => void }) {
  const entries = result.recommendation_history?.entries.slice(-3).reverse() ?? []
  return (
    <section className="dashboard-history">
      <div className="dashboard-card-top">
        <div><p className="dashboard-kicker">Explainability</p><h2>Recommendation history</h2></div>
        <button className="button-quiet" onClick={onProgress}>View progress</button>
      </div>
      {entries.length ? (
        <ol>{entries.map((entry, index) => (
          <li key={`${entry.effective_date}-${entry.change_type}-${index}`}>
            <time dateTime={entry.effective_date}>{entry.effective_date}</time>
            <div>
              <strong>{entry.change_type.replaceAll('_', ' ')}</strong>
              <p>{entry.user_summary}</p>
              <small>{entry.source.replaceAll('_', ' ')} · {entry.is_plan_change
                ? 'Active plan changed' : 'Evaluation only; active plan unchanged'}</small>
            </div>
          </li>
        ))}</ol>
      ) : <p>No caller-supplied recommendation events yet. Evaluations do not imply an active plan change.</p>}
    </section>
  )
}

export function Overview(props: OverviewProps) {
  const { result, profile, onPlan, onProgress } = props
  if (!result) return <EmptyOverview {...props} />

  const integration = result.integration_status
  const status = integration
    ? statusPresentation[integration.app_status]
    : { label: 'Current plan', tone: 'neutral' as const }
  const safety = result.target_safety

  return (
    <div className="overview-page">
      <header className="overview-heading">
        <div>
          <p className="eyebrow">FitAdapt / Live analysis</p>
          <h1>Your plan, in context.</h1>
          <p>One active recommendation. Proposed changes stay separate until accepted by the caller.</p>
        </div>
        <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
      </header>
      <div className="overview-top-grid">
        <ActivePlanCard result={result} />
        <ProposalCard result={result} onPlan={onPlan} />
      </div>
      {safety && safety.status !== 'eligible' && (
        <aside className={`dashboard-safety ${safety.status}`} role="status">
          <StatusBadge tone={safety.status === 'ineligible' ? 'danger' : 'warning'}>
            {safety.status === 'ineligible' ? 'Safety ineligible' : 'Safety constrained'}
          </StatusBadge>
          <span>{safety.status === 'ineligible'
            ? 'An automated weight-loss target is not available under the current safety policy.'
            : 'The effective target was limited by the safety policy.'}
            {' '}Review the safety details in Progress.</span>
        </aside>
      )}
      <InsightCards result={result} profile={profile} />
      <IntelligenceModules result={result} />
      <RecentHistory result={result} onProgress={onProgress} />
      <p className="demo-disclaimer">
        This is deterministic decision support, not a diagnosis or measured
        metabolism. Use Plan and Progress for complete assumptions, provenance and evidence.
      </p>
    </div>
  )
}
