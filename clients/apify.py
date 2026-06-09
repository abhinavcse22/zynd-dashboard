"""Apify client for LinkedIn post scraping.

Runs harvestapi/linkedin-post-search — a cookieless LinkedIn post scraper.
No li_at session cookie required.

Actor input schema:
  {
    "searchQueries": ["langchain agent", "crewai agent"],
    "maxPosts": 50,
    "postedLimit": "24h",   # "1h" | "24h" | "week" | "month"
    "sortBy": "date",       # "relevance" | "date"
    "profileScraperMode": "short"
  }

Output per post:
  {
    "type": "post",
    "id": "...",
    "linkedinUrl": "https://www.linkedin.com/posts/...",
    "content": "post text",
    "author": {
      "publicIdentifier": "username",
      "name": "Full Name",
      "linkedinUrl": "https://www.linkedin.com/in/...",
      "info": "Headline / Company"
    },
    "postedAt": { "timestamp": 1234567890000, "date": "2025-01-01" },
    "engagement": { "likes": 12, "comments": 3, "shares": 1 }
  }
"""

import time
import requests
from datetime import datetime, timedelta, timezone
from config import APIFY_API_TOKEN, APIFY_BASE_URL, APIFY_LINKEDIN_ACTOR

DEFAULT_ACTOR = "harvestapi/linkedin-post-search"


def _headers():
    return {"Authorization": f"Bearer {APIFY_API_TOKEN}"}


def scrape_posts(search_queries: list[str], max_results_per_query: int = 30) -> list[dict]:
    """Run the LinkedIn posts scraper for a list of search queries.

    Batches all queries into a single actor run to minimize API usage.
    Returns a flat list of raw post objects from Apify.
    """
    if not APIFY_API_TOKEN:
        print("  [Apify] APIFY_API_TOKEN not set - returning empty list")
        return []

    actor = APIFY_LINKEDIN_ACTOR or DEFAULT_ACTOR
    actor_input = {
        "searchQueries": search_queries,
        "maxPosts": max_results_per_query,
        "postedLimit": "24h",
        "sortBy": "date",
        "profileScraperMode": "short",
    }

    print(f"  [Apify] Starting actor {actor} with {len(search_queries)} queries...")

    run_url = f"{APIFY_BASE_URL}/acts/{actor}/runs"
    try:
        r = requests.post(
            run_url,
            headers=_headers(),
            json={"input": actor_input},
            params={"token": APIFY_API_TOKEN},
        )
        r.raise_for_status()
        run = r.json().get("data", {})
        run_id = run.get("id")
    except requests.RequestException as e:
        print(f"  [Apify] Failed to start actor run: {e}")
        return []

    if not run_id:
        print("  [Apify] No run ID returned - check actor name and API token")
        return []

    print(f"  [Apify] Run started: {run_id}. Waiting for completion...")
    posts = _wait_and_fetch(run_id)
    print(f"  [Apify] Scraped {len(posts)} raw posts")
    return posts


def _wait_and_fetch(run_id: str, timeout_seconds: int = 300) -> list[dict]:
    """Poll the run until it finishes, then return dataset items."""
    status_url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
    deadline = time.time() + timeout_seconds
    backoff = 10

    while time.time() < deadline:
        try:
            r = requests.get(status_url, headers=_headers())
            r.raise_for_status()
            run_data = r.json().get("data", {})
            status = run_data.get("status", "")
        except requests.RequestException as e:
            print(f"  [Apify] Status check error: {e}")
            time.sleep(backoff)
            continue

        if status in ("SUCCEEDED", "FINISHED"):
            dataset_id = run_data.get("defaultDatasetId")
            return _fetch_dataset(dataset_id)
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f"  [Apify] Run ended with status: {status}")
            return []

        print(f"  [Apify] Run status: {status}. Waiting {backoff}s...")
        time.sleep(backoff)
        backoff = min(backoff * 1.5, 60)

    print(f"  [Apify] Timed out waiting for run {run_id}")
    return []


def _fetch_dataset(dataset_id: str) -> list[dict]:
    """Fetch all items from an Apify dataset."""
    if not dataset_id:
        return []

    items = []
    offset = 0
    limit = 200

    while True:
        try:
            r = requests.get(
                f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
                headers=_headers(),
                params={"offset": offset, "limit": limit, "format": "json"},
            )
            r.raise_for_status()
            batch = r.json()
        except requests.RequestException as e:
            print(f"  [Apify] Dataset fetch error: {e}")
            break

        if not batch:
            break

        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return items


def filter_posts_by_date(posts: list[dict], lookback_days: int = 1) -> list[dict]:
    """Keep only posts published within the lookback window.

    Returns posts sorted newest-first.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    filtered = []

    for post in posts:
        posted_at = _extract_date(post)
        if posted_at and posted_at >= cutoff:
            post["_parsed_date"] = posted_at.isoformat()
            filtered.append(post)

    filtered.sort(key=lambda p: p.get("_parsed_date", ""), reverse=True)
    return filtered


def _extract_date(post: dict):
    """Extract timestamp from harvestapi output or legacy field names."""
    # harvestapi nests under postedAt.timestamp (milliseconds)
    posted_at = post.get("postedAt")
    if isinstance(posted_at, dict):
        ts = posted_at.get("timestamp")
        if ts:
            try:
                if ts > 1e10:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
        raw_date = posted_at.get("date")
        if raw_date:
            try:
                return datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                pass

    # Fallback: top-level fields from other actors
    for field in ("publishedAt", "timestamp", "date", "createdAt", "posted_at"):
        raw = post.get(field)
        if not raw:
            continue
        try:
            if isinstance(raw, (int, float)):
                if raw > 1e10:
                    raw = raw / 1000
                return datetime.fromtimestamp(raw, tz=timezone.utc)
            if isinstance(raw, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        except Exception:
            continue
    return None


def normalize_post(post: dict, signal_type: str = "") -> dict:
    """Normalize a harvestapi (or legacy) Apify post object to a consistent schema."""
    author = post.get("author") or {}
    engagement = post.get("engagement") or {}

    # harvestapi fields
    author_url = author.get("linkedinUrl") or post.get("authorLinkedInUrl") or post.get("authorUrl") or ""
    author_name = author.get("name") or post.get("authorName") or post.get("author") or ""
    author_headline = author.get("info") or post.get("authorHeadline") or post.get("headline") or ""
    text = post.get("content") or post.get("text") or post.get("commentary") or ""

    return {
        "post_url": post.get("linkedinUrl") or post.get("postUrl") or post.get("url") or "",
        "author_linkedin_url": author_url,
        "author_name": author_name,
        "author_headline": author_headline,
        "author_location": post.get("authorLocation") or post.get("location") or "",
        "company_name": post.get("companyName") or post.get("company") or "",
        "text": text[:2000],
        "posted_at": post.get("_parsed_date") or "",
        "likes": engagement.get("likes") or post.get("likesCount") or post.get("likes") or 0,
        "comments": engagement.get("comments") or post.get("commentsCount") or post.get("comments") or 0,
        "reposts": engagement.get("shares") or post.get("repostsCount") or post.get("reposts") or 0,
        "signal_type": signal_type,
    }
