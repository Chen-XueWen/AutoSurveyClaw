"""Persistent cache for per-paper knowledge cards.

Keys: sha256(paper_id or title.lower())[:16] → {key}.json
TTL:  30 days (papers don't change content after publication)
Dir:  .surveyclaw_cache/paper_knowledge/

Follows the same pattern as surveyclaw/literature/cache.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path(".surveyclaw_cache") / "paper_knowledge"
_TTL_SEC = 86400 * 30  # 30 days


def _cache_dir(base: Path | None = None) -> Path:
    d = base or _DEFAULT_CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(paper_id: str, title: str) -> str:
    """Deterministic cache key: prefer paper_id, fall back to title."""
    raw = (paper_id.strip().lower() if paper_id.strip() else title.strip().lower())
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_card(
    paper_id: str,
    title: str,
    *,
    cache_base: Path | None = None,
) -> dict[str, Any] | None:
    """Return cached knowledge card or None if miss/expired."""
    d = _cache_dir(cache_base)
    key = _cache_key(paper_id, title)
    path = d / f"{key}.json"

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data.get("extracted_at", 0)
        if age > _TTL_SEC:
            logger.debug("Paper cache expired for %r (age=%.0fd)", title[:50], age / 86400)
            return None
        card = data.get("card")
        if not isinstance(card, dict):
            return None
        logger.info("[paper_reader] cache HIT: %s", title[:60])
        return data  # return full entry (card + metadata)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def put_card(
    paper_id: str,
    title: str,
    card: dict[str, Any],
    *,
    cite_key: str = "",
    fulltext_source: str = "",
    cache_base: Path | None = None,
) -> None:
    """Write a knowledge card to cache."""
    d = _cache_dir(cache_base)
    key = _cache_key(paper_id, title)
    path = d / f"{key}.json"

    payload = {
        "paper_id": paper_id,
        "title": title,
        "cite_key": cite_key,
        "fulltext_source": fulltext_source,
        "extracted_at": time.time(),
        "card": card,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("[paper_reader] cached card for: %s", title[:60])
