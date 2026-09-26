import type { TrainingContext as TrainingContextValue } from "../types";
import { Notice, SectionCard } from "./ui";

type Props = {
  context: TrainingContextValue;
  onChange: (context: TrainingContextValue) => void;
};

const occupationLabels = {
  mostly_seated: "Mostly seated",
  mixed: "Mixed",
  mostly_on_feet: "Mostly on feet",
  physically_demanding: "Physically demanding",
} as const;
const focusLabels = {
  general: "General fitness",
  resistance: "Resistance",
  endurance: "Endurance",
  intermittent_sport: "Intermittent sport",
  mixed: "Mixed training",
} as const;
const intensityLabels = {
  low: "Low",
  moderate: "Moderate",
  vigorous: "Vigorous",
} as const;

export function TrainingContext({ context, onChange }: Props) {
  const update = (patch: Partial<TrainingContextValue>) =>
    onChange({ ...context, ...patch });
  return (
    <SectionCard
      title="Training and performance context"
      description="A little context helps FitAdapt describe training demand. It does not add workout calories or change your current plan."
    >
      <div className="field-grid">
        <label>
          Occupation activity
          <select
            aria-label="Occupation activity"
            value={context.occupation_activity}
            onChange={(event) =>
              update({
                occupation_activity: event.target
                  .value as TrainingContextValue["occupation_activity"],
              })
            }
          >
            {Object.entries(occupationLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Primary training focus
          <select
            aria-label="Primary training focus"
            value={context.primary_training_focus}
            onChange={(event) =>
              update({
                primary_training_focus: event.target
                  .value as TrainingContextValue["primary_training_focus"],
              })
            }
          >
            {Object.entries(focusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="field-grid training-quick-fields">
        <label>
          Resistance days per week
          <input
            aria-label="Resistance days per week"
            type="number"
            min="0"
            max="7"
            value={context.resistance_days_per_week}
            onChange={(event) =>
              update({ resistance_days_per_week: Number(event.target.value) })
            }
          />
        </label>
        <label>
          Cardio days per week
          <input
            aria-label="Cardio days per week"
            type="number"
            min="0"
            max="7"
            value={context.cardio_days_per_week}
            onChange={(event) =>
              update({ cardio_days_per_week: Number(event.target.value) })
            }
          />
        </label>
        <label>
          Sport days per week
          <input
            aria-label="Sport days per week"
            type="number"
            min="0"
            max="7"
            value={context.sport_days_per_week}
            onChange={(event) =>
              update({ sport_days_per_week: Number(event.target.value) })
            }
          />
        </label>
      </div>
      <details className="training-details">
        <summary>More training details</summary>
        <div className="field-grid">
          <label>
            Typical daily steps{" "}
            <span className="supporting-copy">Optional</span>
            <input
              aria-label="Typical daily steps"
              type="number"
              min="0"
              max="100000"
              placeholder="Unknown"
              value={context.typical_daily_steps ?? ""}
              onChange={(event) =>
                update({
                  typical_daily_steps:
                    event.target.value === ""
                      ? null
                      : Number(event.target.value),
                })
              }
            />
          </label>
          <label>
            Resistance minutes per week
            <input
              aria-label="Resistance minutes per week"
              type="number"
              min="0"
              max="1680"
              value={context.resistance_minutes_per_week}
              onChange={(event) =>
                update({
                  resistance_minutes_per_week: Number(event.target.value),
                })
              }
            />
          </label>
          <label>
            Cardio minutes per week
            <input
              aria-label="Cardio minutes per week"
              type="number"
              min="0"
              max="2100"
              value={context.cardio_minutes_per_week}
              onChange={(event) =>
                update({ cardio_minutes_per_week: Number(event.target.value) })
              }
            />
            <select
              aria-label="Cardio intensity"
              value={context.cardio_intensity ?? ""}
              onChange={(event) =>
                update({
                  cardio_intensity:
                    event.target.value === ""
                      ? null
                      : (event.target
                          .value as TrainingContextValue["cardio_intensity"]),
                })
              }
            >
              <option value="">Intensity unknown</option>
              {Object.entries(intensityLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sport minutes per week
            <input
              aria-label="Sport minutes per week"
              type="number"
              min="0"
              max="2100"
              value={context.sport_minutes_per_week}
              onChange={(event) =>
                update({ sport_minutes_per_week: Number(event.target.value) })
              }
            />
            <select
              aria-label="Sport intensity"
              value={context.sport_intensity ?? ""}
              onChange={(event) =>
                update({
                  sport_intensity:
                    event.target.value === ""
                      ? null
                      : (event.target
                          .value as TrainingContextValue["sport_intensity"]),
                })
              }
            >
              <option value="">Intensity unknown</option>
              {Object.entries(intensityLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>
      <Notice>
        Energy needs still come from baseline and adaptive TDEE. Training-aware
        macro adjustments are future policy work.
      </Notice>
    </SectionCard>
  );
}
