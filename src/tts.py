"""
Text-to-Speech CLI — generates MP3 from a stored script using OpenAI TTS.
Usage: python -m src.tts --id 42
"""

import argparse
import logging
import random
import sys
from pathlib import Path

from openai import OpenAI

from .config import load_settings
from .db import init_db, get_story, update_tts_path
from .discord_notify import send_tts_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


VOICES = ["onyx", "echo", "fable", "nova", "shimmer", "alloy"]

# Best voices for mystery/creepy narration — used for random pick
MYSTERY_VOICES = ["onyx", "echo", "fable"]


def generate_tts_for_story(
    settings,
    story_id: int,
    title: str,
    script: str,
    voice: str | None = None,
) -> str | None:
    """
    Generate TTS for a story and send to Discord.
    Can be called directly from the pipeline (no DB lookup needed).
    Returns the MP3 path on success, None on failure.
    """
    if voice is None or voice == "random":
        voice = random.choice(MYSTERY_VOICES)
        logger.info("Randomly selected voice: %s", voice)

    logger.info("Generating TTS for story #%d (voice=%s): %s", story_id, voice, title[:60])

    client = OpenAI(api_key=settings.openai_api_key)
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = output_dir / f"story_{story_id}.mp3"

    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice=voice,
        input=script,
        response_format="mp3",
    ) as response:
        response.stream_to_file(str(mp3_path))
    logger.info("MP3 saved to %s", mp3_path)

    update_tts_path(settings.db_path, story_id, str(mp3_path))

    if settings.discord_webhook_url:
        send_tts_file(settings, story_id, title, str(mp3_path), voice=voice)

    return str(mp3_path)


def generate_tts(story_id: int, voice: str | None = None) -> None:
    """Generate an MP3 for the given story ID (CLI entrypoint)."""
    # Pick a random mystery voice if none specified
    if voice is None or voice == "random":
        voice = random.choice(MYSTERY_VOICES)
        logger.info("Randomly selected voice: %s", voice)
    settings = load_settings()

    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not set")
        sys.exit(1)

    init_db(settings.db_path)

    # Load story from database
    story = get_story(settings.db_path, story_id)
    if story is None:
        logger.error("Story #%d not found in database", story_id)
        sys.exit(1)

    script = story.get("script")
    if not script or not script.strip():
        logger.error("Story #%d has no script text", story_id)
        sys.exit(1)

    title = story.get("title", f"Story #{story_id}")

    mp3_path = generate_tts_for_story(settings, story_id, title, script, voice)
    if mp3_path:
        logger.info("✅ Done! MP3 for story #%d saved to %s", story_id, mp3_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate TTS audio for a stored mystery story script."
    )
    parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="Database ID of the story to convert to speech.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="random",
        choices=["random"] + VOICES,
        help=f"OpenAI TTS voice. 'random' picks from {', '.join(MYSTERY_VOICES)} (default: random)",
    )
    args = parser.parse_args()
    generate_tts(args.id, args.voice)


if __name__ == "__main__":
    main()
