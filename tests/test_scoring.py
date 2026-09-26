from scoring import evaluate_entries, forward_return_pct

SERIES = [("2026-09-01", 100.0), ("2026-09-08", 110.0), ("2026-09-02", 100.0), ("2026-09-09", 90.0)]


def test_forward_return_uses_recorded_price():
    prices = dict(SERIES)
    assert forward_return_pct(prices, "2026-09-01") == 10.0
    assert forward_return_pct(prices, "2026-09-01", start_price=200.0) == -45.0
    assert forward_return_pct(prices, "2026-09-05") is None


def test_evaluate_entries_hits_and_brier():
    entries = [
        {"date": "2026-09-01", "recommendation": "buy", "prob_up_7d": 70},    # up -> hit
        {"date": "2026-09-02", "recommendation": "buy", "prob_up_7d": 70},    # down -> miss
        {"date": "2026-09-03", "recommendation": "hold", "prob_up_7d": 50},   # no outcome yet
    ]
    report = evaluate_entries(entries, SERIES)
    summary = report["summary"]
    assert summary["evaluated_calls"] == 2
    assert summary["directional_hit_rate_pct"] == 50.0
    assert summary["brier_score"] == round((0.3 ** 2 + 0.7 ** 2) / 2, 4)


def test_legacy_hold_entries_have_no_hit_or_brier():
    report = evaluate_entries([{"date": "2026-09-01", "recommendation": "hold", "confidence": 72}], SERIES)
    row = report["rows"][0]
    assert row["hit"] is None and row["brier"] is None
    assert report["summary"]["hold_calls"] == 1
