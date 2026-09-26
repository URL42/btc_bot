import json

import pytest

import analyze
from notifier import format_message


@pytest.fixture
def history_file(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr(analyze, "HISTORY_FILE", path)
    return path


def test_recommendation_thresholds():
    assert analyze.recommendation_for(60) == "buy"
    assert analyze.recommendation_for(59.9) == "hold"
    assert analyze.recommendation_for(40) == "avoid"
    assert analyze.conviction_for(50) == 0
    assert analyze.conviction_for(80) == 60


@pytest.mark.parametrize("value,expected", [(62, 62.0), ("62%", 62.0), (0.62, 62.0), (140, 100.0)])
def test_parse_probability(value, expected):
    assert analyze._parse_probability({"prob_up_7d": value}) == pytest.approx(expected)


def test_parse_probability_missing():
    with pytest.raises(ValueError):
        analyze._parse_probability({"recommendation": "buy"})


def test_save_history_upserts_same_day_and_prunes(history_file):
    today = analyze.today_utc()
    history_file.write_text(json.dumps([
        {"date": "2000-01-01", "recommendation": "hold"},
        {"date": today, "recommendation": "hold"},
    ]))
    analyze.save_history({"date": today, "recommendation": "buy"})
    saved = json.loads(history_file.read_text())
    assert saved == [{"date": today, "recommendation": "buy"}]


def test_format_message_escapes_markdown(history_file):
    history_file.write_text("[]")
    msg = format_message({
        "recommendation": "hold",
        "prob_up_7d": 55.0,
        "quant_score": 12,
        "price_at_recommendation": 84000.0,
        "reasoning": ["MA_7 above MA_30 *strongly*"],
        "provider": "ollama",
        "model": "qwen_test",
        "track_record": {"evaluated_calls": 0},
    })
    assert "MA\\_7 above MA\\_30 \\*strongly\\*" in msg
    assert "qwen\\_test" in msg
    assert "P(up in 7d):* 55%" in msg
