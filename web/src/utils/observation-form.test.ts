import { describe, expect, it } from 'vitest'
import { observationFormErrors } from './observation-form'

describe('daily logging validation', () => {
  it('distinguishes missing from zero and preserves domain bounds', () => {
    expect(observationFormErrors({ observed_on: '2026-01-01', steps: null, energy_intake_kcal: 0 })).toEqual({})
    expect(observationFormErrors({ observed_on: '2026-01-01', steps: 0 })).toEqual({})
    expect(observationFormErrors({ observed_on: '2026-01-01', steps: -1, body_weight_kg: 20, hunger_rating: 0 })).toMatchObject({ steps: expect.any(String), body_weight_kg: expect.any(String), hunger_rating: expect.any(String) })
  })
})
