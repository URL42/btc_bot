# BTC Bot AI Pipeline

An automated Bitcoin monitoring agent that blends structured market data, news sentiment, and community chatter to produce daily buy/hold/avoid guidance and Telegram alerts.

> ⚠️ **Disclaimer:** The bot offers informational analysis only. Do not treat its output as financial advice or an invitation to trade.

---

## Key Capabilities
- **Price Intelligence:** Pulls 300+ days of BTC/USD history from CoinGecko, derives momentum and volatility indicators, and tracks recent recommendations for continuity.
- **Sentiment Signals:** Scrapes CoinDesk RSS headlines + article bodies and Reddit r/Bitcoin hot posts with retry/backoff safeguards and trimmed summaries.
- **LLM Decisioning:** Packages curated metrics into a compact JSON payload for `gpt-4.1`, requesting structured recommendations with quantified confidence.
- **Persistent History:** Stores the last 30 days of decisions in `data/history.json` for prompt context and Telegram recaps.
- **Telegram Notifications:** Delivers formatted alerts (and graceful error messages) using `python-telegram-bot`.

---

## Repository Layout

```
AI_Agents/BTC_bot/
├── analyze.py            # Feature engineering + OpenAI orchestration
├── trend_scraper.py      # CoinGecko price fetch with retries/timeouts
├── sentiment_scraper.py  # CoinDesk + Reddit ingestion and summarisation
├── notifier.py           # Telegram messaging helper
├── main.py               # Pipeline entrypoint
├── data/                 # Stored recommendation history (git-ignored by default)
├── pyproject.toml        # Runtime dependencies (Python ≥ 3.10)
├── uv.lock               # Optional uv pin file
└── README.md             # You are here
```

---

## Prerequisites

- Python **3.10 – 3.12** (3.13 works if the ecosystem is ready).
- Poetry, uv, or pip/venv for dependency management.
- API access to:
  - [OpenAI Responses or Chat Completions API](https://platform.openai.com/docs/)
  - Telegram Bot token with permissions to message your target chat.

---

## Local Setup

1. **Clone & navigate**
   ```bash
   git clone <repo-url>
   cd AI_Agents/BTC_bot
   ```

2. **Create virtual environment (pick one)**
   ```bash
   # Using uv
   uv venv
   source .venv/bin/activate

   # OR using python -m venv
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   uv sync
   # or
   pip install -r <(uv pip compile pyproject.toml)  # if you don't use uv lock
   # or simply
   pip install -e .
   ```

4. **Configure environment**
   - Copy `.env_example` to `.env`.
   - Fill in:
     ```
     OPENAI_API_KEY=sk-...
     TELEGRAM_BOT_TOKEN=...
     TELEGRAM_CHAT_ID=...
     ```
   - Additional tweaks:
     - `COINGECKO_DAYS` (optional override via your own wrapper if desired)
     - Proxy settings if your network requires them.

5. **History directory**
   - The pipeline writes recommendation history to `data/history.json`.
   - Keep the folder on disk (create it manually if you plan to reset the repo):
     ```bash
     mkdir -p data
     ```
   - Add `data/` to `.gitignore` if you prefer not to commit historical outputs.

---

## Running the Pipeline

```bash
python main.py
```

The script will:
1. Download BTC price history (with retry/backoff).
2. Scrape CoinDesk + Reddit sentiment.
3. Derive market indicators and build a structured payload.
4. Query OpenAI (`gpt-4.1`) for JSON recommendations.
5. Persist the result to `data/history.json`.
6. Push a formatted Telegram alert.

Logs display the raw model output and surface scraper or messaging failures.

---

## Testing & Validation

- **Static syntax check**
  ```bash
  python -m py_compile *.py
  ```
- **Dry-run analysis**
  ```bash
  python analyze.py
  ```
  Outputs the JSON response and updates history without sending Telegram messages.

- **Notifier smoke test**
  ```bash
  python - <<'PY'
  from notifier import send_notification
  import asyncio
  asyncio.run(send_notification('{"recommendation": "hold", "confidence": 55, "reasoning": ["Test message"]}'))
  PY
  ```
  Confirms credentials and messaging formatting.

---

## Deployment Notes

- **Scheduling:** For periodic runs, wrap `main.py` in cron, systemd timers, GitHub Actions, or hosted task runners. Ensure the environment variables are available and the `data/` directory is writable.
- **Infrastructure:** Outbound HTTPS access is required to reach CoinGecko, CoinDesk, Reddit, OpenAI, and Telegram. Configure proxies/firewalls accordingly.
- **Secrets:** Use `.env`, key vaults, or platform-specific secret stores. Never commit raw tokens.

---

## Troubleshooting

- **Rate-limited scrapers:** The fetch clients include exponential backoff, but repeated 429s will surface as runtime errors. Increase jitter, add caching, or supply API credentials where possible.
- **Token limits:** If you trigger OpenAI’s context ceiling, consider reducing `MAX_ARTICLES` / `MAX_REDDIT_POSTS` in `sentiment_scraper.py` or adjusting summary lengths.
- **Telegram failures:** The notifier now logs credential issues and send failures explicitly. Verify `TELEGRAM_CHAT_ID` is a numeric string (prefix `-100` for supergroups).
- **History parsing issues:** Corrupted `data/history.json` will be ignored, but you may delete the file to reset the memory.

---

## Roadmap Ideas

- Add programmatic sentiment scoring (VADER/FinBERT) and quantitative factor models alongside the LLM output.
- Integrate official Reddit API with OAuth to reduce scraping brittleness.
- Run backtests to compare recommendation accuracy vs. benchmarks.
- Support additional notification channels (email, Slack, Discord).

---

## Contributing

1. Fork & branch (`git checkout -b feature/...`).
2. Install dependencies + tests.
3. Run `python -m py_compile *.py` before opening PRs.
4. Submit descriptive commits/PR descriptions and include test evidence where applicable.

Feel free to open issues for bugs, feature proposals, or documentation gaps.
