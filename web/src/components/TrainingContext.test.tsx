import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { TrainingContext } from "./TrainingContext";
import type { TrainingContext as TrainingContextValue } from "../types";

const initial: TrainingContextValue = {
  occupation_activity: "mostly_seated",
  primary_training_focus: "general",
  resistance_days_per_week: 0,
  resistance_minutes_per_week: 0,
  cardio_days_per_week: 0,
  cardio_minutes_per_week: 0,
  sport_days_per_week: 0,
  sport_minutes_per_week: 0,
  cardio_intensity: null,
  sport_intensity: null,
  typical_daily_steps: null,
};

describe("training context controls", () => {
  it("keeps human labels, explicit zero values, and optional steps", () => {
    function Harness() {
      const [value, setValue] = useState(initial);
      return <TrainingContext context={value} onChange={setValue} />;
    }
    render(<Harness />);
    expect(
      screen.getByRole("option", { name: "Mostly seated" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Resistance days per week")).toHaveValue(0);
    fireEvent.change(screen.getByLabelText("Primary training focus"), {
      target: { value: "resistance" },
    });
    fireEvent.click(screen.getByText("More training details"));
    fireEvent.change(screen.getByLabelText("Typical daily steps"), {
      target: { value: "8000" },
    });
    expect(screen.getByLabelText("Primary training focus")).toHaveValue(
      "resistance",
    );
    expect(screen.getByLabelText("Typical daily steps")).toHaveValue(8000);
  });
});
