"""
Personalized Feedback Generator
Uses Google Gemini API to generate feedback based on quiz performance.
"""

import os, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


def generate_feedback(features: dict, performance_label: str) -> str:
    """
    Generate personalized performance feedback.

    Args:
        features: dict with score, accuracy, time_taken, attempt_number, previous_avg
        performance_label: predicted performance category

    Returns:
        Feedback string
    """
    if not GEMINI_API_KEY:
        return _static_feedback(features, performance_label)

    score = features.get("score", 0)
    accuracy = features.get("accuracy", 0)
    time_taken = features.get("time_taken", 0)
    attempt = features.get("attempt_number", 1)
    prev_avg = features.get("previous_avg", score)

    prompt = f"""
You are an HR system that writes short, helpful employee assessment feedback.

Employee quiz result:
- Score: {score}%
- Accuracy: {accuracy}%
- Time taken: {time_taken} minutes
- Attempt number: {attempt}
- Previous average score: {prev_avg}%
- Performance category: {performance_label}

Write 2-3 sentences of honest, constructive, professional feedback for this employee.
Keep it natural and specific. Do not use bullet points. Do not mention AI or machine learning.
""".strip()

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=10
        )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except Exception as e:
        print("[Feedback Generator] API error:", e, ". Using static feedback.")
        return _static_feedback(features, performance_label)


def _static_feedback(features: dict, label: str) -> str:
    """Fallback feedback when API is unavailable."""
    score = features.get("score", 0)
    time_taken = features.get("time_taken", 0)
    attempt = features.get("attempt_number", 1)

    if label == "High Performer":
        return (f"You scored {score}% and completed the assessment in {time_taken} minutes - excellent work! "
                "Your results show a strong grasp of the material. Keep up the consistent performance.")
    elif label == "Average Performer":
        return (f"You scored {score}%, which is a decent result. "
                "There is room to improve in certain areas - reviewing the topics where you lost marks would help. "
                f"{'This is your first attempt; practice will help.' if attempt == 1 else 'You are making progress with each attempt.'}")
    else:
        return (f"You scored {score}% on this assessment. "
                "It looks like some topics need more attention before the next attempt. "
                "Consider reviewing the material carefully and trying again when ready.")
