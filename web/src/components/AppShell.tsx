import type { KeyboardEvent, ReactNode } from 'react'
import { JOURNEY, type JourneyState, type JourneyStep } from '../utils/journey'
import { StatusBadge } from './ui'

function BrandHeader({ onLoadDemo }: { onLoadDemo: () => void }) {
  return <header className="brand-header"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true">FA</span><div><strong>FitAdapt</strong><span>Transparent fitness intelligence</span></div></div><div className="brand-actions"><StatusBadge tone="success">Session only</StatusBadge><button className="button-quiet" onClick={onLoadDemo}>Load demo</button></div></header>
}

function JourneyNavigation({ current, stateFor, onNavigate }: { current: JourneyStep; stateFor: (step: JourneyStep) => JourneyState; onNavigate: (step: JourneyStep) => void }) {
  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
    event.preventDefault()
    const offset = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : -1
    const next = JOURNEY[(index + offset + JOURNEY.length) % JOURNEY.length]
    onNavigate(next.id)
    document.getElementById(`journey-${next.id}`)?.focus()
  }
  return <nav className="journey-nav" aria-label="FitAdapt journey"><ol>{JOURNEY.map((step, index) => { const state = stateFor(step.id); return <li key={step.id}><button id={`journey-${step.id}`} aria-current={current === step.id ? 'step' : undefined} onClick={() => onNavigate(step.id)} onKeyDown={event => move(event, index)}><span className="journey-number">{step.number}</span><span className="journey-copy"><strong>{step.label}</strong><small>{step.description}</small></span><span className={`journey-state ${state.replace(' ', '-')}`}>{state}</span></button></li> })}</ol></nav>
}

export function AppShell({ current, stateFor, onNavigate, onLoadDemo, children }: { current: JourneyStep; stateFor: (step: JourneyStep) => JourneyState; onNavigate: (step: JourneyStep) => void; onLoadDemo: () => void; children: ReactNode }) {
  return <div className="app-frame"><BrandHeader onLoadDemo={onLoadDemo} /><div className="app-layout"><aside><JourneyNavigation current={current} stateFor={stateFor} onNavigate={onNavigate} /><p className="privacy-note"><strong>Your session stays here.</strong> FitAdapt sends data to the configured API only when you analyze. Nothing is saved remotely by this client.</p></aside><main className="stage-content" aria-live="polite">{children}</main></div></div>
}
