import requests
import feedparser
import json
import re
import os
import random

# ── CONFIG ──────────────────────────────────────────────────
WIKIPEDIA_PAGES = [
    "Mother", "Motherhood", "Mother_goddess",
    "Queen_Mother_of_the_West", "Demeter", "Isis",
    "Memory", "Archive", "Oral_tradition"
]

RSS_FEEDS = [
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    # Add your own Substack/blog RSS links here
]

# Keywords to keep (leave empty [] to keep all sentences)
KEYWORDS = []

# Words to block (basic filter)
BLOCKED_WORDS = [
    "fuck", "shit", "porn", "kill yourself", "rape"
]

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/sentences.json")
MAX_SENTENCES = 800
# ────────────────────────────────────────────────────────────


def split_sentences(text):
    """Split text into clean individual sentences."""
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s) > 30]


def is_clean(sentence):
    """Return False if sentence contains blocked words."""
    lower = sentence.lower()
    return not any(bad in lower for bad in BLOCKED_WORDS)


def keyword_match(sentence):
    """Return True if no keyword filter, or if sentence contains a keyword."""
    if not KEYWORDS:
        return True
    lower = sentence.lower()
    return any(kw.lower() in lower for kw in KEYWORDS)


def scrape_wikipedia():
    """Fetch sentences from Wikipedia page summaries."""
    results = []
    for page in WIKIPEDIA_PAGES:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page}"
            r = requests.get(url, timeout=10)
            data = r.json()
            text = data.get("extract", "")
            sentences = split_sentences(text)
            for s in sentences:
                if is_clean(s) and keyword_match(s):
                    results.append({"text": s, "source": "wikipedia", "page": page})
            print(f"  Wikipedia [{page}]: {len(sentences)} sentences")
        except Exception as e:
            print(f"  Wikipedia [{page}] ERROR: {e}")
    return results


def scrape_rss():
    """Fetch sentences from RSS feeds."""
    results = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:  # max 20 articles per feed
                # Use summary or title
                text = entry.get("summary", "") or entry.get("title", "")
                # Strip HTML tags
                text = re.sub(r'<[^>]+>', '', text)
                sentences = split_sentences(text)
                for s in sentences:
                    if is_clean(s) and keyword_match(s):
                        results.append({"text": s, "source": "rss", "feed": url})
            print(f"  RSS [{url[:50]}]: collected sentences")
        except Exception as e:
            print(f"  RSS [{url}] ERROR: {e}")
    return results


def load_existing():
    """Load existing saved sentences."""
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_sentences(sentences):
    """Save sentences to JSON file."""
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(sentences)} sentences to {OUTPUT_FILE}")


def main():
    print("🔍 Starting scrape...\n")

    existing = load_existing()
    print(f"📦 Existing sentences: {len(existing)}")

    new_sentences = []
    new_sentences += scrape_wikipedia()
    new_sentences += scrape_rss()

    print(f"\n📥 New sentences collected: {len(new_sentences)}")

    # Merge: new + old, remove duplicates by text
    all_texts = {s["text"] for s in existing}
    for s in new_sentences:
        if s["text"] not in all_texts:
            existing.append(s)
            all_texts.add(s["text"])

    # Keep max MAX_SENTENCES, random selection
    if len(existing) > MAX_SENTENCES:
        existing = random.sample(existing, MAX_SENTENCES)

    save_sentences(existing)


if __name__ == "__main__":
    main()
