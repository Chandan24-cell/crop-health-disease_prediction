from typing import Literal

from pydantic import BaseModel, Field


class Quality(BaseModel):
    blur_score: float
    brightness: float
    resolution: list[int]
    issues: list[str]


class PredictionItem(BaseModel):
    label: str
    crop: str
    disease: str
    probability: float


class Severity(BaseModel):
    percent: float
    category: str
    confidence: float = 0.0
    uncertainty_percent: float = 100.0
    method: str = "not_assessed"
    conflicting_signals: bool = False
    lesion_mask_png_b64: str | None = None
    leaf_outline_png_b64: str | None = None


class PredictResponse(BaseModel):
    status: Literal["ok", "retake", "unsupported", "uncertain"]
    quality: Quality
    top3: list[PredictionItem]
    calibrated_confidence: float
    decision_reason: str
    severity: Severity
    gradcam_png_b64: str | None = None
    advice: dict[str, str]
    model_version: str
    latency_ms: float
    request_id: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str


class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=160)
    comment: str | None = Field(default=None, max_length=2000)
    photo_consent: bool = Field(default=False)
    image_b64: str | None = Field(default=None)


class BatchLeafResult(BaseModel):
    leaf_index: int
    filename: str
    prediction: PredictResponse


class BatchAggregatedVerdict(BaseModel):
    majority_vote_label: str
    confidence_weighted_label: str
    final_verdict_label: str
    crop: str
    disease: str
    aggregated_confidence: float
    total_leaves: int
    vote_breakdown: dict[str, int]
    weighted_scores: dict[str, float]
    status: Literal["ok", "uncertain", "unsupported", "retake"]
    advice: dict[str, str]


class BatchPredictResponse(BaseModel):
    status: Literal["ok", "uncertain", "unsupported", "retake"]
    leaves: list[BatchLeafResult]
    verdict: BatchAggregatedVerdict
    model_version: str
    latency_ms: float
    batch_id: str


# ── Feature 5: Outbreak Schemas ─────────────────────────────────────────


class OutbreakReportRequest(BaseModel):
    disease_label: str = Field(min_length=1, max_length=160)
    crop: str = Field(min_length=1, max_length=100)
    latitude: float
    longitude: float
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    severity_category: str = Field(default="Unknown")
    timestamp: str | None = None


class OutbreakPoint(BaseModel):
    id: str
    sample: bool = False
    state: str | None = None
    disease: str
    crop: str
    lat: float
    lng: float
    intensity: float
    timestamp: str
    severity: str


class OutbreakAlert(BaseModel):
    region_name: str
    disease: str
    case_count: int
    risk_level: Literal["Low", "Medium", "High", "Critical"]
    recommendation: str


# ── Feature 7: Feedback Loop Review ─────────────────────────────────────


class FeedbackReviewItem(BaseModel):
    id: str
    request_id: str
    predicted_label: str
    user_label: str
    comment: str | None = None
    has_photo: bool = False
    photo_path: str | None = None
    timestamp: str
    status: Literal["pending", "approved", "rejected"] = "pending"


# ── Feature 10: Analytics Dashboard ─────────────────────────────────────


class AnalyticsSummary(BaseModel):
    total_scans: int
    scans_past_7_days: dict[str, int]
    class_distribution: dict[str, int]
    rejection_rate_percent: float
    average_confidence: float
    drift_alert: bool
    drift_message: str | None = None
