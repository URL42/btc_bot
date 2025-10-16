# analyze.py

import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from openai import OpenAI

# Load environment (API key, etc.)
load_dotenv()
client = OpenAI()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"

HISTORY_DAYS = 7
MAX_HISTORY_DAYS_STORED = 30

DATA_DIR.mkdir(exist_ok=True)


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


def load_history(days: int = HISTORY_DAYS) -> List[Dict]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = []
    for entry in _read_history():
        try:
            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        if entry_date >= cutoff:
            result.append(entry)
    return result


def _write_history(entries: Sequence[Dict]) -> None:
    tmp_path = HISTORY_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(entries), f, indent=2, ensure_ascii=False)
    tmp_path.replace(HISTORY_FILE)


def save_history(new_entry: Dict) -> None:
    history = _read_history()
    history.append(new_entry)

    cutoff = datetime.utcnow() - timedelta(days=MAX_HISTORY_DAYS_STORED)
    pruned = []
    for entry in history:
        try:
            entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        if entry_date >= cutoff:
            pruned.append(entry)

    _write_history(pruned)


def _prepare_price_series(btc_history: Sequence[Dict]) -> List[Tuple[str, float]]:
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


def _percentage_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def _rolling_average(values: List[float], window: int) -> Optional[float]:
    if len(values) < window or window <= 0:
        return None
    return mean(values[-window:])


def _calculate_rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) <= period:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent_deltas = deltas[-period:]
    gains = [delta for delta in recent_deltas if delta > 0]
    losses = [-delta for delta in recent_deltas if delta < 0]

    if not gains and not losses:
        return 50.0

    average_gain = mean(gains) if gains else 0.0
    average_loss = mean(losses) if losses else 0.0

    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0

    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


def _calculate_volatility(values: List[float], window: int = 30) -> Optional[float]:
    if len(values) <= window:
        return None
    recent = values[-window:]
    returns = []
    for i in range(1, len(recent)):
        if recent[i - 1] == 0:
            continue
        returns.append((recent[i] - recent[i - 1]) / recent[i - 1])
    if len(returns) < 2:
        return None
    return pstdev(returns) * (252 ** 0.5)  # annualized volatility approximation


def _build_price_metrics(series: List[Tuple[str, float]]) -> Dict:
    if not series:
        return {}

    dates = [d for d, _ in series]
    closes = [p for _, p in series]
    latest_price = closes[-1]

    def change_over(days: int) -> Optional[float]:
        if len(closes) <= days:
            return None
        past_price = closes[-(days + 1)]
        return _percentage_change(latest_price, past_price)

    metrics = {
        "latest_date": dates[-1],
        "latest_price": round(latest_price, 2),
        "change_7d_pct": _round_optional(change_over(7)),
        "change_30d_pct": _round_optional(change_over(30)),
        "change_90d_pct": _round_optional(change_over(90)),
        "ma_7": _round_optional(_rolling_average(closes, 7)),
        "ma_30": _round_optional(_rolling_average(closes, 30)),
        "ma_90": _round_optional(_rolling_average(closes, 90)),
        "rsi_14": _round_optional(_calculate_rsi(closes, 14)),
        "volatility_30d": _round_optional(_calculate_volatility(closes, 30)),
        "recent_prices": [
            {"date": dates[i], "price": round(closes[i], 2)}
            for i in range(max(0, len(closes) - 14), len(closes))
        ],
    }

    return metrics


def _round_optional(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, ndigits)


def _summarize_articles(articles: Sequence[Dict]) -> List[Dict]:
    highlights = []
    for article in articles:
        title = article.get("title")
        content = article.get("content", "")
        if not title or not isinstance(title, str):
            continue
        summary = content.strip()[:400]
        highlights.append({
            "title": title.strip(),
            "summary": summary,
            "published": article.get("published", ""),
        })
    return highlights


def _summarize_reddit(posts: Sequence[Dict]) -> List[Dict]:
    sorted_posts = sorted(
        (
            post for post in posts
            if isinstance(post.get("title"), str)
        ),
        key=lambda item: item.get("upvotes", 0),
        reverse=True,
    )

    highlights = []
    for post in sorted_posts[:5]:
        highlights.append({
            "title": post["title"].strip(),
            "body": post.get("body", "")[:400],
            "upvotes": post.get("upvotes", 0),
            "comments": post.get("comments", 0),
        })
    return highlights


def _build_history_summary(entries: Sequence[Dict]) -> List[Dict]:
    summary = []
    for entry in entries:
        recommendation = entry.get("recommendation")
        confidence = entry.get("confidence")
        if not isinstance(recommendation, str):
            continue
        summary.append({
            "date": entry.get("date", ""),
            "recommendation": recommendation.upper(),
            "confidence": confidence,
        })
    return summary


def _invoke_model(prompt: str) -> str:
    """
    Prefer the Responses API for structured JSON, fall back to Chat if needed.
    """
    try:
        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {"role": "system", "content": "You are a Bitcoin financial analyst bot. Return compact JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            top_p=0.9,
            response_format={"type": "json_object"},
        )
        result_text = response.output_text.strip()
        if result_text:
            return result_text
    except Exception as primary_error:
        fallback_error = primary_error
    else:
        fallback_error = None

    # Fallback for clients without Responses support.
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a Bitcoin financial analyst bot. Respond only in JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as chat_error:
        if fallback_error:
            raise RuntimeError("Model call failed for both Responses and Chat APIs") from chat_error
        raise


def analyze_market(btc_history: Sequence[Dict], sentiment_context: Dict) -> str:
    price_series = _prepare_price_series(btc_history)
    price_metrics = _build_price_metrics(price_series)
    history_entries = load_history()
    history_summary = _build_history_summary(history_entries)

    macro_highlights = _summarize_articles(sentiment_context.get("coindesk_articles", []))
    reddit_highlights = _summarize_reddit(sentiment_context.get("reddit_posts", []))

    structured_payload = {
        "price_metrics": price_metrics,
        "recent_price_points": price_metrics.get("recent_prices", []),
        "recent_recommendations": history_summary,
        "macro_highlights": macro_highlights,
        "reddit_highlights": reddit_highlights,
    }

    prompt = (
        "Evaluate the following structured Bitcoin market data and produce a JSON decision.\n"
        "Your output must include:\n"
        '  - "recommendation": one of ["buy", "hold", "avoid"]\n'
        '  - "confidence": integer 0-100 expressing conviction\n'
        '  - "reasoning": array of 3-5 concise bullet strings culminating in a summary item\n'
        "Rules:\n"
        "- Tie your reasoning to quantitative signals (trend, momentum, volatility) and sentiment cues provided.\n"
        "- Reference continuation or change relative to recent recommendations when applicable.\n"
        "- Be explicit about conflicting data or uncertainties.\n"
        "- Keep reasoning items under 160 characters each.\n"
        "\n"
        "Structured data:\n"
        f"{json.dumps(structured_payload, ensure_ascii=False, indent=2)}"
    )

    result_text = _invoke_model(prompt)
    print("\n✅ GPT Analysis Result:\n")
    print(result_text)

    try:
        parsed = json.loads(result_text)
        confidence_value = parsed.get("confidence", "")
        if isinstance(confidence_value, str):
            try:
                confidence_value = float(confidence_value)
            except ValueError:
                confidence_value = confidence_value.strip()
        if isinstance(confidence_value, float):
            confidence_value = round(confidence_value, 1)

        reasoning = parsed.get("reasoning", [])
        if isinstance(reasoning, str):
            reasoning = [reasoning]
        elif isinstance(reasoning, list):
            reasoning = [str(item) for item in reasoning]
        else:
            reasoning = []

        save_history({
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "recommendation": parsed.get("recommendation", ""),
            "confidence": confidence_value,
            "reasoning": reasoning,
        })
    except Exception as exc:
        print("⚠️ Could not parse/save history:", exc)

    return result_text


if __name__ == "__main__":
    from trend_scraper import get_btc_historical
    from sentiment_scraper import get_sentiment_context

    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()

    print("🧠 Analyzing market, please wait...")
    analyze_market(btc_history, sentiment)
