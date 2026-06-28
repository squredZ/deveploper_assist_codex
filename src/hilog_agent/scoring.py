from typing import Literal


def score_feature_keywords(
    question: str,
    keywords: list[str],
    symptoms: list[str],
) -> int:
    score = 0
    for keyword in keywords:
        if keyword and keyword in question:
            score += 3
    for symptom in symptoms:
        if symptom and symptom in question:
            score += 3
    return score


def confidence_label(score: float) -> Literal["high", "medium", "low"]:
    if score >= 70:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
