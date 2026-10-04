import { useEffect, useState, type KeyboardEvent, type ReactNode } from 'react'
import { JOURNEY, type JourneyState, type JourneyStep } from '../utils/journey'
import { StatusBadge } from './ui'

type Theme = 'light' | 'dark'
const themeKey = 'fitadapt-theme'

function initialTheme(): Theme {
  try {
    return window.localStorage.getItem(themeKey) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function BrandHeader({ onLoadDemo, theme, onTheme }: {
  onLoadDemo: () => void
  theme: Theme
  onTheme: () => void
}) {
  return (
    <header className="brand-header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">F</span>
        <div><strong>FitAdapt</strong><span>Adaptive Diet Intelligence</span></div>
      </div>
      <div className="brand-actions">
        <StatusBadge tone="purple">Engine demo</StatusBadge>
        <button
          className="button-quiet theme-toggle"
          type="button"
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          onClick={onTheme}
        >
          {theme === 'light' ? '◐ Dark' : '◑ Light'}
        </button>
        <button className="button-secondary" type="button" onClick={onLoadDemo}>
          Load demo
        </button>
      </div>
    </header>
  )
}

function JourneyNavigation({ current, stateFor, onNavigate }: {
  current: JourneyStep
  stateFor: (step: JourneyStep) => JourneyState
  onNavigate: (step: JourneyStep) => void
}) {
  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
    event.preventDefault()
    const offset = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : -1
    const next = JOURNEY[(index + offset + JOURNEY.length) % JOURNEY.length]
    onNavigate(next.id)
    document.getElementById(`journey-${next.id}`)?.focus()
  }

  return (
    <nav className="journey-nav" aria-label="FitAdapt sections">
      <p className="nav-caption">Workspace</p>
      <ol>
        {JOURNEY.map((step, index) => {
          const state = stateFor(step.id)
          return (
            <li key={step.id}>
              <button
                id={`journey-${step.id}`}
                aria-current={current === step.id ? 'step' : undefined}
                onClick={() => onNavigate(step.id)}
                onKeyDown={event => move(event, index)}
              >
                <span className="journey-number">{step.number}</span>
                <span className="journey-copy">
                  <strong>{step.label}</strong><small>{step.description}</small>
                </span>
                <span className={`journey-state ${state.replace(' ', '-')}`}>{state}</span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function AppShell({ current, stateFor, onNavigate, onLoadDemo, children }: {
  current: JourneyStep
  stateFor: (step: JourneyStep) => JourneyState
  onNavigate: (step: JourneyStep) => void
  onLoadDemo: () => void
  children: ReactNode
}) {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      window.localStorage.setItem(themeKey, theme)
    } catch {
      // Private browsing can disable storage; the in-memory theme still works.
    }
  }, [theme])

  return (
    <div className="app-frame">
      <BrandHeader
        onLoadDemo={onLoadDemo}
        theme={theme}
        onTheme={() => setTheme(theme === 'light' ? 'dark' : 'light')}
      />
      <div className="app-layout">
        <aside>
          <JourneyNavigation current={current} stateFor={stateFor} onNavigate={onNavigate} />
          <p className="privacy-note">
            <strong>Private by design</strong> Session inputs are sent only to your
            configured API when you analyze. This demo does not save your profile.
          </p>
        </aside>
        <main className="stage-content" id="main-content" aria-live="polite">
          {children}
        </main>
      </div>
    </div>
  )
}
