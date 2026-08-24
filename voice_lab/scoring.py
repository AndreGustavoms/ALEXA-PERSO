from __future__ import annotations

from typing import Any


WEIGHTS = {
    "end_to_end_accuracy": 0.35,
    "low_normal_voice_recall": 0.25,
    "speech_cut_rate": 0.20,
    "wake_recall": 0.10,
    "false_wake_rate": 0.05,
    "latency_score": 0.05,
}


def score_configuration(metrics: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in WEIGHTS if metrics.get(key) is None]
    if missing:
        return {"status": "insufficient_data", "score": None, "missing": missing}
    clipping = float(metrics.get("clipping", 0.0))
    if clipping > 0.005:
        return {
            "status": "rejected_by_guardrail",
            "score": None,
            "reason": "clipping_above_0.5_percent",
        }
    values = {
        **metrics,
        "speech_cut_rate": 1.0 - float(metrics["speech_cut_rate"]),
        "false_wake_rate": 1.0 - float(metrics["false_wake_rate"]),
    }
    score = sum(float(values[key]) * weight for key, weight in WEIGHTS.items())
    return {"status": "scored", "score": round(score, 4), "missing": []}
