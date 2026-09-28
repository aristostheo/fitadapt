import type { TargetSafetyAssessment } from "../types";
import { whole } from "../utils/presentation";
import { Notice } from "./ui";

export function TargetSafetyCard({
  assessment,
}: {
  assessment?: TargetSafetyAssessment;
}) {
  if (!assessment || assessment.status === "eligible") return null;
  if (assessment.status === "ineligible") {
    return (
      <Notice tone="warning">
        FitAdapt does not generate automated weight-loss targets below this
        body-size threshold. Consider discussing weight goals with a qualified
        healthcare professional.
      </Notice>
    );
  }
  return (
    <Notice>
      Your requested loss rate would require a larger deficit than FitAdapt
      allows, so the plan uses a more conservative target of{" "}
      {whole(assessment.effective_target_kcal_per_day, "kcal/day")}.
    </Notice>
  );
}
