# analyze.py

import os
import json
from datetime import datetime, timedelta
from openai import OpenAI, BadRequestError, APIError
from dotenv import load_dotenv

# Load environment
load_dotenv()
client = OpenAI()

HISTORY_FILE = "history.json"
HISTORY_DAYS = 7

# You can override via env if you want:
PRIMARY_MODEL = os.environ.get("ANALYSIS_MODEL", "gpt-5")
FALLBACK_MODEL = os.environ.get("ANALYSIS_FALLBACK_MODEL", "gpt-4.1")


def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except FileNotFoundError:
        return []

    cutoff = datetime.now() - timedelta(days=HISTORY_DAYS)
    return [
        h for h in history
        if datetime.strptime(h["date"], "%Y-%m-%d") >= cutoff
    ]


def save_history(new_entry):
    history = load_history()
    history.append(new_entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def analyze_market(btc_history, sentiment_context):
    history_entries = load_history()
    history_summary = "\n".join(
        f"{h['date']}: {h['recommendation'].upper()} @ {h['confidence']}%"
        for h in history_entries
    ) or "No prior recommendations available."

    # Focus GPT on recent window but keep your 300-day context as requested
    price_summary = "\n".join(
        f"{day['date']}: ${day['price_usd']:.2f}"
        for day in btc_history[-300:]
    )

    coindesk_summaries = "\n".join(
        f"- {article['title']} | {article['content'][:500]}..."
        for article in sentiment_context.get("coindesk_articles", [])
    )

    reddit_summaries = "\n".join(
        f"- {post['title']} | {post['body'][:500]}..."
        for post in sentiment_context.get("reddit_posts", [])
    )

    prompt = f"""
You are an expert financial market analyst with deep expertise in Bitcoin price trends, macroeconomic drivers, and online sentiment signals.

You will be given:
- BTC price history for the past 300 days
- news headlines + partial article content from macro sources
- recent Reddit discussion threads

Your task is to:
1. Identify key price trends (e.g. support/resistance, volatility, patterns)
2. Extract macro factors that could influence Bitcoin in the short term (e.g. regulation, inflation, ETFs, institutional shifts)
3. Weigh in social sentiment from Reddit as potential confirmation or contradiction
4. Make a recommendation with short, clear reasoning

Please consider your prior 1-week recommendation history:
{history_summary}

If you've already recommended the same action in the past 1–2 days, only repeat it if new evidence strongly supports it. Otherwise, note the continuation or explain the change.

Your final output must be in this exact JSON format:

{{
  "recommendation": "buy | hold | avoid",
  "confidence": 0-100,
  "reasoning": [
    "1–4 short bullet points explaining your decision",
    "include a final summary bullet"
  ]
}}

--- BTC PRICE DATA ---
{price_summary}

--- MACRO NEWS ---
{coindesk_summaries}

--- REDDIT SENTIMENT ---
{reddit_summaries}
"""

    def call_model(model_name: str):
        # NOTE: no temperature here — gpt-5 rejected custom values
        return client.chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a Bitcoin financial analyst bot. Respond only in JSON."},
                {"role": "user", "content": prompt},
            ],
        )

    # Try primary (gpt-5), then fallback (gpt-4.1)
    try:
        response = call_model(PRIMARY_MODEL)
    except (BadRequestError, APIError) as e:
        print(f"⚠️ Primary model '{PRIMARY_MODEL}' failed: {e}. Falling back to '{FALLBACK_MODEL}'...")
        # For gpt-4.1, temperature is allowed — keep outputs steady but not required
        response = client.chat.completions.create(
            model=FALLBACK_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a Bitcoin financial analyst bot. Respond only in JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

    result = response.choices[0].message.content.strip()
    print("\n✅ GPT Analysis Result:\n")
    print(result)

    # Save to history
    try:
        parsed = json.loads(result)
        save_history({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "recommendation": parsed["recommendation"],
            "confidence": parsed["confidence"],
            "reasoning": parsed.get("reasoning", "")
        })
    except Exception as e:
        print("⚠️ Could not parse/save history:", e)

    return result


if __name__ == "__main__":
    from trend_scraper import get_btc_historical
    from sentiment_scraper import get_sentiment_context

    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()

    print("🧠 Analyzing market, please wait...")
    analyze_market(btc_history, sentiment)
