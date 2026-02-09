"""
Script generator — uses GPT-4o to produce narration scripts and visual keywords.
"""

import json
import logging
from typing import Dict, Tuple, List

from openai import OpenAI

from .config import Settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a narrator for a dark, atmospheric mystery short video channel.
Given a Reddit post about an unsolved mystery, strange phenomenon, or dark real event, generate:

1. A narration script in English, between 130 and 150 words.
   Structure: attention-grabbing hook → factual development → a "proof" or eerie detail → open-ended conclusion.
   Tone: calm, eerie, and factual — like a whispered documentary. No clickbait, no hype.
   Do NOT mention Reddit, upvotes, or the source. Write as if telling a standalone story.

2. Exactly 5 to 6 visual keywords in English (single words or 2-word phrases).
   These describe the mood, objects, places, and atmosphere for video clip search.
   Examples: "abandoned hospital", "fog", "night forest", "old photograph", "static noise", "empty hallway".

Respond ONLY with valid JSON in this exact format:
{
  "script": "Your narration script here...",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}"""

_USER_TEMPLATE = """Title: {title}

Content:
{selftext}"""


def generate_script(
    settings: Settings,
    title: str,
    selftext: str,
) -> Tuple[str, List[str]]:
    """
    Generate a narration script and visual keywords from a Reddit post.

    Returns:
        (script_text, keywords_list)

    Raises:
        ValueError: if GPT response cannot be parsed or is out of spec.
        openai.APIError: on API failures.
    """
    client = OpenAI(api_key=settings.openai_api_key)

    # Truncate very long posts to save tokens (keep first ~3000 chars)
    truncated = selftext[:3000] if len(selftext) > 3000 else selftext

    user_message = _USER_TEMPLATE.format(title=title, selftext=truncated)

    logger.info("Generating script for: %s", title[:80])

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=500,
    )

    raw_content = response.choices[0].message.content
    if not raw_content:
        raise ValueError("GPT-4o returned an empty response")

    data = json.loads(raw_content)

    script = data.get("script", "").strip()
    keywords = data.get("keywords", [])

    if not script:
        raise ValueError("GPT-4o returned an empty script")

    if not isinstance(keywords, list) or len(keywords) < 3:
        raise ValueError(
            f"GPT-4o returned invalid keywords: {keywords}"
        )

    # Word count check (soft — log warning but don't reject)
    word_count = len(script.split())
    if word_count < 100 or word_count > 200:
        logger.warning(
            "Script word count %d is outside target range (130-150) for: %s",
            word_count, title[:60],
        )

    logger.info(
        "Script generated: %d words, %d keywords", word_count, len(keywords)
    )
    return script, keywords
