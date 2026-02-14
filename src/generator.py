"""
Script generator — uses GPT-4o to produce narration scripts and visual keywords.
"""

import json
import logging
from typing import Dict, Tuple, List

from openai import OpenAI

from .config import Settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """You are a narrator for a dark, atmospheric mystery short video channel.
Given a Reddit post about an unsolved mystery, strange phenomenon, or dark real event, generate:

1. A narration script in English, approximately {word_count} words (range: {min_words}–{max_words}).
   Structure: attention-grabbing hook → key facts → eerie detail → cliffhanger or open-ended question.
   Tone: calm, eerie, and factual — like a whispered documentary. No clickbait, no hype.
   Language: Use simple, direct words. Avoid complex or fancy vocabulary that doesn't add to the mystery.
   Ending: ALWAYS conclude with either:
      - An open-ended question that makes the viewer wonder
      - A cliffhanger that leaves them wanting more
      - A mysterious statement that invites speculation
   Do NOT mention Reddit, upvotes, or the source. Write as if telling a standalone story.
   
   NARRATIVE PERSPECTIVE & PERSONALIZATION:
   - If the story is NOT in first person OR feels abstract/impersonal, transform it with these elements:
   - Create a protagonist with a full American name (first and last name, e.g., "Michael Torres", "Sarah Bennett").
   - ALWAYS set the story in a real small American town (population under 50,000). Name the town explicitly.
   - CRITICAL: Build a pattern of MULTIPLE recurring events, not just one isolated incident:
     * Mention at least 2-3 similar strange occurrences in the same location/to the same person
     * Add temporal progression (e.g., "First it was the pot, then three days later the photos, by Friday the doors...")
     * Reference other locals or past incidents in the town to establish a history
     * Examples: "Sarah wasn't the first in Ashland to experience this", "The third time it happened, neighbors started talking"
   - This creates grounded, believable stories where viewers think "this feels real and documented" rather than isolated fantasy.
   - For TRUE CRIME or UNSOLVED MYSTERIES about real victims: Keep the factual approach, but ensure specific locations and timeline details are included for authenticity.
   - Character names: If the original story contains names, change them to similar names from the same cultural background while keeping the narrative authentic.

2. Exactly 5 to 6 visual keywords in English (single words or 2-word phrases).
   These describe the mood, objects, places, and atmosphere for video clip search.
   Examples: "abandoned hospital", "fog", "night forest", "old photograph", "static noise", "empty hallway".

Respond ONLY with valid JSON in this exact format:
{{
  "script": "Your narration script here...",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""

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

    # Calculate word count range (±15%)
    target_words = settings.story_word_count
    min_words = int(target_words * 0.85)
    max_words = int(target_words * 1.15)
    
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        word_count=target_words,
        min_words=min_words,
        max_words=max_words
    )

    logger.info("Generating script for: %s (target: %d words)", title[:80], target_words)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=600,
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
    target = settings.story_word_count
    min_acceptable = int(target * 0.75)
    max_acceptable = int(target * 1.25)
    if word_count < min_acceptable or word_count > max_acceptable:
        logger.warning(
            "Script word count %d is outside acceptable range (%d-%d, target: %d) for: %s",
            word_count, min_acceptable, max_acceptable, target, title[:60],
        )

    logger.info(
        "Script generated: %d words, %d keywords", word_count, len(keywords)
    )
    return script, keywords
