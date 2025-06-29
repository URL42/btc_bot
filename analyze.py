# analyze.py

import os
from openai import OpenAI
from dotenv import load_dotenv

# load your OPENAI_API_KEY from .env
load_dotenv()
client = OpenAI()

def analyze_market(btc_history, sentiment_context):
    """
    Combine BTC price data and sentiment data, then get GPT's recommendation.
    """
    # Compose price summary
    price_summary = "\n".join(
        f"{day['date']}: ${day['price_usd']:.2f}"
        for day in btc_history[-30:]  # focus GPT on the last 30 days
    )

    # Compose CoinDesk summaries
    coindesk_summaries = "\n".join(
        f"- {article['title']} | {article['content'][:500]}..."
        for article in sentiment_context.get("coindesk_articles", [])
    )

    # Compose Reddit summaries
    reddit_summaries = "\n".join(
        f"- {post['title']} | {post['body'][:500]}..."
        for post in sentiment_context.get("reddit_posts", [])
    )

    # Build the GPT prompt
    prompt = f"""
You are a financial market analysis expert and a crypto technical analyst.

You will be given:
- BTC price history for the last 30 days
- macro news article summaries
- Reddit discussions

Your job is to give a **recommendation**:
- "buy", "hold", or "avoid"
- a confidence score from 0 to 100
- a short explanation, ideally in bullet points

Return your answer in this JSON format:
{{
  "recommendation": "buy | hold | avoid",
  "confidence": 85,
  "reasoning": "..."
}}

Here is the BTC price data:
{price_summary}

Here is the macro news:
{coindesk_summaries}

Here is the Reddit sentiment:
{reddit_summaries}

What is your recommendation?
"""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a highly accurate financial advisor AI with a specialty in Bitcoin, BTC trend analysis and macro event understanding on BTC markets."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    text = response.choices[0].message.content
    return text


if __name__ == "__main__":
    from trend_scraper import get_btc_historical
    from sentiment_scraper import get_sentiment_context

    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()

    print("🧠 Analyzing market, please wait...")
    result = analyze_market(btc_history, sentiment)
    print("\n✅ GPT Analysis Result:\n")
    print(result)
