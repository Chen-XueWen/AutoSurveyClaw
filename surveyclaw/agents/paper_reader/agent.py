"""PaperReaderAgent — reads one paper's full text and extracts a deep knowledge card.

Single-pass for papers ≤ MAX_SINGLE_PASS_TOKENS (120k tokens, ~90k words).
Hierarchical for longer papers: skeleton pass → per-section passes → consolidation.
"""

from __future__ import annotations

import logging
from typing import Any

from surveyclaw.agents.base import AgentStepResult, BaseAgent
from surveyclaw.utils.thinking_tags import strip_thinking_tags
from surveyclaw.literature.fulltext import (
    MAX_SINGLE_PASS_TOKENS,
    estimate_tokens,
    extract_skeleton,
    split_sections,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are an expert academic researcher writing concise, citable research notes "
    "from full papers for use in a comprehensive literature survey. "
    "Be specific: include model names, dataset names, benchmark numbers, and concrete claims. "
    "Adapt your coverage to the paper type — do not force a fixed structure."
)

_EXTRACT_TMPL = """\
Write a comprehensive research note for the following paper. It will be used in a literature survey on: {topic}

Adapt your coverage to the paper type:
- **Method / system paper**: describe the problem addressed, technical approach, key results with numbers, datasets/benchmarks, limitations, and relationship to prior work.
- **Survey / review paper**: describe scope and coverage, the taxonomy or categorisation proposed, key themes and patterns across the surveyed work, identified gaps, and how it relates to other surveys.
- **Position / theory paper**: describe the central argument, supporting evidence, implications for the field, and open questions raised.

Be specific. Aim for 300-500 words. Write in clear prose — no rigid section headings required.

Paper title: {title}

Paper text:
{text}"""

_SECTION_SUMMARY_TMPL = """\
Summarise this section of "{title}" for a survey on: {topic}

Include any key methods, results (with numbers), claims, or limitations. Be specific and concise.

Section: {heading}

{body}"""

_CONSOLIDATE_TMPL = """\
You have read "{title}" section by section. Write a comprehensive research note for a literature survey on: {topic}

Use the section summaries to produce a cohesive 300-500 word note. Cover the most important contribution, approach, results, limitations, and relationship to prior work. Adapt to the paper type — do not force a fixed structure.

Paper skeleton (intro + section headings + conclusion):
{skeleton}

Section summaries:
{summaries}"""


# ---------------------------------------------------------------------------
# PaperReaderAgent
# ---------------------------------------------------------------------------


class PaperReaderAgent(BaseAgent):
    """Reads one paper's full text and returns a deep knowledge card."""

    name = "paper_reader"

    def execute(self, context: dict[str, Any]) -> AgentStepResult:
        paper: dict[str, Any] = context.get("paper", {})
        topic: str = context.get("topic", "")
        title = str(paper.get("title", "Unknown"))
        cite_key = str(paper.get("cite_key", ""))

        from surveyclaw.literature.fulltext import fetch_fulltext

        # Fetch full text
        try:
            text, source = fetch_fulltext(paper)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[paper_reader] fetch failed for %r: %s", title[:50], exc)
            text = str(paper.get("abstract", ""))
            source = "abstract_only"

        if not text.strip():
            return self._make_result(
                False,
                error=f"No text available for: {title}",
            )

        # Choose single-pass or hierarchical
        token_count = estimate_tokens(text)
        logger.info(
            "[paper_reader] %s | source=%s | ~%d tokens",
            title[:50], source, token_count,
        )

        try:
            if token_count <= MAX_SINGLE_PASS_TOKENS:
                card = self._single_pass(text, title, topic)
            else:
                card = self._hierarchical_pass(text, title, topic)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[paper_reader] extraction failed for %r: %s", title[:50], exc)
            card = _fallback_card(paper, topic)

        card["cite_key"] = cite_key
        card["title"] = title
        card["fulltext_source"] = source
        card["token_count"] = token_count

        return self._make_result(True, data={"card": card, "source": source})

    # ------------------------------------------------------------------

    def _single_pass(self, text: str, title: str, topic: str) -> dict[str, Any]:
        """Single LLM call — fits within context window."""
        prompt = _EXTRACT_TMPL.format(
            topic=topic,
            title=title,
            text=text[:400_000],  # hard char cap (well below 200k tokens)
        )
        # max_tokens=128_000: thinking models (qwen3.5:35b) consume ~2-4k tokens on
        # <think> reasoning before producing the actual answer — 2048 is too small.
        raw = self._chat(_SYSTEM, prompt, max_tokens=128_000)
        notes = strip_thinking_tags(raw).strip()
        if notes:
            return {"notes": notes}
        return _fallback_card({"title": title}, topic)

    def _hierarchical_pass(self, text: str, title: str, topic: str) -> dict[str, Any]:
        """Multi-pass for long papers: per-section summaries → consolidation."""
        skeleton = extract_skeleton(text)
        sections = split_sections(text)

        # Filter to body sections (skip intro/conclusion already in skeleton)
        _skip = {"abstract", "introduction", "conclusion", "summary", "references",
                 "acknowledgement", "appendix", "full_text"}
        body_sections = [
            (h, b) for h, b in sections
            if not any(k in h.lower() for k in _skip) and len(b.split()) > 100
        ]

        logger.info(
            "[paper_reader] hierarchical: %d body sections for %s",
            len(body_sections), title[:50],
        )

        summaries: list[str] = []
        for heading, body in body_sections:
            # Cap each section at 60k tokens to be safe
            body_capped = " ".join(body.split()[:45_000])
            prompt = _SECTION_SUMMARY_TMPL.format(
                title=title, topic=topic, heading=heading, body=body_capped,
            )
            raw = self._chat(_SYSTEM, prompt, max_tokens=128_000)
            summary = strip_thinking_tags(raw).strip()
            summaries.append(f"### {heading}\n{summary}")

        summaries_text = "\n\n".join(summaries) if summaries else "(no body sections found)"
        consolidate_prompt = _CONSOLIDATE_TMPL.format(
            title=title,
            topic=topic,
            skeleton=skeleton[:30_000],
            summaries=summaries_text[:60_000],
        )
        raw = self._chat(_SYSTEM, consolidate_prompt, max_tokens=128_000)
        notes = strip_thinking_tags(raw).strip()
        if notes:
            return {"notes": notes}
        return _fallback_card({"title": title}, topic)


# ---------------------------------------------------------------------------
# Fallback card (used when LLM extraction fails)
# ---------------------------------------------------------------------------


def _fallback_card(paper: dict[str, Any], topic: str) -> dict[str, Any]:
    title = str(paper.get("title", "Unknown"))
    abstract = str(paper.get("abstract", ""))
    notes = abstract if abstract else f"[No text available — paper on {topic}]"
    return {
        "notes": notes,
        "title": title,
        "extraction_failed": True,
    }
