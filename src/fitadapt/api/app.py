"""Stateless FastAPI adapter over FitAdapt's existing domain functions."""

from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

from fitadapt.adaptive.tdee import estimate_adaptive_tdee
from fitadapt.analysis.trends import analyze_observation_trends
from fitadapt.api.errors import install_error_handlers
from fitadapt.api.schemas import (
    AdaptiveTdeeRequest,
    AdaptiveTdeeResponse,
    BaselineRequest,
    BaselineResponse,
    CalorieRecommendationRequest,
    CalorieRecommendationResponse,
    ErrorResponse,
    HealthResponse,
    TrendsRequest,
    TrendsResponse,
    map_adaptive_tdee,
    map_baseline,
    map_recommendation,
    map_trends,
)
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.recommendation.calories import (
    RECOMMENDATION_POLICY_VERSION,
    recommend_calorie_adjustment,
)


def _package_version() -> str:
    """Read installed package metadata, with a deterministic source-tree fallback."""
    try:
        return version("fitadapt")
    except PackageNotFoundError:
        return "0+uninstalled"


ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "FitAdapt domain contract error."},
    500: {"model": ErrorResponse, "description": "Opaque unexpected server error."},
}


def create_app() -> FastAPI:
    """Create a fresh, state-free FitAdapt HTTP application."""
    app = FastAPI(
        title="FitAdapt API",
        version=_package_version(),
        description="Typed, stateless HTTP access to FitAdapt's transparent fitness engine.",
    )
    install_error_handlers(app)

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={500: ERROR_RESPONSES[500]},
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="fitadapt",
            version=app.version,
            recommendation_policy_version=RECOMMENDATION_POLICY_VERSION,
        )

    @app.post("/v1/baseline", response_model=BaselineResponse, responses=ERROR_RESPONSES)
    def baseline(request: BaselineRequest) -> BaselineResponse:
        return map_baseline(calculate_calorie_target(request.profile.to_domain()))

    @app.post("/v1/trends", response_model=TrendsResponse, responses=ERROR_RESPONSES)
    def trends(request: TrendsRequest) -> TrendsResponse:
        return map_trends(
            analyze_observation_trends(
                tuple(item.to_domain() for item in request.observations),
                None if request.trend_config is None else request.trend_config.to_domain(),
            )
        )

    @app.post("/v1/adaptive-tdee", response_model=AdaptiveTdeeResponse, responses=ERROR_RESPONSES)
    def adaptive_tdee(request: AdaptiveTdeeRequest) -> AdaptiveTdeeResponse:
        trend_result = analyze_observation_trends(
            tuple(item.to_domain() for item in request.observations),
            None if request.trend_config is None else request.trend_config.to_domain(),
        )
        return map_adaptive_tdee(
            estimate_adaptive_tdee(
                trend_result,
                None if request.adaptive_config is None else request.adaptive_config.to_domain(),
            )
        )

    @app.post(
        "/v1/recommendations/calories",
        response_model=CalorieRecommendationResponse,
        responses=ERROR_RESPONSES,
    )
    def calorie_recommendation(
        request: CalorieRecommendationRequest,
    ) -> CalorieRecommendationResponse:
        return map_recommendation(
            recommend_calorie_adjustment(
                request.profile.to_domain(),
                tuple(item.to_domain() for item in request.observations),
                None
                if request.recommendation_config is None
                else request.recommendation_config.to_domain(),
                None if request.trend_config is None else request.trend_config.to_domain(),
                None if request.adaptive_config is None else request.adaptive_config.to_domain(),
            )
        )

    return app


app = create_app()
