import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { TrainingContext } from './TrainingContext'
import type { TrainingContext as TrainingContextValue } from '../types'

const initial: TrainingContextValue = {
  occupation_activity: 'mostly_seated',
  primary_training_focus: 'general',
  resistance_days_per_week: 0,
  resistance_minutes_per_week: 0,
  cardio_days_per_week: 0,
  cardio_minutes_per_week: 0,
  sport_days_per_week: 0,
  sport_minutes_per_week: 0,
  cardio_intensity: null,
  sport_intensity: null,
  typical_daily_steps: null,
}

function Harness() {
  const [value, setValue] = useState(initial)
  return <><TrainingContext context={value} onChange={setValue} /><output data-testid="context">{JSON.stringify(value)}</output></>
}

function context(): TrainingContextValue {
  return JSON.parse(screen.getByTestId('context').textContent || '{}') as TrainingContextValue
}

describe('training context form', () => {
  it('shows focus choices, zero days, and unknown optional steps without inactive details', () => {
    render(<Harness />)
    expect(screen.getByRole('group', { name: 'Primary training focus' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'General fitness' })).toBeChecked()
    expect(screen.getByLabelText('Resistance days per week')).toHaveValue(0)
    expect(screen.getByLabelText('Typical daily steps')).toHaveValue(null)
    expect(context().typical_daily_steps).toBeNull()
    expect(screen.queryByLabelText('Cardio minutes per week')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Sport intensity')).not.toBeInTheDocument()
  })

  it('serializes focus, occupation, explicit zero steps, and all active training details', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('radio', { name: 'Resistance' }))
    fireEvent.change(screen.getByLabelText('Occupation activity'), { target: { value: 'mixed' } })
    fireEvent.change(screen.getByLabelText('Typical daily steps'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Resistance days per week'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Resistance minutes per week'), { target: { value: '270' } })
    fireEvent.change(screen.getByLabelText('Cardio days per week'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Cardio minutes per week'), { target: { value: '90' } })
    fireEvent.change(screen.getByLabelText('Cardio intensity'), { target: { value: 'moderate' } })
    fireEvent.change(screen.getByLabelText('Sport days per week'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Sport minutes per week'), { target: { value: '60' } })
    fireEvent.change(screen.getByLabelText('Sport intensity'), { target: { value: 'vigorous' } })
    expect(context()).toEqual({ ...initial, occupation_activity: 'mixed', primary_training_focus: 'resistance', typical_daily_steps: 0, resistance_days_per_week: 4, resistance_minutes_per_week: 270, cardio_days_per_week: 3, cardio_minutes_per_week: 90, cardio_intensity: 'moderate', sport_days_per_week: 1, sport_minutes_per_week: 60, sport_intensity: 'vigorous' })
  })

  it('hides and clears minutes and intensity when active days return to zero', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Cardio days per week'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Cardio minutes per week'), { target: { value: '75' } })
    fireEvent.change(screen.getByLabelText('Cardio intensity'), { target: { value: 'low' } })
    fireEvent.change(screen.getByLabelText('Cardio days per week'), { target: { value: '0' } })
    expect(screen.queryByLabelText('Cardio minutes per week')).not.toBeInTheDocument()
    expect(context()).toMatchObject({ cardio_days_per_week: 0, cardio_minutes_per_week: 0, cardio_intensity: null })
  })

  it('keeps invalid day entry visible with an inline error rather than coercing it', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Sport days per week'), { target: { value: '8' } })
    expect(screen.getByLabelText('Sport days per week')).toHaveValue(8)
    expect(screen.getByText('Enter a whole number from 0 to 7.')).toBeInTheDocument()
    expect(context().sport_days_per_week).toBe(0)
  })
})
