"""
Script generator — uses GPT-4o to produce narration scripts and visual keywords.
"""

import json
import logging
from typing import Tuple, List

from openai import OpenAI

from .config import Settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """You are a narrator for a dark, atmospheric mystery short video channel.
Given a Reddit post about an unsolved mystery, strange phenomenon, or dark real event, generate:

STEP 1 — CHOOSE A UNIQUE SETTING (do this silently, it will appear in the JSON output):
- Pick a country from Europe, Scandinavia, Eastern Europe, the Balkans, or the Baltic states.
  Examples of valid countries: Norway, Finland, Hungary, Romania, Poland, Czech Republic, Estonia,
  Iceland, Bulgaria, Lithuania, Latvia, Slovenia, Slovakia, Serbia, Croatia, Moldova, Albania,
  Montenegro, North Macedonia, Bosnia, Kosovo, Belarus, Ukraine, Greece, Portugal, Austria, Switzerland,
  Ireland, Scotland, Wales, and any other non-US, non-Canadian country you know well.
- FORBIDDEN: United States, Canada, Australia, New Zealand. Never set the story there.
- Pick a REAL small town or city (not the capital) in that country — population under 150,000.
- Invent a protagonist with a full name (first + last) that sounds 100% authentic for that country.
- Invent a secondary character (neighbor, colleague, local) with a different authentic name from the same country.
- Each call MUST produce a different country and different names — never repeat the same combination.

STEP 2 — WRITE THE STORY:
1. A narration script in English, approximately {word_count} words (range: {min_words}–{max_words}).
   Structure: attention-grabbing hook → key facts → eerie detail → cliffhanger or open-ended question.
   Tone: calm, eerie, and factual — like a whispered documentary. No clickbait, no hype.
   Language: Use simple, direct words. Avoid complex or fancy vocabulary that doesn't add to the mystery.
   Ending: ALWAYS conclude with either:
      - An open-ended question that makes the viewer wonder
      - A cliffhanger that leaves them wanting more
      - A mysterious statement that invites speculation
   Do NOT mention Reddit, upvotes, or the source. Write as if telling a standalone story.

   HOOK — CRITICAL RULE:
   - NEVER start with "In the small town of", "In a small village", "In the quiet town", or any
     variation that opens with a place description before the action.
   - The very first sentence must create immediate emotion — dread, unease, confusion, or curiosity.
   - Possible hook styles (vary each story):
       • Drop straight into the strange event, no setup
       • Open with a physical sensation: a sound, smell, or wrongness the protagonist can't explain
       • Start mid-action, protagonist already in the middle of it
       • Lead with a single haunting discovery, then pull back to explain how it got there
       • Open with a neighbor or stranger reporting something before the protagonist realizes it concerns them
       • Begin with the aftermath — something is already wrong when we arrive

   NARRATIVE PERSONALIZATION:
   - Use the protagonist and secondary character names you invented in STEP 1.
   - CRITICAL: Build a pattern of MULTIPLE recurring events, not a single isolated incident:
     * At least 2-3 similar strange occurrences to the same person or in the same place
     * Add temporal progression ("First it was X, then three days later Y, by Friday Z…")
     * Reference other locals or past incidents to give the story history
   - Replace ALL names from the original story with your invented names — no exceptions.
   - For TRUE CRIME or UNSOLVED MYSTERIES: keep factual details, but still use your invented names
     and location for the narrative frame.

2. Exactly 5 to 6 visual keywords in English (single words or 2-word phrases) for video clip search.
   Examples: "abandoned hospital", "fog", "night forest", "old photograph", "static noise", "empty hallway".

Respond ONLY with valid JSON in this exact format:
{{
  "country": "The country you chose",
  "city": "The town or city you chose",
  "protagonist": "Full name of the protagonist",
  "secondary": "Full name of the secondary character",
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
        max_words=max_words,
    )

    logger.info("Generating script for: %s (target: %d words)", title[:80], target_words)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.9,
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
        raise ValueError(f"GPT-4o returned invalid keywords: {keywords}")

    # Log the AI-chosen location context
    logger.info(
        "Location context (AI-chosen): %s, %s — protagonist: %s / secondary: %s",
        data.get("city", "?"),
        data.get("country", "?"),
        data.get("protagonist", "?"),
        data.get("secondary", "?"),
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

    logger.info("Script generated: %d words, %d keywords", word_count, len(keywords))
    return script, keywords
