import type { ChangeEvent, ReactNode } from 'react'

export function StepHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="step-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div><p>{description}</p></header>
}

export function SectionCard({ title, description, children, className = '' }: { title?: string; description?: string; children: ReactNode; className?: string }) {
  return <section className={`section-card ${className}`.trim()}>{title && <div className="card-heading"><h2>{title}</h2>{description && <p>{description}</p>}</div>}{children}</section>
}

export function FieldGroup({ legend, children }: { legend: string; children: ReactNode }) {
  return <fieldset className="field-group"><legend>{legend}</legend><div className="field-grid">{children}</div></fieldset>
}

type NumberFieldProps = {
  label: string
  value: string | number
  onChange: (value: string) => void
  unit?: string
  min?: number
  max?: number
  step?: number | 'any'
  placeholder?: string
  optional?: boolean
  hint?: string
  error?: string
  className?: string
}

export function NumberField({ label, value, onChange, unit, min, max, step, placeholder, optional, hint, error, className = '' }: NumberFieldProps) {
  return <label className={`form-field number-field ${className}`.trim()}>
    <span className="form-field-label">{label}{optional && <span className="optional-tag">Optional</span>}</span>
    <span className={`unit-control ${error ? 'has-error' : ''}`}>
      <input aria-label={label} aria-invalid={error ? true : undefined} type="number" inputMode={step && step !== 1 ? 'decimal' : 'numeric'} min={min} max={max} step={step} placeholder={placeholder} value={value} onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)} />
      {unit && <span className="unit-suffix" aria-hidden="true">{unit}</span>}
    </span>
    {error ? <small className="field-error" role="alert">{error}</small> : hint && <small>{hint}</small>}
  </label>
}

type ChoiceGroupProps<T extends string> = {
  legend: string
  name: string
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (value: T) => void
  compact?: boolean
}

export function ChoiceGroup<T extends string>({ legend, name, value, options, onChange, compact = false }: ChoiceGroupProps<T>) {
  return <fieldset className={`segmented-field ${compact ? 'compact' : ''}`}>
    <legend>{legend}</legend>
    <div className="segmented-options">{options.map((option) => <label key={option.value} className={value === option.value ? 'selected' : ''}>
      <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} />
      <span>{option.label}</span>
    </label>)}</div>
  </fieldset>
}

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'purple' }) {
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
