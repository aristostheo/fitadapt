"""Internal validation helpers shared by FitAdapt domain models."""

import math


def validate_finite_number(
    value: object,
    *,
    field_name: str,
    error_type: type[ValueError],
) -> float:
    """Return a finite numeric value as a float or raise the caller's domain error."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_type(f"{field_name} must be a finite number, not a boolean or text value.")

    value_as_float = float(value)
    if not math.isfinite(value_as_float):
        raise error_type(f"{field_name} must be finite, not NaN or infinity.")
    return value_as_float
