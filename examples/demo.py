"""Run a deterministic, non-identifying FitAdapt decision-support demonstration."""

from datetime import date, timedelta

from fitadapt.adaptive.tdee import estimate_adaptive_tdee
from fitadapt.analysis.trends import analyze_observation_trends
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.domain.observation import DailyObservation
from fitadapt.domain.profile import ActivityLevel, Goal, SexForMifflinEquation, UserProfile
from fitadapt.recommendation.calories import recommend_calorie_adjustment


def build_demo_inputs() -> tuple[UserProfile, tuple[DailyObservation, ...]]:
    """Return deterministic sample inputs without hidden truth or persistence."""
    profile = UserProfile(
        30, 180, 80, SexForMifflinEquation.MALE, ActivityLevel.MODERATELY_ACTIVE, Goal.MAINTAIN, 0
    )
    start = date(2026, 1, 1)
    observations = tuple(
        DailyObservation(start + timedelta(days=index), 80 - 0.03 * index, 2400, steps=5000)
        for index in range(28)
    )
    return profile, observations


def main() -> None:
    profile, observations = build_demo_inputs()
    baseline = calculate_calorie_target(profile)
    trends = analyze_observation_trends(observations)
    adaptive = estimate_adaptive_tdee(trends)
    recommendation = recommend_calorie_adjustment(profile, observations)
    print("FitAdapt demonstration")
    print(f"Baseline target: {baseline.target_calories_kcal_per_day:.1f} kcal/day")
    print(f"Adaptive TDEE: {adaptive.adaptive_tdee_kcal_per_day:.1f} kcal/day")
    print(f"Trend days: {len(trends.points)}")
    print(f"Recommendation: {recommendation.status.value}")


if __name__ == "__main__":
    main()
