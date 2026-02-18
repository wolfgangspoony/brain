"""
Belief confidence calibration for the Brain.
Tracks predictions, records outcomes, and calculates calibration metrics.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

CALIBRATION_FILE = Path(__file__).parent / "calibration_data.json"

# Expected accuracy for each confidence level
EXPECTED_ACCURACY = {
    "uncertain": 0.3,
    "leaning": 0.5,
    "moderate": 0.65,
    "confident": 0.8,
    "certain": 0.95
}


def _load_data() -> dict:
    """Load calibration data from file."""
    if not CALIBRATION_FILE.exists():
        return {"predictions": [], "version": 1}

    try:
        with open(CALIBRATION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"predictions": [], "version": 1}


def _save_data(data: dict) -> None:
    """Save calibration data to file."""
    with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_prediction(
    belief_topic: str,
    confidence: str,
    prediction: str,
    context: str = ""
) -> str:
    """
    Record a prediction made based on a belief.

    Args:
        belief_topic: Topic of the belief
        confidence: Confidence level of the belief
        prediction: What was predicted
        context: Optional context for the prediction

    Returns:
        Prediction ID
    """
    data = _load_data()

    prediction_id = f"pred_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(data['predictions'])}"

    entry = {
        "id": prediction_id,
        "belief_topic": belief_topic,
        "confidence": confidence,
        "prediction": prediction,
        "context": context,
        "timestamp": datetime.now().isoformat(),
        "outcome": None,
        "outcome_recorded_at": None
    }

    data["predictions"].append(entry)
    _save_data(data)

    return prediction_id


def record_outcome(prediction_id: str, was_correct: bool, notes: str = "") -> bool:
    """
    Record whether a prediction was correct.

    Args:
        prediction_id: ID of the prediction
        was_correct: Whether the prediction was correct
        notes: Optional notes about the outcome

    Returns:
        True if successful
    """
    data = _load_data()

    for pred in data["predictions"]:
        if pred["id"] == prediction_id:
            pred["outcome"] = was_correct
            pred["outcome_recorded_at"] = datetime.now().isoformat()
            pred["outcome_notes"] = notes
            _save_data(data)
            return True

    return False


def get_pending_predictions(limit: int = 10) -> list[dict]:
    """
    Get predictions that haven't had outcomes recorded yet.

    Args:
        limit: Maximum number to return

    Returns:
        List of pending predictions
    """
    data = _load_data()

    pending = [p for p in data["predictions"] if p["outcome"] is None]
    pending.sort(key=lambda x: x["timestamp"], reverse=True)

    return pending[:limit]


def calculate_calibration() -> dict:
    """
    Calculate how well-calibrated each confidence level is.

    Returns:
        Dict with calibration metrics per confidence level
    """
    data = _load_data()

    # Group by confidence level
    by_confidence = {}
    for pred in data["predictions"]:
        if pred["outcome"] is None:
            continue

        conf = pred["confidence"]
        if conf not in by_confidence:
            by_confidence[conf] = {"correct": 0, "total": 0}

        by_confidence[conf]["total"] += 1
        if pred["outcome"]:
            by_confidence[conf]["correct"] += 1

    # Calculate calibration
    result = {}
    for conf, counts in by_confidence.items():
        if counts["total"] > 0:
            actual = counts["correct"] / counts["total"]
            expected = EXPECTED_ACCURACY.get(conf, 0.5)
            result[conf] = {
                "expected": expected,
                "actual": round(actual, 3),
                "n": counts["total"],
                "correct": counts["correct"],
                "deviation": round(actual - expected, 3),
                "is_overconfident": actual < expected,
                "is_underconfident": actual > expected
            }

    return result


def get_calibration_summary() -> str:
    """
    Get a human-readable calibration summary.

    Returns:
        Summary string
    """
    cal = calculate_calibration()

    if not cal:
        return "No calibration data yet. Record some predictions and outcomes first."

    lines = ["**Confidence Calibration:**\n"]

    for conf in ["uncertain", "leaning", "moderate", "confident", "certain"]:
        if conf not in cal:
            continue

        c = cal[conf]
        status = ""
        if c["is_overconfident"]:
            status = " (overconfident)"
        elif c["is_underconfident"]:
            status = " (underconfident)"

        lines.append(f"- **{conf}**: {c['actual']:.0%} accurate (expected {c['expected']:.0%}), n={c['n']}{status}")

    return "\n".join(lines)


def suggest_confidence_adjustment(stated_confidence: str) -> tuple[str, str]:
    """
    Suggest an adjusted confidence based on calibration history.

    Args:
        stated_confidence: The confidence level stated

    Returns:
        Tuple of (suggested_confidence, reason)
    """
    cal = calculate_calibration()

    if stated_confidence not in cal:
        return stated_confidence, "Not enough data for this confidence level"

    c = cal[stated_confidence]

    # Need enough data points for reliable adjustment
    if c["n"] < 5:
        return stated_confidence, f"Only {c['n']} data points - need at least 5"

    deviation = c["deviation"]
    levels = ["uncertain", "leaning", "moderate", "confident", "certain"]
    current_idx = levels.index(stated_confidence) if stated_confidence in levels else 2

    # If consistently overconfident (actual < expected), suggest lower
    if deviation < -0.15 and current_idx > 0:
        suggested = levels[current_idx - 1]
        return suggested, f"Historically overconfident at '{stated_confidence}' ({c['actual']:.0%} vs {c['expected']:.0%})"

    # If consistently underconfident (actual > expected), suggest higher
    if deviation > 0.15 and current_idx < len(levels) - 1:
        suggested = levels[current_idx + 1]
        return suggested, f"Historically underconfident at '{stated_confidence}' ({c['actual']:.0%} vs {c['expected']:.0%})"

    return stated_confidence, "Well-calibrated at this level"


def get_calibration_stats() -> dict:
    """
    Get overall calibration statistics.

    Returns:
        Dict with overall stats
    """
    data = _load_data()

    total = len(data["predictions"])
    with_outcome = sum(1 for p in data["predictions"] if p["outcome"] is not None)
    correct = sum(1 for p in data["predictions"] if p["outcome"] is True)

    return {
        "total_predictions": total,
        "outcomes_recorded": with_outcome,
        "pending": total - with_outcome,
        "correct": correct,
        "incorrect": with_outcome - correct,
        "overall_accuracy": round(correct / with_outcome, 3) if with_outcome > 0 else None
    }
