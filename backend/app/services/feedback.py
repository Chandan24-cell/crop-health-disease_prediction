import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path("backend/data/feedback")
        self.queue_file = self.data_dir / "queue.json"
        self.images_dir = self.data_dir / "images"
        self.queue: list[dict] = []
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir.mkdir(parents=True, exist_ok=True)
            if self.queue_file.exists():
                self.queue = json.loads(self.queue_file.read_text(encoding="utf-8"))
            else:
                # Initial demo/seed item for admin preview
                self.queue = [
                    {
                        "id": "feed-demo-1",
                        "request_id": "req-init-101",
                        "predicted_label": "Tomato_Early_blight",
                        "user_label": "Tomato_Late_blight",
                        "comment": "Greasy water-soaked spots appeared after 3 days of heavy rain.",
                        "has_photo": False,
                        "photo_path": None,
                        "timestamp": "2026-10-02T14:30:00Z",
                        "status": "pending",
                    }
                ]
                self._save()
        except Exception as exc:
            logger.warning(f"Failed to initialize feedback storage: {exc}")

    def _save(self) -> None:
        try:
            self.queue_file.write_text(
                json.dumps(self.queue, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"Failed to save feedback queue: {exc}")

    def add_feedback(
        self,
        request_id: str,
        predicted_label: str,
        user_label: str,
        comment: str | None = None,
        photo_consent: bool = False,
        image_b64: str | None = None,
    ) -> dict:
        item_id = f"fb-{uuid4().hex[:8]}"
        photo_path = None
        has_photo = False

        if photo_consent and image_b64:
            try:
                # Strip data URL header if present
                clean_b64 = image_b64
                if "," in clean_b64:
                    clean_b64 = clean_b64.split(",", 1)[1]
                img_data = base64.b64decode(clean_b64)
                img_filename = f"{item_id}.jpg"
                img_dest = self.images_dir / img_filename
                img_dest.write_bytes(img_data)
                photo_path = str(img_dest)
                has_photo = True
            except Exception as exc:
                logger.warning(f"Could not save consented photo: {exc}")

        item = {
            "id": item_id,
            "request_id": request_id,
            "predicted_label": predicted_label,
            "user_label": user_label,
            "comment": comment,
            "has_photo": has_photo,
            "photo_path": photo_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        self.queue.append(item)
        self._save()
        return item

    def get_queue(self, status: str | None = None) -> list[dict]:
        if status and status != "all":
            return [x for x in self.queue if x.get("status") == status]
        return self.queue

    def review_item(self, item_id: str, status: str) -> dict | None:
        for item in self.queue:
            if item.get("id") == item_id:
                item["status"] = status
                item["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                return item
        return None

    def export_approved_dataset(self) -> list[dict]:
        return [
            x
            for x in self.queue
            if x.get("status") == "approved" and x.get("has_photo")
        ]
