"""
SQLite database layer — story storage and deduplication.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _connect(db_path: str) -> sqlite3.Connection:
    """Return a connection with row-factory set to dict-like rows."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent reads
    return conn


def init_db(db_path: str) -> None:
    """Create the stories table if it doesn't exist."""
    conn = _connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            reddit_id       TEXT    UNIQUE NOT NULL,
            subreddit       TEXT    NOT NULL,
            title           TEXT    NOT NULL,
            url             TEXT    NOT NULL,
            score           INTEGER NOT NULL DEFAULT 0,
            selftext        TEXT    NOT NULL DEFAULT '',
            script          TEXT,
            keywords        TEXT,
            tts_file        TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            reddit_created  TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def story_exists(db_path: str, reddit_id: str) -> bool:
    """Check if a story with this reddit_id is already stored."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT 1 FROM stories WHERE reddit_id = ?", (reddit_id,)
    ).fetchone()
    conn.close()
    return row is not None


def insert_story(db_path: str, data: Dict) -> int:
    """
    Insert a new story and return its auto-incremented id.

    Expected keys in `data`:
        reddit_id, subreddit, title, url, score, selftext,
        script, keywords (list), reddit_created (ISO string or None)
    """
    conn = _connect(db_path)
    keywords_json = json.dumps(data.get("keywords", []), ensure_ascii=False)
    cur = conn.execute(
        """
        INSERT INTO stories
            (reddit_id, subreddit, title, url, score, selftext,
             script, keywords, reddit_created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["reddit_id"],
            data["subreddit"],
            data["title"],
            data["url"],
            data.get("score", 0),
            data.get("selftext", ""),
            data.get("script"),
            keywords_json,
            data.get("reddit_created"),
        ),
    )
    conn.commit()
    story_id = cur.lastrowid
    conn.close()
    return story_id


def get_story(db_path: str, story_id: int) -> Optional[Dict]:
    """Retrieve a story by its internal id, or None."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT * FROM stories WHERE id = ?", (story_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    # Parse keywords back to list
    if d.get("keywords"):
        try:
            d["keywords"] = json.loads(d["keywords"])
        except json.JSONDecodeError:
            d["keywords"] = []
    else:
        d["keywords"] = []
    return d


def update_tts_path(db_path: str, story_id: int, path: str) -> None:
    """Set the tts_file path for a story."""
    conn = _connect(db_path)
    conn.execute(
        "UPDATE stories SET tts_file = ? WHERE id = ?", (path, story_id)
    )
    conn.commit()
    conn.close()


def list_stories(
    db_path: str, limit: int = 20, offset: int = 0
) -> List[Dict]:
    """Return recent stories (newest first)."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT id, reddit_id, subreddit, title, score, tts_file, created_at "
        "FROM stories ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
