# indicators.py
"""
Deterministic market features and a transparent rule-based "quant score".

Everything here is pure (no network, no LLM) so it can be backtested by evaluate.py.
"""

from math import copysign, tanh
from statistics import mean, pstdev
from typing import Dict, List, Optional, Sequence, Tuple

# Relative weight of each quant-score component; renormalised over available components.
QUANT_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.25,
    "rsi": 0.15,
    "volume": 0.10,
    "sentiment": 0.20,
}


def round_optional(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, ndigits)


def prepare_price_series(btc_history: Sequence[Dict]) -> List[Tuple[str, float]]:
    series: List[Tuple[str, float]] = []
    for day in btc_history:
        try:
            date = day["date"]
            price = float(day["price_usd"])
        except (KeyError, TypeError, ValueError):
            continue
        if not isinstance(date, str):
            continue
        series.append((date, price))

    series.sort(key=lambda item: item[0])
    return series


def percentage_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def rolling_average(values: List[float], window: int) -> Optional[float]:
    if len(values) < window or window <= 0:
        return None
    return mean(values[-window:])


def calculate_rsi(values: List[float], period: int = 14) -> Optional[float]:
    """Wilder-smoothed RSI (the standard definition used by charting platforms)."""
    if len(values) <= period:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]

    avg_gain = mean(max(d, 0.0) for d in deltas[:period])
    avg_loss = mean(max(-d, 0.0) for d in deltas[:period])
    for delta in deltas[period:]:
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period

    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_volatility(values: List[float], window: int = 30) -> Optional[float]:
    """Annualised volatility of daily returns (BTC trades 365 days a year)."""
    if len(values) <= window:
        return None
    recent = values[-(window + 1):]
    returns = [
        (recent[i] - recent[i - 1]) / recent[i - 1]
        for i in range(1, len(recent))
        if recent[i - 1] != 0
    ]
    if len(returns) < 2:
        return None
    return pstdev(returns) * (365 ** 0.5)


def build_price_metrics(series: List[Tuple[str, float]]) -> Dict:
    if not series:
        return {}

    dates = [d for d, _ in series]
    closes = [p for _, p in series]
    latest_price = closes[-1]

    def change_over(days: int) -> Optional[float]:
        if len(closes) <= days:
            return None
        return percentage_change(latest_price, closes[-(days + 1)])

    return {
        "latest_date": dates[-1],
        "latest_price": round(latest_price, 2),
        "change_7d_pct": round_optional(change_over(7)),
        "change_30d_pct": round_optional(change_over(30)),
        "change_90d_pct": round_optional(change_over(90)),
        "ma_7": round_optional(rolling_average(closes, 7)),
        "ma_30": round_optional(rolling_average(closes, 30)),
        "ma_90": round_optional(rolling_average(closes, 90)),
        "rsi_14": round_optional(calculate_rsi(closes, 14)),
        "volatility_30d_annualised": round_optional(calculate_volatility(closes, 30)),
        "recent_prices": [
            {"date": dates[i], "price": round(closes[i], 2)}
            for i in range(max(0, len(closes) - 14), len(closes))
        ],
    }


def build_volume_metrics(btc_history: Sequence[Dict]) -> Dict:
    volumes: List[float] = []
    for day in btc_history:
        vol = day.get("volume_usd")
        if isinstance(vol, (int, float)) and vol > 0:
            volumes.append(float(vol))

    if not volumes:
        return {}

    current = volumes[-1]
    avg_7d = rolling_average(volumes, 7)
    avg_30d = rolling_average(volumes, 30)
    vol_vs_30d = percentage_change(current, avg_30d) if avg_30d else None

    return {
        "volume_24h_usd": round_optional(current, 0),
        "avg_volume_7d_usd": round_optional(avg_7d, 0),
        "avg_volume_30d_usd": round_optional(avg_30d, 0),
        "volume_vs_30d_avg_pct": round_optional(vol_vs_30d),
    }


def _sign(value: float) -> float:
    return 0.0 if value == 0 else copysign(1.0, value)


def quant_score(
    price_metrics: Dict,
    volume_metrics: Dict,
    fear_greed_value: Optional[float],
) -> Dict:
    """
    Rule-based score from -100 (bearish) to +100 (bullish).

    Components (each in [-1, 1]):
      trend     - MA7 vs MA30, MA30 vs MA90, price vs MA90 alignment
      momentum  - 30-day % change, squashed with tanh (±15% ≈ ±0.76)
      rsi       - mean reversion only at extremes (>70 bearish, <30 bullish)
      volume    - above-average volume confirms the 7-day direction
      sentiment - Fear & Greed read contrarian (extreme fear bullish)
    """
    components: Dict[str, float] = {}

    price = price_metrics.get("latest_price")
    ma7, ma30, ma90 = (price_metrics.get(k) for k in ("ma_7", "ma_30", "ma_90"))
    if None not in (price, ma7, ma30, ma90):
        components["trend"] = mean([_sign(ma7 - ma30), _sign(ma30 - ma90), _sign(price - ma90)])

    change_30d = price_metrics.get("change_30d_pct")
    if change_30d is not None:
        components["momentum"] = tanh(change_30d / 15)

    rsi = price_metrics.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            components["rsi"] = -(rsi - 70) / 30
        elif rsi < 30:
            components["rsi"] = (30 - rsi) / 30
        else:
            components["rsi"] = 0.0

    vol_vs_avg = volume_metrics.get("volume_vs_30d_avg_pct")
    change_7d = price_metrics.get("change_7d_pct")
    if vol_vs_avg is not None and change_7d is not None:
        components["volume"] = _sign(change_7d) * max(0.0, tanh(vol_vs_avg / 50))

    if isinstance(fear_greed_value, (int, float)):
        components["sentiment"] = (50 - fear_greed_value) / 50

    total_weight = sum(QUANT_WEIGHTS[k] for k in components)
    if total_weight == 0:
        return {"score": 0, "components": {}}

    raw = sum(QUANT_WEIGHTS[k] * v for k, v in components.items()) / total_weight
    return {
        "score": int(round(100 * raw)),
        "components": {k: round(v, 2) for k, v in components.items()},
    }
