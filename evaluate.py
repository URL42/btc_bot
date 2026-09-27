# evaluate.py
"""
Measure how predictive the bot is.

1. Backtest the deterministic quant score over the last year of CoinGecko data
   (no LLM calls, so it's free and reproducible).
2. Score every logged LLM recommendation in data/history.json against what BTC did next.

Usage: python evaluate.py [--horizon 7] [--threshold 20]
"""

import argparse
from statistics import correlation, mean
from typing import Dict, List, Optional

from indicators import build_price_metrics, build_volume_metrics, prepare_price_series, quant_score
from scoring import HORIZON_DAYS, evaluate_entries, forward_return_pct
from sentiment_scraper import get_fear_and_greed
from trend_scraper import get_btc_historical

WARMUP_DAYS = 90  # MA90 needs 90 days of history
BUCKETS = [(-101, -40), (-40, -20), (-20, 20), (20, 40), (40, 101)]


def _pct(values: List[bool]) -> Optional[float]:
    return round(100 * mean(values), 1) if values else None


def backtest_quant_score(btc_history: List[Dict], fng_by_date: Dict[str, int], horizon: int, threshold: int) -> None:
    series = prepare_price_series(btc_history)
    price_by_date = dict(series)
    samples = []

    for i in range(WARMUP_DAYS, len(series)):
        date = series[i][0]
        fwd = forward_return_pct(price_by_date, date, horizon=horizon)
        if fwd is None:
            continue
        pm = build_price_metrics(series[: i + 1])
        vm = build_volume_metrics(btc_history[: i + 1])
        q = quant_score(pm, vm, fng_by_date.get(date))
        samples.append({"date": date, "score": q["score"], "components": q["components"], "fwd": fwd})

    if len(samples) < 10:
        print("Not enough data to backtest.")
        return

    scores = [s["score"] for s in samples]
    fwds = [s["fwd"] for s in samples]
    up = [f > 0 for f in fwds]

    print(f"\n=== Quant score backtest: {samples[0]['date']} → {samples[-1]['date']}, {horizon}d horizon ===")
    print(f"Samples: {len(samples)} daily (≈{len(samples) // horizon} non-overlapping windows)")
    print(f"BTC up over {horizon}d: {_pct(up)}% of days (the base rate to beat)")
    print(f"Correlation(score, forward return): {correlation(scores, fwds):+.3f}")

    bull = [s["fwd"] > 0 for s in samples if s["score"] >= threshold]
    bear = [s["fwd"] <= 0 for s in samples if s["score"] <= -threshold]
    print(f"Score ≥ +{threshold} (bullish): {len(bull)} days, right {_pct(bull)}% of the time")
    print(f"Score ≤ -{threshold} (bearish): {len(bear)} days, right {_pct(bear)}% of the time")

    print("\nForward return by score bucket:")
    for lo, hi in BUCKETS:
        in_bucket = [s["fwd"] for s in samples if lo < s["score"] <= hi]
        if in_bucket:
            print(
                f"  ({max(lo, -100):>4}, {min(hi, 100):>4}]  n={len(in_bucket):>3}  "
                f"mean {mean(in_bucket):+6.2f}%  up {_pct([f > 0 for f in in_bucket])}%"
            )

    print("\nPer-component correlation with forward return:")
    names = sorted({k for s in samples for k in s["components"]})
    for name in names:
        pairs = [(s["components"][name], s["fwd"]) for s in samples if name in s["components"]]
        xs, ys = zip(*pairs)
        if len(set(xs)) > 1:
            print(f"  {name:<10} {correlation(xs, ys):+.3f}  (n={len(pairs)})")
        else:
            print(f"  {name:<10} constant, no signal")


def score_llm_history(btc_history: List[Dict], horizon: int) -> None:
    from analyze import _read_history

    series = prepare_price_series(btc_history)
    report = evaluate_entries(_read_history(), series, horizon=horizon)
    summary, rows = report["summary"], report["rows"]

    print(f"\n=== Logged LLM calls, {horizon}d horizon ===")
    if not rows:
        print("No calls old enough to score yet.")
        return
    for r in rows:
        prob = f"P(up) {r['prob_up_7d']:>4.0f}%" if r["prob_up_7d"] is not None else f"conf {r['confidence']!s:>4}   "
        hit = {True: "✓", False: "✗", None: "·"}[r["hit"]]
        print(f"  {r['date']}  {r['recommendation'].upper():<5}  {prob}  → {r['return_pct']:+6.2f}%  {hit}")
    print()
    for key, value in summary.items():
        print(f"  {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--horizon", type=int, default=HORIZON_DAYS)
    parser.add_argument("--threshold", type=int, default=20, help="|quant score| treated as a directional call")
    args = parser.parse_args()

    btc_history = get_btc_historical(days=365)  # CoinGecko free tier max
    fng = get_fear_and_greed(limit=400)
    fng_by_date = {row["date"]: row["value"] for row in fng.get("trend", [])}

    backtest_quant_score(btc_history, fng_by_date, args.horizon, args.threshold)
    score_llm_history(btc_history, args.horizon)


if __name__ == "__main__":
    main()
