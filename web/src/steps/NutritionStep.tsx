import { DietaryPreferences } from '../components/DietaryPreferences'
import { ActionBar, NumberField, SectionCard, StepHeader } from '../components/ui'
import type { MacroStrategy, NutritionPreferenceProfile, NutritionPreferences } from '../types'
import { macroStrategies, parseMacroStrategy, strategyCopy, strategyLabels } from '../utils/presentation'

export function NutritionStep({ preferences, dietaryProfile, dietaryErrors, onStrategy, onCustom, onDietaryProfile, onBack, onContinue }: { preferences: NutritionPreferences; dietaryProfile: NutritionPreferenceProfile; dietaryErrors: readonly string[]; onStrategy: (strategy: MacroStrategy) => void; onCustom: (updates: Partial<NutritionPreferences>) => void; onDietaryProfile: (profile: NutritionPreferenceProfile) => void; onBack: () => void; onContinue: () => void }) {
  const protein = preferences.custom_protein_g_per_kg
  const fat = preferences.custom_fat_percentage
  const proteinError = preferences.macro_strategy === 'custom' && (protein == null || !Number.isFinite(protein) || protein < 1.2 || protein > 2.4) ? 'Use 1.2–2.4 g/kg.' : undefined
  const fatError = preferences.macro_strategy === 'custom' && (fat == null || !Number.isFinite(fat) || fat < 0.2 || fat > 0.4) ? 'Use 20–40%.' : undefined
  return <>
    <StepHeader eyebrow="Step 2 of 5" title="Shape your nutrition plan" description="Choose macro allocation, an eating pattern, and the foods that fit your life." />
    <SectionCard title="Macro approach" description="Sets macro allocation, not TDEE or the selected calorie target.">
      <label className="form-field field-medium"><span className="form-field-label">Macro strategy</span><select aria-label="Macro strategy" value={preferences.macro_strategy} onChange={event => onStrategy(parseMacroStrategy(event.target.value))}>{macroStrategies.map(strategy => <option key={strategy} value={strategy}>{strategyLabels[strategy]}</option>)}</select></label>
      <p className="strategy-copy">{strategyCopy[preferences.macro_strategy]}</p>
      {preferences.macro_strategy === 'custom' && <div className="form-grid custom-fields">
        <NumberField label="Protein grams per kilogram" value={protein ?? ''} onChange={(next) => onCustom({ custom_protein_g_per_kg: next === '' ? null : Number(next) })} unit="g/kg" min={1.2} max={2.4} step="any" error={proteinError} />
        <NumberField label="Fat percentage of calories" value={fat == null ? '' : fat * 100} onChange={(next) => onCustom({ custom_fat_percentage: next === '' ? null : Number(next) / 100 })} unit="%" min={20} max={40} step="any" error={fatError} />
      </div>}
      <p className="form-context">Macro grams can change with the calorie target. Food preferences inform flexibility, not calorie math.</p>
    </SectionCard>
    <DietaryPreferences profile={dietaryProfile} validationErrors={dietaryErrors} onChange={onDietaryProfile} />
    <ActionBar><button className="button-secondary" onClick={onBack}>Back to profile</button><button onClick={onContinue}>Continue to history</button></ActionBar>
  </>
}
