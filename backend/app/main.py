import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .api.v1 import analytics, feedback, health, history, outbreak, predict, weather
from .config import get_settings
from .core.logging import configure_logging
from .services.advice import AdviceService
from .services.analytics import AnalyticsService
from .services.classifier import ModelRegistry
from .services.feedback import FeedbackService
from .services.outbreak import OutbreakService
from .services.report import ScanStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging()
    registry = ModelRegistry(settings.model_dir, settings.model_version)
    registry.load()
    severity_model_path = settings.model_dir / "severity" / "lesion_unet.keras"
    severity_model = None
    if severity_model_path.exists():
        import tensorflow as tf

        severity_model = tf.keras.models.load_model(severity_model_path, compile=False)
    app.state.settings = settings
    app.state.registry = registry
    app.state.severity_model = severity_model
    app.state.store = ScanStore(settings.history_limit)
    app.state.outbreak_service = OutbreakService()
    app.state.feedback_service = FeedbackService(settings.feedback_dir)
    app.state.analytics_service = AnalyticsService(app.state.store)
    kb_path = Path("data/kb/diseases.json")
    if not kb_path.exists():
        kb_path = settings.model_dir / "knowledge_base.json"
    app.state.advice = AdviceService(kb_path)
    yield


app = FastAPI(
    title="Crop Health API",
    version="1.0.0",
    description="Leaf disease prediction and management API",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Prediction", "description": "Upload and analyze crop leaves."}
    ],
)
app.state.limiter = predict.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Performance: Response Compression ──────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Security: CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(predict.router, prefix="/api/v1", tags=["Prediction"])
app.include_router(history.router, prefix="/api/v1", tags=["History"])
app.include_router(health.router, prefix="/api/v1", tags=["Health", "Diseases"])
app.include_router(feedback.router, prefix="/api/v1", tags=["Feedback"])
app.include_router(outbreak.router, prefix="/api/v1", tags=["Outbreak"])
app.include_router(weather.router, prefix="/api/v1", tags=["Weather"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])


@app.middleware("http")
async def security_and_cache_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))[:100]
    request.state.request_id = request_id
    started = time.perf_counter()

    response = await call_next(request)

    # ── Observability (Zero PII logged) ──────────────────────────────
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        },
    )

    # ── Security: OWASP Hardening Headers ───────────────────────────
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self)"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https://*.tile.openstreetmap.org; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "worker-src 'self' blob:;"
    )

    # ── Performance: Cache-Control Headers ───────────────────────────
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    elif any(path.endswith(ext) for ext in [".js", ".css", ".json", ".html", ".webmanifest"]) or path == "/":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    elif path.endswith((".svg", ".png", ".jpg", ".webp", ".woff2", ".ttf")):
        response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"

    return response


@app.get("/health", tags=["Health"])
async def root_health() -> dict[str, str]:
    return {"status": "healthy", "version": "1.1.0"}


frontend = get_settings().frontend_dir
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
