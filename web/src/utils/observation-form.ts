import type { Observation } from '../types'

type NumericObservationKey = Exclude<keyof Observation, 'observed_on'>

export function observationFormErrors(draft: Observation): Partial<Record<NumericObservationKey, string>> {
  const errors: Partial<Record<NumericObservationKey, string>> = {}
  const limits: Partial<Record<NumericObservationKey, [number, number | null, boolean]>> = {
    body_weight_kg: [30, 300, false],
    energy_intake_kcal: [0, 10000, false],
    steps: [0, null, true],
    strength_training_minutes: [0, 1440, false],
    cardio_minutes: [0, 1440, false],
    sleep_hours: [0, 24, false],
    hunger_rating: [1, 5, true],
    energy_rating: [1, 5, true],
  }
  for (const [name, value] of Object.entries(draft)) {
    if (name === 'observed_on' || value == null) continue
    const key = name as NumericObservationKey
    const [minimum, maximum, integer] = limits[key] ?? [0, null, false]
    if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || (maximum !== null && value > maximum) || (integer && !Number.isInteger(value))) {
      errors[key] = `Enter ${integer ? 'a whole number' : 'a value'} ${maximum === null ? `of at least ${minimum}` : `from ${minimum} to ${maximum}`}.`
    }
  }
  return errors
}
