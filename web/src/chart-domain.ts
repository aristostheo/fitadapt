/** Return a visually useful domain without inventing values for null gaps. */
export function paddedDomain(
  points: readonly object[],
  ...keys: readonly string[]
): [number, number] {
  const values = points.flatMap(point => keys.map(key => (point as Record<string, unknown>)[key])).filter(
    (value): value is number => typeof value === 'number' && Number.isFinite(value),
  )
  if (values.length === 0) return [0, 1]

  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const range = maximum - minimum
  const padding = range === 0 ? Math.max(Math.abs(minimum) * 0.02, 1) : range * 0.1
  return [minimum - padding, maximum + padding]
}
