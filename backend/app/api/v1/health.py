from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ...services.advice import AdviceService

router = APIRouter()


def _get_advice_service(request: Request) -> AdviceService:
    service = getattr(request.app.state, "advice", None)
    if service is None:
        service = AdviceService(Path("data/kb/diseases.json"))
        request.app.state.advice = service
    return service


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    registry = getattr(request.app.state, "registry", None)
    loaded = registry.model is not None if registry else False
    version = registry.version if registry else "v2"
    return {
        "status": "ok" if loaded else "degraded",
        "model_loaded": loaded,
        "model_version": version,
    }


@router.get("/model-info")
def model_info(request: Request) -> dict[str, object]:
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        return {"version": "v2", "loaded": False, "labels": [], "metadata": {}}
    return {
        "version": registry.version,
        "loaded": registry.model is not None,
        "labels": registry.labels,
        "metadata": registry.metadata,
    }


@router.get("/diseases")
def diseases(request: Request, lang: str = "en") -> list[dict[str, str]]:
    advice_svc = _get_advice_service(request)
    kb = advice_svc.stores.get(lang, advice_svc.data)
    return [
        {
            "id": key,
            "crop": value.get("crop", ""),
            "name": key.split("_", 1)[-1].replace("_", " "),
        }
        for key, value in kb.items()
    ]


@router.get("/diseases/{disease_id}")
def disease(disease_id: str, request: Request, lang: str = "en") -> dict[str, object]:
    advice_svc = _get_advice_service(request)
    kb = advice_svc.stores.get(lang, advice_svc.data)
    item = kb.get(disease_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    return {"id": disease_id, **item}
