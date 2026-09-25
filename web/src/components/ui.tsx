import type { ReactNode } from 'react'

export function StepHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="step-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div><p>{description}</p></header>
}

export function SectionCard({ title, description, children, className = '' }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return <section className={`section-card ${className}`.trim()}>{title && <div className="card-heading"><h2>{title}</h2>{description && <p>{description}</p>}</div>}{children}</section>
}

export function FieldGroup({ legend, children }: { legend: string; children: ReactNode }) {
  return <fieldset className="field-group"><legend>{legend}</legend><div className="field-grid">{children}</div></fieldset>
}

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'danger' }) {
  return <span className={`status-badge ${tone}`}>{children}</span>
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' | 'danger' }) {
  return <div className={`notice-card ${tone}`}>{children}</div>
}

export function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>
}

export function ActionBar({ children }: { children: ReactNode }) {
  return <div className="action-bar">{children}</div>
}
