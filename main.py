# main.py

from trend_scraper import get_btc_historical
from sentiment_scraper import get_sentiment_context
from analyze import analyze_market
from notifier import send_notification
import asyncio
import json

def run_btc_analysis_pipeline():
    """
    Orchestrate the entire BTC trend + sentiment + analysis + notify pipeline.
    """
    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()
    result_text = analyze_market(btc_history, sentiment)

    # Try to parse JSON
    try:
        result = json.loads(result_text)
        formatted = (
            f"🚀 *BTC Recommendation:*\n\n"
            f"*Action:* {result['recommendation'].upper()}\n"
            f"*Confidence:* {result['confidence']}%\n\n"
            f"*Reasoning:*\n{result['reasoning']}"
        )
    except Exception as e:
        formatted = f"⚠️ Could not parse GPT result, raw:\n\n{result_text}"

    # async send
    asyncio.run(send_notification(formatted))
    
if __name__ == "__main__":
    print("🧩 Running BTC analysis pipeline...")
    run_btc_analysis_pipeline()
    print("✅ Done!")
