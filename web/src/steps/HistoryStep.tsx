import type { ChangeEvent } from 'react'
import { ActionBar, Notice, NumberField, SectionCard, StepHeader } from '../components/ui'
import { CANONICAL_OBSERVATION_FIELDS, type ImportFormat, type ImportPreview } from '../import/observation-import'
import type { Observation } from '../types'
import { decimal, whole } from '../utils/presentation'
import { observationFormErrors } from '../utils/observation-form'

const optionalFields: readonly [keyof Observation, string, string][] = [
  ['protein_g', 'Protein (g)', 'g'], ['carbohydrate_g', 'Carbohydrates (g)', 'g'], ['fat_g', 'Fat (g)', 'g'],
  ['strength_training_minutes', 'Strength training (min)', 'min'], ['cardio_minutes', 'Cardio (min)', 'min'],
  ['sleep_hours', 'Sleep (hours)', 'hours'], ['hunger_rating', 'Hunger rating', '/10'], ['energy_rating', 'Energy rating', '/10'],
]

type HistoryStepProps = {
  observations: Observation[]; draft: Observation; editing: string | null; demoLoaded: boolean
  showOptional: boolean; showAll: boolean; showImport: boolean; importFormat: ImportFormat
  importText: string; preview: ImportPreview | null; importMode: 'merge' | 'replace_all'
  conflictPolicy: 'reject_conflicts' | 'keep_existing' | 'replace_existing'; allowValidOnly: boolean
  importSummary: string; error: string
  onLoadDemo: () => void; onClear: () => void; onToggleImport: () => void
  onImportFormat: (format: ImportFormat) => void; onImportFile: (file: File | undefined) => void
  onImportText: (value: string) => void; onPreview: () => void; onConfirmImport: () => void
  onCancelPreview: () => void; onImportMode: (mode: 'merge' | 'replace_all') => void
  onConflictPolicy: (policy: 'reject_conflicts' | 'keep_existing' | 'replace_existing') => void
  onAllowValidOnly: (value: boolean) => void; onDownloadTemplate: () => void
  onDraft: (key: keyof Observation, value: string) => void; onToggleOptional: () => void
  onSave: () => void; onEdit: (item: Observation) => void; onDelete: (date: string) => void
  onToggleAll: () => void; onBack: () => void; onAnalyze: () => void; loading: boolean
}

function ImportPanel(props: HistoryStepProps) {
  const fileChanged = (event: ChangeEvent<HTMLInputElement>) => void props.onImportFile(event.target.files?.[0])
  return <div className="disclosure import-panel">
    <div className="subsection-heading"><h3>Import historical observations</h3><p>Import is separate from daily logging. Blank CSV cells stay missing; `0` stays zero.</p></div>
    <div className="import-actions">
      <label>Format<select aria-label="Import format" value={props.importFormat} onChange={(event) => props.onImportFormat(event.target.value as ImportFormat)}><option value="json">JSON</option><option value="csv">CSV</option></select></label>
      <label className="file-label">Choose file<input aria-label="Import file" type="file" accept=".json,.csv,application/json,text/csv" onChange={fileChanged} /></label>
      <button className="button-secondary" onClick={props.onDownloadTemplate}>Download CSV template</button>
    </div>
    <label>{props.importFormat === 'json' ? 'Paste JSON observations' : 'Paste CSV observations'}<textarea aria-label="Import observations" value={props.importText} onChange={(event) => props.onImportText(event.target.value)} placeholder={props.importFormat === 'json' ? '[{"observed_on":"2026-01-01","steps":0}]' : CANONICAL_OBSERVATION_FIELDS.join(',')} /></label>
    <button onClick={props.onPreview}>Preview import</button>
    {props.preview && <div className="import-preview" aria-live="polite">
      <h4>Import preview</h4>
      <p>{props.preview.format.toUpperCase()} · {props.preview.totalRows} rows · {props.preview.validRows.length} valid · {props.preview.errors.length} invalid</p>
      <p>Dates: {props.preview.earliestDate || '—'} to {props.preview.latestDate || '—'} · duplicates: {props.preview.duplicateDates.length} · conflicts: {props.preview.conflictingDates.length}</p>
      {props.preview.errors.length > 0 && <><ul>{props.preview.errors.slice(0, 6).map((item, index) => <li key={`${item.row}-${index}`}>Row {item.row || 'file'}: {item.message}</li>)}</ul><label className="checkbox"><input type="checkbox" checked={props.allowValidOnly} onChange={(event) => props.onAllowValidOnly(event.target.checked)} /> Import valid rows only (invalid rows are not silently discarded)</label></>}
      <div className="field-grid"><label>Import mode<select aria-label="Import mode" value={props.importMode} onChange={(event) => props.onImportMode(event.target.value as 'merge' | 'replace_all')}><option value="merge">Merge with current history</option><option value="replace_all">Replace all history</option></select></label>{props.importMode === 'merge' && <label>Conflict policy<select aria-label="Conflict policy" value={props.conflictPolicy} onChange={(event) => props.onConflictPolicy(event.target.value as 'reject_conflicts' | 'keep_existing' | 'replace_existing')}><option value="reject_conflicts">Reject conflicts (recommended)</option><option value="keep_existing">Keep current entries</option><option value="replace_existing">Replace current entries</option></select></label>}</div>
      <p className="preview-rows">Preview: {props.preview.validRows.slice(0, 4).map((item) => item.observed_on).join(', ') || 'No valid rows'}</p>
      <button onClick={props.onConfirmImport}>Confirm import</button><button className="button-quiet" onClick={props.onCancelPreview}>Cancel preview</button>
    </div>}
  </div>
}

function ObservationEditor(props: HistoryStepProps) {
  const fieldErrors = observationFormErrors(props.draft)
  const formError = props.error === 'An observation date and at least one measurement are required.' || props.error === 'Duplicate observation dates are not allowed.' || props.error.startsWith('Observation values')
  return <div className="observation-form">
    <div className="subsection-heading"><h3>{props.editing ? `Edit ${props.editing}` : 'Log one day'}</h3><p>Only record what you know. Empty fields remain unknown, not zero.</p></div>
    <div className="observation-primary-grid">
      <label className="form-field"><span className="form-field-label">Date</span><input aria-label="Date" type="date" value={props.draft.observed_on} onChange={(event) => props.onDraft('observed_on', event.target.value)} /></label>
      <NumberField label="Today's weight (kg)" value={props.draft.body_weight_kg ?? ''} onChange={(next) => props.onDraft('body_weight_kg', next)} unit="kg" min={30} max={300} step="any" placeholder="Unknown" optional error={fieldErrors.body_weight_kg} />
      <NumberField label="Calories (kcal)" value={props.draft.energy_intake_kcal ?? ''} onChange={(next) => props.onDraft('energy_intake_kcal', next)} unit="kcal" min={0} max={10000} step="any" placeholder="Unknown" optional error={fieldErrors.energy_intake_kcal} />
      <NumberField label="Steps" value={props.draft.steps ?? ''} onChange={(next) => props.onDraft('steps', next)} unit="steps" min={0} step={1} placeholder="Unknown" optional error={fieldErrors.steps} />
    </div>
    <button className="button-quiet detail-toggle" aria-expanded={props.showOptional} onClick={props.onToggleOptional}>{props.showOptional ? 'Hide optional fields' : 'Add optional details'}</button>
    {props.showOptional && <div className="form-grid observation-optional-grid">{optionalFields.map(([key, label, unit]) => <NumberField key={key} label={label} value={props.draft[key] ?? ''} onChange={(next) => props.onDraft(key, next)} unit={unit} min={key.endsWith('rating') ? 1 : 0} max={key.endsWith('rating') ? 5 : key === 'sleep_hours' ? 24 : key.endsWith('minutes') ? 1440 : undefined} step={key.endsWith('rating') ? 1 : 'any'} placeholder="Unknown" optional error={fieldErrors[key as keyof typeof fieldErrors]} />)}</div>}
    {formError && <p className="field-error" role="alert">{props.error}</p>}
    <button onClick={props.onSave}>{props.editing ? 'Save observation' : 'Add observation'}</button>
  </div>
}

export function HistoryStep(props: HistoryStepProps) {
  const displayed = [...props.observations].reverse()
  const shown = props.showAll ? displayed : displayed.slice(0, 8)
  const formError = props.error === 'An observation date and at least one measurement are required.' || props.error === 'Duplicate observation dates are not allowed.' || props.error.startsWith('Observation values')
  return <>
    <StepHeader eyebrow="Step 3 of 5" title="Build your evidence" description="Adaptive estimates need consistent weight and calorie history. Missing values stay missing; logged zero stays zero." />
    {props.error && !formError && <Notice tone="danger"><div role="alert">{props.error}</div></Notice>}
    <SectionCard>
      <div className="history-heading"><div><h2>Daily observations <span className="count">{props.observations.length}</span></h2><p>Log one day below, or import a separate history.</p></div><div className="history-actions"><button onClick={props.onLoadDemo}>Load fictional sample</button><button className="button-secondary" onClick={props.onClear}>Clear data</button><button className="button-quiet" aria-expanded={props.showImport} onClick={props.onToggleImport}>Import history</button></div></div>
      {props.demoLoaded && <Notice tone="warning"><strong>Fictional sample data.</strong> Generated locally around the displayed profile weight; not personal, clinical, or real-world evidence.</Notice>}
      {props.showImport && <ImportPanel {...props} />}
      {props.importSummary && <p className="inline-notice" aria-live="polite">{props.importSummary}</p>}
      <ObservationEditor {...props} />
      {props.observations.length > 0 && <><div className="history-table-wrap"><table><caption className="sr-only">Observation history, newest first</caption><thead><tr><th>Date</th><th>Weight</th><th>Calories</th><th>Steps</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{shown.map((item) => <tr key={item.observed_on}><td>{item.observed_on}</td><td>{decimal(item.body_weight_kg, 'kg')}</td><td>{whole(item.energy_intake_kcal, 'kcal')}</td><td>{whole(item.steps, 'steps')}</td><td className="row-actions"><button className="icon-button" aria-label={`Edit ${item.observed_on}`} onClick={() => props.onEdit(item)}>Edit</button><button className="icon-button danger" aria-label={`Delete ${item.observed_on}`} onClick={() => props.onDelete(item.observed_on)}>Delete</button></td></tr>)}</tbody></table></div>{displayed.length > 8 && <button className="button-quiet" onClick={props.onToggleAll}>{props.showAll ? 'Show less' : `Show all ${props.observations.length} observations`}</button>}</>}
    </SectionCard>
    <ActionBar><button className="button-secondary" onClick={props.onBack}>Back to nutrition</button><button disabled={props.loading} onClick={props.onAnalyze}>{props.loading ? 'Analyzing…' : 'Analyze my profile'}</button></ActionBar>
  </>
}
