import { describe, expect, it } from 'vitest'
import { paddedDomain } from './chart-domain'

describe('chart domains', () => {
  it('pads normal values relative to their observed range', () => {
    expect(paddedDomain([{ weight: 92.1 }, { weight: 90.5 }], 'weight')).toEqual([90.34, 92.25999999999999])
  })

  it('adds safe visual padding around a constant series', () => {
    expect(paddedDomain([{ value: 100 }, { value: 100 }], 'value')).toEqual([98, 102])
  })

  it('adds safe visual padding around a single value', () => {
    expect(paddedDomain([{ value: 2500 }], 'value')).toEqual([2450, 2550])
  })

  it('ignores null gaps and returns a safe domain when no finite values exist', () => {
    expect(paddedDomain([{ value: null }, { value: 10 }, { value: null }], 'value')).toEqual([9, 11])
    expect(paddedDomain([{ value: null }, {}], 'value')).toEqual([0, 1])
  })
})
