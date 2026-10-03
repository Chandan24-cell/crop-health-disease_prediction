import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


class OutbreakService:
    def __init__(self, data_file: Path | None = None) -> None:
        self.data_file = data_file or Path("backend/data/outbreaks.json")
        self.reports: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.data_file.exists():
            try:
                self.reports = json.loads(self.data_file.read_text(encoding="utf-8"))
                return
            except Exception as exc:
                logger.warning(f"Could not load outbreak data: {exc}")

        # Seed clearly labeled illustrative India reports until user reports are available.
        self.reports = [
            {"id":"sample-1","disease":"Tomato_Early_blight","crop":"Tomato","lat":19.08,"lng":72.88,"intensity":0.8,"timestamp":"2026-10-01T09:00:00Z","severity":"Moderate","sample":True,"state":"Maharashtra"},
            {"id":"sample-2","disease":"Maize_Common_rust","crop":"Maize","lat":12.97,"lng":77.59,"intensity":0.74,"timestamp":"2026-10-02T09:00:00Z","severity":"Mild","sample":True,"state":"Karnataka"},
            {"id":"sample-3","disease":"Potato_Late_blight","crop":"Potato","lat":26.85,"lng":80.95,"intensity":0.88,"timestamp":"2026-10-03T09:00:00Z","severity":"Severe","sample":True,"state":"Uttar Pradesh"},
        ]

    def _save(self) -> None:
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            self.data_file.write_text(
                json.dumps(self.reports, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"Could not persist outbreak reports: {exc}")

    def add_report(
        self,
        disease_label: str,
        crop: str,
        latitude: float,
        longitude: float,
        confidence: float = 1.0,
        severity_category: str = "Moderate",
    ) -> dict:
        # Round GPS to ~1.1km precision for user privacy protection
        rounded_lat = round(float(latitude), 2)
        rounded_lng = round(float(longitude), 2)
        timestamp = datetime.now(timezone.utc).isoformat()

        report = {
            "id": f"out-{uuid4().hex[:8]}",
            "disease": disease_label,
            "crop": crop,
            "lat": rounded_lat,
            "lng": rounded_lng,
            "intensity": round(float(confidence), 2),
            "timestamp": timestamp,
            "severity": severity_category,
            "sample": False,
        }
        self.reports.append(report)
        self._save()
        return report

    def get_points(
        self, crop: str | None = None, disease: str | None = None
    ) -> list[dict]:
        results = self.reports
        if crop and crop.lower() != "all":
            results = [r for r in results if r.get("crop", "").lower() == crop.lower()]
        if disease and disease.lower() != "all":
            results = [
                r for r in results if r.get("disease", "").lower() == disease.lower()
            ]
        return results

    def get_alerts(self) -> list[dict]:
        # Group reports by rounded area and disease to generate regional alerts
        clusters: dict[tuple[float, float, str], list[dict]] = {}
        for r in self.reports:
            key = (round(r["lat"], 1), round(r["lng"], 1), r["disease"])
            clusters.setdefault(key, []).append(r)

        alerts = []
        for (lat, lng, disease), group in clusters.items():
            if len(group) >= 2:
                crop = group[0].get("crop", "Crops")
                clean_name = disease.split("_", 1)[-1].replace("_", " ")
                risk_level = "High" if len(group) >= 3 else "Medium"
                alerts.append(
                    {
                        "region_name": f"Area ({lat}°, {lng}°)",
                        "disease": clean_name,
                        "case_count": len(group),
                        "risk_level": risk_level,
                        "recommendation": (
                            f"Multiple {clean_name} cases reported in this zone. "
                            f"Inspect {crop} fields promptly and ensure prophylactic fungicide or cultural measures."
                        ),
                    }
                )
        return alerts
