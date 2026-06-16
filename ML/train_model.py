"""
Employee Performance Predictor
Uses a trained Random Forest model to predict performance category.
"""

import os, joblib, numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ML", "model.pkl")

def predict_performance(features: dict) -> str:
    """
    Predict performance category from quiz features.
    
    Args:
        features: dict with keys: score, accuracy, time_taken, attempt_number, previous_avg
    
    Returns:
        'High Performer' | 'Average Performer' | 'Needs Improvement'
    """
    try:
        model = joblib.load(MODEL_PATH)
        X = np.array([[
            features["score"],
            features["accuracy"],
            features["time_taken"],
            features["attempt_number"],
            features["previous_avg"]
        ]])
        label_map = {0: "Needs Improvement", 1: "Average Performer", 2: "High Performer"}
        pred = model.predict(X)[0]
        label = label_map.get(int(pred), "Average Performer")
        return _apply_sanity_override(features, label)
    except Exception as e:
        print(f"[ML Predictor] Model not found or error: {e}. Using rule-based fallback.")
        return _rule_based(features)


def _apply_sanity_override(features: dict, predicted_label: str) -> str:
    """
    Guardrail on top of the ML model's prediction.

    The model weighs `previous_avg` heavily (it's strongly correlated with
    the class label in the synthetic training data), which can cause a
    near-perfect *current* attempt to be downgraded to "Average Performer"
    just because the employee's earlier attempts were weak - or, less
    commonly, a very poor current attempt to be inflated by a strong history.

    This override only kicks in for clear-cut extremes on THIS attempt;
    the model's prediction is left untouched for the ambiguous middle range,
    where factoring in history/trend genuinely adds value.
    """
    score = features.get("score", 0)
    accuracy = features.get("accuracy", score)

    if score >= 85 and accuracy >= 85:
        return "High Performer"
    if score <= 30:
        return "Needs Improvement"

    return predicted_label


def _rule_based(features: dict) -> str:
    """Simple rule-based fallback when model isn't trained yet."""
    score = features.get("score", 0)
    if score >= 80:
        return "High Performer"
    elif score >= 50:
        return "Average Performer"
    else:
        return "Needs Improvement"