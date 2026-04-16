def make_decision(importance_score: float, alert_threshold: float) -> str:
    if importance_score >= alert_threshold:
        return "ALERT"
    if importance_score >= alert_threshold - 2:
        return "DAILY_DIGEST"
    return "IGNORE"
