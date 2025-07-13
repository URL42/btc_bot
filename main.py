# main.py

from trend_scraper import get_btc_historical
from sentiment_scraper import get_sentiment_context
from analyze import analyze_market
from notifier import send_notification
import asyncio

def run_btc_analysis_pipeline():
    """
    Orchestrate the entire BTC trend + sentiment + analysis + notify pipeline.
    """
    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()
    result_text = analyze_market(btc_history, sentiment)

    # Send raw LLM JSON to notifier
    asyncio.run(send_notification(result_text))

if __name__ == "__main__":
    print("🧩 Running BTC analysis pipeline...")
    run_btc_analysis_pipeline()
    print("✅ Done!")
