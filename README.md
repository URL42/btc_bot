# 🤖 BTC_bot — AI-Powered Bitcoin Market Signal Bot

BTC_bot is an autonomous AI agent that analyzes **technical trends**, **macro news**, and **social sentiment** to deliver daily Bitcoin trading recommendations via **Telegram**.

> 📈 "Buy, hold, or avoid? Let GPT-4 analyze the markets and notify you — daily."

---

## 🚀 Features

- 📊 **30-day BTC price trend analysis**
- 🌐 **Macro news + Reddit sentiment fusion**
- 🧠 **GPT-4-powered recommendation engine**
- 🕓 **Runs daily via Docker + cron**
- 📡 **Telegram notification delivery**
- 🧾 **7-day rolling recommendation memory**
- 💬 **Markdown-formatted alerts for readability**

---

## 🧠 How It Works

1. **Trend Analysis**: Pulls up to 350 days of BTC price history; focuses on last 30.
2. **News & Sentiment**:
   - Scrapes recent **CoinDesk** headlines and articles.
   - Extracts top posts from **r/Bitcoin**.
3. **GPT Evaluation**:
   - Weighs price trends, macro events, and Reddit tone.
   - Issues a JSON-formatted recommendation: `buy`, `hold`, or `avoid`.
4. **History Awareness**:
   - Keeps track of past 7 days of advice to avoid repetition.
5. **Telegram Delivery**:
   - Sends beautifully formatted recommendation via bot message.

---

## 🧰 Tech Stack

| Tool               | Purpose                                  |
|--------------------|------------------------------------------|
| Python 3.13        | Main runtime                             |
| OpenAI SDK         | GPT-4.1 market analysis                    |
| python-telegram-bot| Notification delivery                    |
| BeautifulSoup + lxml | HTML parsing from Coindesk, Reddit    |
| dotenv             | Secure API key management                |
| Docker + cron      | Scheduling & automation                  |

---

## 📦 Installation

Clone the repo:

```bash
git clone https://github.com/YOUR_USERNAME/btc_bot.git
cd btc_bot

Create your .env file:
```
OPENAI_API_KEY=your-openai-key
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-or-group-id
```

Install dependencies (if running locally):

```
uv pip install -r requirements.txt
```

👨‍💻 Author
Built with ❤️ by @URL42
Inspired by curiosity. Fueled by coffee ☕ and Bitcoin ₿

🪙 **Not Financial Advice**
This bot is a tool for informational and educational purposes only.
Do your own research before making financial decisions.

⭐ Like This Project?
Give it a ⭐ on GitHub to show support!

MIT No Attribution License (MIT-0) – With Non-Commercial Clause

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights 
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
of the Software, subject to the following condition:

🚫 The Software may NOT be used, in whole or in part, for any **commercial purposes**.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
