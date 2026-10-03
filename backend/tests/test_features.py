from pathlib import Path

import httpx
import pytest

from backend.app.main import app
from backend.app.services.advice import AdviceService
from backend.app.services.analytics import AnalyticsService
from backend.app.services.feedback import FeedbackService
from backend.app.services.outbreak import OutbreakService
from backend.app.services.report import ScanStore


def test_multilingual_advice_service(tmp_path: Path) -> None:
    kb_path = Path("data/kb/diseases.json")
    service = AdviceService(kb_path)

    # English
    adv_en = service.get("Tomato_Late_blight", "severe", language="en")
    assert adv_en["crop"] == "Tomato"
    assert "urgent" in adv_en["specific_advice"].lower()

    # Swahili
    adv_sw = service.get("Tomato_Late_blight", "severe", language="sw")
    assert adv_sw["crop"] == "Nyanya"
    assert "ugani" in adv_sw["specific_advice"].lower()

    # Hindi
    adv_hi = service.get("Tomato_Late_blight", "severe", language="hi")
    assert adv_hi["crop"] == "टमाटर"

    # Tamil
    adv_ta = service.get("Tomato_Late_blight", "severe", language="ta")
    assert adv_ta["crop"] == "தக்காளி"


def test_outbreak_service_privacy_rounding(tmp_path: Path) -> None:
    outbreak_file = tmp_path / "outbreaks.json"
    service = OutbreakService(outbreak_file)

    # Exact coordinates: 0.1234567, 35.7654321
    rep = service.add_report(
        disease_label="Tomato_Late_blight",
        crop="Tomato",
        latitude=0.1234567,
        longitude=35.7654321,
        confidence=0.89,
        severity_category="Severe",
    )

    # Must round to ~1.1km (2 decimal places)
    assert rep["lat"] == 0.12
    assert rep["lng"] == 35.77

    points = service.get_points(crop="Tomato")
    assert any(p["id"] == rep["id"] for p in points)

    alerts = service.get_alerts()
    assert isinstance(alerts, list)


def test_feedback_service(tmp_path: Path) -> None:
    service = FeedbackService(tmp_path)
    item = service.add_feedback(
        request_id="req-test-123",
        predicted_label="Tomato_Early_blight",
        user_label="Tomato_Late_blight",
        comment="Lesions are greasy and water-soaked",
        photo_consent=False,
    )
    assert item["status"] == "pending"
    assert item["user_label"] == "Tomato_Late_blight"

    reviewed = service.review_item(item["id"], "approved")
    assert reviewed is not None and reviewed["status"] == "approved"

    queue = service.get_queue(status="approved")
    assert any(q["id"] == item["id"] for q in queue)


def test_analytics_service() -> None:
    store = ScanStore(limit=100)
    store.add_scan(
        {
            "request_id": "r1",
            "label": "Tomato_Late_blight",
            "status": "ok",
            "confidence": 0.92,
            "latency_ms": 350,
        }
    )
    store.add_scan(
        {
            "request_id": "r2",
            "label": "Not_a_leaf",
            "status": "unsupported",
            "confidence": 0.40,
            "latency_ms": 310,
        }
    )

    analytics = AnalyticsService(store)
    summary = analytics.get_summary()

    assert summary["total_scans"] >= 2
    assert "class_distribution" in summary
    assert "scans_past_7_days" in summary
    assert "rejection_rate_percent" in summary
    assert "average_confidence" in summary


@pytest.mark.anyio
async def test_feature_endpoints() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        # Outbreak points
        pts = await client.get("/api/v1/outbreak/points")
        assert pts.status_code == 200
        assert isinstance(pts.json(), list)

        # Outbreak report
        rep = await client.post(
            "/api/v1/outbreak/report",
            json={
                "disease_label": "Tomato_Early_blight",
                "crop": "Tomato",
                "latitude": -0.28456,
                "longitude": 36.05987,
                "confidence": 0.88,
                "severity_category": "Moderate",
            },
        )
        assert rep.status_code == 200
        assert rep.json()["lat"] == -0.28
        assert rep.json()["lng"] == 36.06

        # Outbreak alerts
        alerts = await client.get("/api/v1/outbreak/alerts")
        assert alerts.status_code == 200

        # Feedback submission & admin review
        fb = await client.post(
            "/api/v1/feedback",
            json={
                "request_id": "req-api-test",
                "label": "Tomato_Late_blight",
                "comment": "Confirmed by extension officer",
                "photo_consent": False,
            },
        )
        assert fb.status_code == 202

        queue = await client.get("/api/v1/admin/feedback")
        assert queue.status_code == 200

        # Analytics summary
        analytics_resp = await client.get("/api/v1/admin/analytics/summary")
        assert analytics_resp.status_code == 200
        assert "class_distribution" in analytics_resp.json()

        # Localized diseases endpoint
        dis_sw = await client.get("/api/v1/diseases?lang=sw")
        assert dis_sw.status_code == 200
        assert any(d["crop"] == "Nyanya" for d in dis_sw.json())

        # Weather risk endpoint
        weather_resp = await client.get(
            "/api/v1/weather/risk?latitude=-0.3&longitude=36.1"
        )
        assert weather_resp.status_code == 200
        assert "data" in weather_resp.json()
