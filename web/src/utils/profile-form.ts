import type { Profile, TrainingContext } from '../types'

export type ProfileNumberKey = 'age_years' | 'height_cm' | 'weight_kg' | 'requested_weekly_change_kg'
export type ProfileDrafts = Partial<Record<ProfileNumberKey, string>>
export type TrainingNumberKey = 'resistance_days_per_week' | 'resistance_minutes_per_week' | 'cardio_days_per_week' | 'cardio_minutes_per_week' | 'sport_days_per_week' | 'sport_minutes_per_week' | 'typical_daily_steps'
export type TrainingDrafts = Partial<Record<TrainingNumberKey, string>>

export function profileFormErrors(profile: Profile, drafts: ProfileDrafts): ProfileDrafts {
  const number = (key: ProfileNumberKey) => drafts[key] === undefined ? profile[key] : drafts[key] === '' ? NaN : Number(drafts[key])
  const errors: ProfileDrafts = {}
  const age = number('age_years')
  const height = number('height_cm')
  const weight = number('weight_kg')
  const change = number('requested_weekly_change_kg')
  if (!Number.isInteger(age) || age < 18 || age > 80) errors.age_years = 'Enter an age from 18 to 80 years.'
  if (!Number.isFinite(height) || height < 100 || height > 250) errors.height_cm = 'Enter a height from 100 to 250 cm.'
  if (!Number.isFinite(weight) || weight < 30 || weight > 300) errors.weight_kg = 'Enter a weight from 30 to 300 kg.'
  if (!Number.isFinite(change)) errors.requested_weekly_change_kg = 'Enter a weekly change.'
  else if (profile.goal === 'cut' && (change >= 0 || change < -weight * 0.0075)) errors.requested_weekly_change_kg = 'Use a negative change up to 0.75% of body weight per week.'
  else if (profile.goal === 'gain' && (change <= 0 || change > weight * 0.005)) errors.requested_weekly_change_kg = 'Use a positive change up to 0.5% of body weight per week.'
  else if (profile.goal === 'maintain' && change !== 0) errors.requested_weekly_change_kg = 'Maintenance requires 0 kg/week.'
  return errors
}

export function trainingFormHasErrors(context: TrainingContext, drafts: TrainingDrafts): boolean {
  for (const [key, text] of Object.entries(drafts) as [TrainingNumberKey, string][]) {
    if (key === 'typical_daily_steps' && text === '') continue
    const value = text === '' ? NaN : Number(text)
    const maximum = key === 'typical_daily_steps' ? 100000 : key.endsWith('days_per_week') ? 7 : key === 'resistance_minutes_per_week' ? 1680 : 2100
    if (!Number.isFinite(value) || value < 0 || value > maximum || ((key.endsWith('days_per_week') || key === 'typical_daily_steps') && !Number.isInteger(value))) return true
  }
  return (context.resistance_days_per_week > 0 && context.resistance_minutes_per_week <= 0)
    || (context.cardio_days_per_week > 0 && (context.cardio_minutes_per_week <= 0 || context.cardio_intensity == null))
    || (context.sport_days_per_week > 0 && (context.sport_minutes_per_week <= 0 || context.sport_intensity == null))
}
