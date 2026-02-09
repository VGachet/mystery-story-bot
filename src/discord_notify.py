"""
Discord webhook notifications — sends production cards and TTS files.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config import Settings

logger = logging.getLogger(__name__)

# Dark purple/blue theme color
_EMBED_COLOR = 0x1A1A2E


def send_story_card(
    settings: Settings,
    story_id: int,
    title: str,
    url: str,
    script: str,
    keywords: List[str],
    score: int,
    subreddit: str,
) -> bool:
    """
    Send a rich embed "Production Card" to Discord.
    Returns True on success, False on failure.
    """
    # Truncate script if it exceeds Discord embed field limit (1024 chars)
    script_display = script if len(script) <= 1024 else script[:1020] + "…"
    keywords_display = ", ".join(keywords) if keywords else "—"

    embed = {
        "title": "🎬 Nouvelle histoire détectée",
        "color": _EMBED_COLOR,
        "fields": [
            {
                "name": "📰 Titre",
                "value": f"[{title[:200]}]({url})",
                "inline": False,
            },
            {
                "name": "📝 Script",
                "value": script_display,
                "inline": False,
            },
            {
                "name": "🔑 Keywords",
                "value": keywords_display,
                "inline": True,
            },
            {
                "name": "📊 Score Reddit",
                "value": str(score),
                "inline": True,
            },
            {
                "name": "🆔 ID BDD",
                "value": f"`{story_id}`",
                "inline": True,
            },
            {
                "name": "📂 Subreddit",
                "value": f"r/{subreddit}",
                "inline": True,
            },
        ],
        "footer": {
            "text": f"mystery-story-bot • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        },
    }

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(
            settings.discord_webhook_url,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Discord card sent for story #%d", story_id)
        return True
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to send Discord card for story #%d: %s", story_id, exc)
        return False


def send_tts_file(
    settings: Settings,
    story_id: int,
    title: str,
    mp3_path: str,
    voice: str = "onyx",
) -> bool:
    """
    Upload an MP3 file to Discord via the webhook.
    Returns True on success, False on failure.
    """
    path = Path(mp3_path)
    if not path.exists():
        logger.error("MP3 file not found: %s", mp3_path)
        return False

    message = f"🎙️ Audio généré pour l'histoire **#{story_id}** — {title[:150]}\n🗣️ Voix : **{voice}**"

    try:
        with open(path, "rb") as f:
            resp = requests.post(
                settings.discord_webhook_url,
                data={"content": message},
                files={"file": (path.name, f, "audio/mpeg")},
                timeout=60,
            )
        resp.raise_for_status()
        logger.info("Discord TTS file sent for story #%d", story_id)
        return True
    except requests.exceptions.RequestException as exc:
        logger.error(
            "Failed to send TTS file to Discord for story #%d: %s",
            story_id, exc,
        )
        return False
