from fastapi import APIRouter, HTTPException, Query, Request

from ...config import get_settings
from ...schemas import OutbreakPoint, OutbreakReportRequest
from ...services.outbreak import OutbreakService

router = APIRouter()


def _get_outbreak_service(request: Request) -> OutbreakService:
    service = getattr(request.app.state, "outbreak_service", None)
    if service is None:
        service = OutbreakService()
        request.app.state.outbreak_service = service
    return service


def _get_settings(request: Request):
    return getattr(request.app.state, "settings", None) or get_settings()


@router.post("/outbreak/report", response_model=OutbreakPoint)
def report_outbreak(request: Request, body: OutbreakReportRequest) -> OutbreakPoint:
    settings = _get_settings(request)
    if not settings.feature_outbreak_map:
        raise HTTPException(status_code=403, detail="Outbreak map feature is disabled")

    service = _get_outbreak_service(request)
    report = service.add_report(
        disease_label=body.disease_label,
        crop=body.crop,
        latitude=body.latitude,
        longitude=body.longitude,
        confidence=body.confidence,
        severity_category=body.severity_category,
    )
    return OutbreakPoint(**report)


@router.get("/outbreak/points", response_model=list[OutbreakPoint])
def list_outbreak_points(
    request: Request,
    crop: str | None = Query(None),
    disease: str | None = Query(None),
) -> list[OutbreakPoint]:
    settings = _get_settings(request)
    if not settings.feature_outbreak_map:
        raise HTTPException(status_code=403, detail="Outbreak map feature is disabled")

    service = _get_outbreak_service(request)
    points = service.get_points(crop=crop, disease=disease)
    return [OutbreakPoint(**p) for p in points]


@router.get("/outbreak/alerts")
def get_outbreak_alerts(request: Request) -> list[dict]:
    settings = _get_settings(request)
    if not settings.feature_outbreak_map:
        raise HTTPException(status_code=403, detail="Outbreak map feature is disabled")

    service = _get_outbreak_service(request)
    return service.get_alerts()
