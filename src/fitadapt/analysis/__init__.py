"""Calendar-aware descriptive analysis of daily observations."""

from fitadapt.analysis.trends import (
    TREND_ANALYSIS_POLICY_VERSION,
    DailyTrendPoint,
    DataQualityReport,
    TrendAnalysisConfig,
    TrendAnalysisError,
    TrendAnalysisResult,
    analyze_observation_trends,
)

__all__ = [
    "TREND_ANALYSIS_POLICY_VERSION",
    "DataQualityReport",
    "DailyTrendPoint",
    "TrendAnalysisConfig",
    "TrendAnalysisError",
    "TrendAnalysisResult",
    "analyze_observation_trends",
]
