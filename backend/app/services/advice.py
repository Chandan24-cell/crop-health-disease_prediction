import json
from pathlib import Path
from typing import Any


class AdviceService:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.stores: dict[str, dict[str, Any]] = {}
        self.data: dict[str, Any] = {}
        self._load_all()

    def _load_all(self) -> None:
        parent = self.base_path.parent
        # Primary English / default
        if self.base_path.exists():
            try:
                self.data = json.loads(self.base_path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        self.stores["en"] = self.data

        # Additional languages: sw, hi, ta
        for lang in ["sw", "hi", "ta"]:
            lang_path = parent / f"diseases_{lang}.json"
            if lang_path.exists():
                try:
                    self.stores[lang] = json.loads(
                        lang_path.read_text(encoding="utf-8")
                    )
                except Exception:
                    self.stores[lang] = self.data
            else:
                self.stores[lang] = self.data

    def get(self, disease: str, severity: str, language: str = "en") -> dict[str, str]:
        lang_data = self.stores.get(language, self.data)
        item = lang_data.get(disease) or self.data.get(disease)
        if not item:
            return {}
        level = severity.lower()
        return {
            "crop": item.get("crop", ""),
            "cause": item.get("cause", ""),
            "symptoms": item.get("symptoms", ""),
            "immediate_actions": item.get("immediate_actions", ""),
            "cultural_controls": item.get("cultural_controls", ""),
            "prevention": item.get("prevention", ""),
            "specific_advice": item.get("severity_advice", {}).get(level, ""),
            "when_to_seek_expert": item.get("when_to_seek_expert", ""),
            "safety_note": item.get("safety_note", ""),
        }
