"""
Main orchestrator — scrape → generate → store → notify.
Run with: python -m src.main
"""

import logging
import random
import sys
from collections import defaultdict
from itertools import cycle
from typing import List, Dict

from .config import load_settings, Settings
from .db import init_db, insert_story
from .scraper import scrape_subreddit
from .generator import generate_script
from .discord_notify import send_story_card
from .tts import generate_tts_for_story

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _validate_settings(settings: Settings) -> None:
    """Abort early if critical keys are missing."""
    missing = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.brightdata_api_key:
        missing.append("BRIGHTDATA_API_KEY")
    if not settings.brightdata_zone:
        missing.append("BRIGHTDATA_ZONE")
    if not settings.discord_webhook_url:
        missing.append("DISCORD_WEBHOOK_URL")
    if missing:
        logger.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)


def run() -> None:
    """Execute the full pipeline."""
    settings = load_settings()
    _validate_settings(settings)

    logger.info("=== mystery-story-bot starting ===")
    # Pick a random subset of subreddits for this run (rotation)
    all_subs = list(settings.subreddits)
    random.shuffle(all_subs)
    active_subs = all_subs[: settings.subs_per_run]

    logger.info(
        "Config: subs_this_run=%s (%d/%d), score=%d–%d, max_per_run=%d",
        active_subs,
        len(active_subs),
        len(settings.subreddits),
        settings.min_score,
        settings.max_score,
        settings.max_stories_per_run,
    )

    # 1. Init database
    init_db(settings.db_path)

    # 2. Scrape selected subreddits
    posts_by_sub: defaultdict[str, List[Dict]] = defaultdict(list)
    total_candidates = 0
    for sub in active_subs:
        try:
            posts = scrape_subreddit(settings, sub)
            random.shuffle(posts)  # randomize within each sub
            posts_by_sub[sub] = posts
            total_candidates += len(posts)
            logger.info("r/%s: %d candidates ready", sub, len(posts))
        except Exception as exc:
            logger.error("Error scraping r/%s: %s", sub, exc, exc_info=True)

    logger.info("Total new candidates across all subreddits: %d", total_candidates)

    if total_candidates == 0:
        logger.info("No new stories found. Exiting.")
        return

    # 3. Round-robin selection across subreddits for diversity
    #    Picks one story from each sub in turn until we hit the cap.
    candidates: List[Dict] = []
    iterators = {sub: iter(posts) for sub, posts in posts_by_sub.items() if posts}
    sub_cycle = cycle(list(iterators.keys()))
    exhausted: set = set()

    while len(candidates) < settings.max_stories_per_run and len(exhausted) < len(iterators):
        sub = next(sub_cycle)
        if sub in exhausted:
            continue
        try:
            post = next(iterators[sub])
            candidates.append(post)
        except StopIteration:
            exhausted.add(sub)

    logger.info(
        "Processing %d stories (capped at %d, round-robin across %d subs)",
        len(candidates), settings.max_stories_per_run, len(iterators),
    )

    # 4. Generate scripts, store, notify
    processed = 0
    errors = 0

    for post in candidates:
        try:
            # Generate script via GPT-4o
            script, keywords = generate_script(
                settings, post["title"], post["selftext"]
            )

            # Store in database
            story_data = {
                **post,
                "script": script,
                "keywords": keywords,
            }
            story_id = insert_story(settings.db_path, story_data)
            logger.info("Story #%d saved: %s", story_id, post["title"][:60])

            # Notify on Discord
            send_story_card(
                settings=settings,
                story_id=story_id,
                title=post["title"],
                url=post["url"],
                script=script,
                keywords=keywords,
                score=post["score"],
                subreddit=post["subreddit"],
            )

            # Generate TTS audio (random voice among onyx/echo/fable)
            try:
                generate_tts_for_story(
                    settings=settings,
                    story_id=story_id,
                    title=post["title"],
                    script=script,
                )
            except Exception as tts_exc:
                logger.error(
                    "TTS failed for story #%d: %s", story_id, tts_exc,
                )

            processed += 1

        except Exception as exc:
            logger.error(
                "Error processing post '%s': %s",
                post["title"][:60], exc, exc_info=True,
            )
            errors += 1

    logger.info(
        "=== Done: %d processed, %d errors, %d total candidates ===",
        processed, errors, total_candidates,
    )


if __name__ == "__main__":
    run()
