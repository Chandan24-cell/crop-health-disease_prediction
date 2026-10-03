import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...config import Settings, get_settings
from ...schemas import (
    BatchAggregatedVerdict,
    BatchLeafResult,
    BatchPredictResponse,
    PredictResponse,
)
from ...services.advice import AdviceService
from ...services.classifier import ModelRegistry
from ...services.explain import create_gradcam
from ...services.quality import assess_quality, decode_image
from ...services.report import ScanStore
from ...services.severity import estimate_severity, has_conflicting_signals

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


def _get_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


def _get_registry(request: Request) -> ModelRegistry:
    reg = getattr(request.app.state, "registry", None)
    if reg is None:
        settings = _get_settings(request)
        reg = ModelRegistry(settings.model_dir, settings.model_version)
        reg.load()
        request.app.state.registry = reg
    return reg


def _get_severity_model(request: Request):
    if hasattr(request.app.state, "severity_model"):
        return request.app.state.severity_model
    settings = _get_settings(request)
    severity_model_path = settings.model_dir / "severity" / "lesion_unet.keras"
    severity_model = None
    if severity_model_path.exists():
        import tensorflow as tf

        severity_model = tf.keras.models.load_model(severity_model_path, compile=False)
    request.app.state.severity_model = severity_model
    return severity_model


def _get_store(request: Request) -> ScanStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        settings = _get_settings(request)
        store = ScanStore(settings.history_limit)
        request.app.state.store = store
    return store


def _get_advice(request: Request) -> AdviceService:
    advice = getattr(request.app.state, "advice", None)
    if advice is None:
        settings = _get_settings(request)
        kb_path = Path("data/kb/diseases.json")
        if not kb_path.exists():
            kb_path = settings.model_dir / "knowledge_base.json"
        advice = AdviceService(kb_path)
        request.app.state.advice = advice
    return advice


async def _predict_bytes(
    data: bytes,
    request: Request,
    language: str = "en",
    consent_location_metadata: bool = False,
    request_id: str | None = None,
) -> PredictResponse:
    started = time.perf_counter()
    req_id = request_id or str(uuid4())
    settings = _get_settings(request)
    registry = _get_registry(request)
    severity_model = _get_severity_model(request)
    store = _get_store(request)
    advice_svc = _get_advice(request)

    if not data:
        raise HTTPException(status_code=400, detail="Upload is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail="Image exceeds the 8 MB upload limit"
        )

    try:
        decoded = decode_image(
            data,
            settings.max_image_dimension,
            settings.strip_exif_gps and not consent_location_metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    quality = assess_quality(decoded.rgb)
    if registry.model is None:
        raise HTTPException(status_code=503, detail="Model is unavailable")

    scores = registry.predict(decoded.rgb)
    order = scores.argsort()[::-1][:3]
    top = [
        {
            "label": registry.labels[i],
            "crop": _crop(registry.labels[i]),
            "disease": _disease(registry.labels[i]),
            "probability": round(float(scores[i]), 6),
        }
        for i in order
    ]
    best_idx, best = int(order[0]), registry.labels[int(order[0])]
    confidence = float(scores[best_idx])
    status = "ok"
    reason = "Prediction passed confidence and supported crop checks."

    if quality["issues"]:
        status, reason = "retake", "Image quality checks failed: " + ", ".join(
            quality["issues"]
        )
    elif best in {"Unknown", "Not_a_leaf"}:
        status, reason = (
            "unsupported",
            "Image is outside the supported crop leaf classes.",
        )
    elif confidence < settings.confidence_threshold:
        status, reason = (
            "uncertain",
            "Top prediction is below the configured confidence threshold.",
        )

    severity = (
        estimate_severity(
            decoded.rgb,
            crop=_crop(best),
            bands_path=settings.severity_bands_path,
            lesion_model=severity_model,
        )
        if status in {"ok", "uncertain"} and best not in {"Unknown", "Not_a_leaf"}
        else {
            "percent": 0.0,
            "category": "Not assessed",
            "confidence": 0.0,
            "uncertainty_percent": 100.0,
            "method": "not_assessed",
            "lesion_mask_png_b64": None,
            "leaf_outline_png_b64": None,
        }
    )
    severity_conflict = has_conflicting_signals(
        best, float(severity["percent"]), str(severity["category"])
    )
    severity["conflicting_signals"] = bool(severity_conflict)
    if severity_conflict:
        status = "uncertain"
        reason = "Classifier and leaf-masked severity disagree; signals flagged as conflicting."

    advice = (
        advice_svc.get(best, str(severity["category"]), language=language)
        if status == "ok"
        else {}
    )
    gradcam = (
        create_gradcam(registry, decoded.rgb, best_idx, method="gradcam++")
        if status in {"ok", "uncertain"}
        else None
    )
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("prediction completed", extra={"request_id": req_id})
    store.add_scan(
        {
            "request_id": req_id,
            "label": best,
            "status": status,
            "confidence": confidence,
            "latency_ms": round(elapsed, 2),
        }
    )

    return PredictResponse(
        status=status,
        quality=quality,
        top3=top,
        calibrated_confidence=confidence,
        decision_reason=reason,
        severity=severity,
        gradcam_png_b64=gradcam,
        advice=advice,
        model_version=registry.version,
        latency_ms=round(elapsed, 2),
        request_id=req_id,
    )


@router.post(
    "/predict",
    response_model=PredictResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "image": {"type": "string", "format": "binary"},
                            "crop_hint": {"type": "string"},
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"},
                            "language": {"type": "string", "default": "en"},
                            "consent_location_metadata": {
                                "type": "boolean",
                                "default": False,
                            },
                        },
                        "required": ["image"],
                    }
                }
            }
        }
    },
)
@limiter.limit(lambda *args: get_settings().rate_limit)
async def predict(
    request: Request,
    image: UploadFile = File(..., description="JPEG or PNG leaf image"),
    crop_hint: str | None = Form(None, examples=["Tomato"]),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    language: str = Form("en"),
    consent_location_metadata: bool = Form(False),
) -> PredictResponse:
    del crop_hint, latitude, longitude
    settings = _get_settings(request)
    data = await image.read(settings.max_upload_bytes + 1)
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return await _predict_bytes(
        data,
        request,
        language=language,
        consent_location_metadata=consent_location_metadata,
        request_id=req_id,
    )


@router.post(
    "/predict/batch",
    response_model=BatchPredictResponse,
)
@limiter.limit(lambda *args: get_settings().rate_limit)
async def predict_batch(
    request: Request,
    images: list[UploadFile] = File(..., description="1 to 5 leaf images"),
    language: str = Form("en"),
) -> BatchPredictResponse:
    settings = _get_settings(request)
    registry = _get_registry(request)
    advice_svc = _get_advice(request)

    if not settings.feature_batch_scan:
        raise HTTPException(status_code=403, detail="Batch scanning is disabled")
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="No leaf images provided")
    if len(images) > 5:
        raise HTTPException(
            status_code=400, detail="Maximum 5 leaves allowed per batch scan"
        )

    batch_start = time.perf_counter()
    batch_id = str(uuid4())
    leaves: list[BatchLeafResult] = []

    vote_counts: dict[str, int] = {}
    weighted_scores: dict[str, float] = {}

    for idx, img_file in enumerate(images):
        img_bytes = await img_file.read(settings.max_upload_bytes + 1)
        pred = await _predict_bytes(
            img_bytes,
            request,
            language=language,
            request_id=f"{batch_id}-leaf-{idx + 1}",
        )
        leaves.append(
            BatchLeafResult(
                leaf_index=idx + 1,
                filename=img_file.filename or f"leaf_{idx+1}.jpg",
                prediction=pred,
            )
        )

        top_label = pred.top3[0].label if pred.top3 else "Unknown"
        conf = pred.calibrated_confidence

        vote_counts[top_label] = vote_counts.get(top_label, 0) + 1
        weighted_scores[top_label] = round(
            weighted_scores.get(top_label, 0.0) + conf, 4
        )

    # Aggregation
    majority_label = max(vote_counts, key=vote_counts.get)
    weighted_label = max(weighted_scores, key=weighted_scores.get)
    final_label = weighted_label

    # Calculate aggregated confidence
    agg_conf = round(weighted_scores[final_label] / len(leaves), 4)

    # Plant-level status
    statuses = [leaf.prediction.status for leaf in leaves]
    if all(s == "retake" for s in statuses):
        verdict_status = "retake"
    elif all(s == "unsupported" for s in statuses):
        verdict_status = "unsupported"
    elif agg_conf < settings.confidence_threshold:
        verdict_status = "uncertain"
    else:
        verdict_status = "ok"

    advice = (
        advice_svc.get(final_label, "Moderate", language=language)
        if verdict_status == "ok"
        else {}
    )

    verdict = BatchAggregatedVerdict(
        majority_vote_label=majority_label,
        confidence_weighted_label=weighted_label,
        final_verdict_label=final_label,
        crop=_crop(final_label),
        disease=_disease(final_label),
        aggregated_confidence=agg_conf,
        total_leaves=len(leaves),
        vote_breakdown=vote_counts,
        weighted_scores=weighted_scores,
        status=verdict_status,
        advice=advice,
    )

    batch_latency = round((time.perf_counter() - batch_start) * 1000, 2)
    return BatchPredictResponse(
        status=verdict_status,
        leaves=leaves,
        verdict=verdict,
        model_version=registry.version,
        latency_ms=batch_latency,
        batch_id=batch_id,
    )


def _crop(label: str) -> str:
    return label.split("_")[0] if "_" in label else "Unknown"


def _disease(label: str) -> str:
    parts = label.split("_", 1)
    return parts[1].replace("_", " ") if len(parts) > 1 else label
