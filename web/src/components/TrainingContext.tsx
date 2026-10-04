import { useState } from 'react'
import type { TrainingContext as TrainingContextValue } from '../types'
import type { TrainingDrafts, TrainingNumberKey } from '../utils/profile-form'
import { ChoiceGroup, NumberField, SectionCard } from './ui'

type Props = {
  context: TrainingContextValue
  onChange: (context: TrainingContextValue) => void
  numericValues?: TrainingDrafts
  onNumericDraft?: (drafts: TrainingDrafts) => void
}

const occupationLabels = {
  mostly_seated: 'Mostly seated',
  mixed: 'Seated and on my feet',
  mostly_on_feet: 'Mostly on my feet',
  physically_demanding: 'Physically demanding',
} as const
const focusOptions: { value: TrainingContextValue['primary_training_focus']; label: string }[] = [
  { value: 'general', label: 'General fitness' },
  { value: 'resistance', label: 'Resistance' },
  { value: 'endurance', label: 'Endurance' },
  { value: 'intermittent_sport', label: 'Intermittent sport' },
  { value: 'mixed', label: 'Mixed' },
]
const intensityLabels = { low: 'Low', moderate: 'Moderate', vigorous: 'Vigorous' } as const
type DayKey = 'resistance_days_per_week' | 'cardio_days_per_week' | 'sport_days_per_week'
type MinuteKey = 'resistance_minutes_per_week' | 'cardio_minutes_per_week' | 'sport_minutes_per_week'
type NumericKey = TrainingNumberKey

export function TrainingContext({ context, onChange, numericValues, onNumericDraft }: Props) {
  const [localRaw, setLocalRaw] = useState<TrainingDrafts>({})
  const raw = numericValues ?? localRaw
  const setRaw = (change: (current: TrainingDrafts) => TrainingDrafts) => {
    const next = change(raw)
    if (onNumericDraft) onNumericDraft(next)
    else setLocalRaw(next)
  }
  const [touched, setTouched] = useState<Partial<Record<NumericKey, boolean>>>({})
  const update = (patch: Partial<TrainingContextValue>) => onChange({ ...context, ...patch })
  const value = (key: NumericKey) => raw[key] ?? context[key] ?? ''
  const editNumber = (key: NumericKey, next: string, maximum: number, integer: boolean) => {
    setTouched((current) => ({ ...current, [key]: true }))
    const parsed = Number(next)
    if (next === '' || !Number.isFinite(parsed) || parsed < 0 || parsed > maximum || (integer && !Number.isInteger(parsed))) {
      setRaw((current) => ({ ...current, [key]: next }))
      if (key === 'typical_daily_steps' && next === '') update({ typical_daily_steps: null })
      return
    }
    setRaw((current) => {
      const copy = { ...current }
      delete copy[key]
      if (parsed === 0 && key === 'resistance_days_per_week') delete copy.resistance_minutes_per_week
      if (parsed === 0 && key === 'cardio_days_per_week') delete copy.cardio_minutes_per_week
      if (parsed === 0 && key === 'sport_days_per_week') delete copy.sport_minutes_per_week
      return copy
    })
    if (key === 'resistance_days_per_week' && parsed === 0) update({ resistance_days_per_week: 0, resistance_minutes_per_week: 0 })
    else if (key === 'cardio_days_per_week' && parsed === 0) update({ cardio_days_per_week: 0, cardio_minutes_per_week: 0, cardio_intensity: null })
    else if (key === 'sport_days_per_week' && parsed === 0) update({ sport_days_per_week: 0, sport_minutes_per_week: 0, sport_intensity: null })
    else update({ [key]: parsed })
  }
  const error = (key: NumericKey, maximum: number, integer = false) => {
    const current = raw[key]
    if (current !== undefined) {
      if (current === '' && key === 'typical_daily_steps') return undefined
      const parsed = Number(current)
      if (current === '' || !Number.isFinite(parsed) || parsed < 0 || parsed > maximum || (integer && !Number.isInteger(parsed))) return `Enter ${integer ? 'a whole number' : 'a value'} from 0 to ${maximum}.`
    }
    if (touched[key] && key.endsWith('minutes_per_week') && context[key] === 0) return 'Add the time for your typical week.'
    return undefined
  }
  const dayField = (label: string, key: DayKey) => <NumberField label={label} value={value(key)} onChange={(next) => editNumber(key, next, 7, true)} unit="days/wk" min={0} max={7} step={1} error={error(key, 7, true)} />
  const minuteField = (label: string, key: MinuteKey, maximum: number) => <NumberField label={label} value={value(key) === 0 ? '' : value(key)} onChange={(next) => editNumber(key, next, maximum, false)} unit="min/wk" min={0} max={maximum} step="any" error={error(key, maximum) || (context[key] === 0 ? 'Enter your weekly minutes.' : undefined)} />
  const intensityField = (label: string, key: 'cardio_intensity' | 'sport_intensity') => <label className="form-field field-medium"><span className="form-field-label">{label}</span><select aria-label={label} aria-invalid={context[key] == null} value={context[key] ?? ''} onChange={(event) => update({ [key]: event.target.value || null })}><option value="">Choose intensity</option>{Object.entries(intensityLabels).map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select>{context[key] == null && <small className="field-error">Choose your typical intensity.</small>}</label>

  return <SectionCard title="Training & performance" description="Use a typical week, not your busiest one. Training can inform macro composition; it does not add workout calories to your target.">
    <ChoiceGroup legend="Primary training focus" name="training-focus" value={context.primary_training_focus} options={focusOptions} onChange={(next) => update({ primary_training_focus: next })} />
    <div className="training-lifestyle form-grid">
      <label className="form-field field-medium"><span className="form-field-label">Occupation activity</span><select aria-label="Occupation activity" value={context.occupation_activity} onChange={(event) => update({ occupation_activity: event.target.value as TrainingContextValue['occupation_activity'] })}>{Object.entries(occupationLabels).map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select></label>
      <NumberField label="Typical daily steps" value={value('typical_daily_steps')} onChange={(next) => editNumber('typical_daily_steps', next, 100000, true)} unit="steps/day" min={0} max={100000} step={1} placeholder="Unknown" optional error={error('typical_daily_steps', 100000, true)} hint="Leave blank if you do not know." />
    </div>
    <div className="training-overview"><div className="subsection-heading"><h3>Weekly training</h3><p>Set days first; add details only for activities you do.</p></div>
      <div className="training-row"><div className="training-row-title"><strong>Resistance</strong><small>Lifting and strength work</small></div>{dayField('Resistance days per week', 'resistance_days_per_week')}{context.resistance_days_per_week > 0 && minuteField('Resistance minutes per week', 'resistance_minutes_per_week', 1680)}</div>
      <div className="training-row"><div className="training-row-title"><strong>Cardio</strong><small>Continuous aerobic work</small></div>{dayField('Cardio days per week', 'cardio_days_per_week')}{context.cardio_days_per_week > 0 && <>{minuteField('Cardio minutes per week', 'cardio_minutes_per_week', 2100)}{intensityField('Cardio intensity', 'cardio_intensity')}</>}</div>
      <div className="training-row"><div className="training-row-title"><strong>Sport</strong><small>Games or intermittent activity</small></div>{dayField('Sport days per week', 'sport_days_per_week')}{context.sport_days_per_week > 0 && <>{minuteField('Sport minutes per week', 'sport_minutes_per_week', 2100)}{intensityField('Sport intensity', 'sport_intensity')}</>}</div>
    </div>
  </SectionCard>
}
