"""PaperReadingOrchestrator — parallel full-text reading for all shortlisted papers.

For each paper in the shortlist:
  1. Check PaperKnowledgeCache — skip if hit
  2. Fetch full text + extract knowledge card via PaperReaderAgent
  3. Write card to cache and to stage_dir/cards/*.md

Uses ThreadPoolExecutor(max_workers=3) for parallelism.
Ollama is local, so no external rate-limit concern — 3 workers keeps GPU busy.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from surveyclaw.agents.base import AgentOrchestrator
from surveyclaw.agents.paper_reader.agent import PaperReaderAgent
from surveyclaw.agents.paper_reader.cache import get_card, put_card

logger = logging.getLogger(__name__)

_MAX_WORKERS = 3


def _safe_filename(s: str) -> str:
    """Sanitise string for use as a filename."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)[:60]


class PaperReadingOrchestrator(AgentOrchestrator):
    """Reads all shortlisted papers in parallel and returns deep knowledge cards."""

    def orchestrate(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run parallel paper reading.

        Parameters
        ----------
        context:
            ``papers``: list of paper dicts from shortlist.jsonl
            ``topic``: survey topic string
            ``stage_dir``: Path to the stage output directory
        """
        papers: list[dict[str, Any]] = context.get("papers", [])
        topic: str = context.get("topic", "")
        stage_dir: Path = context.get("stage_dir", Path("."))

        cards_dir = stage_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)

        all_cards: list[dict[str, Any]] = []
        cache_hits = 0
        to_fetch: list[dict[str, Any]] = []

        # --- Check cache for all papers first ---
        for paper in papers:
            pid = str(paper.get("paper_id", "") or paper.get("id", ""))
            title = str(paper.get("title", ""))
            cached = get_card(pid, title)
            if cached is not None:
                all_cards.append(cached.get("card", cached))
                cache_hits += 1
                # Still write card file if it doesn't exist
                _write_card_file(cards_dir, cached.get("card", cached))
            else:
                to_fetch.append(paper)

        logger.info(
            "[paper_reader] %d papers: %d cache hits, %d to fetch",
            len(papers), cache_hits, len(to_fetch),
        )

        if not to_fetch:
            return {"cards": all_cards, "cache_hits": cache_hits, "fetched": 0}

        # --- Parallel fetching ---
        def _read_one(paper: dict[str, Any]) -> dict[str, Any] | None:
            agent = PaperReaderAgent(self._llm)
            result = agent.execute({"paper": paper, "topic": topic})
            self._accumulate(result)
            if not result.success:
                logger.warning(
                    "[paper_reader] failed: %s — %s",
                    paper.get("title", "?")[:50], result.error,
                )
                return None
            card: dict[str, Any] = result.data.get("card", {})
            source: str = result.data.get("source", "unknown")

            # Cache the card
            pid = str(paper.get("paper_id", "") or paper.get("id", ""))
            title = str(paper.get("title", ""))
            put_card(pid, title, card, cite_key=str(paper.get("cite_key", "")),
                     fulltext_source=source)

            # Write card markdown file
            _write_card_file(cards_dir, card)
            return card

        fetched_count = 0
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_read_one, p): p for p in to_fetch}
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    card = future.result()
                    if card is not None:
                        all_cards.append(card)
                        fetched_count += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[paper_reader] exception for %s: %s",
                        paper.get("title", "?")[:50], exc,
                    )

        logger.info(
            "[paper_reader] done: %d total cards (%d cached, %d fetched)",
            len(all_cards), cache_hits, fetched_count,
        )

        # --- Cross-paper synthesis ---
        synthesis_path = self._run_synthesis(all_cards, topic, stage_dir)

        return {
            "cards": all_cards,
            "cache_hits": cache_hits,
            "fetched": fetched_count,
            "synthesis_path": str(synthesis_path) if synthesis_path else None,
        }

    def _run_synthesis(
        self, cards: list[dict[str, Any]], topic: str, stage_dir: Path
    ) -> Path | None:
        """Read all knowledge cards together and write a cross-paper synthesis."""
        if len(cards) < 2:
            return None

        # Build combined notes from all cards
        parts: list[str] = []
        for card in cards:
            title = card.get("title", "Unknown")
            notes = str(card.get("notes", "")).strip()
            if notes:
                parts.append(f"### {title}\n{notes}")

        if not parts:
            return None

        all_notes = "\n\n---\n\n".join(parts)
        # Cap at ~100k tokens worth of characters
        all_notes_capped = all_notes[:150_000]

        system = (
            "You are a senior academic researcher synthesising a body of literature "
            "for a comprehensive survey paper. Your goal is to identify the big picture — "
            "themes, relationships, gaps — not to summarise individual papers."
        )
        prompt = (
            f"You have read {len(cards)} papers in the field of: {topic}\n\n"
            "Below are research notes for each paper. Write a cross-paper synthesis covering:\n\n"
            "1. **Major themes and approaches** (3–6 named research directions that appear across multiple papers — describe each and list representative papers)\n"
            "2. **Relationships and lineage** (which papers build on, extend, challenge, or complement each other — be specific)\n"
            "3. **Recurring problems** (fundamental challenges the field keeps trying to solve)\n"
            "4. **Gaps and open questions** (what the literature collectively does not address yet)\n\n"
            "Reference papers by title. Aim for 600–900 words.\n\n"
            "---\n\n"
            f"{all_notes_capped}"
        )

        try:
            resp = self._llm.chat(
                [{"role": "user", "content": prompt}],
                system=system,
                max_tokens=128_000,
                temperature=0.4,
            )
            synthesis_text = resp.content.strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[paper_reader] synthesis pass failed: %s", exc)
            return None

        if not synthesis_text:
            return None

        synthesis_path = stage_dir / "synthesis.md"
        synthesis_path.write_text(
            f"# Cross-Paper Synthesis: {topic}\n\n{synthesis_text}\n",
            encoding="utf-8",
        )
        logger.info("[paper_reader] synthesis written: %s", synthesis_path)
        return synthesis_path


# ---------------------------------------------------------------------------
# Card → markdown file
# ---------------------------------------------------------------------------

def _write_card_file(cards_dir: Path, card: dict[str, Any]) -> None:
    """Write a knowledge card dict to a markdown file."""
    title = str(card.get("title", "unknown"))
    cite_key = str(card.get("cite_key", ""))
    fname = _safe_filename(cite_key or title)
    path = cards_dir / f"{fname}.md"

    meta_parts = []
    if card.get("fulltext_source"):
        meta_parts.append(f"source: {card['fulltext_source']}")
    if card.get("token_count"):
        meta_parts.append(f"tokens: {card['token_count']}")

    lines = [f"# {title}", ""]
    if meta_parts:
        lines.append(f"*{' | '.join(meta_parts)}*")
        lines.append("")
    lines.append(str(card.get("notes", "")))

    path.write_text("\n".join(lines), encoding="utf-8")
