"""Stable HTTP error translation for FitAdapt domain contracts."""

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fitadapt.adaptive.tdee import AdaptiveTdeeError
from fitadapt.analysis.trends import TrendAnalysisError
from fitadapt.baseline.targets import MacroPolicyInfeasibleError
from fitadapt.domain.observation import ObservationValidationError
from fitadapt.domain.profile import ProfileValidationError
from fitadapt.personalization.macros import MacroPlanInfeasibleError, NutritionPreferencesError
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
}


def install_error_handlers(app: FastAPI) -> None:
    """Install narrow domain handlers and an opaque last-resort handler."""
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
