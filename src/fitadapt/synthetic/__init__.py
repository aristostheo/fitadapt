"""Reproducible synthetic longitudinal fitness-data generation."""

from fitadapt.synthetic.history import (
    SIMULATION_POLICY_VERSION,
    SyntheticConfigurationError,
    SyntheticDay,
    SyntheticDayTruth,
    SyntheticHistory,
    SyntheticHistoryConfig,
    generate_synthetic_history,
)

__all__ = [
    "SIMULATION_POLICY_VERSION",
    "SyntheticConfigurationError",
    "SyntheticDay",
    "SyntheticDayTruth",
    "SyntheticHistory",
    "SyntheticHistoryConfig",
    "generate_synthetic_history",
]
