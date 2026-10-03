"""Summarize three-seed architecture comparison without selecting on test results."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "models/v2/runs"
OUTPUT = ROOT / "reports/v2/model_comparison.json"


def summarize() -> dict[str, dict[str, dict[str, float | int]]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for metrics_path in RUNS.glob("*/*/seed_*/metrics.json"):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        values[metrics["stage"]][metrics["architecture"]].append(float(metrics["val_macro_f1"]))
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for stage, architectures in values.items():
        result[stage] = {
            architecture: {
                "seeds": len(scores),
                "mean_macro_f1": sum(scores) / len(scores),
                "std_macro_f1": (sum((score - sum(scores) / len(scores)) ** 2 for score in scores) / len(scores))
                ** 0.5,
            }
            for architecture, scores in architectures.items()
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
