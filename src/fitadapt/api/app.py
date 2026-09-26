"""Stateless FastAPI adapter over FitAdapt's existing domain functions."""

import os
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    NutritionPreferenceAssessmentRequest,
    NutritionPreferenceAssessmentResponse,
    NutritionTargetEnvelopeRequest,
    NutritionTargetEnvelopeResponse,
    PersonalizationLifecycleRequest,
    PersonalizationLifecycleResponse,
    PersonalizedMacroPlanRequest,
    PersonalizedMacroPlanResponse,
    ProfileIntelligenceRequest,
    ProfileIntelligenceResponse,
    TrainingDemandAssessmentResponse,
    TrainingDemandRequest,
    TrendsRequest,
    TrendsResponse,
    map_adaptive_tdee,
    map_baseline,
    map_nutrition_preference_assessment,
    map_nutrition_target_envelope,
    map_personalization_lifecycle,
    map_personalized_macro_plan,
    map_profile_intelligence,
    map_recommendation,
    map_training_demand_assessment,
    map_trends,
)
from fitadapt.baseline.targets import calculate_calorie_target
from fitadapt.personalization.dietary import assess_nutrition_preferences
from fitadapt.personalization.intelligence import analyze_profile_intelligence
from fitadapt.personalization.lifecycle import assess_personalization_lifecycle
from fitadapt.personalization.macros import calculate_personalized_macro_plan
from fitadapt.personalization.targets import calculate_nutrition_target_envelope
from fitadapt.personalization.training import assess_training_demand
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

DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def cors_origins(value: str | None = None) -> tuple[str, ...]:
    """Return deterministic, explicit browser origins without wildcard access."""
    configured = os.environ.get("FITADAPT_CORS_ORIGINS") if value is None else value
    if not configured:
        return DEFAULT_CORS_ORIGINS
    origins = tuple(
        dict.fromkeys(origin.strip() for origin in configured.split(",") if origin.strip())
    )
    if "*" in origins:
        raise ValueError("FITADAPT_CORS_ORIGINS must not contain wildcard origins.")
    return origins


def create_app() -> FastAPI:
    """Create a fresh, state-free FitAdapt HTTP application."""
    app = FastAPI(
        title="FitAdapt API",
        version=_package_version(),
        description="Typed, stateless HTTP access to FitAdapt's transparent fitness engine.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=False,
        allow_methods=("GET", "POST"),
        allow_headers=("Content-Type",),
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

    @app.post(
        "/v1/macros/personalized",
        response_model=PersonalizedMacroPlanResponse,
        responses=ERROR_RESPONSES,
    )
    def personalized_macros(request: PersonalizedMacroPlanRequest) -> PersonalizedMacroPlanResponse:
        return map_personalized_macro_plan(
            calculate_personalized_macro_plan(
                request.profile.to_domain(),
                request.calorie_target_kcal_per_day,
                request.calorie_source,
                request.preferences.to_domain(),
            )
        )

    @app.post(
        "/v1/personalization/status",
        response_model=PersonalizationLifecycleResponse,
        responses=ERROR_RESPONSES,
    )
    def personalization_status(
        request: PersonalizationLifecycleRequest,
    ) -> PersonalizationLifecycleResponse:
        return map_personalization_lifecycle(
            assess_personalization_lifecycle(
                request.profile.to_domain(),
                tuple(item.to_domain() for item in request.observations),
                None if request.lifecycle_config is None else request.lifecycle_config.to_domain(),
                None if request.trend_config is None else request.trend_config.to_domain(),
                None if request.adaptive_config is None else request.adaptive_config.to_domain(),
            )
        )

    @app.post(
        "/v1/nutrition/targets",
        response_model=NutritionTargetEnvelopeResponse,
        responses=ERROR_RESPONSES,
    )
    def nutrition_targets(
        request: NutritionTargetEnvelopeRequest,
    ) -> NutritionTargetEnvelopeResponse:
        return map_nutrition_target_envelope(
            calculate_nutrition_target_envelope(
                request.profile.to_domain(),
                request.calorie_target_kcal_per_day,
                request.calorie_source,
                request.preferences.to_domain(),
            )
        )

    @app.post(
        "/v1/nutrition/preferences/assess",
        response_model=NutritionPreferenceAssessmentResponse,
        responses=ERROR_RESPONSES,
    )
    def assess_nutrition_preference_endpoint(
        request: NutritionPreferenceAssessmentRequest,
    ) -> NutritionPreferenceAssessmentResponse:
        envelope = calculate_nutrition_target_envelope(
            request.profile.to_domain(),
            request.calorie_target_kcal_per_day,
            request.calorie_source,
            request.preferences.to_domain(),
        )
        return map_nutrition_preference_assessment(
            assess_nutrition_preferences(request.dietary_preference_profile.to_domain(), envelope)
        )

    @app.post(
        "/v1/training/demand",
        response_model=TrainingDemandAssessmentResponse,
        responses=ERROR_RESPONSES,
    )
    def training_demand(request: TrainingDemandRequest) -> TrainingDemandAssessmentResponse:
        return map_training_demand_assessment(
            assess_training_demand(
                None if request.training_context is None else request.training_context.to_domain(),
                tuple(item.to_domain() for item in request.observations),
            )
        )

    @app.post(
        "/v1/profile-intelligence",
        response_model=ProfileIntelligenceResponse,
        responses=ERROR_RESPONSES,
    )
    def profile_intelligence(request: ProfileIntelligenceRequest) -> ProfileIntelligenceResponse:
        return map_profile_intelligence(
            analyze_profile_intelligence(
                request.profile.to_domain(),
                tuple(item.to_domain() for item in request.observations),
                request.nutrition_preferences.to_domain(),
                include_plan_progression=request.include_plan_progression,
                dietary_profile=(
                    None
                    if request.dietary_preference_profile is None
                    else request.dietary_preference_profile.to_domain()
                ),
                training_context=(
                    None
                    if request.training_context is None
                    else request.training_context.to_domain()
                ),
            )
        )

    return app


app = create_app()
