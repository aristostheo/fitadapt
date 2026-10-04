export type JourneyStep = 'overview' | 'profile' | 'nutrition' | 'history' | 'plan' | 'progress'
export type JourneyState = 'not started' | 'incomplete' | 'ready' | 'current' | 'completed'

export const JOURNEY: readonly {
  id: JourneyStep
  number: string
  label: string
  description: string
}[] = [
  { id: 'overview', number: '00', label: 'Overview', description: 'Engine dashboard' },
  { id: 'profile', number: '01', label: 'Profile', description: 'Body, goal & training' },
  { id: 'nutrition', number: '02', label: 'Nutrition', description: 'Macro strategy' },
  { id: 'history', number: '03', label: 'History', description: 'Daily evidence' },
  { id: 'plan', number: '04', label: 'Plan', description: 'Current guidance' },
  { id: 'progress', number: '05', label: 'Progress', description: 'Trends over time' },
]
