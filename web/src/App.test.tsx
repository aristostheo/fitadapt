import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, client } from './api'

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('FitAdapt web workflow', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
  it('loads fictional sample data and clears session state', () => { render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Load sample history' })); expect(screen.getByText(/Fictional sample data/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Clear data' })); expect(screen.queryByText(/Fictional sample data/)).not.toBeInTheDocument() })
  it('adds, edits, sorts, and deletes observations while preserving zero and missing values', () => { render(<App />); fill('observed on','2026-01-02'); fill('energy intake kcal','0'); fireEvent.click(screen.getByRole('button',{name:'Add observation'})); fill('observed on','2026-01-01'); fireEvent.click(screen.getByRole('button',{name:'Add observation'})); expect(screen.getByText(/intake 0/)).toBeInTheDocument(); expect(screen.getByText(/intake missing/)).toBeInTheDocument(); expect(screen.getAllByText(/2026-01-0/)[0]).toHaveTextContent('2026-01-01'); fireEvent.click(screen.getAllByRole('button',{name:'Edit'})[1]); fill('energy intake kcal','2200'); fireEvent.click(screen.getByRole('button',{name:'Save observation'})); expect(screen.getByText(/intake 2200/)).toBeInTheDocument(); fireEvent.click(screen.getAllByRole('button',{name:'Delete'})[0]); expect(screen.queryByText(/2026-01-01/)).not.toBeInTheDocument() })
  it('imports valid JSON and rejects duplicate dates and malformed JSON', () => { render(<App />); const importer=screen.getByLabelText('Import observations JSON'); fireEvent.change(importer,{target:{value:'[{"observed_on":"2026-01-02","steps":0}]'}}); fireEvent.blur(importer); expect(screen.getByText(/2026-01-02/)).toBeInTheDocument(); fill('observed on','2026-01-02'); fireEvent.click(screen.getByRole('button',{name:'Add observation'})); expect(screen.getByRole('alert')).toHaveTextContent('Duplicate'); fireEvent.change(importer,{target:{value:'{'}}); fireEvent.blur(importer); expect(screen.getByRole('alert')).toHaveTextContent('could not be parsed') })
  it('shows network error and retries when API is offline', async () => { const fetchMock=vi.fn().mockRejectedValue(new Error('offline')); vi.stubGlobal('fetch',fetchMock); render(<App />); fireEvent.click(screen.getByRole('button',{name:'Calculate with FitAdapt API'})); expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach'); fireEvent.click(screen.getByRole('button',{name:'Retry'})); await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(8)) })
  it('shows optional observation fields', () => { render(<App />); fireEvent.click(screen.getByRole('button',{name:'Optional fields'})); expect(screen.getByLabelText('protein g')).toBeInTheDocument() })
  it('renders actionable results and chart empty states from mocked API responses', async () => {
    vi.spyOn(client, 'baseline').mockResolvedValue({ baseline_energy:{estimated_ree_kcal_per_day:1700,estimated_tdee_kcal_per_day:2400},target_calories_kcal_per_day:2300,protein_g_per_day:128,fat_g_per_day:48,carbohydrate_g_per_day:300 } as never)
    vi.spyOn(client, 'trends').mockResolvedValue({ data_quality:{total_calendar_days:28,body_weight_completeness_ratio:1,energy_intake_completeness_ratio:1,step_completeness_ratio:0},points:[{observed_on:'2026-01-01',body_weight_kg:80,trailing_body_weight_mean_kg:null,energy_intake_kcal:2400,trailing_energy_intake_mean_kcal:null,steps:null,trailing_steps_mean:null}] } as never)
    vi.spyOn(client, 'adaptive').mockResolvedValue({ adaptive_tdee_kcal_per_day:2450,median_absolute_deviation_kcal_per_day:20 } as never)
    vi.spyOn(client, 'recommendation').mockResolvedValue({ status:'increase',reasons:[],recent_mean_intake_kcal_per_day:2200,personalized_goal_target_kcal_per_day:2450,raw_adjustment_kcal_per_day:150,recommended_adjustment_kcal_per_day:150,proposed_intake_target_kcal_per_day:2350 } as never)
    render(<App />); fireEvent.click(screen.getByRole('button',{name:'Calculate with FitAdapt API'}));
    await waitFor(()=>expect(screen.getByRole('heading',{name:'increase'})).toBeInTheDocument());
    expect(screen.getByText(/No recorded steps values yet/)).toBeInTheDocument(); expect(screen.getByText(/proposed 2350.0/)).toBeInTheDocument()
  })
  it('renders an insufficient recommendation and clears stale results after an input change', async () => {
    vi.spyOn(client, 'baseline').mockResolvedValue({ baseline_energy:{estimated_ree_kcal_per_day:1700,estimated_tdee_kcal_per_day:2400},target_calories_kcal_per_day:2300,protein_g_per_day:128,fat_g_per_day:48,carbohydrate_g_per_day:300 } as never)
    vi.spyOn(client, 'trends').mockResolvedValue({ data_quality:{total_calendar_days:1,body_weight_completeness_ratio:0,energy_intake_completeness_ratio:0,step_completeness_ratio:0},points:[] } as never)
    vi.spyOn(client, 'adaptive').mockResolvedValue({ adaptive_tdee_kcal_per_day:null,median_absolute_deviation_kcal_per_day:null } as never)
    vi.spyOn(client, 'recommendation').mockResolvedValue({ status:'insufficient_data',reasons:['insufficient_history'],recent_mean_intake_kcal_per_day:null,personalized_goal_target_kcal_per_day:null,raw_adjustment_kcal_per_day:null,recommended_adjustment_kcal_per_day:null,proposed_intake_target_kcal_per_day:null } as never)
    render(<App />); fireEvent.click(screen.getByRole('button',{name:'Calculate with FitAdapt API'}));
    await waitFor(()=>expect(screen.getByText(/Recommendation is unavailable/)).toBeInTheDocument());
    fill('age years','31'); expect(screen.queryByText('REE')).not.toBeInTheDocument()
  })
  it('disables calculation while requests are pending', () => {
    vi.spyOn(client, 'baseline').mockImplementation(()=>new Promise(()=>{}) as never)
    render(<App />); fireEvent.click(screen.getByRole('button',{name:'Calculate with FitAdapt API'}));
    expect(screen.getByRole('button',{name:'Calculating…'})).toBeDisabled()
  })
  it('preserves structured API error categories', async () => {
    const cases:[number, string, string][]=[[400,'domain','profile invalid'],[422,'validation','invalid fields'],[500,'unexpected','server error']]
    for (const [status,kind,message] of cases) { vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status,json:async()=>({error:{message,code:'BAD'}})})); await expect(client.baseline({} as never)).rejects.toMatchObject({kind}); vi.unstubAllGlobals() }
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('offline'))); await expect(client.baseline({} as never)).rejects.toBeInstanceOf(ApiError)
  })
})
