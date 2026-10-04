import { ChoiceGroup, NumberField, SectionCard, StepHeader } from '../components/ui'
import type { Profile } from '../types'
import { numericInput } from '../utils/presentation'

type NumericProfileKey = 'age_years' | 'height_cm' | 'weight_kg' | 'requested_weekly_change_kg'

type Props = {
  profile: Profile
  numericValues?: Partial<Record<NumericProfileKey, string>>
  errors?: Partial<Record<NumericProfileKey, string>>
  onChange: (key: keyof Profile, value: string) => void
}

export function ProfileStep({ profile, numericValues, errors, onChange }: Props) {
  const value = (key: NumericProfileKey) => numericValues?.[key] ?? numericInput(profile[key])

  return <>
    <StepHeader eyebrow="Step 1 of 5" title="Build your profile" description="A few essentials establish your starting estimate. Your history can refine it later." />
    <SectionCard title="The basics" description="These inputs are used by the versioned Mifflin resting-energy equation.">
      <div className="form-grid basics-grid">
        <NumberField label="Age" value={value('age_years')} onChange={(next) => onChange('age_years', next)} unit="years" min={18} max={80} step={1} error={errors?.age_years} />
        <NumberField label="Height (cm)" value={value('height_cm')} onChange={(next) => onChange('height_cm', next)} unit="cm" min={100} max={250} step="any" error={errors?.height_cm} />
        <NumberField label="Weight (kg)" value={value('weight_kg')} onChange={(next) => onChange('weight_kg', next)} unit="kg" min={30} max={300} step="any" error={errors?.weight_kg} />
        <label className="form-field"><span className="form-field-label">Sex used for REE estimate</span><select aria-label="Sex used for REE estimate" value={profile.sex_for_mifflin_equation} onChange={(event) => onChange('sex_for_mifflin_equation', event.target.value)}><option value="male">Male equation</option><option value="female">Female equation</option></select><small>Equation input, not gender identity.</small></label>
      </div>
    </SectionCard>
    <SectionCard title="Your direction" description="Choose a goal and, if changing weight, a signed weekly change.">
      <div className="goal-layout">
        <ChoiceGroup legend="Goal" name="goal" value={profile.goal} options={[{ value: 'cut', label: 'Lose' }, { value: 'maintain', label: 'Maintain' }, { value: 'gain', label: 'Gain' }]} onChange={(next) => onChange('goal', next)} />
        {profile.goal === 'maintain' ? <p className="form-context">Maintenance uses 0 kg/week. Choose Lose or Gain to set a change rate.</p> : <NumberField label="Desired weekly change (kg)" value={value('requested_weekly_change_kg')} onChange={(next) => onChange('requested_weekly_change_kg', next)} unit="kg/week" step="any" error={errors?.requested_weekly_change_kg} hint={profile.goal === 'cut' ? 'Use a negative value for a cut.' : 'Use a positive value for a gain.'} />}
      </div>
    </SectionCard>
    <SectionCard title="Starting activity" description="A population-level assumption until your own observations support an adaptive estimate.">
      <label className="form-field field-medium"><span className="form-field-label">Activity level</span><select aria-label="Activity level" value={profile.activity_level} onChange={(event) => onChange('activity_level', event.target.value)}><option value="sedentary">Mostly sedentary</option><option value="lightly_active">Lightly active</option><option value="moderately_active">Moderately active</option><option value="very_active">Very active</option><option value="extra_active">Extra active</option></select></label>
    </SectionCard>
  </>
}
