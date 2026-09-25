import { useState } from 'react'
import type {
  DietaryPattern,
  FoodCategory,
  FoodConstraint,
  FoodConstraintAction,
  FoodConstraintType,
  NutritionPreferenceProfile,
} from '../types'
import {
  allFoodCategories,
  constraintActions,
  constraintActionLabels,
  constraintTypes,
  constraintTypeLabels,
  dietaryPatterns,
  dietaryPatternLabels,
  foodCategoryGroups,
  foodCategoryLabels,
  parseConstraintAction,
  parseConstraintType,
  parseDietaryPattern,
  parseFoodCategory,
  parsePreferenceLevel,
  parseSelectionMode,
  preferenceLevels,
  preferenceLevelLabels,
} from '../utils/dietary'
import { Notice, SectionCard } from './ui'

type DietaryPreferencesProps = {
  profile: NutritionPreferenceProfile
  validationErrors: readonly string[]
  onChange: (profile: NutritionPreferenceProfile) => void
}

const patternSummaries: Partial<Record<DietaryPattern, string>> = {
  vegetarian: 'Excludes poultry, red meat, fish, and shellfish in the category assessment.',
  vegan: 'Excludes animal meat, fish, shellfish, eggs, and dairy in the category assessment.',
  pescatarian: 'Excludes poultry and red meat while retaining fish and shellfish.',
  halal: 'Pork is excluded. Ingredients, preparation, and certification still require verification.',
  kosher: 'Pork and shellfish are excluded. Ingredients, preparation, and certification still require verification.',
  other: 'No exclusions are inferred automatically; describe the pattern for manual review.',
}

function FoodPreferenceCatalog({ profile, onChange }: Pick<DietaryPreferencesProps, 'profile' | 'onChange'>) {
  const preferenceFor = (category: FoodCategory) => profile.preferences.find(item => item.category === category)?.level ?? ''
  const setPreference = (category: FoodCategory, value: string) => {
    const remaining = profile.preferences.filter(item => item.category !== category)
    const preferences = value === '' ? remaining : [...remaining, { category, level: parsePreferenceLevel(value) }]
    onChange({ ...profile, preferences })
  }

  return <div className="food-groups">{foodCategoryGroups.map((group, index) => <details className="food-group" key={group.label} open={index === 0 ? true : undefined}><summary>{group.label}<span>{group.categories.length} categories</span></summary><div className="food-grid">{group.categories.map(category => <label key={category}>{foodCategoryLabels[category]}<select aria-label={`${foodCategoryLabels[category]} preference`} value={preferenceFor(category)} onChange={event => setPreference(category, event.target.value)}><option value="">Not selected</option>{preferenceLevels.map(level => <option key={level} value={level}>{preferenceLevelLabels[level]}</option>)}</select></label>)}</div></details>)}</div>
}

function ConstraintEditor({ profile, onChange }: Pick<DietaryPreferencesProps, 'profile' | 'onChange'>) {
  const [category, setCategory] = useState<FoodCategory>('poultry')
  const [constraintType, setConstraintType] = useState<FoodConstraintType>('allergy')
  const [action, setAction] = useState<FoodConstraintAction>('exclude')
  const [note, setNote] = useState('')
  const [localError, setLocalError] = useState('')

  const changeType = (value: string) => {
    const next = parseConstraintType(value)
    setConstraintType(next)
    if (next !== 'intolerance') setAction('exclude')
    setLocalError('')
  }
  const addConstraint = () => {
    if (profile.constraints.some(item => item.category === category && item.constraint_type === constraintType)) {
      setLocalError(`${foodCategoryLabels[category]} already has this constraint type.`)
      return
    }
    const next: FoodConstraint = {
      category,
      constraint_type: constraintType,
      action: constraintType === 'intolerance' ? action : 'exclude',
      ...(note.trim() ? { note: note.trim() } : {}),
    }
    onChange({ ...profile, constraints: [...profile.constraints, next] })
    setNote('')
    setLocalError('')
  }
  const removeConstraint = (index: number) => {
    onChange({ ...profile, constraints: profile.constraints.filter((_, itemIndex) => itemIndex !== index) })
    setLocalError('')
  }

  return <SectionCard className="constraint-card" title="Safety and required exclusions" description="Hard constraints override preferences. FitAdapt does not provide medical nutrition therapy."><div className="constraint-form"><label>Food category<select aria-label="Constraint food category" value={category} onChange={event => { setCategory(parseFoodCategory(event.target.value)); setLocalError('') }}>{allFoodCategories.map(item => <option key={item} value={item}>{foodCategoryLabels[item]}</option>)}</select></label><label>Constraint type<select aria-label="Constraint type" value={constraintType} onChange={event => changeType(event.target.value)}>{constraintTypes.map(item => <option key={item} value={item}>{constraintTypeLabels[item]}</option>)}</select></label><label>Action<select aria-label="Constraint action" value={constraintType === 'intolerance' ? action : 'exclude'} disabled={constraintType !== 'intolerance'} onChange={event => setAction(parseConstraintAction(event.target.value))}>{constraintActions.map(item => <option key={item} value={item}>{constraintActionLabels[item]}</option>)}</select><small>{constraintType === 'intolerance' ? 'Choose whether to exclude or limit this category.' : 'This constraint must exclude the category.'}</small></label><label>Optional note<input aria-label="Constraint note" value={note} maxLength={160} onChange={event => setNote(event.target.value)} /></label></div>{localError && <Notice tone="danger"><span role="alert">{localError}</span></Notice>}<button onClick={addConstraint}>Add constraint</button>{profile.constraints.length > 0 && <ul className="constraint-list">{profile.constraints.map((item, index) => <li key={`${item.category}-${item.constraint_type}-${index}`}><div><strong>{foodCategoryLabels[item.category]}</strong><span>{constraintTypeLabels[item.constraint_type]} · {constraintActionLabels[item.action]}{item.note ? ` · ${item.note}` : ''}</span></div><button className="button-quiet danger-text" aria-label={`Remove ${foodCategoryLabels[item.category]} ${constraintTypeLabels[item.constraint_type]} constraint`} onClick={() => removeConstraint(index)}>Remove</button></li>)}</ul>}</SectionCard>
}

export function DietaryPreferences({ profile, validationErrors, onChange }: DietaryPreferencesProps) {
  const acceptedCount = profile.preferences.filter(item => item.level !== 'dislike').length
  const updatePattern = (value: string) => {
    const dietaryPattern = parseDietaryPattern(value)
    onChange({
      ...profile,
      dietary_pattern: dietaryPattern,
      other_description: dietaryPattern === 'other' ? profile.other_description ?? '' : undefined,
    })
  }

  return <div className="dietary-onboarding"><SectionCard title="Eating pattern" description="Patterns provide conservative category-level exclusions. They are not certifications or medical advice."><fieldset className="choice-fieldset"><legend>Which pattern best describes how you eat?</legend><div className="choice-grid pattern-grid">{dietaryPatterns.map(pattern => <label className={`choice-card ${profile.dietary_pattern === pattern ? 'selected' : ''}`} key={pattern}><input type="radio" name="dietary-pattern" value={pattern} checked={profile.dietary_pattern === pattern} onChange={event => updatePattern(event.target.value)} /><span><strong>{dietaryPatternLabels[pattern]}</strong>{patternSummaries[pattern] && <small>{patternSummaries[pattern]}</small>}</span></label>)}</div></fieldset>{profile.dietary_pattern === 'other' && <label className="other-pattern">Describe your dietary pattern<textarea aria-label="Other dietary pattern description" value={profile.other_description ?? ''} onChange={event => onChange({ ...profile, other_description: event.target.value })} /><small>Required. No exclusions are inferred from free text.</small></label>}{profile.dietary_pattern === 'halal' || profile.dietary_pattern === 'kosher' ? <Notice tone="warning">FitAdapt does not verify ingredients, preparation methods, facilities, or certification. Review those details independently.</Notice> : null}</SectionCard><SectionCard title="Food flexibility" description="Choose whether most policy-allowed categories are available to you or explicitly select your food pool."><fieldset className="choice-fieldset"><legend>How should FitAdapt interpret unspecified categories?</legend><div className="choice-grid mode-grid"><label className={`choice-card ${profile.selection_mode === 'broad' ? 'selected' : ''}`}><input type="radio" name="selection-mode" value="broad" checked={profile.selection_mode === 'broad'} onChange={event => onChange({ ...profile, selection_mode: parseSelectionMode(event.target.value) })} /><span><strong>I eat most foods</strong><small>Generally accept categories unless a pattern or constraint removes them.</small></span></label><label className={`choice-card ${profile.selection_mode === 'selected' ? 'selected' : ''}`}><input type="radio" name="selection-mode" value="selected" checked={profile.selection_mode === 'selected'} onChange={event => onChange({ ...profile, selection_mode: parseSelectionMode(event.target.value) })} /><span><strong>Let me choose foods</strong><small>Only Okay, Like, and Favorite categories count as accepted.</small></span></label></div></fieldset>{profile.selection_mode === 'broad' ? <details className="preference-disclosure"><summary>Fine-tune preferences</summary><p>Optional preferences do not override dietary patterns or safety constraints.</p><FoodPreferenceCatalog profile={profile} onChange={onChange} /></details> : <><Notice tone={acceptedCount === 0 ? 'warning' : 'info'}>{acceptedCount === 0 ? 'No accepted categories yet. Mark at least one category Okay, Like, or Favorite.' : `${acceptedCount} categories currently count as accepted.`}</Notice><FoodPreferenceCatalog profile={profile} onChange={onChange} /></>}</SectionCard><ConstraintEditor profile={profile} onChange={onChange} />{validationErrors.length > 0 && <Notice tone="danger"><div role="alert"><strong>Review the Nutrition stage:</strong><ul>{validationErrors.map(error => <li key={error}>{error}</li>)}</ul></div></Notice>}</div>
}
