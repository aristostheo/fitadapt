"""Conservative, explainable calorie decision support."""

from fitadapt.recommendation.calories import (
    CalorieRecommendation,
    CalorieRecommendationConfig,
    CalorieRecommendationError,
    RecommendationReason,
    RecommendationStatus,
    recommend_calorie_adjustment,
)

__all__ = [
    "CalorieRecommendation",
    "CalorieRecommendationConfig",
    "CalorieRecommendationError",
    "RecommendationReason",
    "RecommendationStatus",
    "recommend_calorie_adjustment",
]
