import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import feedparser
import json
import re
import os
import psycopg2
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

# Get DATABASE_URL from argument, environment, or hardcoded fallback
if len(sys.argv) > 1 and sys.argv[1] and sys.argv[1] != '""':
    DATABASE_URL = sys.argv[1]
    print("Using DATABASE_URL from argument")
else:
    DATABASE_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:YqPFZxFQtNzOMREvzqLuNInEHSjhORbY@maglev.proxy.rlwy.net:44365/railway"
    print(f"Using DATABASE_URL from environment/fallback: {bool(DATABASE_URL)}")
    
# ── KEYWORDS ─────────────────────────────────────────────────
KEYWORDS = ["mama", "mother", "mommy"]

# ── DATABASE ─────────────────────────────────────────────────
def get_db():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set!")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentences (
            id SERIAL PRIMARY KEY,
            text TEXT NOT NULL UNIQUE,
            source VARCHAR(50),
            extra TEXT,
            image TEXT,
            added DATE DEFAULT CURRENT_DATE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scrape_stamps (
            source VARCHAR(50) PRIMARY KEY,
            last_scraped DATE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Database ready")

def save_to_db(new_items, blocklist):
    conn = get_db()
    cur = conn.cursor()
    added = 0
    blocked = 0
    duplicates = 0

    for item in new_items:
        if not is_clean(item["text"], blocklist):
            blocked += 1
            continue
        try:
            cur.execute(
                """INSERT INTO sentences (text, source, extra, image, added)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (text) DO NOTHING""",
                [
                    item["text"],
                    item["source"],
                    item.get("extra", ""),
                    item.get("image", None),
                    item.get("added", str(date.today()))
                ]
            )
            if cur.rowcount > 0:
                added += 1
            else:
                duplicates += 1
        except Exception as e:
            print(f"  DB insert error: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"  [+] added: {added}  [=] duplicates: {duplicates}  [x] blocked: {blocked}")
    return added

def get_count(source):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sentences WHERE source = %s", [source])
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count

def get_total():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM sentences GROUP BY source")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def already_scraped_today(source):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT last_scraped FROM scrape_stamps WHERE source = %s",
            [source]
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return str(row[0]) == str(date.today())
        return False
    except:
        return False

def mark_scraped_today(source):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO scrape_stamps (source, last_scraped)
           VALUES (%s, %s)
           ON CONFLICT (source) DO UPDATE SET last_scraped = %s""",
        [source, str(date.today()), str(date.today())]
    )
    conn.commit()
    cur.close()
    conn.close()

# ── BLOCKLIST ────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
BLOCKLIST_FILE = os.path.join(DATA_DIR, "blocklist.txt")

def load_blocklist():
    try:
        with open(BLOCKLIST_FILE, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except:
        return [
            "motherfucker", "motherfucking", "porn", "rape",
            "kill yourself", "bdsm", "kink", "ddlg", "daddy",
            "littlegirl", "abdl", "domina", "femdom", "milf",
            "nsfw", "mommy milkers", "mommydom", "inzest",
            "soumise", "tetine", "nude", "naked", "sex"
        ]

# ── HELPERS ──────────────────────────────────────────────────
def split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    # Skip if mostly hashtags
    words = text.split()
    if len(words) > 0:
        hashtag_count = sum(1 for w in words if w.startswith('#'))
        if hashtag_count / len(words) > 0.4:
            return []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s) > 20]

def is_clean(text, blocklist):
    lower = text.lower()
    return not any(bad in lower for bad in blocklist)

def has_keyword(text):
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)

def make_entry(text, source, extra="", image=None):
    return {
        "text": text,
        "source": source,
        "extra": extra,
        "image": image,
        "added": str(date.today())
    }

# ── WIKIPEDIA PAGES ──────────────────────────────────────────
WIKIPEDIA_PAGES = [
    "Mother", "Motherhood", "Mother_goddess",
    "Queen_Mother_of_the_West", "Demeter", "Isis",
    "Memory", "Oral_tradition", "Mourning",
    "Matriarchy", "Womb", "Childbirth",
    "Breastfeeding", "Lullaby", "Grief"
]

# ── RSS FEEDS ────────────────────────────────────────────────
RSS_FEEDS = [
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.lemonde.fr/rss/une.xml",
    "https://rsshub.app/apnews/topics/apf-topnews",
]

TUMBLR_TAGS = [
    "https://www.tumblr.com/tagged/mother/rss",
    "https://www.tumblr.com/tagged/mama/rss",
    "https://www.tumblr.com/tagged/mommy/rss",
]

MASTODON_INSTANCES = ["mastodon.social", "fosstodon.org"]
MASTODON_TAGS = ["mother", "mama", "mommy"]


# ── SCRAPERS ─────────────────────────────────────────────────
def scrape_wikipedia():
    print("\nWikipedia (daily)...")
    if already_scraped_today("wikipedia"):
        print(f"  Already scraped today. Current: {get_count('wikipedia')} sentences")
        return

    blocklist = load_blocklist()
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

    save_to_db(new_items, blocklist)
    mark_scraped_today("wikipedia")


def scrape_tumblr():
    print("\nTumblr (daily)...")
    if already_scraped_today("tumblr"):
        print(f"  Already scraped today. Current: {get_count('tumblr')} sentences")
        return

    blocklist = load_blocklist()
    new_items = []

    for tag_url in TUMBLR_TAGS:
        try:
            feed = feedparser.parse(tag_url)
            for entry in feed.entries[:20]:
                text = entry.get("summary", "") or entry.get("title", "")
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'http\S+', '', text).strip()
                for s in split_sentences(text):
                    if has_keyword(s):
                        new_items.append(make_entry(s, "tumblr", tag_url))
            print(f"  [{tag_url}]: done")
        except Exception as e:
            print(f"  [{tag_url}] error: {e}")

    save_to_db(new_items, blocklist)
    mark_scraped_today("tumblr")


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
    new_items = []

    token = get_bluesky_token()
    if not token:
        print("  Skipping -- no token")
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

    save_to_db(new_items, blocklist)


def scrape_mastodon():
    print("\nMastodon (hourly)...")
    blocklist = load_blocklist()
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

                    image_url = None
                    for att in post.get("media_attachments", []):
                        if att.get("type") == "image":
                            image_url = att.get("url")
                            break

                    for s in split_sentences(text):
                        if has_keyword(s):
                            new_items.append(
                                make_entry(s, "mastodon", tag, image_url)
                            )
                print(f"  [{instance}/#{tag}]: done")
            except Exception as e:
                print(f"  [{instance}/#{tag}] error: {e}")

    save_to_db(new_items, blocklist)


def scrape_reddit():
    print("\nReddit (hourly)...")
    blocklist = load_blocklist()
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

                image_url = None
                preview = pd.get("preview", {})
                images = preview.get("images", [])
                if images:
                    source = images[0].get("source", {})
                    image_url = source.get("url", "").replace("&amp;", "&")

                for text in [pd.get("title", ""), pd.get("selftext", "")]:
                    for s in split_sentences(text):
                        if has_keyword(s):
                            new_items.append(
                                make_entry(s, "reddit", term, image_url)
                            )
            print(f"  [{term}]: {len(posts)} posts checked")
        except Exception as e:
            print(f"  [{term}] error: {e}")

    save_to_db(new_items, blocklist)


def scrape_newspapers():
    print("\nNewspapers (hourly)...")
    blocklist = load_blocklist()
    new_items = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                text = entry.get("summary", "") or entry.get("title", "")
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'http\S+', '', text).strip()

                image_url = None
                media = entry.get("media_content", [])
                if media:
                    image_url = media[0].get("url")
                if not image_url:
                    for enc in entry.get("enclosures", []):
                        if "image" in enc.get("type", ""):
                            image_url = enc.get("href")
                            break

                for s in split_sentences(text):
                    if is_clean(s, blocklist) and has_keyword(s):
                        new_items.append(
                            make_entry(s, "newspapers", feed_url, image_url)
                        )
            print(f"  [{feed_url[:50]}]: done")
        except Exception as e:
            print(f"  [{feed_url[:50]}] error: {e}")

    save_to_db(new_items, blocklist)


# ── MAIN ─────────────────────────────────────────────────────
def main():
    print(f"DATABASE_URL exists: {bool(os.environ.get('DATABASE_URL'))}")

    init_db()

    scrape_wikipedia()
    scrape_tumblr()
    scrape_bluesky()
    scrape_mastodon()
    scrape_reddit()
    scrape_newspapers()

    print("\nCurrent totals:")
    rows = get_total()
    grand_total = 0
    for source, count in rows:
        print(f"  {source}: {count}")
        grand_total += count
    print(f"  TOTAL: {grand_total} / 7000 needed")
    if grand_total < 7000:
        print(f"  NEED {7000 - grand_total} more sentences")
    else:
        print(f"  Ready for gallery!")

if __name__ == "__main__":
    main()
