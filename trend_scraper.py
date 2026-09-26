# trend_scraper.py

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import requests

DEFAULT_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
BACKOFF_BASE = 2


def _request_with_retries(url: str, params: Dict) -> Dict:
    """
    Issue a GET request with basic retry/backoff handling for flaky upstreams.
    """
    headers = {"User-Agent": "trend-sentiment-bot/1.1"}
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code == 429:
                # Respect rate limits with exponential backoff
                wait_seconds = BACKOFF_BASE ** attempt
                time.sleep(wait_seconds)
                continue

            if response.ok:
                try:
                    return response.json()
                except ValueError as exc:
                    last_error = exc
            else:
                last_error = requests.HTTPError(
                    f"Failed to fetch BTC history: {response.status_code}"
                )

        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE ** attempt)

    raise RuntimeError(f"Unable to fetch BTC history after {MAX_RETRIES} attempts") from last_error


def _validate_price_point(point: List) -> bool:
    """
    Ensure the incoming price point has the expected [timestamp_ms, price] structure.
    """
    if not isinstance(point, list) or len(point) != 2:
        return False
    ts_ms, price = point
    return isinstance(ts_ms, (int, float)) and isinstance(price, (int, float))


def _validate_volume_point(point: List) -> bool:
    """
    Ensure the volume point has the expected [timestamp_ms, volume] structure.
    """
    if not isinstance(point, list) or len(point) != 2:
        return False
    ts_ms, vol = point
    return isinstance(ts_ms, (int, float)) and isinstance(vol, (int, float))


def get_btc_historical(days=350):
    """
    Fetch BTC daily closing prices and volumes over the past N days from CoinGecko.
    Returns a list of dicts with date, price_usd, and volume_usd.
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily",
    }
    data = _request_with_retries(url, params)
    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    if not isinstance(prices, list) or not prices:
        raise ValueError("CoinGecko response missing price data")

    # Build volume lookup by date string (last write wins, matching price dedup behaviour)
    volume_by_date: Dict[str, float] = {}
    for point in volumes:
        if not _validate_volume_point(point):
            continue
        ts_ms, vol = point
        date_str = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        volume_by_date[date_str] = vol

    # prices: [ [timestamp_ms, price], ... ]
    result = []
    for point in prices:
        if not _validate_price_point(point):
            continue
        ts_ms, price = point
        date_str = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        if result and result[-1]["date"] == date_str:
            # CoinGecko occasionally duplicates the most recent entry; keep the latest price.
            result[-1]["price_usd"] = price
            result[-1]["volume_usd"] = volume_by_date.get(date_str)
            continue
        result.append({
            "date": date_str,
            "price_usd": price,
            "volume_usd": volume_by_date.get(date_str),
        })

    # Guard against missing trailing days due to partial data.
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days + 1)).strftime("%Y-%m-%d")
    result = [entry for entry in result if entry["date"] >= cutoff_date]

    return result

if __name__ == "__main__":
    history = get_btc_historical()
    for day in history:
        print(f"{day['date']}: ${day['price_usd']:.2f}")
