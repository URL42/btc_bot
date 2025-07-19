# sentiment_scraper.py

import requests
from bs4 import BeautifulSoup
import time

def get_coindesk_articles():
    """
    Fetch CoinDesk RSS, then visit each article to get full text.
    Adds retry w/ backoff and User-Agent to avoid 429s.
    """
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # simulate real browser
    }

    # Retry up to 3 times if rate limited
    for attempt in range(3):
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            break
        elif response.status_code == 429:
            wait_time = 5 * (attempt + 1)
            print(f"⏳ Rate limited by CoinDesk (429), retrying in {wait_time}s...")
            time.sleep(wait_time)
        else:
            raise Exception(f"Failed to fetch CoinDesk RSS: {response.status_code}")
    else:
        raise Exception("Failed to fetch CoinDesk RSS after 3 attempts")

    soup = BeautifulSoup(response.text, "xml")
    articles = []

    for item in soup.find_all("item"):
        title = item.find("title").text
        link = item.find("link").text
        
        # get the article body
        article_text = fetch_article_body(link)
        
        articles.append({
            "title": title,
            "link": link,
            "content": article_text
        })
    return articles


def fetch_article_body(url):
    """
    Get the full text from a CoinDesk article page with fallback.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # improved spoofing
    }

    response = requests.get(url, headers=headers)
    if not response.ok:
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


def get_reddit_bitcoin_posts():
    """
    Scrape r/Bitcoin hot posts with titles and body text.
    """
    url = "https://www.reddit.com/r/Bitcoin/hot/.json?limit=10"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BTCBot/1.0; +https://github.com/yourname/btc_bot)"
    }

    response = requests.get(url, headers=headers)
    if not response.ok:
        raise Exception(f"Failed to fetch Reddit: {response.status_code}")
    
    data = response.json()
    posts = []
    for post in data.get("data", {}).get("children", []):
        post_data = post.get("data", {})
        title = post_data.get("title", "")
        body = post_data.get("selftext", "")
        posts.append({
            "title": title,
            "body": body
        })
    return posts


def get_sentiment_context():
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
        print("-", r)
