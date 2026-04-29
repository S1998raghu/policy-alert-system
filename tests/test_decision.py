from app.decision import make_decision


def test_alert_at_threshold():
    assert make_decision(7.0, 7.0) == "ALERT"


def test_alert_above_threshold():
    assert make_decision(9.5, 7.0) == "ALERT"


def test_daily_digest_just_below_threshold():
    assert make_decision(6.0, 7.0) == "DAILY_DIGEST"


def test_daily_digest_at_lower_bound():
    assert make_decision(5.0, 7.0) == "DAILY_DIGEST"


def test_ignore_below_digest_band():
    assert make_decision(4.9, 7.0) == "IGNORE"


def test_ignore_zero_score():
    assert make_decision(0.0, 7.0) == "IGNORE"


def test_high_threshold():
    assert make_decision(8.0, 10.0) == "DAILY_DIGEST"
    assert make_decision(10.0, 10.0) == "ALERT"
    assert make_decision(7.9, 10.0) == "IGNORE"
