"""Extract and summarize article text from URLs. Free, no API keys.

Used by news_collector.py to enrich news articles with 3-4 sentence summaries.
Only processes top N articles per category to avoid being slow.

Usage:
    # As a module:
    from article_summarizer import summarize_url, enrich_articles

    # As CLI:
    python tools/article_summarizer.py --url "https://..."
    python tools/article_summarizer.py --enrich data/news/2026-03-24/geopolitical/events.json
"""

import argparse
import json
import re
import sys

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BOILERPLATE = [
    "cookie", "privacy", "subscribe", "sign up", "newsletter", "javascript",
    "advertisement", "sponsored", "skip to", "read more", "accept all",
    "terms of", "log in", "create account", "share this", "follow us",
]


def extract_text(url: str, timeout: int = 8) -> str:
    """Fetch a URL and extract clean text from the HTML."""
    try:
        resp = requests.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        html = resp.text

        # Try to find article body via common tags
        # Look for <article>, <main>, or common article class patterns
        article_match = re.search(
            r'<article[^>]*>(.*?)</article>',
            html, flags=re.DOTALL | re.IGNORECASE
        )
        if article_match:
            html = article_match.group(1)
        else:
            # Try <main>
            main_match = re.search(
                r'<main[^>]*>(.*?)</main>',
                html, flags=re.DOTALL | re.IGNORECASE
            )
            if main_match:
                html = main_match.group(1)

        # Strip scripts, styles, nav, header, footer
        for tag in ["script", "style", "nav", "header", "footer", "aside", "form"]:
            html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Strip all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Decode HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&#39;', "'").replace('&quot;', '"').replace('&nbsp;', ' ')

        return text
    except Exception:
        return ""


def summarize_text(text: str, max_sentences: int = 4) -> str:
    """Extract the most informative sentences from article text."""
    if not text or len(text) < 100:
        return ""

    # Find proper sentences (start with capital, 40-300 chars, end with punctuation)
    sentences = re.findall(r'([A-Z][^.!?]{40,300}[.!?])', text)

    # Filter out boilerplate
    clean = []
    for s in sentences:
        s = s.strip()
        if any(bp in s.lower() for bp in BOILERPLATE):
            continue
        if len(s) < 50:
            continue
        # Skip sentences that are mostly numbers/special chars
        alpha_ratio = sum(c.isalpha() for c in s) / len(s) if s else 0
        if alpha_ratio < 0.5:
            continue
        clean.append(s)

    if not clean:
        return ""

    # Take first N unique sentences (article lead is usually the summary)
    seen = set()
    result = []
    for s in clean:
        # Dedup by first 50 chars
        key = s[:50].lower()
        if key not in seen:
            seen.add(key)
            result.append(s)
        if len(result) >= max_sentences:
            break

    return " ".join(result)


def summarize_url(url: str, max_sentences: int = 4) -> str:
    """Full pipeline: fetch URL -> extract text -> summarize."""
    text = extract_text(url)
    return summarize_text(text, max_sentences)


def enrich_articles(articles: list, max_to_enrich: int = 8) -> list:
    """Add summaries to a list of article dicts. Only enriches top N English articles.

    Modifies articles in-place: adds 'summary' field.
    Returns the enriched list.
    """
    enriched = 0
    for article in articles:
        if enriched >= max_to_enrich:
            break

        # Skip if already has summary
        if article.get("summary"):
            continue

        # Only English articles
        lang = article.get("language", "")
        if lang and "english" not in lang.lower() and lang.lower() not in ("", "en"):
            continue

        url = article.get("url", article.get("link", ""))
        if not url:
            continue

        summary = summarize_url(url, max_sentences=3)
        if summary:
            article["summary"] = summary
            enriched += 1

    return articles


def enrich_json_file(filepath: str, max_to_enrich: int = 8):
    """Enrich articles in a JSON file and save back."""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    if not articles:
        print(f"No articles found in {filepath}")
        return

    before = sum(1 for a in articles if a.get("summary"))
    enrich_articles(articles, max_to_enrich)
    after = sum(1 for a in articles if a.get("summary"))

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    print(f"Enriched {after - before} articles (had {before}, now {after})")


def main():
    parser = argparse.ArgumentParser(description="Article summarizer")
    parser.add_argument("--url", help="Summarize a single URL")
    parser.add_argument("--enrich", help="Enrich articles in a JSON file with summaries")
    parser.add_argument("--max", type=int, default=8, help="Max articles to enrich")
    args = parser.parse_args()

    if args.url:
        summary = summarize_url(args.url)
        print(summary if summary else "Could not extract summary")
    elif args.enrich:
        enrich_json_file(args.enrich, args.max)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
