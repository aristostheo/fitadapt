import { describe, expect, it } from 'vitest'
import { profileFormErrors, trainingFormHasErrors } from './profile-form'
import type { Profile, TrainingContext } from '../types'

const profile: Profile = { age_years: 30, height_cm: 180, weight_kg: 80, sex_for_mifflin_equation: 'male', activity_level: 'moderately_active', goal: 'maintain', requested_weekly_change_kg: 0 }
const training: TrainingContext = { occupation_activity: 'mostly_seated', primary_training_focus: 'general', resistance_days_per_week: 0, resistance_minutes_per_week: 0, cardio_days_per_week: 0, cardio_minutes_per_week: 0, cardio_intensity: null, sport_days_per_week: 0, sport_minutes_per_week: 0, sport_intensity: null, typical_daily_steps: null }

describe('frontend form gates', () => {
  it('requires profile values and signed goal rates without replacing invalid text with zero', () => {
    expect(profileFormErrors(profile, {})).toEqual({})
    expect(profileFormErrors(profile, { age_years: '' }).age_years).toContain('18 to 80')
    expect(profileFormErrors({ ...profile, goal: 'cut', requested_weekly_change_kg: -0.4 }, {})).toEqual({})
    expect(profileFormErrors({ ...profile, goal: 'cut' }, { requested_weekly_change_kg: '0' }).requested_weekly_change_kg).toContain('negative')
    expect(profileFormErrors({ ...profile, goal: 'gain' }, { requested_weekly_change_kg: '0.5' }).requested_weekly_change_kg).toContain('0.5%')
  })

  it('blocks incomplete active training while accepting zero days and unknown steps', () => {
    expect(trainingFormHasErrors(training, {})).toBe(false)
    expect(trainingFormHasErrors(training, { typical_daily_steps: '' })).toBe(false)
    expect(trainingFormHasErrors(training, { cardio_days_per_week: '8' })).toBe(true)
    expect(trainingFormHasErrors({ ...training, cardio_days_per_week: 2 }, {})).toBe(true)
    expect(trainingFormHasErrors({ ...training, cardio_days_per_week: 2, cardio_minutes_per_week: 90, cardio_intensity: 'moderate' }, {})).toBe(false)
  })
})
