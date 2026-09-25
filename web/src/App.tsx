import { useState } from 'react'
import { ApiError, getProfileIntelligence } from './api'
import { AppShell } from './components/AppShell'
import { CANONICAL_OBSERVATION_FIELDS, CSV_TEMPLATE, CSV_TEMPLATE_FILENAME, previewObservationImport, type ImportFormat, type ImportPreview } from './import/observation-import'
import { createFictionalSample } from './sample-history'
import { HistoryStep } from './steps/HistoryStep'
import { NutritionStep } from './steps/NutritionStep'
import { PlanStep } from './steps/PlanStep'
import { ProfileStep } from './steps/ProfileStep'
import { ProgressStep } from './steps/ProgressStep'
import type { MacroStrategy, NutritionPreferenceProfile, NutritionPreferences, Observation, Profile, ProfileIntelligenceRequest, ProfileIntelligenceResponse } from './types'
import { dietaryProfileErrors, initialDietaryProfile } from './utils/dietary'
import { JOURNEY, type JourneyState, type JourneyStep } from './utils/journey'
import './index.css'

const emptyObservation: Observation = { observed_on: '', body_weight_kg: null, energy_intake_kcal: null, steps: null }
const initialProfile: Profile = { age_years: 30, height_cm: 180, weight_kg: 80, sex_for_mifflin_equation: 'male', activity_level: 'moderately_active', goal: 'maintain', requested_weekly_change_kg: 0 }

export default function App() {
  const [currentStep, setCurrentStep] = useState<JourneyStep>('profile')
  const [profile, setProfile] = useState<Profile>(initialProfile)
  const [preferences, setPreferences] = useState<NutritionPreferences>({ macro_strategy: 'balanced' })
  const [dietaryProfile, setDietaryProfile] = useState<NutritionPreferenceProfile>(initialDietaryProfile)
  const [observations, setObservations] = useState<Observation[]>([])
  const [draft, setDraft] = useState<Observation>(emptyObservation)
  const [editing, setEditing] = useState<string | null>(null)
  const [showOptional, setShowOptional] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [includeProgression, setIncludeProgression] = useState(false)
  const [results, setResults] = useState<ProfileIntelligenceResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastRequest, setLastRequest] = useState<ProfileIntelligenceRequest | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [importFormat, setImportFormat] = useState<ImportFormat>('json')
  const [importText, setImportText] = useState('')
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [importMode, setImportMode] = useState<'merge' | 'replace_all'>('merge')
  const [conflictPolicy, setConflictPolicy] = useState<'reject_conflicts' | 'keep_existing' | 'replace_existing'>('reject_conflicts')
  const [allowValidOnly, setAllowValidOnly] = useState(false)
  const [importSummary, setImportSummary] = useState('')
  const [demoLoaded, setDemoLoaded] = useState(false)

  const clearStale = () => { setResults(null); setError('') }
  const sorted = (items: Observation[]) => [...items].sort((left, right) => left.observed_on.localeCompare(right.observed_on))
  const dietaryErrors = dietaryProfileErrors(dietaryProfile)
  const request = (): ProfileIntelligenceRequest => ({ profile, observations, nutrition_preferences: preferences.macro_strategy === 'custom' ? preferences : { macro_strategy: preferences.macro_strategy }, dietary_preference_profile: dietaryProfile, include_plan_progression: includeProgression })
  const updateProfile = (key: keyof Profile, value: string) => { const selection = key === 'sex_for_mifflin_equation' || key === 'activity_level' || key === 'goal'; const next = { ...profile, [key]: selection ? value : Number(value) } as Profile; if (key === 'goal') next.requested_weekly_change_kg = value === 'cut' ? -0.4 : value === 'gain' ? 0.2 : 0; setProfile(next); clearStale() }
  const updatePreference = (strategy: MacroStrategy) => { setPreferences(strategy === 'custom' ? { macro_strategy: strategy, custom_protein_g_per_kg: 1.8, custom_fat_percentage: 0.25 } : { macro_strategy: strategy }); clearStale() }
  const updateCustomPreference = (updates: Partial<NutritionPreferences>) => { setPreferences(current => ({ ...current, ...updates })); clearStale() }
  const updateDietaryProfile = (next: NutritionPreferenceProfile) => { setDietaryProfile(next); clearStale() }
  const updateDraft = (key: keyof Observation, value: string) => { const next = { ...draft } as Record<string, string | number | null | undefined>; next[key] = key === 'observed_on' ? value : value === '' ? null : Number(value); setDraft(next as unknown as Observation) }
  const saveObservation = () => { const measurement = CANONICAL_OBSERVATION_FIELDS.slice(1).some(key => draft[key] != null); if (!draft.observed_on || !measurement) { setError('An observation date and at least one measurement are required.'); return } if (!editing && observations.some(item => item.observed_on === draft.observed_on)) { setError('Duplicate observation dates are not allowed.'); return } setObservations(current => sorted([...current.filter(item => item.observed_on !== editing), draft])); setDraft(emptyObservation); setEditing(null); setDemoLoaded(false); clearStale() }
  const startPreview = (text: string, format = importFormat) => { setImportText(text); setImportFormat(format); setPreview(previewObservationImport(text, format, observations.map(item => item.observed_on))); setImportSummary('') }
  const importFile = async (file: File | undefined) => { if (!file) return; const format: ImportFormat = file.name.toLowerCase().endsWith('.csv') ? 'csv' : 'json'; startPreview(await file.text(), format) }
  const confirmImport = () => { if (!preview) return; if (preview.errors.length > 0 && !allowValidOnly) { setError('Fix import errors or explicitly choose to import valid rows only.'); return } if (importMode === 'merge' && preview.conflictingDates.length > 0 && conflictPolicy === 'reject_conflicts') { setError('Resolve date conflicts before merging.'); return } const incoming = preview.validRows; let next: Observation[]; let skipped = 0; let replaced = 0; if (importMode === 'replace_all') next = incoming; else if (conflictPolicy === 'keep_existing') { next = [...observations, ...incoming.filter(item => !preview.conflictingDates.includes(item.observed_on))]; skipped = preview.conflictingDates.length } else if (conflictPolicy === 'replace_existing') { next = [...observations.filter(item => !preview.conflictingDates.includes(item.observed_on)), ...incoming]; replaced = preview.conflictingDates.length } else next = [...observations, ...incoming]; setObservations(sorted(next)); setImportSummary(`Imported ${incoming.length - skipped} rows; skipped ${skipped}; replaced ${replaced}; invalid ${preview.errors.length}.`); setPreview(null); setImportText(''); setDemoLoaded(false); clearStale() }
  const downloadTemplate = () => { const url = URL.createObjectURL(new Blob([CSV_TEMPLATE], { type: 'text/csv' })); const link = document.createElement('a'); link.href = url; link.download = CSV_TEMPLATE_FILENAME; link.click(); URL.revokeObjectURL(url) }
  const loadDemo = () => { setObservations(createFictionalSample(profile)); setShowAll(false); setDemoLoaded(true); clearStale() }
  const analyze = async (nextRequest = request()) => { if (loading) return; if (dietaryProfileErrors(nextRequest.dietary_preference_profile).length > 0) { setCurrentStep('nutrition'); return } if (nextRequest.nutrition_preferences.macro_strategy === 'custom' && ((nextRequest.nutrition_preferences.custom_protein_g_per_kg ?? 0) < 1.2 || (nextRequest.nutrition_preferences.custom_protein_g_per_kg ?? 0) > 2.4 || (nextRequest.nutrition_preferences.custom_fat_percentage ?? 0) < .2 || (nextRequest.nutrition_preferences.custom_fat_percentage ?? 0) > .4)) { setError('Custom protein must be 1.2–2.4 g/kg and fat must be 20–40% of calories.'); setCurrentStep('plan'); return } setLoading(true); setError(''); setLastRequest(nextRequest); setCurrentStep('plan'); try { setResults(await getProfileIntelligence(nextRequest)) } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'Cannot reach the FitAdapt API.') } finally { setLoading(false) } }
  const stateFor = (step: JourneyStep): JourneyState => { if (step === currentStep) return 'current'; const currentIndex = JOURNEY.findIndex(item => item.id === currentStep); const index = JOURNEY.findIndex(item => item.id === step); if (step === 'nutrition' && dietaryErrors.length > 0) return 'incomplete'; if (index < currentIndex) return 'completed'; if (step === 'history') return observations.length > 0 ? 'ready' : 'incomplete'; if (step === 'plan' || step === 'progress') return results ? 'ready' : 'not started'; return 'ready' }

  return <AppShell current={currentStep} stateFor={stateFor} onNavigate={setCurrentStep} onLoadDemo={() => { loadDemo(); setCurrentStep('history') }}>
    {currentStep === 'profile' && <ProfileStep profile={profile} onChange={updateProfile} onContinue={() => setCurrentStep('nutrition')} />}
    {currentStep === 'nutrition' && <NutritionStep preferences={preferences} dietaryProfile={dietaryProfile} dietaryErrors={dietaryErrors} onStrategy={updatePreference} onCustom={updateCustomPreference} onDietaryProfile={updateDietaryProfile} onBack={() => setCurrentStep('profile')} onContinue={() => { if (dietaryErrors.length === 0) setCurrentStep('history') }} />}
    {currentStep === 'history' && <HistoryStep observations={observations} draft={draft} editing={editing} demoLoaded={demoLoaded} showOptional={showOptional} showAll={showAll} showImport={showImport} importFormat={importFormat} importText={importText} preview={preview} importMode={importMode} conflictPolicy={conflictPolicy} allowValidOnly={allowValidOnly} importSummary={importSummary} error={error} onLoadDemo={loadDemo} onClear={() => { setObservations([]); setDraft(emptyObservation); setDemoLoaded(false); clearStale() }} onToggleImport={() => setShowImport(!showImport)} onImportFormat={format => { setImportFormat(format); setPreview(null) }} onImportFile={file => void importFile(file)} onImportText={setImportText} onPreview={() => startPreview(importText)} onConfirmImport={confirmImport} onCancelPreview={() => { setPreview(null); setImportText('') }} onImportMode={setImportMode} onConflictPolicy={setConflictPolicy} onAllowValidOnly={setAllowValidOnly} onDownloadTemplate={downloadTemplate} onDraft={updateDraft} onToggleOptional={() => setShowOptional(!showOptional)} onSave={saveObservation} onEdit={item => { setDraft(item); setEditing(item.observed_on) }} onDelete={observedOn => { setObservations(current => current.filter(value => value.observed_on !== observedOn)); setDemoLoaded(false); clearStale() }} onToggleAll={() => setShowAll(!showAll)} onBack={() => setCurrentStep('nutrition')} onAnalyze={() => void analyze()} loading={loading} />}
    {currentStep === 'plan' && <PlanStep result={results} error={error} loading={loading} includeProgression={includeProgression} canRetry={lastRequest != null} onIncludeProgression={value => { setIncludeProgression(value); clearStale() }} onAnalyze={() => void analyze()} onRetry={() => lastRequest && void analyze(lastRequest)} onBack={() => setCurrentStep('history')} onProgress={() => setCurrentStep('progress')} />}
    {currentStep === 'progress' && <ProgressStep result={results} onBack={() => setCurrentStep('plan')} />}
  </AppShell>
}
