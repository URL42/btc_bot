# notifier.py

import os
from telegram import Bot

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_notification(result_text: str):
    import json

    print("🔍 Raw LLM output:", result_text)

    try:
        parsed = json.loads(result_text)
    except Exception as e:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Failed to parse LLM result.")
        return

    from analyze import load_history
    history = load_history()

    recommendation = parsed.get("recommendation", "N/A").upper()
    confidence = parsed.get("confidence", "N/A")

    # Handle list or string reasoning
    raw_reasoning = parsed.get("reasoning", "")
    if isinstance(raw_reasoning, list):
        reasoning = "\n".join(f"• {r}" for r in raw_reasoning)
    else:
        reasoning = raw_reasoning.strip().replace("-", "•")

    history_lines = "\n".join(
        f"{h['date']}: {h['recommendation'].upper()} @ {h['confidence']}%"
        for h in history
    )

    msg = f"""📈 *BTC Market Recommendation*

*Recommendation:* {recommendation}
*Confidence:* {confidence}%
*Reasoning:*
{reasoning}

📅 *History:*
{history_lines}
"""

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )
