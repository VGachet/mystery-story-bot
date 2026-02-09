"""
Reddit scraper — fetches posts via Bright Data Web Unlocker.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List

import requests

from .config import Settings
from .db import story_exists

logger = logging.getLogger(__name__)

# Reddit JSON sort/time combinations — 2 feeds is the sweet spot
# (top/week catches trending stories, hot catches fresh ones)
_FEEDS = [
    ("top", "week"),
    ("hot", None),
]


def _build_reddit_url(subreddit: str, sort: str, time_filter: str | None, limit: int = 50) -> str:
    """Build a Reddit .json URL for the given subreddit and sort parameters."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    if time_filter:
        url += f"&t={time_filter}"
    # Add raw_json=1 to get unescaped characters
    url += "&raw_json=1"
    return url


def _fetch_via_brightdata(
    settings: Settings,
    target_url: str,
    max_retries: int = 3,
) -> dict | None:
    """
    Send a request through Bright Data Web Unlocker and return parsed JSON.
    Retries with exponential backoff on failure.
    """
    headers = {
        "Authorization": f"Bearer {settings.brightdata_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "zone": settings.brightdata_zone,
        "url": target_url,
        "format": "raw",
    }

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Bright Data request (attempt %d/%d): %s",
                attempt, max_retries, target_url,
            )
            resp = requests.post(
                settings.brightdata_endpoint,
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()

            # Bright Data sometimes returns an empty body (200 OK but no content)
            body = resp.text.strip()
            if not body:
                logger.warning(
                    "Bright Data returned empty body on attempt %d (status=%d)",
                    attempt, resp.status_code,
                )
            else:
                data = json.loads(body)
                return data

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "Bright Data HTTP %s on attempt %d: %s", status, attempt, exc
            )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Bright Data request error on attempt %d: %s", attempt, exc
            )
        except json.JSONDecodeError as exc:
            # Log a snippet of the response body for debugging
            snippet = resp.text[:200] if resp else "(no response)"
            logger.warning(
                "Failed to parse Bright Data response as JSON on attempt %d: %s — body: %s",
                attempt, exc, snippet,
            )

        if attempt < max_retries:
            wait = 2 ** attempt  # 2s, 4s, 8s
            logger.info("Retrying in %ds…", wait)
            time.sleep(wait)

    logger.error("All %d Bright Data attempts failed for %s", max_retries, target_url)
    return None


def _parse_posts(raw_json: dict) -> List[Dict]:
    """Extract relevant fields from Reddit listing JSON."""
    posts = []
    children = raw_json.get("data", {}).get("children", [])
    for child in children:
        d = child.get("data", {})
        if not d:
            continue
        created_utc = d.get("created_utc")
        reddit_created = None
        if created_utc:
            reddit_created = datetime.fromtimestamp(
                created_utc, tz=timezone.utc
            ).isoformat()

        posts.append(
            {
                "reddit_id": d.get("id", ""),
                "subreddit": d.get("subreddit", ""),
                "title": d.get("title", ""),
                "selftext": d.get("selftext", ""),
                "score": d.get("score", 0),
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "reddit_created": reddit_created,
            }
        )
    return posts


def scrape_subreddit(
    settings: Settings,
    subreddit: str,
) -> List[Dict]:
    """
    Scrape a subreddit and return new, filtered posts.

    Filtering:
    - Score between min_score and max_score
    - Non-empty selftext (we need textual content)
    - Not already in the database (deduplication)
    """
    all_new_posts: List[Dict] = []
    seen_ids: set = set()

    for sort, time_filter in _FEEDS:
        target_url = _build_reddit_url(subreddit, sort, time_filter)
        raw = _fetch_via_brightdata(settings, target_url)
        if raw is None:
            continue

        posts = _parse_posts(raw)
        logger.info(
            "r/%s (%s/%s): retrieved %d posts",
            subreddit, sort, time_filter or "-", len(posts),
        )

        for post in posts:
            rid = post["reddit_id"]
            # Skip duplicates within this run
            if rid in seen_ids:
                continue
            seen_ids.add(rid)

            # Score filter
            if not (settings.min_score <= post["score"] <= settings.max_score):
                continue

            # Must have textual content
            if not post["selftext"] or len(post["selftext"].strip()) < 100:
                continue

            # Database deduplication
            if story_exists(settings.db_path, rid):
                continue

            all_new_posts.append(post)

    logger.info(
        "r/%s: %d new posts after filtering & dedup", subreddit, len(all_new_posts)
    )
    return all_new_posts
