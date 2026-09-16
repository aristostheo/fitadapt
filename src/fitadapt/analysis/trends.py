"""Leakage-free calendar-day rolling trends using pandas internally."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from fitadapt.domain.observation import DailyObservation

TREND_ANALYSIS_POLICY_VERSION = "calendar_trends_v1"
TREND_ASSUMPTIONS = (
    "The timeline includes every calendar date from first through last observation.",
    "Rolling windows are trailing calendar days and never use future values.",
    "Missing values are not imputed and public missing values are returned as None.",
    "Window weight change compares trailing means exactly one configured window apart.",
)


class TrendAnalysisError(ValueError):
    """Raised when trend-analysis inputs or configuration violate the public contract."""


@dataclass(frozen=True, slots=True)
class TrendAnalysisConfig:
    """Versioned trailing calendar-window policy for descriptive trend features."""

    window_size_days: int = 7
    minimum_observations: int = 4

    def __post_init__(self) -> None:
        if isinstance(self.window_size_days, bool) or not isinstance(self.window_size_days, int):
            raise TrendAnalysisError("window_size_days must be an integer.")
        if self.window_size_days <= 0:
            raise TrendAnalysisError("window_size_days must be positive.")
        if isinstance(self.minimum_observations, bool) or not isinstance(
            self.minimum_observations, int
        ):
            raise TrendAnalysisError("minimum_observations must be an integer.")
        if not 1 <= self.minimum_observations <= self.window_size_days:
            raise TrendAnalysisError("minimum_observations must be between 1 and window_size_days.")


@dataclass(frozen=True, slots=True)
class DailyTrendPoint:
    """Raw values and leakage-free rolling features for one calendar date."""

    observed_on: date
    observation_present: bool
    body_weight_kg: float | None
    energy_intake_kcal: float | None
    steps: int | None
    trailing_body_weight_mean_kg: float | None
    trailing_energy_intake_mean_kcal: float | None
    trailing_steps_mean: float | None
    body_weight_contributor_count: int
    energy_intake_contributor_count: int
    steps_contributor_count: int
    window_weight_change_kg: float | None


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Calendar-denominated completeness metrics for analyzed measurements."""

    first_date: date | None
    last_date: date | None
    total_calendar_days: int
    submitted_observation_records: int
    missing_calendar_days: int
    present_body_weight_values: int
    missing_body_weight_values: int
    body_weight_completeness_ratio: float
    present_energy_intake_values: int
    missing_energy_intake_values: int
    energy_intake_completeness_ratio: float
    present_step_values: int
    missing_step_values: int
    step_completeness_ratio: float


@dataclass(frozen=True, slots=True)
class TrendAnalysisResult:
    """Immutable calendar-aware trend points and their transparent quality report."""

    policy_version: str
    config: TrendAnalysisConfig
    points: tuple[DailyTrendPoint, ...]
    data_quality: DataQualityReport
    assumptions: tuple[str, ...]


def analyze_observation_trends(
    observations: Iterable[DailyObservation], config: TrendAnalysisConfig | None = None
) -> TrendAnalysisResult:
    """Analyze validated observations on a continuous, trailing calendar-day timeline."""
    effective_config = config if config is not None else TrendAnalysisConfig()
    if not isinstance(effective_config, TrendAnalysisConfig):
        raise TrendAnalysisError("config must be a TrendAnalysisConfig or None.")
    submitted = tuple(observations)
    if not all(isinstance(observation, DailyObservation) for observation in submitted):
        raise TrendAnalysisError("observations must contain DailyObservation instances.")
    dates = [observation.observed_on for observation in submitted]
    if len(dates) != len(set(dates)):
        raise TrendAnalysisError("Duplicate observed_on dates are not allowed.")
    if not submitted:
        return TrendAnalysisResult(
            TREND_ANALYSIS_POLICY_VERSION,
            effective_config,
            (),
            _empty_quality_report(),
            TREND_ASSUMPTIONS,
        )
    frame = _build_calendar_frame(submitted)
    return TrendAnalysisResult(
        TREND_ANALYSIS_POLICY_VERSION,
        effective_config,
        _build_points(frame, effective_config),
        _build_quality_report(frame),
        TREND_ASSUMPTIONS,
    )


def _build_calendar_frame(observations: tuple[DailyObservation, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "observed_on": [item.observed_on for item in observations],
            "body_weight_kg": [item.body_weight_kg for item in observations],
            "energy_intake_kcal": [item.energy_intake_kcal for item in observations],
            "steps": [item.steps for item in observations],
            "observation_present": True,
        }
    ).set_index("observed_on")
    frame.index = pd.to_datetime(frame.index)
    return frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq="D"))


def _build_points(frame: pd.DataFrame, config: TrendAnalysisConfig) -> tuple[DailyTrendPoint, ...]:
    names = ("body_weight_kg", "energy_intake_kcal", "steps")
    means = {
        name: frame[name]
        .rolling(config.window_size_days, min_periods=config.minimum_observations)
        .mean()
        for name in names
    }
    counts = {
        name: frame[name].rolling(config.window_size_days, min_periods=1).count() for name in names
    }
    weight_change = means["body_weight_kg"] - means["body_weight_kg"].shift(config.window_size_days)
    return tuple(
        DailyTrendPoint(
            timestamp.date(),
            False
            if pd.isna(frame["observation_present"].iloc[position])
            else bool(frame["observation_present"].iloc[position]),
            _float_or_none(frame["body_weight_kg"].iloc[position]),
            _float_or_none(frame["energy_intake_kcal"].iloc[position]),
            _int_or_none(frame["steps"].iloc[position]),
            _float_or_none(means["body_weight_kg"].iloc[position]),
            _float_or_none(means["energy_intake_kcal"].iloc[position]),
            _float_or_none(means["steps"].iloc[position]),
            int(counts["body_weight_kg"].iloc[position]),
            int(counts["energy_intake_kcal"].iloc[position]),
            int(counts["steps"].iloc[position]),
            _float_or_none(weight_change.iloc[position]),
        )
        for position, timestamp in enumerate(frame.index)
    )


def _build_quality_report(frame: pd.DataFrame) -> DataQualityReport:
    total = len(frame)
    present_records = int(frame["observation_present"].fillna(False).sum())
    counts = {
        name: int(frame[name].count()) for name in ("body_weight_kg", "energy_intake_kcal", "steps")
    }
    return DataQualityReport(
        frame.index[0].date(),
        frame.index[-1].date(),
        total,
        present_records,
        total - present_records,
        counts["body_weight_kg"],
        total - counts["body_weight_kg"],
        counts["body_weight_kg"] / total,
        counts["energy_intake_kcal"],
        total - counts["energy_intake_kcal"],
        counts["energy_intake_kcal"] / total,
        counts["steps"],
        total - counts["steps"],
        counts["steps"] / total,
    )


def _empty_quality_report() -> DataQualityReport:
    return DataQualityReport(None, None, 0, 0, 0, 0, 0, 0.0, 0, 0, 0.0, 0, 0, 0.0)


def _float_or_none(value: object) -> float | None:
    return None if pd.isna(value) else float(value)


def _int_or_none(value: object) -> int | None:
    return None if pd.isna(value) else int(value)
