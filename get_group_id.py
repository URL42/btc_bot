# file: get_group_id.py
from telegram.ext import ApplicationBuilder, MessageHandler, filters
import asyncio
import os

async def handle(update, context):
    print(update)

app = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
app.add_handler(MessageHandler(filters.ALL, handle))
app.run_polling()