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
