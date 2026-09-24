import type { Observation, Profile } from './types'

const weightVariation = [.18, -.07, .11, -.14, .04, .21, -.03, .09, -.12, .06, -.18, .15, -.02, .12, -.09, .03, -.16, .08, -.05, .14, -.11, .02, -.13, .1, -.04, .17, -.08, .05]
const calories = [2380, 2250, 2460, 2320, 2410, 2190, 2510, 2280, 2440, 2350, 2220, 2490, 2310, 2420, 2260, 2470, 2340, 2200, 2530, 2290, 2410, 2240, 2480, 2330, 2450, 2270, 2500, 2360]
const steps = [6400, 8200, 7100, 9300, 7600, 5800, 10200, 6900, 8500, 7400, 6100, 9700, 7800, 8900, 6600, 9400, 7200, 5600, 10800, 7000, 8600, 6300, 9800, 7500, 9100, 6800, 10100, 7900]

/** Fictional, deterministic, complete history centred on the active profile weight. */
export function createFictionalSample(profile: Profile): Observation[] {
  return Array.from({ length: 28 }, (_, index): Observation => ({
    observed_on: `2026-01-${String(index + 1).padStart(2, '0')}`,
    body_weight_kg: Number((profile.weight_kg - index * .015 + weightVariation[index]).toFixed(2)),
    energy_intake_kcal: calories[index],
    steps: steps[index],
  }))
}
