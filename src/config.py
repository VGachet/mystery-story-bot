"""
Configuration — loads environment variables with sensible defaults.
"""

import os
import pathlib
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    # --- API keys --------------------------------------------------------
    openai_api_key: str = ""
    brightdata_api_key: str = ""
    brightdata_zone: str = ""
    discord_webhook_url: str = ""

    # --- Paths -----------------------------------------------------------
    db_path: str = "data/stories.db"
    output_dir: str = "output"

    # --- Scraping --------------------------------------------------------
    subreddits: List[str] = field(default_factory=list)
    subs_per_run: int = 4
    min_score: int = 30
    max_score: int = 200
    max_stories_per_run: int = 5

    # --- Bright Data endpoint --------------------------------------------
    brightdata_endpoint: str = "https://api.brightdata.com/request"


def load_settings() -> Settings:
    """Build a Settings instance from environment variables."""
    subreddits_raw = os.getenv(
        "SUBREDDITS",
        "UnresolvedMysteries,HighStrangeness,TheGrittyPast,OddlyTerrifying,"
        "LetsNotMeet,TrueCrimeDiscussion,Paranormal,Glitch_in_the_Matrix,"
        "CreepyWikipedia,Thetruthishere,RBI,Humanoidencounters",
    )
    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        brightdata_api_key=os.getenv("BRIGHTDATA_API_KEY", ""),
        brightdata_zone=os.getenv("BRIGHTDATA_ZONE", ""),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
        db_path=os.getenv("DB_PATH", "data/stories.db"),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        subreddits=subreddits,
        subs_per_run=int(os.getenv("SUBS_PER_RUN", "4")),
        min_score=int(os.getenv("MIN_SCORE", "30")),
        max_score=int(os.getenv("MAX_SCORE", "200")),
        max_stories_per_run=int(os.getenv("MAX_STORIES_PER_RUN", "5")),
    )
