import { useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { client, type Observation, type Profile } from './api'
import { paddedDomain } from './chart-domain'
import './index.css'

const sample = Array.from({ length: 28 }, (_, index): Observation => ({ observed_on: `2026-01-${String(index + 1).padStart(2, '0')}`, body_weight_kg: 80 - index * 0.03, energy_intake_kcal: 2400, steps: 5000 }))
const emptyObservation: Observation = { observed_on: '', body_weight_kg: null, energy_intake_kcal: null, steps: null }
const optionalFields = [['protein_g', 'Protein (g)'], ['carbohydrate_g', 'Carbohydrates (g)'], ['fat_g', 'Fat (g)'], ['strength_training_minutes', 'Strength training (min)'], ['cardio_minutes', 'Cardio (min)'], ['sleep_hours', 'Sleep (hours)'], ['hunger_rating', 'Hunger rating'], ['energy_rating', 'Energy rating']] as const
const reasonText: Record<string, string> = {
  insufficient_history: 'Add more calendar days of history before using a recommendation.',
  insufficient_weight_completeness: 'Log weight more consistently so the trend is reliable.',
  insufficient_intake_completeness: 'Log calorie intake more consistently to compare it with your trend.',
  missing_recent_intake: 'Add recent calorie entries before adjusting your intake target.',
  missing_weight_trend: 'Add enough weight entries to establish a calendar-based trend.',
  adaptive_tdee_unavailable: 'More consistent weight and calorie history is needed to estimate your personal TDEE.',
  insufficient_adaptive_estimates: 'More eligible days are needed before your adaptive estimate is stable enough.',
  non_positive_proposed_target: 'The proposed intake target is not actionable.',
  macro_policy_infeasible_proposed_target: 'The proposed intake target cannot support the current macro policy.',
  within_hold_threshold: 'Your recent intake is already close to the personalized target.',
  limited_by_maximum_adjustment: 'The suggested change is capped for a gradual adjustment.',
  adjustment_recommended: 'Your recent intake differs meaningfully from the personalized target.',
}
const statusText: Record<string, string> = { insufficient_data: 'Recommendation unavailable', hold: 'Hold current intake', increase_calories: 'Increase daily intake', decrease_calories: 'Decrease daily intake' }
const whole = (value: number | null | undefined, unit: string) => value == null ? 'Unavailable' : `${Math.round(value).toLocaleString()} ${unit}`
const weight = (value: number) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)
const percent = (value: number) => `${Math.round(value * 100)}%`
const numericInput = (value: number) => Number.isFinite(value) ? String(value) : ''

function Chart({ title, data, raw, trend, unit, format = value => Math.round(value).toLocaleString() }: { title: string; data: Record<string, unknown>[]; raw: string; trend: string; unit: string; format?: (value: number) => string }) {
  if (!data.some(point => point[raw] != null)) return <article className="empty-card"><h3>{title}</h3><p>No recorded {unit} values yet. Add entries to see this chart.</p></article>
  return <article className="chart-card"><h3>{title}</h3><p className="chart-key">Coral: recorded value · green: trailing mean</p><ResponsiveContainer width="100%" height={220}><LineChart data={data}><XAxis dataKey="observed_on" hide /><YAxis domain={paddedDomain(data, raw, trend)} tickFormatter={value => format(Number(value))} unit={` ${unit}`} width={56} /><Tooltip formatter={value => `${format(Number(value))} ${unit}`} /><Line type="linear" connectNulls={false} dataKey={raw} stroke="#d5633d" dot={false} name={`Recorded (${unit})`} /><Line type="linear" connectNulls={false} dataKey={trend} stroke="#17343b" dot={false} name={`Trailing mean (${unit})`} /></LineChart></ResponsiveContainer></article>
}

function ObservationValue({ value, unit, preserveDecimals = false }: { value: number | null | undefined; unit: string; preserveDecimals?: boolean }) { return <>{value == null ? '—' : `${preserveDecimals ? weight(value) : Math.round(value).toLocaleString()} ${unit}`}</> }

export default function App() {
  const [profile, setProfile] = useState<Profile>({ age_years: 30, height_cm: 180, weight_kg: 80, sex_for_mifflin_equation: 'male', activity_level: 'moderately_active', goal: 'maintain', requested_weekly_change_kg: 0 })
  const [observations, setObservations] = useState<Observation[]>([])
  const [draft, setDraft] = useState<Observation>(emptyObservation)
  const [editing, setEditing] = useState<string | null>(null)
  const [showOptional, setShowOptional] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [importText, setImportText] = useState('')
  const [results, setResults] = useState<any>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const stale = () => setResults(undefined)
  const displayed = [...observations].reverse()
  const shown = showAll ? displayed : displayed.slice(0, 8)
  const setField = (key: keyof Observation, value: string) => setDraft({ ...draft, [key]: value === '' ? null : key === 'observed_on' ? value : Number(value) })
  const updateProfile = (key: keyof Profile, value: string) => { const choice = ['sex_for_mifflin_equation', 'activity_level', 'goal'].includes(key); setProfile({ ...profile, [key]: choice ? value : Number(value) } as Profile); stale() }
  const save = () => {
    if (!draft.observed_on) { setError('An observation date is required.'); return }
    if (!editing && observations.some(observation => observation.observed_on === draft.observed_on)) { setError('Duplicate observation dates are not allowed.'); return }
    setObservations(current => [...current.filter(observation => observation.observed_on !== editing), draft].sort((a, b) => a.observed_on.localeCompare(b.observed_on)))
    setDraft(emptyObservation); setEditing(null); setError(''); stale()
  }
  const importObservations = () => {
    try {
      const parsed: unknown = JSON.parse(importText)
      if (!Array.isArray(parsed) || parsed.some(value => !value || typeof value !== 'object' || !('observed_on' in value))) throw new Error()
      const imported = parsed as Observation[]
      if (new Set(imported.map(observation => observation.observed_on)).size !== imported.length) throw new Error()
      setObservations([...imported].sort((a, b) => a.observed_on.localeCompare(b.observed_on))); setImportText(''); setShowImport(false); setError(''); stale()
    } catch { setError('Observation JSON could not be parsed. Use an array with one unique date per record.') }
  }
  const clear = () => { setObservations([]); setDraft(emptyObservation); setEditing(null); setShowAll(false); stale() }
  const calculate = async () => { setLoading(true); setError(''); try { const [baseline, trends, adaptive, recommendation] = await Promise.all([client.baseline(profile), client.trends(observations), client.adaptive(observations), client.recommendation(profile, observations)]); setResults({ baseline, trends, adaptive, recommendation }) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Cannot reach the FitAdapt API.') } finally { setLoading(false) } }
  const points = results?.trends?.points ?? []
  const recommendation = results?.recommendation
  const adaptive = results?.adaptive
  const reason = recommendation?.reasons?.[0]
  const edit = (observation: Observation) => { setDraft(observation); setEditing(observation.observed_on) }
  const remove = (date: string) => { setObservations(current => current.filter(value => value.observed_on !== date)); stale() }

  return <main>
    <header className="hero"><p className="eyebrow">FITADAPT / DECISION SUPPORT</p><h1>Build a clear picture.</h1><p>Use your profile and daily history to review transparent estimates. Nothing is stored in this browser.</p></header>
    <section><div className="section-heading"><div><p className="eyebrow">01 / PROFILE</p><h2>Starting point</h2></div><p className="section-note">Baseline estimates use your profile. Personalized estimates need history.</p></div>
      <div className="profile-grid">
        <label>Age<input aria-label="Age" type="number" value={numericInput(profile.age_years)} onChange={event => updateProfile('age_years', event.target.value)} /></label><label>Height (cm)<input aria-label="Height (cm)" type="number" value={numericInput(profile.height_cm)} onChange={event => updateProfile('height_cm', event.target.value)} /></label><label>Weight (kg)<input aria-label="Weight (kg)" type="number" value={numericInput(profile.weight_kg)} onChange={event => updateProfile('weight_kg', event.target.value)} /></label>
        <label>Sex used for REE estimate<select aria-label="Sex used for REE estimate" value={profile.sex_for_mifflin_equation} onChange={event => updateProfile('sex_for_mifflin_equation', event.target.value)}><option value="male">Male equation</option><option value="female">Female equation</option></select><small>Required by the Mifflin equation.</small></label>
        <label>Activity level<select aria-label="Activity level" value={profile.activity_level} onChange={event => updateProfile('activity_level', event.target.value)}><option value="sedentary">Mostly sedentary</option><option value="lightly_active">Lightly active</option><option value="moderately_active">Moderately active</option><option value="very_active">Very active</option><option value="extra_active">Extra active</option></select><small>A population-level starting assumption.</small></label>
        <label>Goal<select aria-label="Goal" value={profile.goal} onChange={event => { const goal = event.target.value; setProfile({ ...profile, goal, requested_weekly_change_kg: goal === 'cut' ? -0.4 : goal === 'gain' ? 0.2 : 0 } as Profile); stale() }}><option value="cut">Cut</option><option value="maintain">Maintain</option><option value="gain">Gain</option></select></label><label>Desired weekly change (kg)<input aria-label="Desired weekly change (kg)" type="number" step="0.01" value={numericInput(profile.requested_weekly_change_kg)} onChange={event => updateProfile('requested_weekly_change_kg', event.target.value)} /><small>Negative for a cut, zero to maintain, positive to gain.</small></label>
      </div>
    </section>
    <section><div className="section-heading"><div><p className="eyebrow">02 / DAILY HISTORY</p><h2>Daily observations <span className="count">{observations.length}</span></h2></div><p className="section-note">Adaptive estimates need sufficient, consistent weight and calorie history.</p></div>
      <div className="history-actions"><button onClick={() => { setObservations(sample); setShowAll(false); stale() }}>Load sample history</button><button className="secondary" onClick={clear}>Clear data</button><button className="text-button" aria-expanded={showImport} onClick={() => setShowImport(!showImport)}>Import JSON</button></div>{observations.length > 0 && <p className="notice">Fictional sample data — not personal or clinical data.</p>}
      {showImport && <div className="disclosure"><label htmlFor="json-import">Observation JSON</label><textarea id="json-import" aria-label="Import observations JSON" value={importText} onChange={event => setImportText(event.target.value)} placeholder="Paste an array of observations" /><button onClick={importObservations}>Import observations</button></div>}
      <div className="observation-form"><div className="form-grid"><label>Date<input aria-label="Date" type="date" value={draft.observed_on} onChange={event => setField('observed_on', event.target.value)} /></label><label>Weight (kg)<input aria-label="Today's weight (kg)" type="number" value={draft.body_weight_kg ?? ''} onChange={event => setField('body_weight_kg', event.target.value)} /></label><label>Calories (kcal)<input aria-label="Calories (kcal)" type="number" value={draft.energy_intake_kcal ?? ''} onChange={event => setField('energy_intake_kcal', event.target.value)} /></label><label>Steps<input aria-label="Steps" type="number" value={draft.steps ?? ''} onChange={event => setField('steps', event.target.value)} /></label></div><button className="text-button" aria-expanded={showOptional} onClick={() => setShowOptional(!showOptional)}>{showOptional ? 'Hide optional fields' : 'Add optional details'}</button>{showOptional && <div className="form-grid optional-grid">{optionalFields.map(([key, label]) => <label key={key}>{label}<input aria-label={label} type="number" value={draft[key] ?? ''} onChange={event => setField(key, event.target.value)} /></label>)}</div>}<button onClick={save}>{editing ? 'Save observation' : 'Add observation'}</button></div>
      {observations.length > 0 && <><div className="history-table-wrap"><table><caption className="sr-only">Observation history, newest first</caption><thead><tr><th>Date</th><th>Weight</th><th>Calories</th><th>Steps</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{shown.map(observation => <tr key={observation.observed_on}><td>{observation.observed_on}</td><td><ObservationValue value={observation.body_weight_kg} unit="kg" preserveDecimals /></td><td><ObservationValue value={observation.energy_intake_kcal} unit="kcal" /></td><td><ObservationValue value={observation.steps} unit="steps" /></td><td className="row-actions"><button className="icon-button" aria-label={`Edit ${observation.observed_on}`} onClick={() => edit(observation)}>Edit</button><button className="icon-button danger" aria-label={`Delete ${observation.observed_on}`} onClick={() => remove(observation.observed_on)}>Delete</button></td></tr>)}</tbody></table></div><div className="mobile-history">{shown.map(observation => <article key={observation.observed_on}><strong>{observation.observed_on}</strong><p>Weight <ObservationValue value={observation.body_weight_kg} unit="kg" preserveDecimals /> · Calories <ObservationValue value={observation.energy_intake_kcal} unit="kcal" /> · Steps <ObservationValue value={observation.steps} unit="steps" /></p><div className="row-actions"><button className="icon-button" aria-label={`Edit ${observation.observed_on}`} onClick={() => edit(observation)}>Edit</button><button className="icon-button danger" aria-label={`Delete ${observation.observed_on}`} onClick={() => remove(observation.observed_on)}>Delete</button></div></article>)}</div>{displayed.length > 8 && <button className="text-button" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show less' : `Show all ${observations.length} observations`}</button>}</>}
    </section>
    <section><div className="section-heading"><div><p className="eyebrow">03 / ANALYSIS</p><h2>Results</h2></div><p className="section-note">Baseline uses your profile. Adaptive results use your logged history.</p></div><button disabled={loading} onClick={calculate}>{loading ? 'Analyzing…' : 'Analyze my data'}</button>{error && <p role="alert" className="error">{error} <button onClick={calculate}>Retry</button></p>}
      {!results && <article className="empty-card"><h3>Ready when you are</h3><p>Analyze your profile for a baseline. Add consistent history to unlock adaptive and recommendation results.</p></article>}
      {results && <div className="result-stack"><div><h3 className="result-label">Baseline estimates</h3><div className="metric-grid">{[['REE', whole(results.baseline.baseline_energy.estimated_ree_kcal_per_day, 'kcal/day')], ['Baseline TDEE', whole(results.baseline.baseline_energy.estimated_tdee_kcal_per_day, 'kcal/day')], ['Baseline calorie target', whole(results.baseline.target_calories_kcal_per_day, 'kcal/day')], ['Protein', whole(results.baseline.protein_g_per_day, 'g/day')], ['Fat', whole(results.baseline.fat_g_per_day, 'g/day')], ['Carbohydrates', whole(results.baseline.carbohydrate_g_per_day, 'g/day')]].map(([label, value]) => <article key={String(label)} className="metric"><span>{label}</span><strong>{value}</strong></article>)}</div><p className="macro-note">Protein, fat, and carbohydrates use the V0.1 baseline macro policy and the baseline calorie target. They are not personalized macro recommendations.</p></div><article className="quality-card"><h3>History quality</h3><p>{results.trends.data_quality.total_calendar_days} calendar days recorded</p><div><span>Weight <strong>{percent(results.trends.data_quality.body_weight_completeness_ratio)}</strong></span><span>Calories <strong>{percent(results.trends.data_quality.energy_intake_completeness_ratio)}</strong></span><span>Steps <strong>{percent(results.trends.data_quality.step_completeness_ratio)}</strong></span></div></article><div className="chart-grid"><Chart title="Weight trend" data={points} raw="body_weight_kg" trend="trailing_body_weight_mean_kg" unit="kg" format={weight} /><Chart title="Calorie intake trend" data={points} raw="energy_intake_kcal" trend="trailing_energy_intake_mean_kcal" unit="kcal" /><Chart title="Step trend" data={points} raw="steps" trend="trailing_steps_mean" unit="steps" /></div><div className="personal-grid"><article><p className="eyebrow">PERSONALIZED / ADAPTIVE</p><h3>Adaptive TDEE</h3>{adaptive.adaptive_tdee_kcal_per_day == null ? <p>Not available yet. Keep logging consistent weight and calorie entries to build eligible estimates.</p> : <><strong className="big-metric">{whole(adaptive.adaptive_tdee_kcal_per_day, 'kcal/day')}</strong><p>{adaptive.eligible_daily_estimate_count} eligible estimates · median absolute deviation: {whole(adaptive.median_absolute_deviation_kcal_per_day, 'kcal/day')} (a measure of variability, not confidence)</p><p>Baseline comparison: {whole(results.baseline.baseline_energy.estimated_tdee_kcal_per_day, 'kcal/day')}</p></>}</article><article className="recommendation"><p className="eyebrow">PERSONALIZED / RECOMMENDATION</p><h3>{statusText[recommendation.status] ?? 'Recommendation'}</h3><p className="primary-reason">{reasonText[reason] ?? 'Review your data before changing your intake.'}</p>{recommendation.status === 'insufficient_data' ? <p>Add the data noted above, then analyze again. No calorie change is suggested yet.</p> : <dl><div><dt>Recent intake</dt><dd>{whole(recommendation.recent_mean_intake_kcal_per_day, 'kcal/day')}</dd></div><div><dt>Personalized target</dt><dd>{whole(recommendation.personalized_goal_target_kcal_per_day, 'kcal/day')}</dd></div><div><dt>Suggested change</dt><dd>{whole(recommendation.recommended_adjustment_kcal_per_day, 'kcal/day')}</dd></div><div><dt>Proposed intake</dt><dd>{whole(recommendation.proposed_intake_target_kcal_per_day, 'kcal/day')}</dd></div></dl>}<details><summary>Recommendation details</summary><ul>{recommendation.reasons.map((value: string) => <li key={value}>{reasonText[value] ?? 'Additional review is needed.'}</li>)}</ul>{recommendation.raw_adjustment_kcal_per_day != null && <p>Uncapped calculation: {whole(recommendation.raw_adjustment_kcal_per_day, 'kcal/day')}</p>}</details><small>Decision support only. Recommendations are never automatically applied.</small></article></div></div>}
    </section>
  </main>
}
