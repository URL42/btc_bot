# BTC Bot AI Pipeline

An automated Bitcoin monitoring agent that blends price data, news sentiment and a
rule-based score, asks an LLM for a calibrated probability, and sends a daily
BUY / HOLD / AVOID alert to Telegram.

> ⚠️ **Disclaimer:** Informational analysis only. Not financial advice.

---

## How it works

1. `trend_scraper.py` — ~350 days of BTC/USD price + 24h volume from CoinGecko.
2. `sentiment_scraper.py` — CoinDesk RSS + article bodies, Reddit r/Bitcoin, Fear & Greed
   index. A failing source is skipped with a warning rather than aborting the run.
3. `indicators.py` — deterministic features (MA7/30/90, Wilder RSI-14, 7/30/90d change,
   annualised volatility, volume vs 30d average) and the **quant score** (-100…+100).
4. `analyze.py` — builds the payload, adds the bot's own **track record** (past calls scored
   against real outcomes by `scoring.py`), and asks the LLM for `prob_up_7d`: the probability
   BTC is higher in 7 days. Code, not the model, maps that to a label:
   `≥ BUY_THRESHOLD (60)` → BUY, `≤ AVOID_THRESHOLD (40)` → AVOID, otherwise HOLD.
   One entry per UTC day is kept in `data/history.json` (re-runs replace it; 365 days retained).
5. `notifier.py` — Telegram message with label, probability, quant score, recent calls,
   track record and the model used. Falls back to plain text if Markdown is rejected.

`llm.py` handles the providers; `main.py` wires it all together.

---

## Choosing a model

| Provider  | Needs                     | Default model   | Notes |
|-----------|---------------------------|-----------------|-------|
| `openai`  | `OPENAI_API_KEY`          | `gpt-4.1`       | Chat Completions, JSON mode |
| `deepseek`| `DEEPSEEK_API_KEY`        | `deepseek-chat` | OpenAI-compatible API; `deepseek-reasoner` also works |
| `ollama`  | `OLLAMA_BASE_URL`         | `qwen3.5:9b`    | Native `/api/chat` with `num_ctx` raised to 16k |

Precedence: CLI flag → env → default.

```bash
uv run python main.py --provider ollama --model gpt-oss:20b --no-notify --no-save
uv run python main.py --provider deepseek
```

- Default provider: `LLM_PROVIDER`. Per-provider model: `OPENAI_MODEL`, `DEEPSEEK_MODEL`, `OLLAMA_MODEL`.
- `--no-notify` skips Telegram; `--no-save` leaves history untouched (use both to trial models).
- Ollama from Docker: use a LAN IP or `http://host.docker.internal:11434` (compose maps it).
- `OLLAMA_THINK=false` (default) disables "thinking" on qwen3.x / deepseek-r1 models, which
  otherwise made a run ~15x slower (≈16 s vs ≈4.5 min on qwen3.5:9b).
- Models that reject JSON mode or temperature are retried with defaults; `<think>` blocks and
  code fences are stripped before parsing.

See `.env.example` for every setting.

---

## Model & scoring

**Output contract.** The model returns `{"prob_up_7d": 0-100, "reasoning": [...]}`. A probability
over a fixed horizon is falsifiable; the old "HOLD @ 74% confidence" was not (confidence in *what*?).
`confidence` in history is now *conviction* = `|p − 50| × 2`.

**Evaluate.**

```bash
uv run python evaluate.py            # --horizon 7 --threshold 20
```

1. Backtests the quant score over the last year (no LLM cost): correlation with the forward
   return, hit rates, returns by score bucket, per-component correlation.
2. Scores every logged call: BUY/AVOID hit rate and the Brier score of `prob_up_7d`
   (0.25 = always saying 50%; lower is better).

**What the numbers said (2026-09-26).** Across 268 days the quant score had ~0 correlation
(+0.003) with 7-day returns, and no component was significant (with ~38 independent weeks,
|r| < ~0.16 is noise). That's normal for BTC at this horizon. The LLM sees the same inputs,
so don't expect edge by default. Measure it: after a few weeks, if the Brier score isn't
below 0.25, the model is adding noise. Don't tune weights to one year of backtest; that's overfitting.

**Why it used to always say HOLD.** The prompt showed the model its last 7 HOLD calls and
asked whether they were "vindicated" — HOLD can never be wrong, so it kept repeating. The prompt
now gets aggregate calibration stats instead of prior labels.

---

## Setup

```bash
uv sync                      # or: pip install -r requirements.txt
cp .env.example .env         # fill in TELEGRAM_*, provider keys, LLM_PROVIDER
```

## Running

```bash
uv run python main.py        # full pipeline
uv run python analyze.py     # same, without Telegram (alias for main.py --no-notify)
uv run python evaluate.py    # accuracy report
uv run pytest                # unit tests (offline)
```

Docker / cron (deps are baked into the image; the container runs as uid 1000):

```bash
docker compose build
docker compose run --rm btc-bot                                   # what cron runs
docker compose run --rm btc-bot python3 main.py --provider ollama --no-notify
```

`get_group_id.py` prints incoming updates to help find a Telegram chat ID.

---

## Troubleshooting

- **Reddit unavailable:** Reddit blocks unauthenticated `.json` scraping; the run continues
  without it. Use the official API with OAuth if you want it back.
- **Ollama timeouts:** raise `LLM_TIMEOUT` (default 900 s for Ollama) or use a smaller model.
- **Telegram failures:** check `TELEGRAM_CHAT_ID` (supergroups start with `-100`). Pipeline
  failures are also sent to Telegram as a plain-text error.
- **History:** `data/history.json` is ignored if corrupt. `data/history_2025-10_legacy.json`
  holds the old Oct-2025 calls.
