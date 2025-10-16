# sentiment_scraper.py

import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
BACKOFF_BASE = 2
MAX_ARTICLES = 5
MAX_REDDIT_POSTS = 10


def _request_with_retries(
    url: str,
    *,
    headers: Optional[Dict] = None,
    params: Optional[Dict] = None,
    expect_json: bool = False,
) -> requests.Response:
    """
    Generic GET helper with retries/backoff that returns a Response instance.
    """
    headers = headers or {}
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code in (429, 503):
                wait_seconds = BACKOFF_BASE ** attempt
                time.sleep(wait_seconds)
                continue

            if response.ok:
                if expect_json:
                    try:
                        # Touch response.json() so JSON decoding errors surface here.
                        response.json()
                    except ValueError as exc:
                        last_error = exc
                    else:
                        return response
                else:
                    return response

            last_error = requests.HTTPError(
                f"Failed request {url}: {response.status_code}"
            )

        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE ** attempt)

    raise RuntimeError(f"Unable to fetch {url} after {MAX_RETRIES} attempts") from last_error


def _trim_text(text: str, limit: int = 1200) -> str:
    """
    Keep scraped bodies to a manageable length while preserving sentence boundaries.
    """
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_period = truncated.rfind(".")
    if last_period > limit * 0.6:
        return truncated[: last_period + 1]
    return truncated + "..."


def get_coindesk_articles() -> List[Dict]:
    """
    Fetch CoinDesk RSS, then visit a limited set of articles to get body text.
    """
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BTCBot/1.1"
    }

    rss_response = _request_with_retries(url, headers=headers)
    soup = BeautifulSoup(rss_response.text, "xml")
    articles: List[Dict] = []

    for item in soup.find_all("item")[:MAX_ARTICLES]:
        title_tag = item.find("title")
        link_tag = item.find("link")
        pub_date_tag = item.find("pubDate")
        if not title_tag or not link_tag:
            continue

        link = link_tag.text.strip()
        article_text = fetch_article_body(link)

        articles.append({
            "title": title_tag.text.strip(),
            "link": link,
            "published": pub_date_tag.text.strip() if pub_date_tag else "",
            "content": _trim_text(article_text),
        })

    return articles


def fetch_article_body(url: str) -> str:
    """
    Get the full text from a CoinDesk article page with fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BTCBot/1.1"
    }

    try:
        response = _request_with_retries(url, headers=headers)
    except RuntimeError:
        return "Unable to fetch article content."

    page = BeautifulSoup(response.text, "html.parser")

    # first try article
    article_block = page.find("article")
    if article_block:
        paragraphs = [p.get_text(strip=True) for p in article_block.find_all("p")]
        if paragraphs:
            return " ".join(paragraphs)

    # fallback: div with common article class
    hero_block = page.find("div", class_="article-hero-content")
    if hero_block:
        paragraphs = [p.get_text(strip=True) for p in hero_block.find_all("p")]
        if paragraphs:
            return " ".join(paragraphs)

    # fallback: any large text block
    paragraphs = [p.get_text(strip=True) for p in page.find_all("p")]
    if paragraphs:
        return " ".join(paragraphs)

    return "No article content found."


def get_reddit_bitcoin_posts(limit: int = MAX_REDDIT_POSTS) -> List[Dict]:
    """
    Scrape r/Bitcoin hot posts with titles and body text.
    """
    url = "https://www.reddit.com/r/Bitcoin/hot/.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BTCBot/1.1; +https://github.com/yourname/btc_bot)"
    }
    params = {"limit": limit}

    try:
        response = _request_with_retries(url, headers=headers, params=params, expect_json=True)
    except RuntimeError as exc:
        return [{
            "title": "Failed to fetch Reddit posts",
            "body": str(exc),
        }]

    data = response.json()
    posts = []
    for post in data.get("data", {}).get("children", []):
        post_data = post.get("data", {})
        title = post_data.get("title", "").strip()
        body = post_data.get("selftext", "").strip()
        if not title:
            continue
        posts.append({
            "title": title,
            "body": _trim_text(body or "No post body provided.", limit=600),
            "upvotes": post_data.get("ups", 0),
            "comments": post_data.get("num_comments", 0),
            "created_utc": post_data.get("created_utc", 0),
        })
    return posts


def get_sentiment_context() -> Dict[str, List[Dict]]:
    """
    Combine CoinDesk articles with Reddit posts (titles + bodies).
    """
    coindesk = get_coindesk_articles()
    reddit = get_reddit_bitcoin_posts()
    return {
        "coindesk_articles": coindesk,
        "reddit_posts": reddit,
    }


if __name__ == "__main__":
    sentiment = get_sentiment_context()
    print("CoinDesk Articles with Full Content:")
    for a in sentiment["coindesk_articles"]:
        print("-", a['title'])
        print(a['content'][:300], "...")  # show first 300 chars
    print("\nReddit r/Bitcoin Posts:")
    for r in sentiment["reddit_posts"]:
        print("-", r["title"])
