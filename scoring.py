# scoring.py
"""
Score past recommendations against what the price actually did.

A call is judged over HORIZON_DAYS: BUY is a hit if price rose, AVOID a hit if it fell.
HOLD makes no directional claim, so it is only scored through its probability (Brier).
"""

from datetime import date, timedelta
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

HORIZON_DAYS = 7


def forward_return_pct(
    price_by_date: Dict[str, float],
    start_date: str,
    start_price: Optional[float] = None,
    horizon: int = HORIZON_DAYS,
) -> Optional[float]:
    try:
        end_date = (date.fromisoformat(start_date) + timedelta(days=horizon)).isoformat()
    except ValueError:
        return None
    end_price = price_by_date.get(end_date)
    start_price = start_price or price_by_date.get(start_date)
    if not end_price or not start_price:
        return None
    return (end_price - start_price) / start_price * 100


def brier(prob_pct: float, went_up: bool) -> float:
    return (prob_pct / 100 - (1.0 if went_up else 0.0)) ** 2


def evaluate_entries(
    entries: Sequence[Dict],
    price_series: Sequence[Tuple[str, float]],
    horizon: int = HORIZON_DAYS,
) -> Dict:
    """Return per-entry outcomes plus summary stats for entries whose horizon has elapsed."""
    price_by_date = dict(price_series)
    rows: List[Dict] = []

    for entry in entries:
        ret = forward_return_pct(
            price_by_date,
            entry.get("date", ""),
            entry.get("price_at_recommendation"),
            horizon,
        )
        if ret is None:
            continue
        rec = str(entry.get("recommendation", "")).lower()
        went_up = ret > 0
        prob = entry.get("prob_up_7d")
        rows.append({
            "date": entry["date"],
            "recommendation": rec,
            "prob_up_7d": prob,
            "confidence": entry.get("confidence"),
            "return_pct": round(ret, 2),
            "hit": {"buy": went_up, "avoid": not went_up}.get(rec),
            "brier": round(brier(prob, went_up), 4) if isinstance(prob, (int, float)) else None,
        })

    directional = [r for r in rows if r["hit"] is not None]
    briers = [r["brier"] for r in rows if r["brier"] is not None]

    summary = {
        "horizon_days": horizon,
        "evaluated_calls": len(rows),
        "realized_up_rate_pct": round(100 * mean(r["return_pct"] > 0 for r in rows), 1) if rows else None,
        "directional_calls": len(directional),
        "directional_hit_rate_pct": round(100 * mean(r["hit"] for r in directional), 1) if directional else None,
        "hold_calls": sum(r["recommendation"] == "hold" for r in rows),
        "probabilistic_calls": len(briers),
        "brier_score": round(mean(briers), 4) if briers else None,
        "brier_coin_flip": 0.25,
        "avg_prob_up_pct": (
            round(mean(r["prob_up_7d"] for r in rows if r["brier"] is not None), 1) if briers else None
        ),
    }
    return {"summary": summary, "rows": rows}
