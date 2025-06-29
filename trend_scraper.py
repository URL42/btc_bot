# trend_scraper.py

import requests
from datetime import datetime

def get_btc_historical(days=350):
    """
    Fetch BTC daily closing prices over the past N days from CoinGecko.
    Returns a list of dicts with date + price.
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily",
    }
    response = requests.get(url, params=params, headers={"User-Agent": "trend-sentiment-bot/1.0"})
    
    if not response.ok:
        raise Exception(f"Failed to fetch BTC history: {response.status_code}")
    
    data = response.json()
    prices = data.get("prices", [])
    
    # prices: [ [timestamp_ms, price], ... ]
    result = []
    for point in prices:
        ts_ms, price = point
        date_str = datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
        result.append({
            "date": date_str,
            "price_usd": price
        })
    
    return result

if __name__ == "__main__":
    history = get_btc_historical()
    for day in history:
        print(f"{day['date']}: ${day['price_usd']:.2f}")
