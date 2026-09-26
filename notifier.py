# notifier.py

import os
import re
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import BadRequest, TelegramError

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


def _md(text) -> str:
    """Escape Telegram legacy-Markdown control characters in dynamic text."""
    return re.sub(r"([_*`\[])", r"\\\1", str(text))


def _history_line(entry: Dict) -> str:
    rec = str(entry.get("recommendation", "N/A")).upper()
    if entry.get("prob_up_7d") is not None:
        detail = f"P(up) {entry['prob_up_7d']:.0f}%"
    else:
        detail = f"conf {entry.get('confidence', 'N/A')}"
    price = entry.get("price_at_recommendation")
    price_str = f" · ${price:,.0f}" if isinstance(price, (int, float)) else ""
    return f"{entry['date']}: {rec} · {detail}{price_str}"


def format_message(result: Dict) -> str:
    from analyze import AVOID_THRESHOLD, BUY_THRESHOLD, load_history

    reasoning = "\n".join(f"• {_md(item)}" for item in result.get("reasoning", [])) or "• No reasoning provided."
    history_lines = "\n".join(_md(_history_line(h)) for h in load_history()) or "No prior recommendations recorded."

    track = result.get("track_record") or {}
    if track.get("evaluated_calls"):
        parts = [f"{track['evaluated_calls']} calls scored"]
        if track.get("directional_hit_rate_pct") is not None:
            parts.append(f"buy/avoid hit rate {track['directional_hit_rate_pct']}%")
        if track.get("brier_score") is not None:
            parts.append(f"Brier {track['brier_score']} (coin flip 0.25)")
        track_line = f"\n🎯 *Track record ({track['horizon_days']}d):* {_md(', '.join(parts))}\n"
    else:
        track_line = ""

    price = result.get("price_at_recommendation")
    price_line = f"*Price:* ${price:,.0f}\n" if isinstance(price, (int, float)) else ""

    return (
        "📈 *BTC Market Recommendation*\n\n"
        f"*Recommendation:* {result['recommendation'].upper()}\n"
        f"*P(up in 7d):* {result['prob_up_7d']:.0f}% "
        f"(buy ≥{BUY_THRESHOLD:.0f}, avoid ≤{AVOID_THRESHOLD:.0f})\n"
        f"*Quant score:* {result['quant_score']:+d} (-100…+100)\n"
        f"{price_line}"
        f"*Reasoning:*\n{reasoning}\n\n"
        f"📅 *History:*\n{history_lines}\n"
        f"{track_line}\n"
        f"_Model: {_md(result['provider'] + '/' + result['model'])}_"
    )


async def _send(bot: Bot, chat_id: str, text: str, markdown: bool = True) -> None:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown" if markdown else None,
            disable_web_page_preview=True,
        )
    except BadRequest as exc:
        if not markdown:
            raise
        # Unbalanced entities in model text shouldn't cost us the alert.
        print(f"⚠️ Markdown rejected ({exc}); resending as plain text.")
        await _send(bot, chat_id, text.replace("\\", ""), markdown=False)


async def send_notification(result: Dict) -> None:
    bot, chat_id = _ensure_bot()
    if not bot or not chat_id:
        return
    try:
        await _send(bot, chat_id, format_message(result))
    except TelegramError as exc:
        print(f"⚠️ Failed to send Telegram message: {exc}")


async def send_error(message: str) -> None:
    bot, chat_id = _ensure_bot()
    if not bot or not chat_id:
        return
    try:
        await _send(bot, chat_id, f"❌ BTC analysis failed: {message}", markdown=False)
    except TelegramError as exc:
        print(f"⚠️ Failed to send Telegram error: {exc}")
