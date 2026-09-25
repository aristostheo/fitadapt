import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, getProfileIntelligence } from './api'
import { createFictionalSample } from './sample-history'
import type { MacroCalorieSource, NutritionTargetEnvelope, PersonalizedMacroPlan, PersonalizedPlanSnapshot, ProfileIntelligenceResponse } from './types'

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } })

function macroPlan(source: MacroCalorieSource): PersonalizedMacroPlan {
  return { calorie_target_kcal_per_day: 2450, calorie_source: source, strategy: 'higher_protein', body_weight_kg: 80, protein_g_per_kg: 2, fat_percentage: .25, protein_g_per_day: 160, fat_g_per_day: 68, carbohydrate_g_per_day: 298, protein_kcal_per_day: 640, fat_kcal_per_day: 613, carbohydrate_kcal_per_day: 1192, macro_policy_version: 'preference_macros_v1', assumptions: [] }
}

function targetEnvelope(source: MacroCalorieSource): NutritionTargetEnvelope {
  return {
    selected_calorie_target_kcal_per_day: 2450,
    calorie_adherence_range: { lower_bound: 2350.4, selected_value: 2450, upper_bound: 2549.6, unit: 'kcal/day', interpretation: 'Daily adherence range', range_kind: 'adherence' },
    protein_preferred_range: { lower_bound: 144.2, selected_value: 160, upper_bound: 175.8, unit: 'g/day', interpretation: 'Preferred protein range', range_kind: 'preferred' },
    fat_preferred_range: { lower_bound: 54.4, selected_value: 68, upper_bound: 81.6, unit: 'g/day', interpretation: 'Preferred fat range', range_kind: 'preferred' },
    carbohydrate_flexible_range: { lower_bound: 239.6, selected_value: 298, upper_bound: 356.4, unit: 'g/day', interpretation: 'Flexible carbohydrate range', range_kind: 'flexible_remainder' },
    macro_plan: macroPlan(source),
    macro_strategy: 'higher_protein',
    calorie_source: source,
    policy_floors: ['protein_floor', 'fat_floor'],
    range_policy_version: 'nutrition_target_ranges_v1',
    macro_policy_version: 'preference_macros_v1',
    assumptions: ['Ranges are flexible policy bounds.'],
  }
}

function response(stage: 'baseline' | 'calibrating' | 'early_personalized' | 'personalized' = 'personalized', progression = false): ProfileIntelligenceResponse {
  const source: MacroCalorieSource = stage === 'personalized' ? 'personalized' : 'baseline'
  const plan: PersonalizedPlanSnapshot = { as_of_date: '2026-01-14', lifecycle_stage: stage, lifecycle_requirements: [], calorie_basis: source, baseline_calorie_target_kcal_per_day: 2300, selected_calorie_target_kcal_per_day: 2450, previous_selected_calorie_target_kcal_per_day: 2400, change_from_previous_snapshot_kcal_per_day: 50, adaptive_tdee_kcal_per_day: 2450, adaptive_median_absolute_deviation_kcal_per_day: 6, eligible_adaptive_estimate_count: 8, recommendation_status: 'increase_calories', recommendation_reasons: ['adjustment_recommended'], raw_recommendation_adjustment_kcal_per_day: 160, limited_recommendation_adjustment_kcal_per_day: 150, macro_plan: macroPlan(source), planning_policy_version: 'personalized_planning_v1', baseline_energy_formula_version: 'mifflin', baseline_activity_policy_version: 'activity', baseline_energy_equivalent_policy_version: 'energy', baseline_macro_policy_version: 'baseline', lifecycle_policy_version: 'lifecycle', trend_policy_version: 'trends', adaptive_policy_version: 'adaptive', recommendation_policy_version: 'recommendation', personalized_macro_policy_version: 'preference_macros_v1', assumptions: [], target_envelope: targetEnvelope(source) }
  return { policy_version: 'profile_intelligence_v1', baseline: { baseline_energy: { estimated_ree_kcal_per_day: 1700, activity_level: 'moderately_active', activity_multiplier: 1.55, estimated_tdee_kcal_per_day: 2400, ree_formula_version: 'mifflin', activity_policy_version: 'activity' }, goal: 'maintain', requested_weekly_change_kg: 0, daily_calorie_adjustment_kcal: 0, target_calories_kcal_per_day: 2400, protein_g_per_day: 128, fat_g_per_day: 48, carbohydrate_g_per_day: 300, energy_equivalent_policy_version: 'energy', macro_policy_version: 'baseline', assumptions: [] }, trends: { policy_version: 'trends', config: { window_size_days: 7, minimum_observations: 4 }, points: [{ observed_on: '2026-01-14', observation_present: true, body_weight_kg: 79.94, energy_intake_kcal: 2400, steps: null, trailing_body_weight_mean_kg: 79.97, trailing_energy_intake_mean_kcal: 2400, trailing_steps_mean: null, body_weight_contributor_count: 7, energy_intake_contributor_count: 7, steps_contributor_count: 0, window_weight_change_kg: -.2 }], data_quality: { first_date: '2026-01-01', last_date: '2026-01-14', total_calendar_days: 14, submitted_observation_records: 14, missing_calendar_days: 0, present_body_weight_values: 14, missing_body_weight_values: 0, body_weight_completeness_ratio: 1, present_energy_intake_values: 14, missing_energy_intake_values: 0, energy_intake_completeness_ratio: 1, present_step_values: 0, missing_step_values: 14, step_completeness_ratio: 0 }, assumptions: [] }, adaptive_tdee: { policy_version: 'adaptive', config: { energy_equivalent_kcal_per_kg: 7700, aggregation_window_days: 14, minimum_estimate_points: 4 }, daily_estimates: [], adaptive_tdee_kcal_per_day: 2450, median_absolute_deviation_kcal_per_day: 6, eligible_points_used: 4, total_eligible_points: 8, aggregation_start_date: '2026-01-01', aggregation_end_date: '2026-01-14', assumptions: [] }, lifecycle: { stage, requirements: stage === 'baseline' ? ['add_history', 'log_body_weight', 'log_energy_intake'] : [], calendar_history_days: 14, weight_observation_count: 14, intake_observation_count: 14, weight_completeness: 1, intake_completeness: 1, eligible_adaptive_estimate_count: 8, required_eligible_estimate_count: 4, adaptive_tdee_kcal_per_day: 2450, median_absolute_deviation_kcal_per_day: 6, lifecycle_policy_version: 'lifecycle', trend_policy_version: 'trends', adaptive_policy_version: 'adaptive', assumptions: [] }, recommendation: { status: 'increase_calories', reasons: ['adjustment_recommended'], goal: 'maintain', requested_weekly_change_kg: 0, observed_window_weight_change_kg: -.2, baseline_estimated_tdee_kcal_per_day: 2400, baseline_calorie_target_kcal_per_day: 2400, adaptive_tdee_kcal_per_day: 2450, recent_mean_intake_kcal_per_day: 2300, personalized_goal_target_kcal_per_day: 2450, raw_adjustment_kcal_per_day: 150, recommended_adjustment_kcal_per_day: 150, proposed_intake_target_kcal_per_day: 2450, calendar_history_days: 14, weight_completeness: 1, intake_completeness: 1, adaptive_estimate_count: 4, recommendation_policy_version: 'recommendation', trend_policy_version: 'trends', adaptive_policy_version: 'adaptive', energy_equivalent_policy_version: 'energy', assumptions: [] }, latest_plan: plan, plan_progression: progression ? { snapshots: [plan], submitted_observation_count: 1, planning_policy_version: 'planning', assumptions: [] } : null, assumptions: [] }
}

function mockApi(value = response()) { const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => value }); vi.stubGlobal('fetch', fetchMock); return fetchMock }

describe('unified profile intelligence workflow', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('makes one unified request with defaults and no legacy analysis routes', async () => {
    const fetchMock = mockApi(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(fetchMock).toHaveBeenCalledTimes(1); const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]; expect(url).toContain('/v1/profile-intelligence'); expect(JSON.parse(String(options.body))).toMatchObject({ nutrition_preferences: { macro_strategy: 'balanced' }, include_plan_progression: false }); expect(url).not.toContain('/v1/baseline')
  })

  it('shows custom inputs only for custom strategy and removes stale custom values when switching', async () => {
    const fetchMock = mockApi(); render(<App />); expect(screen.queryByLabelText('Protein grams per kilogram')).not.toBeInTheDocument(); fill('Macro strategy', 'custom'); expect(screen.getByLabelText('Protein grams per kilogram')).toBeInTheDocument(); fill('Protein grams per kilogram', '2.2'); fill('Fat percentage of calories', '30'); fill('Macro strategy', 'balanced'); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await waitFor(() => expect(fetchMock).toHaveBeenCalled()); expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)).nutrition_preferences).toEqual({ macro_strategy: 'balanced' })
  })

  it('validates custom bounds through the API and clears stale results after input changes', async () => {
    mockApi(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN'); fill('Age', '024'); expect(screen.getByLabelText('Age')).toHaveValue(24); expect(screen.queryByText('CURRENT PROPOSED PLAN')).not.toBeInTheDocument(); fill('Macro strategy', 'custom'); expect(screen.getByText('Approved range: 1.2–2.4 g/kg.')).toBeInTheDocument()
  })

  it.each(['baseline', 'calibrating', 'early_personalized', 'personalized'] as const)('renders %s lifecycle evidence and readable requirements', async stage => {
    mockApi(response(stage)); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findAllByText(stage.replace('_', ' ')); expect(screen.getByText('History')).toBeInTheDocument(); if (stage === 'baseline') { expect(screen.getByText('Add your first weight and calorie entries.')).toBeInTheDocument(); expect(screen.queryByText('add_history')).not.toBeInTheDocument() }
  })

  it('renders the personalized selected point, rounded policy ranges, and flexibility guidance', async () => {
    mockApi(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(screen.getByText('2,350–2,550 kcal/day')).toBeInTheDocument(); expect(screen.getByText('Preferred range: 144–176 g/day')).toBeInTheDocument(); expect(screen.getByText('Preferred range: 54–82 g/day')).toBeInTheDocument(); expect(screen.getByText('Flexible range: 240–356 g/day')).toBeInTheDocument()
    expect(screen.getByText('160 g/day')).toBeInTheDocument(); expect(screen.getByText('68 g/day')).toBeInTheDocument(); expect(screen.getByText('298 g/day')).toBeInTheDocument(); expect(screen.getByText('personalized calorie source')).toBeInTheDocument()
    expect(screen.getByText(/one feasible point within flexible policy ranges/)).toBeInTheDocument(); expect(screen.getByText(/do not need to hit exact grams perfectly/)).toBeInTheDocument(); expect(screen.getByText(/arbitrary combinations of every endpoint may not reconcile exactly/)).toBeInTheDocument()
    expect(screen.getByText(/MAD describes observed variability, not statistical confidence/)).toBeInTheDocument(); expect(screen.getByText('No recorded steps values yet. Add entries to see this chart.')).toBeInTheDocument()
  })

  it('uses clear calculated-goal and capped next-step labels with humanized macro strategies', async () => {
    mockApi(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(screen.getByText('Next-step intake target')).toBeInTheDocument(); expect(screen.getByText('Calculated goal intake')).toBeInTheDocument(); expect(screen.getByText(/caps the next step to move gradually/)).toBeInTheDocument(); expect(screen.getAllByText('Higher protein')).not.toHaveLength(0)
    expect(screen.getByRole('option', { name: 'Balanced' })).toBeInTheDocument(); expect(screen.getByRole('option', { name: 'Higher carbohydrate' })).toBeInTheDocument(); expect(screen.getByRole('option', { name: 'Higher fat' })).toBeInTheDocument(); expect(screen.getByRole('option', { name: 'Custom' })).toBeInTheDocument()
  })

  it('sends progression opt-in and renders returned plan history without another request', async () => {
    const fetchMock = mockApi(response('personalized', true)); render(<App />); fireEvent.click(screen.getByLabelText('Include plan history')); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN'); expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)).include_plan_progression).toBe(true); fireEvent.click(screen.getByRole('button', { name: 'Show plan history' })); expect(screen.getByText('Each point uses only observations available up to that date.')).toBeInTheDocument(); expect(screen.getByRole('columnheader', { name: 'Target / range' })).toBeInTheDocument(); expect(screen.getAllByText('2,350–2,550 kcal/day')).toHaveLength(2); expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('preserves manual add, edit, delete, zero, and optional observation behavior', () => {
    render(<App />); fill('Date', '2026-01-02'); fill('Calories (kcal)', '0'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' })); expect(screen.getByText('0 kcal')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Add optional details' })); expect(screen.getByLabelText('Protein (g)')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Edit 2026-01-02' })); fill('Calories (kcal)', '2200'); fireEvent.click(screen.getByRole('button', { name: 'Save observation' })); expect(screen.getByText('2,200 kcal')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Delete 2026-01-02' })); expect(screen.queryByText('2,200 kcal')).not.toBeInTheDocument()
  })

  it('loads and clears a fictional sample matched to the active profile weight', () => {
    render(<App />); fireEvent.change(screen.getAllByRole('spinbutton')[2], { target: { value: '91' } }); fireEvent.click(screen.getByRole('button', { name: 'Load sample history' })); expect(screen.getByRole('heading', { name: /Daily observations 28/ })).toBeInTheDocument(); expect(screen.getByText('90.64 kg')).toBeInTheDocument(); expect(screen.getByText(/Fictional sample data/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Clear data' })); expect(screen.getByRole('heading', { name: /Daily observations 0/ })).toBeInTheDocument()
  })

  it('creates deterministic, complete fictional variation around the supplied profile weight', () => {
    const profile = { age_years: 30, height_cm: 180, weight_kg: 91, sex_for_mifflin_equation: 'male', activity_level: 'moderately_active', goal: 'maintain', requested_weekly_change_kg: 0 } as const
    const first = createFictionalSample(profile); const second = createFictionalSample(profile)
    expect(first).toEqual(second); expect(first).toHaveLength(28); expect(first.every(item => item.body_weight_kg != null && item.energy_intake_kcal != null && item.steps != null)).toBe(true)
    expect(Math.max(...first.map(item => Math.abs((item.body_weight_kg ?? 0) - profile.weight_kg)))).toBeLessThan(1)
    expect(new Set(first.map(item => item.body_weight_kg)).size).toBeGreaterThan(10); expect(new Set(first.map(item => item.energy_intake_kcal)).size).toBeGreaterThan(10); expect(new Set(first.map(item => item.steps)).size).toBeGreaterThan(10)
  })

  it('previews imports before mutation, rejects conflicts, and supports keep-existing merge', () => {
    render(<App />); fill('Date', '2026-01-01'); fill('Steps', '10'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' })); fireEvent.click(screen.getByRole('button', { name: 'Import history' })); fill('Import observations', '[{"observed_on":"2026-01-01","steps":20},{"observed_on":"2026-01-02","steps":0}]'); fireEvent.click(screen.getByRole('button', { name: 'Preview import' })); expect(screen.getByText(/conflicts: 1/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Confirm import' })); expect(screen.getByRole('alert')).toHaveTextContent('Resolve date conflicts'); fill('Conflict policy', 'keep_existing'); fireEvent.click(screen.getByRole('button', { name: 'Confirm import' })); expect(screen.getByRole('heading', { name: /Daily observations 2/ })).toBeInTheDocument(); expect(screen.getByText(/Imported 1 rows; skipped 1; replaced 0; invalid 0/)).toBeInTheDocument()
  })

  it('cancels an import preview without changing current observations', () => {
    render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Import history' })); fill('Import observations', '[{"observed_on":"2026-01-01","steps":10}]'); fireEvent.click(screen.getByRole('button', { name: 'Preview import' })); fireEvent.click(screen.getByRole('button', { name: 'Cancel preview' })); expect(screen.getByRole('heading', { name: /Daily observations 0/ })).toBeInTheDocument()
  })

  it('blocks invalid custom preferences before sending and prevents duplicate analysis while loading', async () => {
    let resolveResponse: ((value: unknown) => void) | undefined
    const pending = new Promise(resolve => { resolveResponse = resolve })
    const fetchMock = vi.fn().mockReturnValue(pending)
    vi.stubGlobal('fetch', fetchMock); render(<App />); fill('Macro strategy', 'custom'); fill('Protein grams per kilogram', '3'); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); expect(screen.getByRole('alert')).toHaveTextContent('Custom protein'); expect(fetchMock).not.toHaveBeenCalled(); fill('Protein grams per kilogram', '2'); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeDisabled(); fireEvent.click(screen.getByRole('button', { name: 'Analyzing…' })); expect(fetchMock).toHaveBeenCalledTimes(1); resolveResponse?.({ ok: true, status: 200, json: async () => response() }); await screen.findByText('CURRENT PROPOSED PLAN')
  })

  it('preserves structured domain, validation, server, network, and unexpected errors', async () => {
    const cases: [number, string][] = [[400, 'domain'], [422, 'validation'], [500, 'server'], [503, 'unexpected']]
    for (const [status, kind] of cases) { vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ error: { message: 'invalid', code: 'BAD' } }) })); await expect(getProfileIntelligence({} as ProfileIntelligenceResponse as never)).rejects.toMatchObject({ kind }); vi.unstubAllGlobals() }
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline'))); await expect(getProfileIntelligence({} as never)).rejects.toBeInstanceOf(ApiError)
  })

  it.each(['balanced', 'higher_carb', 'higher_fat', 'higher_protein', 'custom'] as const)('serializes the %s macro strategy in the unified request', async strategy => {
    const fetchMock = mockApi(); render(<App />); fill('Macro strategy', strategy)
    fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    const body = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body))
    expect(body.nutrition_preferences.macro_strategy).toBe(strategy)
    if (strategy === 'custom') expect(body.nutrition_preferences).toMatchObject({ custom_protein_g_per_kg: 1.8, custom_fat_percentage: .25 })
  })

  it('clears stale results for observation and progression input changes without clearing for table controls', async () => {
    mockApi(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    fill('Date', '2026-01-01'); fill('Steps', '10'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' }))
    expect(screen.queryByText('CURRENT PROPOSED PLAN')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    fireEvent.click(screen.getByLabelText('Include plan history')); expect(screen.queryByText('CURRENT PROPOSED PLAN')).not.toBeInTheDocument()
  })

  it('renders baseline plans, a personalized fallback, and no raw recommendation codes as primary copy', async () => {
    const baseline = response('baseline'); baseline.latest_plan.calorie_basis = 'baseline'; baseline.latest_plan.lifecycle_stage = 'baseline'
    mockApi(baseline); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(screen.getByText('baseline basis')).toBeInTheDocument(); expect(screen.getByText('baseline calorie source')).toBeInTheDocument(); expect(screen.getByText('2,350–2,550 kcal/day')).toBeInTheDocument(); expect(screen.getByText(/Legacy V0\.1 baseline macros are intentionally secondary/)).toBeInTheDocument()
    expect(screen.queryByText('adjustment_recommended')).not.toBeInTheDocument()
  })

  it('explains a baseline fallback when personalized evidence cannot safely change the target', async () => {
    const fallback = response(); fallback.latest_plan.calorie_basis = 'baseline'
    mockApi(fallback); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(screen.getByText(/current recommendation safety gate retained your baseline target/)).toBeInTheDocument()
  })

  it('renders a requested empty plan progression without a second API request', async () => {
    const value = response(); value.plan_progression = { snapshots: [], submitted_observation_count: 0, planning_policy_version: 'planning', assumptions: [] }
    const fetchMock = mockApi(value); render(<App />); fireEvent.click(screen.getByLabelText('Include plan history')); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' }))
    await screen.findByText('CURRENT PROPOSED PLAN'); fireEvent.click(screen.getByRole('button', { name: 'Show plan history' }))
    expect(screen.getByText('No entries yet, so there is no plan history to reconstruct.')).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('retries the exact same unified request after an API failure', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ error: { message: 'nope' } }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => response() })
    vi.stubGlobal('fetch', fetchMock); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' }))
    await screen.findByRole('alert'); fireEvent.click(screen.getByRole('button', { name: 'Retry' })); await screen.findByText('CURRENT PROPOSED PLAN')
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(fetchMock.mock.calls[1][1]?.body).toBe(fetchMock.mock.calls[0][1]?.body)
  })

  it('supports replace-existing and replace-all import modes only after confirmation', () => {
    render(<App />); fill('Date', '2026-01-01'); fill('Steps', '10'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' })); fireEvent.click(screen.getByRole('button', { name: 'Import history' }))
    fill('Import observations', '[{"observed_on":"2026-01-01","steps":20},{"observed_on":"2026-01-02","steps":30}]'); fireEvent.click(screen.getByRole('button', { name: 'Preview import' })); fill('Conflict policy', 'replace_existing'); fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }))
    expect(screen.getByText(/Imported 2 rows; skipped 0; replaced 1/)).toBeInTheDocument(); expect(screen.getByText('20 steps')).toBeInTheDocument()
    fill('Import observations', '[{"observed_on":"2026-02-01","steps":40}]'); fireEvent.click(screen.getByRole('button', { name: 'Preview import' })); fill('Import mode', 'replace_all'); fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }))
    expect(screen.getByRole('heading', { name: /Daily observations 1/ })).toBeInTheDocument(); expect(screen.getByText('2026-02-01')).toBeInTheDocument()
  })

  it('requires explicit valid-only confirmation before importing partial input', () => {
    render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Import history' })); fill('Import observations', '[{"observed_on":"2026-01-01","steps":0},{"observed_on":"2026-01-02","steps":"bad"}]'); fireEvent.click(screen.getByRole('button', { name: 'Preview import' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm import' })); expect(screen.getByRole('alert')).toHaveTextContent('explicitly choose')
    fireEvent.click(screen.getByRole('checkbox', { name: /Import valid rows only/ })); fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }))
    expect(screen.getByText('0 steps')).toBeInTheDocument(); expect(screen.getByText(/invalid 1/)).toBeInTheDocument()
  })

  it('keeps import controls accessible and renders deterministically for equal responses', async () => {
    mockApi(); const { rerender } = render(<App />); expect(screen.getByRole('button', { name: 'Import history' })).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN'); const first = screen.getAllByText('2,450 kcal/day')[0].textContent
    rerender(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my profile' })); await screen.findByText('CURRENT PROPOSED PLAN'); expect(screen.getAllByText('2,450 kcal/day')[0].textContent).toBe(first)
  })
})
