from collections import deque
from typing import Any


class ScanStore:
    def __init__(self, limit: int = 500) -> None:
        self.records: deque[dict[str, Any]] = deque(maxlen=limit)
        self.feedback: deque[dict[str, Any]] = deque(maxlen=limit)

    def add_scan(self, record: dict[str, Any]) -> None:
        self.records.appendleft(record)
