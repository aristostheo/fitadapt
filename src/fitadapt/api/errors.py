"""Stable HTTP error translation for FitAdapt domain contracts."""

import math
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fitadapt.adaptive.tdee import AdaptiveTdeeError
from fitadapt.analysis.trends import TrendAnalysisError
from fitadapt.baseline.targets import MacroPolicyInfeasibleError
from fitadapt.domain.observation import ObservationValidationError
from fitadapt.domain.profile import ProfileValidationError
from fitadapt.personalization.dietary import NutritionDietaryError
from fitadapt.personalization.intelligence import ProfileIntelligenceError
from fitadapt.personalization.lifecycle import PersonalizationLifecycleError
from fitadapt.personalization.macros import MacroPlanInfeasibleError, NutritionPreferencesError
from fitadapt.personalization.planning import PersonalizedPlanningError
from fitadapt.personalization.targets import NutritionTargetEnvelopeError
from fitadapt.personalization.training import TrainingDomainError
from fitadapt.recommendation.calories import CalorieRecommendationError

DOMAIN_ERROR_CODES: dict[type[ValueError], str] = {
    ProfileValidationError: "profile_validation_error",
    ObservationValidationError: "observation_validation_error",
    TrendAnalysisError: "trend_analysis_error",
    AdaptiveTdeeError: "adaptive_tdee_error",
    MacroPolicyInfeasibleError: "macro_policy_infeasible",
    CalorieRecommendationError: "recommendation_error",
    NutritionPreferencesError: "nutrition_preferences_error",
    MacroPlanInfeasibleError: "macro_plan_infeasible",
    PersonalizationLifecycleError: "personalization_lifecycle_error",
    PersonalizedPlanningError: "personalized_planning_error",
    ProfileIntelligenceError: "profile_intelligence_error",
    NutritionTargetEnvelopeError: "nutrition_target_envelope_error",
    NutritionDietaryError: "nutrition_dietary_error",
    TrainingDomainError: "training_domain_error",
}


def install_error_handlers(app: FastAPI) -> None:
    """Install narrow domain handlers and an opaque last-resort handler."""
    app.add_exception_handler(RequestValidationError, _validation_handler)
    for error_type, code in DOMAIN_ERROR_CODES.items():
        app.add_exception_handler(error_type, _domain_handler(code))
    app.add_exception_handler(Exception, _unexpected_handler)


def _domain_handler(code: str) -> Callable[[Request, ValueError], JSONResponse]:
    async def handler(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"error": {"code": code, "message": str(error)}}
        )

    return handler


async def _unexpected_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_server_error", "message": "Internal server error."}},
    )


async def _validation_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    """Keep standard 422 details JSON-safe when a rejected value is non-finite."""
    return JSONResponse(status_code=422, content={"detail": _json_safe(error.errors())})


def _json_safe(value: object) -> object:
    """Make rejected diagnostic values JSON-safe without changing their validation details."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, bytes | bytearray):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value
