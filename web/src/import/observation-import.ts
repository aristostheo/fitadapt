import Papa from 'papaparse'
import type { Observation } from '../types'

export const MAX_IMPORT_ROWS = 5000
export const CANONICAL_OBSERVATION_FIELDS = ['observed_on', 'body_weight_kg', 'energy_intake_kcal', 'protein_g', 'carbohydrate_g', 'fat_g', 'steps', 'strength_training_minutes', 'cardio_minutes', 'sleep_hours', 'hunger_rating', 'energy_rating'] as const
export const CSV_TEMPLATE_FILENAME = 'fitadapt-observations-template.csv'
export const CSV_TEMPLATE = `${CANONICAL_OBSERVATION_FIELDS.join(',')}\n2026-01-01,75.4,2200,130,250,65,8000,45,0,7.5,3,4\n`

export type ImportFormat = 'json' | 'csv'
export interface ImportRowError { row: number; message: string }
export interface ImportPreview { format: ImportFormat; totalRows: number; validRows: Observation[]; errors: ImportRowError[]; earliestDate: string | null; latestDate: string | null; duplicateDates: string[]; conflictingDates: string[] }

const numericFields = new Set<keyof Observation>(['body_weight_kg', 'energy_intake_kcal', 'protein_g', 'carbohydrate_g', 'fat_g', 'steps', 'strength_training_minutes', 'cardio_minutes', 'sleep_hours', 'hunger_rating', 'energy_rating'])
const integerFields = new Set<keyof Observation>(['steps', 'hunger_rating', 'energy_rating'])
const aliases: Record<string, keyof Observation> = { date: 'observed_on', weight_kg: 'body_weight_kg', calories: 'energy_intake_kcal', calorie_intake_kcal: 'energy_intake_kcal' }

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function validDate(value: string): boolean { const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value); if (!match) return false; const date = new Date(`${value}T00:00:00Z`); return date.getUTCFullYear() === Number(match[1]) && date.getUTCMonth() + 1 === Number(match[2]) && date.getUTCDate() === Number(match[3]) }
function limits(key: keyof Observation, value: number): string | null {
  if (key === 'body_weight_kg' && (value < 30 || value > 300)) return 'Body weight must be 30–300 kg.'
  if ((key === 'strength_training_minutes' || key === 'cardio_minutes') && (value < 0 || value > 1440)) return 'Training minutes must be 0–1440.'
  if (key === 'sleep_hours' && (value < 0 || value > 24)) return 'Sleep must be 0–24 hours.'
  if ((key === 'hunger_rating' || key === 'energy_rating') && (value < 1 || value > 5)) return 'Ratings must be 1–5.'
  if (key !== 'body_weight_kg' && value < 0) return 'This value cannot be negative.'
  return null
}

function parseNumber(value: unknown, key: keyof Observation, csv: boolean): number | null | string {
  if (value === null || value === undefined || (csv && value === '')) return null
  if (typeof value === 'boolean') return 'Boolean values are not valid numbers.'
  if (typeof value === 'string' && !csv) return 'JSON numeric values must be numbers, not strings.'
  const number = csv && typeof value === 'string' ? Number(value) : value
  if (typeof number !== 'number' || !Number.isFinite(number)) return 'A finite numeric value is required.'
  if (integerFields.has(key) && !Number.isInteger(number)) return 'This field must be an integer.'
  return limits(key, number) || number
}

function normalizeRow(source: Record<string, unknown>, row: number, csv: boolean): { observation?: Observation; errors: ImportRowError[] } {
  const errors: ImportRowError[] = []
  const normalized: Record<string, unknown> = {}
  for (const [originalKey, value] of Object.entries(source)) {
    const key = aliases[originalKey] || originalKey
    if (!CANONICAL_OBSERVATION_FIELDS.includes(key as typeof CANONICAL_OBSERVATION_FIELDS[number])) { errors.push({ row, message: `Unknown field '${originalKey}'.` }); continue }
    if (key in normalized) { errors.push({ row, message: `Duplicate field '${key}'.` }); continue }
    normalized[key] = value
  }
  if (typeof normalized.observed_on !== 'string' || !validDate(normalized.observed_on)) errors.push({ row, message: 'observed_on must be an ISO calendar date (YYYY-MM-DD).' })
  const observation: Observation = { observed_on: typeof normalized.observed_on === 'string' ? normalized.observed_on : '' }
  for (const key of numericFields) {
    const value = parseNumber(normalized[key], key, csv)
    if (typeof value === 'string') errors.push({ row, message: `${key}: ${value}` })
    else (observation as unknown as Record<string, unknown>)[key] = value
  }
  if (Array.from(numericFields).every(key => observation[key] === null)) errors.push({ row, message: 'At least one measurement is required.' })
  return errors.length ? { errors } : { observation, errors }
}

function finalize(format: ImportFormat, totalRows: number, rows: { source: Record<string, unknown>; row: number }[], existingDates: readonly string[]): ImportPreview {
  const errors: ImportRowError[] = []
  if (totalRows > MAX_IMPORT_ROWS) errors.push({ row: 0, message: `Imports are limited to ${MAX_IMPORT_ROWS} rows.` })
  const parsed = rows.slice(0, MAX_IMPORT_ROWS).map(item => normalizeRow(item.source, item.row, format === 'csv'))
  errors.push(...parsed.flatMap(item => item.errors))
  const candidates = parsed.flatMap(item => item.observation ? [item.observation] : [])
  const counts = new Map<string, number>()
  for (const item of candidates) counts.set(item.observed_on, (counts.get(item.observed_on) || 0) + 1)
  const duplicateDates = [...counts].filter(([, count]) => count > 1).map(([date]) => date).sort()
  for (const date of duplicateDates) errors.push({ row: 0, message: `Duplicate import date ${date}.` })
  const validRows = candidates.filter(item => !duplicateDates.includes(item.observed_on)).sort((a, b) => a.observed_on.localeCompare(b.observed_on))
  const conflictingDates = validRows.filter(item => existingDates.includes(item.observed_on)).map(item => item.observed_on)
  const dates = validRows.map(item => item.observed_on)
  return { format, totalRows, validRows, errors, earliestDate: dates[0] || null, latestDate: dates.at(-1) || null, duplicateDates, conflictingDates }
}

export function previewObservationImport(text: string, format: ImportFormat, existingDates: readonly string[] = []): ImportPreview {
  if (format === 'json') {
    try {
      const value: unknown = JSON.parse(text)
      const items = Array.isArray(value) ? value : isRecord(value) && Array.isArray(value.observations) ? value.observations : null
      if (!items) return { format, totalRows: 0, validRows: [], errors: [{ row: 0, message: 'JSON must be an observation array or an object containing an observations array.' }], earliestDate: null, latestDate: null, duplicateDates: [], conflictingDates: [] }
      const rows = items.map((item, index) => ({ source: isRecord(item) ? item : {}, row: index + 1 }))
      const preview = finalize(format, items.length, rows, existingDates)
      if (items.some(item => !isRecord(item))) preview.errors.push({ row: 0, message: 'JSON observations must be objects.' })
      return preview
    } catch { return { format, totalRows: 0, validRows: [], errors: [{ row: 0, message: 'Invalid JSON.' }], earliestDate: null, latestDate: null, duplicateDates: [], conflictingDates: [] } }
  }
  const parsed = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: 'greedy' })
  const rows = parsed.data.map((source, index) => ({ source, row: index + 2 }))
  const preview = finalize(format, parsed.data.length, rows, existingDates)
  for (const error of parsed.errors) preview.errors.push({ row: (error.row ?? 0) + 2, message: error.message })
  return preview
}
