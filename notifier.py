# notifier.py

import os
from dotenv import load_dotenv
from telegram import Bot
import asyncio
#import logging
#logging.basicConfig(level=logging.DEBUG)

# load .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file")

bot = Bot(token=TELEGRAM_TOKEN)

async def send_notification(message: str):
    """
    Send a message to Telegram asynchronously.
    """
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")

# no __main__ block here — let main.py orchestrate it