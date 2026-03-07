import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import feedparser
import json
import re
import os
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

# ── KEYWORDS ─────────────────────────────────────────────────
KEYWORDS = ["mama", "mother", "mommy"]

# ── FILE PATHS ───────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")

FILES = {
    "wikipedia":  os.path.join(DATA_DIR, "wikipedia.json"),
    "reddit":     os.path.join(DATA_DIR, "reddit.json"),
    "bluesky":    os.path.join(DATA_DIR, "bluesky.json"),
    "tumblr":     os.path.join(DATA_DIR, "tumblr.json"),
    "mastodon":   os.path.join(DATA_DIR, "mastodon.json"),
    "newspapers": os.path.join(DATA_DIR, "newspapers.json"),
}

# Daily stamp files
STAMPS = {
    "wikipedia": os.path.join(DATA_DIR, "wiki_last_scraped.txt"),
    "tumblr":    os.path.join(DATA_DIR, "tumblr_last_scraped.txt"),
}

MAX = {
    "wikipedia":  8000,
    "reddit":     8000,
    "bluesky":    8000,
    "tumblr":     8000,
    "mastodon":   8000,
    "newspapers": 8000,
}

BLOCKLIST_FILE = os.path.join(DATA_DIR, "blocklist.txt")
TUMBLR_TAGS = ["mother", "mama", "mommy", "my-mother", "my-mom"]
MASTODON_INSTANCES = ["mastodon.social", "fosstodon.org"]
MASTODON_TAGS = ["mother", "mama", "mommy"]
RSS_FEEDS = [
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.lemonde.fr/rss/une.xml",
    "https://rsshub.app/apnews/topics/apf-topnews",
]
WIKIPEDIA_PAGES = [
    "Mother", "Motherhood", "Mother_goddess",
    "Queen_Mother_of_the_West", "Demeter", "Isis",
    "Memory", "Oral_tradition", "Mourning",
    "Matriarchy", "Womb", "Childbirth",
    "Breastfeeding", "Lullaby", "Grief"
]
NEWS_KEYWORDS = [
    "mother", "mama", "mom ", "child", "family",
    "daughter", "son", "parent", "birth", "baby",
    "infant", "woman", "maternity"
]

# ── HELPERS ──────────────────────────────────────────────────
def load_blocklist():
    """Load blocked words from blocklist.txt."""
    try:
        with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
            return [
                line.strip().lower()
                for line in f.readlines()
                if line.strip()
            ]
    except:
        return []


def split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove lines that are mostly hashtags
    words = text.split()
    hashtag_count = sum(1 for w in words if w.startswith('#'))
    if len(words) > 0 and hashtag_count / len(words) > 0.4:
        return []  # skip if more than 40% hashtags
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s) > 20]

def is_clean(text, blocklist):
    lower = text.lower()
    return not any(bad in lower for bad in blocklist)

def has_keyword(text):
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)

def make_entry(text, source, extra=""):
    return {
        "text": text,
        "source": source,
        "extra": extra,
        "added": str(date.today())
    }

def load_file(source):
    try:
        with open(FILES[source], "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_file(source, sentences):
    os.makedirs(DATA_DIR, exist_ok=True)
    if len(sentences) > MAX[source]:
        sentences = sentences[-MAX[source]:]
    with open(FILES[source], "w", encoding="utf-8") as f:
        json.dump(sentences, f, ensure_ascii=False, indent=2)
    print(f"  [saved] {source}: {len(sentences)} total sentences")

def merge_new(existing, new_items, blocklist):
    """Add new items, skip duplicates and blocked sentences."""
    existing_texts = {s["text"] for s in existing}
    added = 0
    blocked = 0
    skipped = 0
    for item in new_items:
        if item["text"] in existing_texts:
            skipped += 1
        elif not is_clean(item["text"], blocklist):
            blocked += 1
        else:
            existing.append(item)
            existing_texts.add(item["text"])
            added += 1
    print(f"  [+] added: {added}  [=] duplicates: {skipped}  [x] blocked: {blocked}")
    return existing, added

def already_scraped_today(source):
    try:
        with open(STAMPS[source], "r") as f:
            return f.read().strip() == str(date.today())
    except:
        return False

def mark_scraped_today(source):
    with open(STAMPS[source], "w") as f:
        f.write(str(date.today()))

# ── WIKIPEDIA (daily) ────────────────────────────────────────
def scrape_wikipedia():
    print("\nWikipedia (daily)...")
    if already_scraped_today("wikipedia"):
        count = len(load_file("wikipedia"))
        print(f"  Already scraped today. Current: {count} sentences")
        return

    blocklist = load_blocklist()
    existing = load_file("wikipedia")
    new_items = []

    for page in WIKIPEDIA_PAGES:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page}"
            r = requests.get(url, timeout=10, headers={
                "User-Agent": "MemoryPalaceBot/1.0 (gallery art project)"
            })
            r.raise_for_status()
            data = r.json()
            text = data.get("extract", "")
            for s in split_sentences(text):
                if has_keyword(s):
                    new_items.append(make_entry(s, "wikipedia", page))
            print(f"  [{page}]: done")
        except Exception as e:
            print(f"  [{page}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("wikipedia", merged)
    mark_scraped_today("wikipedia")


# ── TUMBLR (daily) ───────────────────────────────────────────
def scrape_tumblr():
    print("\nTumblr (daily)...")
    if already_scraped_today("tumblr"):
        count = len(load_file("tumblr"))
        print(f"  Already scraped today. Current: {count} sentences")
        return

    blocklist = load_blocklist()
    existing = load_file("tumblr")
    new_items = []

    for tag in TUMBLR_TAGS:
        try:
            url = f"https://{tag}.tumblr.com/rss"
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                text = entry.get("summary", "") or entry.get("title", "")
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'http\S+', '', text).strip()
                for s in split_sentences(text):
                    if has_keyword(s):
                        new_items.append(make_entry(s, "tumblr", tag))
            print(f"  [{tag}]: done")
        except Exception as e:
            print(f"  [{tag}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("tumblr", merged)
    mark_scraped_today("tumblr")


# ── BLUESKY (hourly) ─────────────────────────────────────────
def get_bluesky_token():
    username = os.environ.get("BSKY_USERNAME")
    password = os.environ.get("BSKY_APP_PASSWORD")
    if not username or not password:
        print("  No Bluesky credentials in .env")
        return None
    try:
        r = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": username, "password": password},
            timeout=10
        )
        r.raise_for_status()
        return r.json().get("accessJwt")
    except Exception as e:
        print(f"  Bluesky login error: {e}")
        return None

def scrape_bluesky():
    print("\nBluesky (hourly)...")
    blocklist = load_blocklist()
    existing = load_file("bluesky")
    new_items = []

    token = get_bluesky_token()
    if not token:
        print("  Skipping — no token")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    for keyword in KEYWORDS:
        try:
            url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
            params = {"q": keyword, "limit": 50}
            r = requests.get(url, params=params,
                           headers=headers, timeout=15)
            r.raise_for_status()
            posts = r.json().get("posts", [])
            for post in posts:
                text = post.get("record", {}).get("text", "")
                text = re.sub(r'http\S+', '', text).strip()
                text = re.sub(r'@\S+', '', text).strip()
                for s in split_sentences(text):
                    if has_keyword(s):
                        new_items.append(make_entry(s, "bluesky", keyword))
            print(f"  [{keyword}]: {len(posts)} posts checked")
        except Exception as e:
            print(f"  [{keyword}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("bluesky", merged)


# ── MASTODON (hourly) ────────────────────────────────────────
def scrape_mastodon():
    print("\nMastodon (hourly)...")
    blocklist = load_blocklist()
    existing = load_file("mastodon")
    new_items = []

    for instance in MASTODON_INSTANCES:
        for tag in MASTODON_TAGS:
            try:
                url = f"https://{instance}/api/v1/timelines/tag/{tag}"
                r = requests.get(url, params={"limit": 30}, timeout=10)
                posts = r.json()
                for post in posts:
                    text = re.sub(r'<[^>]+>', '', post.get("content", ""))
                    text = re.sub(r'http\S+', '', text).strip()
                    text = re.sub(r'@\S+', '', text).strip()

                    # Get image if post has one
                    image_url = None
                    attachments = post.get("media_attachments", [])
                    for att in attachments:
                        if att.get("type") == "image":
                            image_url = att.get("url")
                            break

                    for s in split_sentences(text):
                        if has_keyword(s):
                            entry = make_entry(s, "mastodon", tag)
                            if image_url:
                                entry["image"] = image_url
                            new_items.append(entry)
                print(f"  [{instance}/#{tag}]: done")
            except Exception as e:
                print(f"  [{instance}/#{tag}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("mastodon", merged)


# ── REDDIT (hourly) ──────────────────────────────────────────
def scrape_reddit():
    print("\nReddit (hourly)...")
    blocklist = load_blocklist()
    existing = load_file("reddit")
    new_items = []
    headers = {"User-Agent": "memory-palace-bot/1.0"}

    for term in KEYWORDS:
        try:
            url = "https://www.reddit.com/search.json"
            params = {"q": term, "sort": "new", "limit": 50}
            r = requests.get(url, params=params,
                           headers=headers, timeout=10)
            posts = r.json().get("data", {}).get("children", [])
            for post in posts:
                pd = post.get("data", {})

                # Get image if post has one
                image_url = None
                preview = pd.get("preview", {})
                images = preview.get("images", [])
                if images:
                    source = images[0].get("source", {})
                    image_url = source.get("url", "").replace("&amp;", "&")

                for text in [pd.get("title", ""), pd.get("selftext", "")]:
                    for s in split_sentences(text):
                        if has_keyword(s):
                            entry = make_entry(s, "reddit", term)
                            if image_url:
                                entry["image"] = image_url
                            new_items.append(entry)
            print(f"  [{term}]: {len(posts)} posts checked")
        except Exception as e:
            print(f"  [{term}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("reddit", merged)


# ── NEWSPAPERS (hourly) ──────────────────────────────────────
def scrape_newspapers():
    print("\nNewspapers (hourly)...")
    blocklist = load_blocklist()
    existing = load_file("newspapers")
    new_items = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                text = entry.get("summary", "") or entry.get("title", "")
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'http\S+', '', text).strip()

                # Try to get article image
                image_url = None
                media = entry.get("media_content", [])
                if media:
                    image_url = media[0].get("url")
                if not image_url:
                    enclosures = entry.get("enclosures", [])
                    for enc in enclosures:
                        if "image" in enc.get("type", ""):
                            image_url = enc.get("href")
                            break

                for s in split_sentences(text):
                    if is_clean(s, blocklist) and has_keyword(s):
                        entry_data = make_entry(s, "newspapers", feed_url)
                        if image_url:
                            entry_data["image"] = image_url
                        new_items.append(entry_data)
            print(f"  [{feed_url[:50]}]: done")
        except Exception as e:
            print(f"  [{feed_url[:50]}] error: {e}")

    merged, added = merge_new(existing, new_items, blocklist)
    save_file("newspapers", merged)

# ── MAIN ─────────────────────────────────────────────────────
def main():
    print(f"Scraping started -- {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    scrape_wikipedia()
    scrape_tumblr()
    scrape_bluesky()
    scrape_mastodon()
    scrape_reddit()
    scrape_newspapers()

    print("\nCurrent totals:")
    grand_total = 0
    for source, filepath in FILES.items():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                count = len(json.load(f))
                grand_total += count
                needed = max(0, 7000 - grand_total)
                print(f"  {source}: {count}")
        except:
            print(f"  {source}: 0")
    print(f"  TOTAL: {grand_total} / 7000 needed")
    if grand_total < 7000:
        print(f"  NEED {7000 - grand_total} more sentences for full gallery day")
    else:
        print(f"  Ready for gallery!")

if __name__ == "__main__":
    main()
