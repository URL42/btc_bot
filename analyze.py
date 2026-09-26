# analyze.py

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from indicators import (
    build_price_metrics,
    build_volume_metrics,
    prepare_price_series,
    quant_score,
)
from llm import LLMConfig, complete_json, resolve_config
from scoring import HORIZON_DAYS, evaluate_entries

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"

HISTORY_DAYS = 7
# Keep a year so evaluate.py has enough calls to measure accuracy.
MAX_HISTORY_DAYS_STORED = 365
SCHEMA_VERSION = 2

# P(up in 7d) thresholds that map the model's probability onto a label.
BUY_THRESHOLD = float(os.getenv("BUY_THRESHOLD", "60"))
AVOID_THRESHOLD = float(os.getenv("AVOID_THRESHOLD", "40"))

DATA_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "You are a disciplined, well-calibrated Bitcoin market analyst. "
    "You respond with a single JSON object and nothing else."
)


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_history() -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    cleaned = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        date_str = entry.get("date")
        if not isinstance(date_str, str):
            continue
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        cleaned.append(entry)
    return cleaned


def _within_days(entries: Sequence[Dict], days: int) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [entry for entry in entries if entry["date"] > cutoff]


def load_history(days: int = HISTORY_DAYS) -> List[Dict]:
    return _within_days(_read_history(), days)


def _write_history(entries: Sequence[Dict]) -> None:
    tmp_path = HISTORY_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(entries), f, indent=2, ensure_ascii=False)
    tmp_path.replace(HISTORY_FILE)


def save_history(new_entry: Dict) -> None:
    """Insert or replace the entry for new_entry['date'] (one call per UTC day)."""
    history = [e for e in _read_history() if e["date"] != new_entry["date"]]
    history.append(new_entry)
    history.sort(key=lambda e: e["date"])
    _write_history(_within_days(history, MAX_HISTORY_DAYS_STORED))


def recommendation_for(prob_up: float) -> str:
    if prob_up >= BUY_THRESHOLD:
        return "buy"
    if prob_up <= AVOID_THRESHOLD:
        return "avoid"
    return "hold"


def conviction_for(prob_up: float) -> int:
    """0 = coin flip, 100 = certain in either direction."""
    return int(round(abs(prob_up - 50) * 2))


def _summarize_articles(articles: Sequence[Dict]) -> List[Dict]:
    highlights = []
    for article in articles:
        title = article.get("title")
        content = article.get("content", "")
        if not title or not isinstance(title, str):
            continue
        highlights.append({
            "title": title.strip(),
            "summary": content.strip()[:400],
            "published": article.get("published", ""),
        })
    return highlights


def _summarize_reddit(posts: Sequence[Dict]) -> List[Dict]:
    sorted_posts = sorted(
        (post for post in posts if isinstance(post.get("title"), str)),
        key=lambda item: item.get("upvotes", 0),
        reverse=True,
    )
    return [
        {
            "title": post["title"].strip(),
            "body": post.get("body", "")[:400],
            "upvotes": post.get("upvotes", 0),
            "comments": post.get("comments", 0),
        }
        for post in sorted_posts[:5]
    ]


def _build_prompt(payload: Dict) -> str:
    return (
        f"Estimate the probability (0-100) that BTC/USD will be HIGHER {HORIZON_DAYS} days from now "
        "than latest_price, using only the structured data below.\n\n"
        "Work through these steps privately; do not output them:\n"
        "1. TREND & MOMENTUM: MA7/MA30/MA90 alignment, RSI-14 (Wilder; >70 overbought, <30 oversold), "
        "7d/30d/90d % change.\n"
        "2. VOLUME: does 24h volume vs its 30-day average confirm or contradict the recent move?\n"
        "3. SENTIMENT: Fear & Greed level and 7-day direction, CoinDesk headlines, Reddit tone. "
        "Extreme readings are often contrarian.\n"
        "4. QUANT SCORE: a deterministic rule-based score from -100 (bearish) to +100 (bullish) with its "
        "components. It is a rough summary with no proven edge in backtests; use it as a cross-check, "
        "not an answer.\n"
        "5. CONFLICTS: name the signals that contradict each other and how you weigh them.\n"
        "6. TRACK RECORD: your past calls have been scored against real outcomes (Brier: lower is better, "
        "0.25 = always saying 50). If you have been overconfident, move toward 50; if underconfident, "
        "commit more. Do not anchor on or repeat earlier calls; judge today's data on its merits.\n\n"
        "Calibration: BTC rises over a random 7-day window a little over half the time, and short-horizon "
        "moves are noisy. Probabilities outside 35-65 need strong, aligned evidence, but use them when it "
        "is there. A value near 50 is correct when evidence is genuinely mixed.\n\n"
        "Output ONLY this JSON object:\n"
        '{"prob_up_7d": <integer 0-100>, "reasoning": ["<bullet>", ...]}\n'
        "reasoning: 3-5 strings, each under 160 characters; the last one is the synthesis.\n\n"
        "Structured data:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _parse_probability(parsed: Dict) -> float:
    value = parsed.get("prob_up_7d")
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        prob = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Model response has no usable prob_up_7d: {parsed!r}")
    if 0 < prob <= 1:
        prob *= 100  # model answered as a fraction
    return max(0.0, min(100.0, prob))


def _parse_reasoning(parsed: Dict) -> List[str]:
    reasoning = parsed.get("reasoning", [])
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    elif not isinstance(reasoning, list):
        reasoning = []
    return [str(item).strip() for item in reasoning if str(item).strip()][:5]


def analyze_market(
    btc_history: Sequence[Dict],
    sentiment_context: Dict,
    llm_config: Optional[LLMConfig] = None,
    save: bool = True,
) -> Dict:
    llm_config = llm_config or resolve_config()

    price_series = prepare_price_series(btc_history)
    price_metrics = build_price_metrics(price_series)
    volume_metrics = build_volume_metrics(btc_history)
    fear_and_greed = sentiment_context.get("fear_and_greed", {})
    quant = quant_score(price_metrics, volume_metrics, fear_and_greed.get("current_value"))
    track_record = evaluate_entries(_read_history(), price_series)["summary"]

    payload = {
        "price_metrics": price_metrics,
        "volume_metrics": volume_metrics,
        "quant_score": quant,
        "fear_and_greed": fear_and_greed,
        "track_record": track_record,
        "macro_highlights": _summarize_articles(sentiment_context.get("coindesk_articles", [])),
        "reddit_highlights": _summarize_reddit(sentiment_context.get("reddit_posts", [])),
    }

    print(f"🧠 Querying {llm_config.label} ...")
    parsed, raw = complete_json(SYSTEM_PROMPT, _build_prompt(payload), llm_config)
    print("\n✅ Model output:\n")
    print(raw)

    prob_up = round(_parse_probability(parsed), 1)
    result = {
        "schema_version": SCHEMA_VERSION,
        "date": today_utc(),
        "recommendation": recommendation_for(prob_up),
        "prob_up_7d": prob_up,
        "confidence": conviction_for(prob_up),
        "quant_score": quant["score"],
        "reasoning": _parse_reasoning(parsed),
        "price_at_recommendation": price_metrics.get("latest_price"),
        "provider": llm_config.provider,
        "model": llm_config.model,
        "track_record": track_record,
    }

    if save:
        save_history({k: v for k, v in result.items() if k != "track_record"})
    return result


if __name__ == "__main__":
    # Dry run: analyse without sending Telegram.
    import sys

    from main import main

    sys.exit(main(["--no-notify", *sys.argv[1:]]))
