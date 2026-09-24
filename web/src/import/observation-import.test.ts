import { describe, expect, it } from 'vitest'
import { CANONICAL_OBSERVATION_FIELDS, CSV_TEMPLATE, MAX_IMPORT_ROWS, previewObservationImport } from './observation-import'

describe('historical observation import', () => {
  it('previews JSON arrays and wrapped observations with zero preserved', () => {
    const array = previewObservationImport('[{"observed_on":"2026-01-01","steps":0}]', 'json')
    const wrapped = previewObservationImport('{"observations":[{"observed_on":"2026-01-02","energy_intake_kcal":0}]}', 'json')
    expect(array.validRows[0].steps).toBe(0)
    expect(wrapped.validRows[0].energy_intake_kcal).toBe(0)
  })

  it('parses CSV blank values as null and string zero as numeric zero', () => {
    const preview = previewObservationImport('observed_on,body_weight_kg,energy_intake_kcal,steps\n2026-01-01,,0,5000', 'csv')
    expect(preview.validRows[0]).toMatchObject({ body_weight_kg: null, energy_intake_kcal: 0, steps: 5000 })
  })

  it('rejects JSON numeric strings, invalid dates, unknown fields, and empty rows with row numbers', () => {
    const numeric = previewObservationImport('[{"observed_on":"2026-01-01","steps":"0"}]', 'json')
    const invalid = previewObservationImport('[{"observed_on":"2026-02-30","steps":1},{"observed_on":"2026-01-02","unknown":1}]', 'json')
    const empty = previewObservationImport('[{"observed_on":"2026-01-03"}]', 'json')
    expect(numeric.errors[0]).toMatchObject({ row: 1 })
    expect(invalid.errors.map(item => item.message).join(' ')).toContain('Unknown field')
    expect(empty.errors.map(item => item.message).join(' ')).toContain('At least one measurement')
  })

  it('rejects a JSON root that is not an observation array or wrapper', () => {
    const preview = previewObservationImport('{"observed_on":"2026-01-01"}', 'json')
    expect(preview.validRows).toEqual([])
    expect(preview.errors[0].message).toContain('observation array')
  })

  it('detects import duplicates and conflicts with current history', () => {
    const preview = previewObservationImport('[{"observed_on":"2026-01-01","steps":1},{"observed_on":"2026-01-01","steps":2},{"observed_on":"2026-01-02","steps":3}]', 'json', ['2026-01-02'])
    expect(preview.duplicateDates).toEqual(['2026-01-01'])
    expect(preview.conflictingDates).toEqual(['2026-01-02'])
  })

  it('sorts valid rows and rejects files over the centralized safe limit', () => {
    const sorted = previewObservationImport('[{"observed_on":"2026-01-02","steps":1},{"observed_on":"2026-01-01","steps":1}]', 'json')
    const overLimit = previewObservationImport(JSON.stringify(Array.from({ length: MAX_IMPORT_ROWS + 1 }, (_, index) => ({ observed_on: `2026-01-${String(index % 28 + 1).padStart(2, '0')}`, steps: 1 }))), 'json')
    expect(sorted.validRows.map(item => item.observed_on)).toEqual(['2026-01-01', '2026-01-02'])
    expect(overLimit.errors.map(item => item.message).join(' ')).toContain(`${MAX_IMPORT_ROWS} rows`)
  })

  it('ships a fictional CSV template with every canonical header', () => {
    expect(CSV_TEMPLATE.split('\n')[0].split(',')).toEqual(CANONICAL_OBSERVATION_FIELDS)
    expect(CSV_TEMPLATE).toContain('2026-01-01')
  })
})
