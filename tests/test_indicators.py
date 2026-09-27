from indicators import calculate_rsi, calculate_volatility, quant_score


def test_rsi_extremes():
    assert calculate_rsi(list(range(1, 40))) == 100.0
    assert calculate_rsi(list(range(40, 1, -1))) == 0.0
    assert calculate_rsi([10.0] * 30) == 50.0
    assert calculate_rsi([1, 2, 3]) is None


def test_rsi_wilder_is_bounded_and_mixed():
    values = [100 + (i % 5) - (i % 3) for i in range(60)]
    rsi = calculate_rsi(values)
    assert 0 < rsi < 100


def test_volatility_needs_window():
    assert calculate_volatility([1.0] * 10, window=30) is None
    assert calculate_volatility([100.0] * 40, window=30) == 0.0


def test_quant_score_bullish_and_bearish():
    bull = quant_score(
        {"latest_price": 110, "ma_7": 105, "ma_30": 100, "ma_90": 90, "change_30d_pct": 20,
         "change_7d_pct": 5, "rsi_14": 55},
        {"volume_vs_30d_avg_pct": 40},
        20,  # extreme fear -> contrarian bullish
    )
    bear = quant_score(
        {"latest_price": 80, "ma_7": 85, "ma_30": 90, "ma_90": 100, "change_30d_pct": -20,
         "change_7d_pct": -5, "rsi_14": 45},
        {"volume_vs_30d_avg_pct": 40},
        85,
    )
    assert 50 < bull["score"] <= 100
    assert -100 <= bear["score"] < -50


def test_quant_score_handles_missing_inputs():
    assert quant_score({}, {}, None) == {"score": 0, "components": {}}
    only_fng = quant_score({}, {}, 75)
    assert only_fng["score"] == -50
