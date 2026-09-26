"""Deterministic training-demand and performance-context assessment."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from fitadapt.domain._validation import validate_finite_number
from fitadapt.domain.observation import DailyObservation

TRAINING_DEMAND_POLICY_VERSION = "training_demand_v1"
TRAINING_OBSERVATION_WINDOW_DAYS = 14
TRAINING_MINIMUM_CONTRIBUTORS = 4
TRAINING_MINIMUM_COMPLETENESS = 0.5
MAXIMUM_TYPICAL_STEPS = 100_000
MAXIMUM_WEEKLY_RESISTANCE_MINUTES = 1_680.0
MAXIMUM_WEEKLY_CARDIO_MINUTES = 2_100.0
MAXIMUM_WEEKLY_SPORT_MINUTES = 2_100.0


class TrainingDomainError(ValueError):
    """Raised when training context or assessment inputs violate the domain contract."""


class OccupationActivity(StrEnum):
    MOSTLY_SEATED = "mostly_seated"
    MIXED = "mixed"
    MOSTLY_ON_FEET = "mostly_on_feet"
    PHYSICALLY_DEMANDING = "physically_demanding"


class TrainingIntensity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    VIGOROUS = "vigorous"


class PrimaryTrainingFocus(StrEnum):
    GENERAL = "general"
    RESISTANCE = "resistance"
    ENDURANCE = "endurance"
    INTERMITTENT_SPORT = "intermittent_sport"
    MIXED = "mixed"


class TrainingDemandLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TrainingPriority(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class TrainingEvidenceSource(StrEnum):
    QUESTIONNAIRE = "questionnaire"
    OBSERVATIONS = "observations"
    COMBINED = "combined"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class TrainingContext:
    """Optional questionnaire context; values are policy inputs, not calorie estimates."""

    occupation_activity: OccupationActivity
    resistance_days_per_week: int = 0
    resistance_minutes_per_week: float = 0.0
    cardio_days_per_week: int = 0
    cardio_minutes_per_week: float = 0.0
    cardio_intensity: TrainingIntensity | None = None
    sport_days_per_week: int = 0
    sport_minutes_per_week: float = 0.0
    sport_intensity: TrainingIntensity | None = None
    primary_training_focus: PrimaryTrainingFocus = PrimaryTrainingFocus.GENERAL
    typical_daily_steps: int | None = None

    def __post_init__(self) -> None:
        _require_enum(self.occupation_activity, OccupationActivity, "occupation_activity")
        _require_enum(self.primary_training_focus, PrimaryTrainingFocus, "primary_training_focus")
        if self.cardio_intensity is not None:
            _require_enum(self.cardio_intensity, TrainingIntensity, "cardio_intensity")
        if self.sport_intensity is not None:
            _require_enum(self.sport_intensity, TrainingIntensity, "sport_intensity")
        _validate_days(self.resistance_days_per_week, "resistance_days_per_week")
        _validate_days(self.cardio_days_per_week, "cardio_days_per_week")
        _validate_days(self.sport_days_per_week, "sport_days_per_week")
        resistance_minutes = _validate_minutes(
            self.resistance_minutes_per_week,
            "resistance_minutes_per_week",
            MAXIMUM_WEEKLY_RESISTANCE_MINUTES,
        )
        cardio_minutes = _validate_minutes(
            self.cardio_minutes_per_week,
            "cardio_minutes_per_week",
            MAXIMUM_WEEKLY_CARDIO_MINUTES,
        )
        sport_minutes = _validate_minutes(
            self.sport_minutes_per_week,
            "sport_minutes_per_week",
            MAXIMUM_WEEKLY_SPORT_MINUTES,
        )
        if self.resistance_days_per_week == 0 and resistance_minutes > 0:
            raise TrainingDomainError("resistance minutes require at least one resistance day.")
        if self.cardio_days_per_week == 0 and cardio_minutes > 0:
            raise TrainingDomainError("cardio minutes require at least one cardio day.")
        if self.sport_days_per_week == 0 and sport_minutes > 0:
            raise TrainingDomainError("sport minutes require at least one sport day.")
        if self.resistance_days_per_week > 0 and resistance_minutes <= 0:
            raise TrainingDomainError("positive resistance days require positive weekly minutes.")
        if self.cardio_days_per_week > 0:
            if cardio_minutes <= 0 or self.cardio_intensity is None:
                raise TrainingDomainError("cardio days require positive minutes and intensity.")
        if self.sport_days_per_week > 0:
            if sport_minutes <= 0 or self.sport_intensity is None:
                raise TrainingDomainError("sport days require positive minutes and intensity.")
        if self.typical_daily_steps is not None:
            if isinstance(self.typical_daily_steps, bool) or not isinstance(
                self.typical_daily_steps, int
            ):
                raise TrainingDomainError("typical_daily_steps must be an integer or None.")
            if not 0 <= self.typical_daily_steps <= MAXIMUM_TYPICAL_STEPS:
                raise TrainingDomainError(
                    f"typical_daily_steps must be between 0 and {MAXIMUM_TYPICAL_STEPS}."
                )
        object.__setattr__(self, "resistance_minutes_per_week", resistance_minutes)
        object.__setattr__(self, "cardio_minutes_per_week", cardio_minutes)
        object.__setattr__(self, "sport_minutes_per_week", sport_minutes)


@dataclass(frozen=True, slots=True)
class TrainingDemandConfig:
    """Versioned, interpretable thresholds for training-demand classification."""

    policy_version: str = TRAINING_DEMAND_POLICY_VERSION
    observation_window_days: int = TRAINING_OBSERVATION_WINDOW_DAYS
    minimum_contributors: int = TRAINING_MINIMUM_CONTRIBUTORS
    minimum_completeness: float = TRAINING_MINIMUM_COMPLETENESS
    moderate_minutes_per_week: float = 120.0
    high_minutes_per_week: float = 240.0
    very_high_minutes_per_week: float = 360.0
    very_high_minimum_days_per_week: int = 4
    moderate_steps_per_day: int = 7_500
    high_steps_per_day: int = 12_500
    occupation_supports_high: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise TrainingDomainError("policy_version must be a non-empty string.")
        for name in (
            "observation_window_days",
            "minimum_contributors",
            "very_high_minimum_days_per_week",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise TrainingDomainError(f"{name} must be a positive integer.")
        completeness = validate_finite_number(
            self.minimum_completeness,
            field_name="minimum_completeness",
            error_type=TrainingDomainError,
        )
        if not 0 < completeness <= 1:
            raise TrainingDomainError("minimum_completeness must be greater than 0 and at most 1.")
        thresholds = tuple(
            validate_finite_number(
                getattr(self, name), field_name=name, error_type=TrainingDomainError
            )
            for name in (
                "moderate_minutes_per_week",
                "high_minutes_per_week",
                "very_high_minutes_per_week",
            )
        )
        if not 0 < thresholds[0] < thresholds[1] < thresholds[2]:
            raise TrainingDomainError("weekly minute thresholds must be strictly increasing.")
        for name in ("moderate_steps_per_day", "high_steps_per_day"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise TrainingDomainError(f"{name} must be a non-negative integer.")
        if self.moderate_steps_per_day >= self.high_steps_per_day:
            raise TrainingDomainError("step thresholds must be strictly increasing.")
        if not isinstance(self.occupation_supports_high, bool):
            raise TrainingDomainError("occupation_supports_high must be a boolean.")
        object.__setattr__(self, "minimum_completeness", completeness)
        for name, value in zip(
            ("moderate_minutes_per_week", "high_minutes_per_week", "very_high_minutes_per_week"),
            thresholds,
            strict=True,
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class TrainingStreamEvidence:
    eligible_calendar_days: int
    observation_records: int
    contributor_count: int
    completeness: float
    mean_value: float | None
    weekly_equivalent: float | None
    evidence_available: bool


@dataclass(frozen=True, slots=True)
class TrainingDemandAssessment:
    assessment_available: bool
    effective_date: date | None
    overall_demand: TrainingDemandLevel | None
    resistance_demand: TrainingDemandLevel | None
    aerobic_sport_demand: TrainingDemandLevel | None
    protein_priority: TrainingPriority | None
    carbohydrate_performance_priority: TrainingPriority | None
    evidence_source: TrainingEvidenceSource
    questionnaire_summary: tuple[str, ...]
    step_evidence: TrainingStreamEvidence
    strength_evidence: TrainingStreamEvidence
    cardio_evidence: TrainingStreamEvidence
    reason_codes: tuple[str, ...]
    policy_version: str
    assumptions: tuple[str, ...]


_EMPTY_STREAM = TrainingStreamEvidence(0, 0, 0, 0.0, None, None, False)


def assess_training_demand(
    training_context: TrainingContext | None = None,
    observations: Sequence[DailyObservation] = (),
    config: TrainingDemandConfig | None = None,
) -> TrainingDemandAssessment:
    """Assess training context without changing calories, macros, or recommendations."""
    if training_context is not None and not isinstance(training_context, TrainingContext):
        raise TrainingDomainError("training_context must be a TrainingContext or None.")
    if not isinstance(observations, (tuple, list)) or not all(
        isinstance(item, DailyObservation) for item in observations
    ):
        raise TrainingDomainError(
            "observations must be a list or tuple of DailyObservation instances."
        )
    effective_config = config or TrainingDemandConfig()
    if not isinstance(effective_config, TrainingDemandConfig):
        raise TrainingDomainError("config must be a TrainingDemandConfig or None.")
    submitted = tuple(observations)
    dates = [item.observed_on for item in submitted]
    if len(dates) != len(set(dates)):
        raise TrainingDomainError("Duplicate observed_on dates are not allowed.")
    effective_date = max(dates) if dates else None
    streams = _observed_streams(submitted, effective_date, effective_config)
    usable_observed = tuple(item for item in streams if item.evidence_available)
    questionnaire_available = training_context is not None
    if not questionnaire_available and not usable_observed:
        return _assessment(
            False,
            effective_date,
            TrainingEvidenceSource.INSUFFICIENT,
            streams,
            (),
            effective_config,
            (),
        )
    source = (
        TrainingEvidenceSource.COMBINED
        if questionnaire_available and usable_observed
        else TrainingEvidenceSource.QUESTIONNAIRE
        if questionnaire_available
        else TrainingEvidenceSource.OBSERVATIONS
    )
    resistance_level = _resistance_level(training_context, streams, effective_config)
    aerobic_level = _aerobic_level(training_context, streams, effective_config)
    overall = _overall_level(
        training_context, resistance_level, aerobic_level, streams, effective_config
    )
    reasons = _reasons(training_context, streams, resistance_level, aerobic_level, overall)
    questionnaire_summary = _questionnaire_summary(training_context)
    protein = _priority(resistance_level)
    carbohydrate = _priority(aerobic_level)
    return _assessment(
        True,
        effective_date,
        source,
        streams,
        questionnaire_summary,
        effective_config,
        reasons,
        overall,
        resistance_level,
        aerobic_level,
        protein,
        carbohydrate,
    )


def _assessment(
    available: bool,
    effective_date: date | None,
    source: TrainingEvidenceSource,
    streams: tuple[TrainingStreamEvidence, ...],
    questionnaire_summary: tuple[str, ...],
    config: TrainingDemandConfig,
    reasons: tuple[str, ...],
    overall: TrainingDemandLevel | None = None,
    resistance: TrainingDemandLevel | None = None,
    aerobic: TrainingDemandLevel | None = None,
    protein: TrainingPriority | None = None,
    carbohydrate: TrainingPriority | None = None,
) -> TrainingDemandAssessment:
    return TrainingDemandAssessment(
        available,
        effective_date,
        overall,
        resistance,
        aerobic,
        protein,
        carbohydrate,
        source,
        questionnaire_summary,
        streams[0],
        streams[1],
        streams[2],
        reasons,
        config.policy_version,
        (
            "Training demand is an informational product-policy classification, not a diagnosis "
            "or confidence score.",
            "The assessment does not estimate workout calories or change TDEE, calories, macros, "
            "target envelopes, or recommendations.",
            "Missing activity values remain unknown; explicit zero values are valid observed "
            "evidence.",
            "Observed streams replace questionnaire assumptions only when their contributor "
            "coverage meets policy minimums.",
        ),
    )


def _observed_streams(
    observations: tuple[DailyObservation, ...],
    effective_date: date | None,
    config: TrainingDemandConfig,
) -> tuple[TrainingStreamEvidence, TrainingStreamEvidence, TrainingStreamEvidence]:
    if effective_date is None:
        return _EMPTY_STREAM, _EMPTY_STREAM, _EMPTY_STREAM
    start = effective_date - timedelta(days=config.observation_window_days - 1)
    eligible = tuple(item for item in observations if start <= item.observed_on <= effective_date)
    eligible_days = len({item.observed_on for item in eligible})
    return tuple(
        _stream(eligible, eligible_days, field, config)
        for field in ("steps", "strength_training_minutes", "cardio_minutes")
    )  # type: ignore[return-value]


def _stream(
    observations: tuple[DailyObservation, ...],
    eligible_days: int,
    field: str,
    config: TrainingDemandConfig,
) -> TrainingStreamEvidence:
    values = tuple(getattr(item, field) for item in observations)
    present = tuple(value for value in values if value is not None)
    contributor_count = len(present)
    completeness = contributor_count / eligible_days if eligible_days else 0.0
    available = (
        contributor_count >= config.minimum_contributors
        and completeness >= config.minimum_completeness
    )
    mean_value = sum(present) / contributor_count if present else None
    weekly = mean_value * 7 if mean_value is not None else None
    return TrainingStreamEvidence(
        eligible_days,
        len(observations),
        contributor_count,
        completeness,
        None if mean_value is None else float(mean_value),
        None if weekly is None else float(weekly),
        available,
    )


def _resistance_level(
    context: TrainingContext | None,
    streams: tuple[TrainingStreamEvidence, ...],
    config: TrainingDemandConfig,
) -> TrainingDemandLevel | None:
    evidence = streams[1]
    if evidence.evidence_available and evidence.weekly_equivalent is not None:
        return _volume_level(evidence.weekly_equivalent, 0, config)
    if context is None:
        return None
    return _volume_level(
        context.resistance_minutes_per_week, context.resistance_days_per_week, config
    )


def _aerobic_level(
    context: TrainingContext | None,
    streams: tuple[TrainingStreamEvidence, ...],
    config: TrainingDemandConfig,
) -> TrainingDemandLevel | None:
    cardio = streams[2]
    if cardio.evidence_available and cardio.weekly_equivalent is not None:
        return _volume_level(cardio.weekly_equivalent, 0, config)
    if context is None:
        return None
    cardio_weight = _intensity_weight(context.cardio_intensity)
    sport_weight = _intensity_weight(context.sport_intensity)
    weighted = (
        context.cardio_minutes_per_week * cardio_weight
        + context.sport_minutes_per_week * sport_weight
    )
    days = context.cardio_days_per_week + context.sport_days_per_week
    return _volume_level(weighted, days, config)


def _volume_level(volume: float, days: int, config: TrainingDemandConfig) -> TrainingDemandLevel:
    if volume <= 0:
        return TrainingDemandLevel.LOW
    if (
        volume >= config.very_high_minutes_per_week
        and days >= config.very_high_minimum_days_per_week
    ):
        return TrainingDemandLevel.VERY_HIGH
    if volume >= config.high_minutes_per_week:
        return TrainingDemandLevel.HIGH
    return TrainingDemandLevel.MODERATE


def _overall_level(
    context: TrainingContext | None,
    resistance: TrainingDemandLevel | None,
    aerobic: TrainingDemandLevel | None,
    streams: tuple[TrainingStreamEvidence, ...],
    config: TrainingDemandConfig,
) -> TrainingDemandLevel | None:
    levels = [level for level in (resistance, aerobic) if level is not None]
    if not levels:
        steps = context.typical_daily_steps if context is not None else streams[0].mean_value
        if steps is None:
            return None
        return (
            TrainingDemandLevel.MODERATE
            if steps >= config.moderate_steps_per_day
            else TrainingDemandLevel.LOW
        )
    strongest = max(levels, key=lambda level: tuple(TrainingDemandLevel).index(level))
    steps = context.typical_daily_steps if context is not None else streams[0].mean_value
    occupation_support = (
        context is not None
        and context.occupation_activity is OccupationActivity.PHYSICALLY_DEMANDING
    )
    if strongest is TrainingDemandLevel.LOW and (
        occupation_support or (steps or 0) >= config.moderate_steps_per_day
    ):
        return TrainingDemandLevel.MODERATE
    if (
        strongest is TrainingDemandLevel.HIGH
        and occupation_support
        and config.occupation_supports_high
    ):
        return TrainingDemandLevel.VERY_HIGH
    return strongest


def _priority(level: TrainingDemandLevel | None) -> TrainingPriority | None:
    if level is None or level is TrainingDemandLevel.LOW:
        return TrainingPriority.LOW if level is not None else None
    if level is TrainingDemandLevel.MODERATE:
        return TrainingPriority.MODERATE
    return TrainingPriority.HIGH


def _reasons(
    context: TrainingContext | None,
    streams: tuple[TrainingStreamEvidence, ...],
    resistance: TrainingDemandLevel | None,
    aerobic: TrainingDemandLevel | None,
    overall: TrainingDemandLevel | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if context is not None:
        reasons.append("questionnaire_context_used")
    if streams[0].evidence_available:
        reasons.append("observed_steps_used")
    if streams[1].evidence_available:
        reasons.append("observed_strength_minutes_used")
    if streams[2].evidence_available:
        reasons.append("observed_cardio_minutes_used")
    if resistance is TrainingDemandLevel.LOW:
        reasons.append("low_structured_resistance_volume")
    elif resistance in (TrainingDemandLevel.HIGH, TrainingDemandLevel.VERY_HIGH):
        reasons.append("substantial_resistance_volume")
    if aerobic in (TrainingDemandLevel.HIGH, TrainingDemandLevel.VERY_HIGH):
        reasons.append("substantial_aerobic_volume")
    if overall is TrainingDemandLevel.VERY_HIGH:
        reasons.append("very_high_requires_multiple_supporting_signals")
    if not reasons:
        reasons.append("insufficient_training_evidence")
    return tuple(dict.fromkeys(reasons))


def _questionnaire_summary(context: TrainingContext | None) -> tuple[str, ...]:
    if context is None:
        return ()
    return (
        f"occupation_activity:{context.occupation_activity.value}",
        f"primary_training_focus:{context.primary_training_focus.value}",
        f"resistance_days_per_week:{context.resistance_days_per_week}",
        f"cardio_days_per_week:{context.cardio_days_per_week}",
        f"sport_days_per_week:{context.sport_days_per_week}",
    )


def _intensity_weight(intensity: TrainingIntensity | None) -> float:
    return {
        None: 1.0,
        TrainingIntensity.LOW: 1.0,
        TrainingIntensity.MODERATE: 1.25,
        TrainingIntensity.VIGOROUS: 1.5,
    }[intensity]


def _validate_days(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 7:
        raise TrainingDomainError(f"{field_name} must be an integer between 0 and 7.")


def _validate_minutes(value: object, field_name: str, maximum: float) -> float:
    result = validate_finite_number(value, field_name=field_name, error_type=TrainingDomainError)
    if not 0 <= result <= maximum:
        raise TrainingDomainError(f"{field_name} must be between 0 and {maximum:g} minutes.")
    return result


def _require_enum(value: object, enum_type: type[StrEnum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TrainingDomainError(f"{field_name} must be a {enum_type.__name__} enum value.")
