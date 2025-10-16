# notifier.py

import json
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

load_dotenv()

_bot: Optional[Bot] = None
_chat_id: Optional[str] = None


def _ensure_bot() -> Tuple[Optional[Bot], Optional[str]]:
    """
    Lazily instantiate the Telegram bot to surface credential issues gracefully.
    """
    global _bot, _chat_id

    if _bot and _chat_id:
        return _bot, _chat_id

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram credentials missing. Skipping notification.")
        return None, None

    try:
        _bot = Bot(token=token)
    except TelegramError as exc:
        print(f"⚠️ Failed to initialise Telegram bot: {exc}")
        return None, None

    _chat_id = chat_id
    return _bot, _chat_id


def _format_reasoning(reasoning_field) -> str:
    if isinstance(reasoning_field, list):
        return "\n".join(f"• {item}" for item in reasoning_field)
    if isinstance(reasoning_field, str):
        cleaned = reasoning_field.strip().replace(" - ", "\n• ")
        if cleaned.startswith("•"):
            return cleaned
        return f"• {cleaned}" if cleaned else "• No reasoning provided."
    return "• No reasoning provided."


async def send_notification(result_text: str) -> None:
    print("🔍 Raw LLM output:", result_text)

    bot, chat_id = _ensure_bot()
    if not bot or not chat_id:
        return

    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        await bot.send_message(chat_id=chat_id, text="❌ Failed to parse LLM result.")
        return

    from analyze import load_history

    history = load_history()
    history_lines = "\n".join(
        f"{h['date']}: {h.get('recommendation', 'N/A')} @ {h.get('confidence', 'N/A')}"
        for h in history
    ) or "No prior recommendations recorded."

    recommendation = str(parsed.get("recommendation", "N/A")).upper()
    confidence = parsed.get("confidence", "N/A")
    reasoning = _format_reasoning(parsed.get("reasoning", []))

    msg = f"""📈 *BTC Market Recommendation*

*Recommendation:* {recommendation}
*Confidence:* {confidence}%
*Reasoning:*
{reasoning}

📅 *History:*
{history_lines}
"""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        print(f"⚠️ Failed to send Telegram message: {exc}")
