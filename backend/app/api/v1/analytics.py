from fastapi import APIRouter, HTTPException, Request

from ...config import get_settings
from ...schemas import AnalyticsSummary
from ...services.analytics import AnalyticsService

router = APIRouter()


def _get_analytics_service(request: Request) -> AnalyticsService:
    service = getattr(request.app.state, "analytics_service", None)
    if service is None:
        store = getattr(request.app.state, "store", None)
        service = AnalyticsService(store)
        request.app.state.analytics_service = service
    return service


def _get_settings(request: Request):
    return getattr(request.app.state, "settings", None) or get_settings()


@router.get("/admin/analytics/summary", response_model=AnalyticsSummary)
def get_analytics_summary(request: Request) -> AnalyticsSummary:
    settings = _get_settings(request)
    if not settings.feature_analytics:
        raise HTTPException(status_code=403, detail="Analytics feature is disabled")

    service = _get_analytics_service(request)
    summary = service.get_summary()
    return AnalyticsSummary(**summary)
