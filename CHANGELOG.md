# Changelog

All notable changes to the Fieldnote Crop Health Application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-10-03

### Added
- **Progressive Web App (PWA)**: Offline-first service worker shell, Web App Manifest with icons, background cache strategy, and on-device WASM fallback.
- **Multilingual Support & Voice Read-Aloud**: Full internationalization for English, Swahili (Kiswahili), Hindi (हिंदी), and Tamil (தமிழ்). Included Web Speech API voice synthesis read-aloud for accessibility in the field.
- **Multi-Leaf Batch Scanning**: Capture and analyze up to 5 leaves per plant simultaneously with aggregated plant-level verdict (majority voting + confidence weighting) and visual thumbnail gallery.
- **Weather-Aware Blight Risk**: Integrated Open-Meteo API to compute real-time relative humidity and temperature risk scores with fungal sporulation warnings.
- **Community Outbreak Map**: Privacy-first opt-in geo-reporting with GPS coordinate rounding (~1.1 km grid resolution), Leaflet heat layer visualization, and county-level outbreak clustering.
- **Treatment Planner & Schedule**: Integrated pesticide application schedule, pre-harvest interval (PHI) & re-entry interval (REI) safety countdowns, PPE gear checklist, and cost-per-acre estimates.
- **Active-Learning Feedback Loop**: Farmer-driven diagnosis confirmation and correction submission with optional photo sharing consent for model retraining.
- **Exportable PDF Field Reports**: Client-side PDF diagnostic summary generation (jsPDF) with visual Grad-CAM overlays and full treatment tables.
- **Expert Escalation**: One-tap pre-filled WhatsApp and Email deep-links connecting growers directly to regional agricultural extension officers.
- **Admin Drift & Model Analytics**: Real-time sliding-window drift detection comparing class distributions, mean confidence, and image quality metrics.
- **Responsible Use & Limitations Page**: In-app safety disclosures detailing AI decision boundaries, lookalike abiotic symptoms, and CIB&RC pesticide label verification.

### Security
- Added OWASP Top 10 defense middleware: Strict CSP headers, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Permissions-Policy`.
- Added image upload sandboxing with `Image.MAX_IMAGE_PIXELS = 16_000_000` to prevent decompression bombs.
- Added automatic EXIF metadata and GPS coordinate stripping on all ingested images.
- Enforced zero PII logging across all application logging sinks.

### Performance
- Maintained CPU p95 inference latency under 800 ms per image via automated preprocessing resize.
- Configured FastAPI `GZipMiddleware` with 1KB minimum threshold for high-speed response compression.
- Implemented aggressive 30-day static asset caching headers with immutable directives in Nginx reverse proxy.

### DevOps & Testing
- Multi-stage production `Dockerfile` with non-root unprivileged `appuser`.
- Multi-container `docker-compose.yml` (`api` + `nginx` with rate limiting and caching).
- GitHub Actions CI pipeline with linting, unit/contract tests (>91% coverage), model regression gate (macro-F1 >= baseline - 0.01), Playwright E2E, and Docker build checks.

---

## [1.0.0] - 2026-09-15

### Added
- Core dual-backbone leaf disease diagnosis API (MobileNetV3 & EfficientNet-B0) supporting Tomato and Potato crops.
- 8 disease classes + 2 healthy classes classification.
- Temperature-scaled confidence calibration with Platt scaling.
- Grad-CAM++ class activation heatmaps and lesion segmentation mask overlays.
- Image quality assessment (blur detection via Laplacian variance, brightness/contrast filtering).
- Static single-page web app with interactive leaf comparison sliders.
- Localized agronomic knowledge base with organic, biological, and chemical intervention steps.
