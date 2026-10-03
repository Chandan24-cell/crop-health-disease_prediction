# Fieldnote REST API Specification

The Fieldnote API is built on FastAPI and conforms to OpenAPI 3.1.0 standards. Interactive Swagger documentation is available at `/docs` and ReDoc at `/redoc`.

Base URL: `/api/v1`

---

## 1. Leaf Disease Prediction

### Single Leaf Scan
**Endpoint:** `POST /api/v1/predict`
**Content-Type:** `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | Binary File | Yes | Leaf image (JPEG, PNG, WebP). Max 16MB. |
| `crop` | String | No | Target crop filter (`tomato`, `potato`, `auto`). |

#### Example `curl` Request
```bash
curl -X POST "http://localhost:8000/api/v1/predict" \
     -F "file=@leaf.jpg;type=image/jpeg" \
     -F "crop=tomato"
```

#### Response (`200 OK`)
```json
{
  "request_id": "req_a1b2c3d4e5",
  "prediction": {
    "crop": "Tomato",
    "disease": "Early blight",
    "raw_class": "tomato_early_blight",
    "confidence": 0.942,
    "top2": [
      { "disease": "Early blight", "confidence": 0.942 },
      { "disease": "Target spot", "confidence": 0.038 }
    ],
    "is_confident": true
  },
  "severity": {
    "leaf_area_px": 128450,
    "lesion_area_px": 14200,
    "percent_affected": 11.05,
    "category": "Moderate",
    "lesion_mask_png_b64": "iVBORw0KGgoAAAANSUhEUg...",
    "leaf_outline_png_b64": "iVBORw0KGgoAAAANSUhEUg..."
  },
  "quality": {
    "is_blurry": false,
    "laplacian_var": 182.4,
    "mean_brightness": 124.6,
    "quality_score": 0.92
  },
  "advice": {
    "immediate_actions": "Prune lower infected leaves immediately and destroy off-field.",
    "organic_treatment": "Apply copper octanoate or copper hydroxide spray.",
    "chemical_treatment": "Chlorothalonil or Mancozeb protective fungicide.",
    "safety_note": "Observe 7-day Pre-Harvest Interval (PHI) before harvest."
  },
  "gradcam_png_b64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

---

### Multi-Leaf Batch Scan
**Endpoint:** `POST /api/v1/predict/batch`
**Content-Type:** `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `files` | Array of Files | Yes | Up to 5 leaf images from the same plant. |
| `crop` | String | No | Target crop (`tomato`, `potato`, `auto`). |

#### Response (`200 OK`)
```json
{
  "total_leaves": 3,
  "crop": "Tomato",
  "disease": "Early blight",
  "majority_vote_label": "tomato_early_blight",
  "aggregated_confidence": 0.915,
  "confidence_distribution": {
    "tomato_early_blight": 0.915,
    "tomato_healthy": 0.085
  },
  "leaves": [
    { "leaf_index": 1, "raw_class": "tomato_early_blight", "confidence": 0.94 },
    { "leaf_index": 2, "raw_class": "tomato_early_blight", "confidence": 0.89 },
    { "leaf_index": 3, "raw_class": "tomato_healthy", "confidence": 0.81 }
  ]
}
```

---

## 2. Weather Blight Risk Calculation

**Endpoint:** `GET /api/v1/weather/risk`

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `lat` | Float | Yes | Latitude (-90.0 to 90.0) |
| `lon` | Float | Yes | Longitude (-180.0 to 180.0) |

#### Response (`200 OK`)
```json
{
  "temperature_c": 21.4,
  "relative_humidity": 88.0,
  "precipitation_mm": 2.4,
  "risk_score": 0.85,
  "risk_category": "High",
  "blight_risk_factors": [
    "High relative humidity (>85%) promotes rapid fungal sporulation.",
    "Moderate temperatures (18°C-24°C) optimal for late blight germination."
  ]
}
```

---

## 3. Community Outbreak Reporting

### Submit Anonymous Report
**Endpoint:** `POST /api/v1/outbreak/report`
**Content-Type:** `application/json`

```json
{
  "latitude": -1.286389,
  "longitude": 36.817223,
  "crop": "Tomato",
  "disease": "Early blight",
  "severity_category": "Moderate",
  "county": "Kiambu"
}
```
*Note: Coords are automatically truncated/rounded to 2 decimal places (~1.1 km) before saving.*

---

### Fetch Outbreak GeoJSON / Heat Clusters
**Endpoint:** `GET /api/v1/outbreak/reports`
**Endpoint:** `GET /api/v1/outbreak/clusters`

---

## 4. Active-Learning Feedback Loop

### Submit Scan Correction
**Endpoint:** `POST /api/v1/feedback`
**Content-Type:** `application/json`

```json
{
  "scan_id": "req_a1b2c3d4e5",
  "predicted_class": "tomato_early_blight",
  "corrected_class": "tomato_target_spot",
  "farmer_notes": "Lesions show distinct concentric rings with yellow halos.",
  "photo_consent": true
}
```

---

## 5. Model Analytics & Drift Monitoring (Admin)

**Endpoint:** `GET /api/v1/admin/analytics/summary`
**Endpoint:** `GET /api/v1/admin/analytics/drift`

#### Response (`200 OK`)
```json
{
  "total_scans": 1420,
  "mean_confidence": 0.912,
  "blurry_rate": 0.042,
  "class_distribution": {
    "tomato_early_blight": 0.42,
    "tomato_late_blight": 0.28,
    "tomato_healthy": 0.15,
    "potato_late_blight": 0.15
  },
  "drift_status": {
    "is_drift_detected": false,
    "max_kl_divergence": 0.034
  }
}
```

---

## 6. System Health

**Endpoint:** `GET /api/v1/health`

#### Response (`200 OK`)
```json
{
  "status": "healthy",
  "version": "1.1.0",
  "timestamp": "2026-10-03T05:45:00Z"
}
```
