# main.py

import argparse
import asyncio
from typing import List, Optional

from llm import PROVIDERS, resolve_config


def run_btc_analysis_pipeline(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    notify: bool = True,
    save: bool = True,
) -> dict:
    """
    Orchestrate the entire BTC trend + sentiment + analysis + notify pipeline.
    """
    from analyze import analyze_market
    from notifier import send_notification
    from sentiment_scraper import get_sentiment_context
    from trend_scraper import get_btc_historical

    llm_config = resolve_config(provider, model)
    btc_history = get_btc_historical(days=350)
    sentiment = get_sentiment_context()
    result = analyze_market(btc_history, sentiment, llm_config=llm_config, save=save)

    if notify:
        asyncio.run(send_notification(result))
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BTC trend + sentiment analysis bot")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), help="LLM provider (default: LLM_PROVIDER env or openai)")
    parser.add_argument("--model", help="Model name (default: <PROVIDER>_MODEL env or the provider default)")
    parser.add_argument("--no-notify", action="store_true", help="Skip the Telegram message")
    parser.add_argument("--no-save", action="store_true", help="Don't write the result to data/history.json")
    args = parser.parse_args(argv)

    print("🧩 Running BTC analysis pipeline...")
    try:
        result = run_btc_analysis_pipeline(
            provider=args.provider,
            model=args.model,
            notify=not args.no_notify,
            save=not args.no_save,
        )
    except Exception as exc:
        print(f"❌ Pipeline failed: {exc}")
        if not args.no_notify:
            from notifier import send_error

            asyncio.run(send_error(f"{type(exc).__name__}: {exc}"))
        raise

    print(
        f"✅ Done! {result['recommendation'].upper()} · P(up 7d) {result['prob_up_7d']:.0f}% · "
        f"quant {result['quant_score']:+d} · {result['provider']}/{result['model']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
