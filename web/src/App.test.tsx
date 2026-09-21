import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, client } from './api'
import { paddedDomain } from './chart-domain'

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

function mockAnalysis(recommendation: Record<string, unknown> = { status: 'increase_calories', reasons: ['adjustment_recommended'], recent_mean_intake_kcal_per_day: 2200.4, personalized_goal_target_kcal_per_day: 2450.2, raw_adjustment_kcal_per_day: 150.6, recommended_adjustment_kcal_per_day: 150.4, proposed_intake_target_kcal_per_day: 2350.8 }) {
  vi.spyOn(client, 'baseline').mockResolvedValue({ baseline_energy: { estimated_ree_kcal_per_day: 1700.6, estimated_tdee_kcal_per_day: 2400.2 }, target_calories_kcal_per_day: 2300.7, protein_g_per_day: 128.4, fat_g_per_day: 48.4, carbohydrate_g_per_day: 300.2 } as never)
  vi.spyOn(client, 'trends').mockResolvedValue({ data_quality: { total_calendar_days: 28, body_weight_completeness_ratio: 1, energy_intake_completeness_ratio: 1, step_completeness_ratio: 0 }, points: [{ observed_on: '2026-01-01', body_weight_kg: 80, trailing_body_weight_mean_kg: null, energy_intake_kcal: 2400, trailing_energy_intake_mean_kcal: null, steps: null, trailing_steps_mean: null }] } as never)
  vi.spyOn(client, 'adaptive').mockResolvedValue({ adaptive_tdee_kcal_per_day: 2450.2, median_absolute_deviation_kcal_per_day: 6.2, eligible_daily_estimate_count: 14 } as never)
  vi.spyOn(client, 'recommendation').mockResolvedValue(recommendation as never)
}

describe('FitAdapt web workflow', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('uses padded, data-relative chart domains for ordinary series', () => {
    const domain = paddedDomain([{ weight: 92.1 }, { weight: 90.5 }], 'weight')
    expect(domain[0]).toBeCloseTo(90.34)
    expect(domain[1]).toBeCloseTo(92.26)
  })

  it('handles constant, single-value, and null chart series safely', () => {
    expect(paddedDomain([{ calories: 2400 }, { calories: 2400 }], 'calories')).toEqual([2352, 2448])
    expect(paddedDomain([{ steps: 5000 }], 'steps')).toEqual([4900, 5100])
    expect(paddedDomain([{ weight: null }, { weight: null }], 'weight')).toEqual([0, 1])
  })

  it('shows all required profile fields with user-facing labels', () => {
    render(<App />)
    for (const label of ['Age', 'Height (cm)', 'Sex used for REE estimate', 'Activity level', 'Goal', 'Desired weekly change (kg)']) expect(screen.getByLabelText(label, { exact: true })).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: /^Weight \(kg\)$/ })).toBeInTheDocument()
    expect(screen.getByText('Required by the Mifflin equation.')).toBeInTheDocument()
  })

  it('normalizes profile age display without a leading zero', () => {
    render(<App />)
    fill('Age', '024')
    expect(screen.getByLabelText('Age')).toHaveValue(24)
  })

  it('loads sample history in a compact newest-first view and clears it', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Load sample history' }))
    expect(screen.getByRole('heading', { name: /Daily observations 28/ })).toBeInTheDocument()
    expect(screen.getAllByText('2026-01-28')).not.toHaveLength(0)
    expect(screen.queryByText('2026-01-01')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show all 28 observations' }))
    expect(screen.getAllByText('2026-01-01')).not.toHaveLength(0)
    expect(screen.getAllByText('79.97 kg')).not.toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Clear data' }))
    expect(screen.getByRole('heading', { name: /Daily observations 0/ })).toBeInTheDocument()
  })

  it('adds, edits, deletes, and preserves zero separately from missing values', () => {
    render(<App />)
    fill('Date', '2026-01-02'); fill('Calories (kcal)', '0'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' }))
    fill('Date', '2026-01-01'); fireEvent.click(screen.getByRole('button', { name: 'Add observation' }))
    expect(screen.getAllByText('0 kcal')).not.toHaveLength(0); expect(screen.getAllByText('—')).not.toHaveLength(0)
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit 2026-01-02' })[0]); fill('Calories (kcal)', '2200'); fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    expect(screen.getAllByText('2,200 kcal')).not.toHaveLength(0)
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete 2026-01-01' })[0]); expect(screen.queryByText('2026-01-01')).not.toBeInTheDocument()
  })

  it('keeps JSON import collapsed until requested and validates imported dates', () => {
    render(<App />)
    expect(screen.queryByLabelText('Import observations JSON')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Import JSON' }))
    fill('Import observations JSON', '[{"observed_on":"2026-01-02","steps":0}]'); fireEvent.click(screen.getByRole('button', { name: 'Import observations' }))
    expect(screen.getAllByText('2026-01-02')).not.toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Import JSON' })); fill('Import observations JSON', '[{"observed_on":"2026-01-02"},{"observed_on":"2026-01-02"}]'); fireEvent.click(screen.getByRole('button', { name: 'Import observations' }))
    expect(screen.getByRole('alert')).toHaveTextContent('could not be parsed')
  })

  it('keeps optional observation fields secondary', () => {
    render(<App />)
    expect(screen.queryByLabelText('Protein (g)')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Add optional details' }))
    expect(screen.getByLabelText('Protein (g)')).toBeInTheDocument()
  })

  it('renders rounded baseline and personalized values with units and compact empty charts', async () => {
    mockAnalysis(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my data' }))
    await screen.findByRole('heading', { name: 'Increase daily intake' })
    expect(screen.getByText('1,701 kcal/day')).toBeInTheDocument(); expect(screen.getByText('128 g/day')).toBeInTheDocument()
    expect(screen.getByText('2,351 kcal/day')).toBeInTheDocument(); expect(screen.getByText(/14 eligible estimates · median absolute deviation: 6 kcal\/day/)).toBeInTheDocument()
    expect(screen.getByText(/Protein, fat, and carbohydrates use the V0.1 baseline macro policy/)).toBeInTheDocument()
    expect(screen.getByText('No recorded steps values yet. Add entries to see this chart.')).toBeInTheDocument()
  })

  it('translates recommendation reason codes into next-step guidance', async () => {
    mockAnalysis({ status: 'insufficient_data', reasons: ['insufficient_weight_completeness'], recent_mean_intake_kcal_per_day: null, personalized_goal_target_kcal_per_day: null, raw_adjustment_kcal_per_day: null, recommended_adjustment_kcal_per_day: null, proposed_intake_target_kcal_per_day: null })
    render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my data' }))
    await screen.findByRole('heading', { name: 'Recommendation unavailable' })
    expect(screen.getAllByText('Log weight more consistently so the trend is reliable.')).not.toHaveLength(0)
    expect(screen.queryByText('insufficient_weight_completeness')).not.toBeInTheDocument()
  })

  it('clears stale results, disables analysis while loading, and retries network errors', async () => {
    mockAnalysis(); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Analyze my data' })); await screen.findByText('Baseline estimates')
    fill('Age', '31'); expect(screen.queryByText('Baseline estimates')).not.toBeInTheDocument()
    vi.restoreAllMocks(); vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    fireEvent.click(screen.getByRole('button', { name: 'Analyze my data' })); expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('preserves structured API error categories', async () => {
    const cases: [number, string][] = [[400, 'domain'], [422, 'validation'], [500, 'unexpected']]
    for (const [status, kind] of cases) { vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ error: { message: 'invalid', code: 'BAD' } }) })); await expect(client.baseline({} as never)).rejects.toMatchObject({ kind }); vi.unstubAllGlobals() }
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline'))); await expect(client.baseline({} as never)).rejects.toBeInstanceOf(ApiError)
  })
})
