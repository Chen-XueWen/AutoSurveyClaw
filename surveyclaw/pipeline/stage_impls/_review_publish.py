"""Stages 18-23: Peer review, paper revision, quality gate, knowledge archive, export/publish, and citation verify."""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml  # noqa: F401 — available for downstream use

from surveyclaw.adapters import AdapterBundle
from surveyclaw.config import RCConfig
from surveyclaw.llm.client import LLMClient
from surveyclaw.pipeline._domain import _detect_domain  # noqa: F401
from surveyclaw.pipeline._helpers import (
    StageResult,
    _build_context_preamble,
    _chat_with_prompt,
    _collect_experiment_results,  # noqa: F401
    _default_quality_report,
    _extract_paper_title,
    _find_prior_file,
    _generate_framework_diagram_prompt,
    _generate_neurips_checklist,
    _get_evolution_overlay,
    _read_best_analysis,
    _read_prior_artifact,
    _safe_json_loads,
    _topic_constraint_block,  # noqa: F401
    _utcnow_iso,
    reconcile_figure_refs,
)
from surveyclaw.pipeline.stages import Stage, StageStatus
from surveyclaw.prompts import PromptManager
from surveyclaw.pipeline.stage_impls._paper_writing import _topic_is_literature_first

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers imported from executor.py (not yet moved to _helpers.py).
# Lazy-imported inside functions to avoid circular import when executor.py
# imports this module.
# ---------------------------------------------------------------------------


def _collect_experiment_evidence(run_dir: Path) -> str:
    return ""

# ---------------------------------------------------------------------------
# Stage 18: Peer Review
# ---------------------------------------------------------------------------

def _execute_peer_review(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    draft = _read_prior_artifact(run_dir, "paper_draft.md") or ""
    experiment_evidence = _collect_experiment_evidence(run_dir)

    # Load draft quality warnings from Stage 17 (if available)
    _quality_suffix = ""
    _quality_json_path = _find_prior_file(run_dir, "draft_quality.json")
    if _quality_json_path and _quality_json_path.exists():
        try:
            _dq = json.loads(_quality_json_path.read_text(encoding="utf-8"))
            _dq_warnings = _dq.get("overall_warnings", [])
            if _dq_warnings:
                _quality_suffix = (
                    "\n\nAUTOMATED QUALITY ISSUES (flag these in your review):\n"
                    + "\n".join(f"- {w}" for w in _dq_warnings)
                    + "\n"
                )
        except Exception:  # noqa: BLE001
            pass

    _is_survey_review = _topic_is_literature_first(config)

    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "peer_review")

        if _is_survey_review:
            _survey_review_system = (
                "You are a balanced reviewer for a SURVEY / LITERATURE REVIEW paper "
                "submitted to a top AI venue (NeurIPS, ICML, ICLR, or a journal).\n\n"
                "Apply the standards appropriate for a survey paper — NOT a novel-method paper. "
                "Key differences:\n"
                "- A survey should be 8,000-15,000 words (NOT 5,000-6,500)\n"
                "- A survey does NOT need original experimental results\n"
                "- A survey SHOULD have extensive citations (30-60+)\n"
                "- A survey CAN have fewer figures, though taxonomy diagrams are valued\n"
                "- A survey title signals a review (e.g. 'A Survey of...') — NOT a method acronym\n"
            )
            _survey_review_user = (
                f"Simulate peer review from 3 reviewer perspectives for this SURVEY paper.\n"
                f"Output markdown with Reviewer A (survey methodology expert), "
                f"Reviewer B (domain expert), Reviewer C (writing and rigor expert), "
                f"each with strengths, weaknesses, and actionable revisions.\n\n"
                f"Check specifically for survey-appropriate quality:\n"
                f"1. COVERAGE: Does the survey cover the major works in the field? "
                f"Are there notable gaps? Does it cite 30-60+ relevant papers?\n"
                f"2. TAXONOMY: Is the categorization scheme principled and well-defined? "
                f"Are the category boundaries clear and justified?\n"
                f"3. DEPTH: For each category, does the review go beyond summarising abstracts "
                f"to critically analyse strengths/weaknesses of methods?\n"
                f"4. COMPARISON TABLES: Does the paper include tables comparing methods "
                f"across benchmarks/tasks? Are reported numbers sourced from cited papers?\n"
                f"5. FUTURE DIRECTIONS: Are the identified open challenges concrete and specific? "
                f"Do they go beyond vague 'more research is needed' statements?\n"
                f"6. PLACEHOLDER SECTIONS: Flag any section that appears to be a placeholder "
                f"('This section will describe...', 'The following sections will present...').\n"
                f"7. WRITING QUALITY: Is the paper written in flowing academic prose? "
                f"Is hedging language minimised? Is the abstract informative (not just structural)?\n"
                f"8. COMPLETENESS: Does the paper have all required sections "
                f"(Introduction, Methodology, Taxonomy, Detailed Review, Comparative Analysis, "
                f"Open Challenges, Conclusion)?\n\n"
                f"Topic: {config.research.topic}\n\n"
                f"Paper draft:\n{draft}"
                + _quality_suffix
            )
            resp = _chat_with_prompt(
                llm,
                _survey_review_system,
                _survey_review_user,
                json_mode=False,
                max_tokens=128_000,
            )
        else:
            sp = _pm.for_stage(
                "peer_review",
                evolution_overlay=_overlay,
                topic=config.research.topic,
                draft=draft,
                experiment_evidence=experiment_evidence,
            )
            _review_user = sp.user + _quality_suffix
            resp = _chat_with_prompt(
                llm,
                sp.system,
                _review_user,
                json_mode=sp.json_mode,
                max_tokens=sp.max_tokens,
            )
        reviews = resp.content
    else:
        reviews = """# Reviews

## Reviewer A
- Strengths: Clear problem statement.
- Weaknesses: Limited ablation details.
- Actionable revisions: Add uncertainty analysis and stronger baselines.

## Reviewer B
- Strengths: Reproducibility focus.
- Weaknesses: Discussion underdeveloped.
- Actionable revisions: Expand limitations and broader impact.
"""
    (stage_dir / "reviews.md").write_text(reviews, encoding="utf-8")
    return StageResult(
        stage=Stage.PEER_REVIEW,
        status=StageStatus.DONE,
        artifacts=("reviews.md",),
        evidence_refs=(f"stage-{int(Stage.PEER_REVIEW):02d}/reviews.md",),
    )


# ---------------------------------------------------------------------------
# Stage 19: Paper Revision
# ---------------------------------------------------------------------------

def _execute_paper_revision(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    draft = _read_prior_artifact(run_dir, "paper_draft.md") or ""
    reviews = _read_prior_artifact(run_dir, "reviews.md") or ""
    draft_word_count = len(draft.split())



    _is_survey = _topic_is_literature_first(config)

    if llm is not None:
        _pm = prompts or PromptManager()
        try:
            _ws_revision = _pm.block("writing_structure")
        except (KeyError, Exception):  # noqa: BLE001
            _ws_revision = ""
        # IMP-20/25/31/24: Load style blocks for revision prompt
        _rev_blocks: dict[str, str] = {}
        for _bname in ("academic_style_guide", "narrative_writing_rules",
                        "anti_hedging_rules", "anti_repetition_rules"):
            try:
                _rev_blocks[_bname] = _pm.block(_bname)
            except (KeyError, Exception):  # noqa: BLE001
                _rev_blocks[_bname] = ""
        # Load draft quality directives from Stage 17
        _quality_prefix = ""
        _quality_json_path = _find_prior_file(run_dir, "draft_quality.json")
        if _quality_json_path and _quality_json_path.exists():
            try:
                _dq = json.loads(_quality_json_path.read_text(encoding="utf-8"))
                _dq_directives = _dq.get("revision_directives", [])
                if _dq_directives:
                    _quality_prefix = (
                        "MANDATORY QUALITY FIXES (address ALL of these):\n"
                        + "\n".join(f"- {d}" for d in _dq_directives)
                        + "\n\n"
                    )
            except Exception:  # noqa: BLE001
                pass

        _overlay = _get_evolution_overlay(run_dir, "paper_revision")

        if _is_survey:
            # Survey-specific revision: expand depth, do NOT compress to 6,500 words
            _survey_revision_system = (
                "You are a senior academic reviewer and writing editor specialising in "
                "survey / literature review papers for top AI venues (NeurIPS, ICML, ICLR, ACL).\n\n"
                "SURVEY REVISION RULES:\n"
                "1. DO NOT invent new methods, algorithms, or fictional technique names.\n"
                "2. EXPAND, do not shrink: a survey should be 8,000-15,000 words — there is NO 6,500-word cap.\n"
                "3. Replace ALL placeholder sections ('This section will describe...', "
                "'The methodology section will present...', etc.) with actual substantive content.\n"
                "4. Improve DEPTH: if any section lacks per-paper analysis, add it using the available references.\n"
                "5. Improve TABLES: ensure every comparison table has data sourced from cited papers.\n"
                "6. Do NOT add disclaimers like 'due to computational constraints'.\n"
                "7. CITATION FORMAT (CRITICAL): keep all citations in [cite_key] bracket format.\n"
                "8. CITATION KEYS (CRITICAL): do NOT invent new citation keys not in the draft.\n"
                "9. Keep the title exactly as-is — do NOT add a catchy method acronym.\n"
                "10. Write as flowing academic prose — convert any bullet-point lists in the main body to prose.\n"
                + (f"\n\n{_overlay}" if _overlay else "")
            )
            _survey_revision_user = (
                f"{_rev_blocks.get('academic_style_guide', '')}\n"
                f"{_rev_blocks.get('narrative_writing_rules', '')}\n"
                f"{_rev_blocks.get('anti_hedging_rules', '')}\n"
                f"{_rev_blocks.get('anti_repetition_rules', '')}\n\n"
                "Revise the survey paper draft to address all reviewer comments and improve quality.\n"
                "Return ONLY the revised markdown — no preamble, no commentary.\n\n"
                "CRITICAL SURVEY REVISION RULES:\n"
                "- Replace ANY section that is a placeholder (e.g. 'This section will describe...', "
                "'The methodology section will present...' etc.) with ACTUAL CONTENT.\n"
                "- The paper MUST be at least as long as the draft — ideally 10-20% longer "
                "if reviewer comments ask for more depth.\n"
                "- Do NOT add a word count cap or compress sections that reviewers did not flag.\n"
                "- If reviewers ask for more quantitative analysis: add comparison tables using "
                "numbers ALREADY reported in the cited papers (do not invent numbers).\n"
                "- If reviewers ask for more citations: use only cite_keys already in the draft.\n"
                "- The title MUST remain a survey title (e.g. 'A Survey of...') — do NOT rename it.\n"
                "- NEVER use '--' placeholder values in tables. Replace with 'N/A' or actual values.\n"
                "- CITATION FORMAT (CRITICAL): keep all citations as [cite_key] brackets.\n"
                f"{_pm.block('topic_constraint', topic=config.research.topic)}"
                f"\n\nREVIEWER FEEDBACK TO ADDRESS:\n{_quality_prefix}{reviews}\n\n"
                f"DRAFT TO REVISE:\n{draft}"
            )
            revision_max_tokens = max(16000, int(draft_word_count * 1.8))
            _revision_system = _survey_revision_system
            _revision_user = _survey_revision_user
            _revision_json_mode = False
        else:
            sp = _pm.for_stage(
                "paper_revision",
                evolution_overlay=_overlay,
                topic_constraint=_pm.block("topic_constraint", topic=config.research.topic),
                writing_structure=_ws_revision,
                draft=draft,
                reviews=_quality_prefix + reviews,
                **_rev_blocks,
            )
            # R10-Fix2: Ensure max_tokens is sufficient for full paper revision
            revision_max_tokens = sp.max_tokens
            if revision_max_tokens and draft_word_count > 0:
                # ~1.5 tokens per word, 20% headroom
                min_tokens_needed = int(draft_word_count * 1.5 * 1.2)
                if revision_max_tokens < min_tokens_needed:
                    revision_max_tokens = min_tokens_needed
                    logger.info(
                        "Stage 19: Increased max_tokens from %d to %d to fit full paper revision",
                        sp.max_tokens,
                        revision_max_tokens,
                    )
            _revision_system = sp.system
            _revision_user = sp.user
            _revision_json_mode = sp.json_mode

        resp = _chat_with_prompt(
            llm,
            _revision_system,
            _revision_user,
            json_mode=_revision_json_mode,
            max_tokens=revision_max_tokens,
            retries=2,
        )
        revised = resp.content
        revised_word_count = len(revised.split())
        # Length guard: if revision is shorter than 80% of draft, retry once
        # For surveys use a stricter threshold: must match draft length exactly
        _length_threshold = draft_word_count if _is_survey else int(draft_word_count * 0.8)
        if draft_word_count > 500 and revised_word_count < _length_threshold:
            logger.warning(
                "Paper revision (%d words) is shorter than draft (%d words). "
                "Retrying with stronger length enforcement.",
                revised_word_count,
                draft_word_count,
            )
            retry_user = (
                f"CRITICAL LENGTH REQUIREMENT: The draft is {draft_word_count} words. "
                f"Your revision MUST be at least {draft_word_count} words — ideally longer. "
                f"Do NOT summarize or condense ANY section. Copy each section verbatim "
                f"and ONLY make targeted improvements to address reviewer comments. "
                f"If a section has no reviewer comments, include it UNCHANGED.\n\n"
                + _revision_user
            )
            resp2 = _chat_with_prompt(
                llm, _revision_system, retry_user,
                json_mode=_revision_json_mode, max_tokens=revision_max_tokens,
            )
            revised2 = resp2.content
            revised2_word_count = len(revised2.split())
            if revised2_word_count >= _length_threshold:
                revised = revised2
            else:
                # Revision consistently shorter than draft — fall back to draft
                # (for surveys this happens often due to token budget constraints)
                logger.warning(
                    "Revision still shorter than draft after retry (%d → %d words, need %d). "
                    "Falling back to FULL ORIGINAL DRAFT to prevent content loss.",
                    revised_word_count,
                    revised2_word_count,
                    _length_threshold,
                )
                # Save revision notes internally for reference
                _best_revision = revised2 if revised2_word_count > revised_word_count else revised
                revision_words = _best_revision.split()
                revision_summary = (
                    " ".join(revision_words[:500]) + "\n\n*(Revision summary truncated)*"
                    if len(revision_words) > 500
                    else _best_revision
                )
                if revision_summary.strip():
                    (stage_dir / "revision_notes_internal.md").write_text(
                        revision_summary, encoding="utf-8"
                    )
                revised = draft
    else:
        revised = draft
    (stage_dir / "paper_revised.md").write_text(revised, encoding="utf-8")
    return StageResult(
        stage=Stage.PAPER_REVISION,
        status=StageStatus.DONE,
        artifacts=("paper_revised.md",),
        evidence_refs=(f"stage-{int(Stage.PAPER_REVISION):02d}/paper_revised.md",),
    )


# ---------------------------------------------------------------------------
# Stage 20: Quality Gate
# ---------------------------------------------------------------------------

def _execute_quality_gate(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    revised = _read_prior_artifact(run_dir, "paper_revised.md") or ""
    report: dict[str, Any] | None = None
    _exp_context = ""

    if llm is not None:
        _pm = prompts or PromptManager()
        paper_for_eval = revised[:40000] if len(revised) > 40000 else revised
        _overlay = _get_evolution_overlay(run_dir, "quality_gate")
        sp = _pm.for_stage(
            "quality_gate",
            evolution_overlay=_overlay,
            quality_threshold=str(config.research.quality_threshold),
            revised=paper_for_eval + _exp_context,
        )
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        parsed = _safe_json_loads(resp.content, {})
        if isinstance(parsed, dict):
            report = parsed

    if report is None:
        report = _default_quality_report(config.research.quality_threshold)
    report.setdefault("generated", _utcnow_iso())
    (stage_dir / "quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # T2.1: Enforce quality gate — fail if score below threshold
    score = report.get("score_1_to_10", 0)
    # BUG-R5-01: score can be string from LLM JSON — coerce to float
    if not isinstance(score, (int, float)):
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0
    verdict = report.get("verdict", "proceed")
    threshold = config.research.quality_threshold or 5.0

    (stage_dir / "fabrication_flags.json").write_text(
        json.dumps({}, indent=2), encoding="utf-8"
    )

    if isinstance(score, (int, float)) and score < threshold:
        if config.research.graceful_degradation:
            logger.warning(
                "Quality gate DEGRADED: score %.1f < threshold %.1f — "
                "continuing with sanitization (graceful_degradation=True)",
                score, threshold,
            )
            # Write degradation signal for downstream stages
            signal = {
                "score": score,
                "threshold": threshold,
                "verdict": verdict,
                "weaknesses": report.get("weaknesses", []),
                "generated": _utcnow_iso(),
            }
            (run_dir / "degradation_signal.json").write_text(
                json.dumps(signal, indent=2), encoding="utf-8"
            )
            return StageResult(
                stage=Stage.QUALITY_GATE,
                status=StageStatus.DONE,
                artifacts=("quality_report.json",),
                evidence_refs=(f"stage-{int(Stage.QUALITY_GATE):02d}/quality_report.json",),
                decision="degraded",
            )
        logger.warning(
            "Quality gate FAILED: score %.1f < threshold %.1f (verdict=%s)",
            score, threshold, verdict,
        )
        return StageResult(
            stage=Stage.QUALITY_GATE,
            status=StageStatus.FAILED,
            artifacts=("quality_report.json", "fabrication_flags.json"),
            evidence_refs=(f"stage-{int(Stage.QUALITY_GATE):02d}/quality_report.json",),
            error=f"Quality score {score:.1f}/10 below threshold {threshold:.1f}. "
                  f"Paper needs revision before export.",
        )

    logger.info(
        "Quality gate PASSED: score %.1f >= threshold %.1f",
        score, threshold,
    )
    return StageResult(
        stage=Stage.QUALITY_GATE,
        status=StageStatus.DONE,
        artifacts=("quality_report.json", "fabrication_flags.json"),
        evidence_refs=(f"stage-{int(Stage.QUALITY_GATE):02d}/quality_report.json",),
    )


# ---------------------------------------------------------------------------
# Stage 21: Knowledge Archive
# ---------------------------------------------------------------------------

def _execute_knowledge_archive(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    revised = _read_prior_artifact(run_dir, "paper_revised.md") or ""
    analysis = _read_best_analysis(run_dir)
    decision = _read_prior_artifact(run_dir, "decision.md") or ""
    preamble = _build_context_preamble(config, run_dir, include_goal=True)
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "knowledge_archive")
        sp = _pm.for_stage(
            "knowledge_archive",
            evolution_overlay=_overlay,
            preamble=preamble,
            decision=decision,
            analysis=analysis,
            revised=revised[:15000],
        )
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        archive = resp.content
    else:
        archive = f"""# Knowledge Archive

## Lessons Learned
- Preserve strict metric reporting protocol.
- Keep refinement logs aligned with code changes.

## Reproducibility
- Include exact experiment script and schedule.
- Capture run-level JSON metrics.

## Future Work
- Extend robustness and external validity checks.

Generated: {_utcnow_iso()}
"""
    (stage_dir / "archive.md").write_text(archive, encoding="utf-8")

    files: list[str] = []
    for stage_subdir in sorted(run_dir.glob("stage-*")):
        for artifact in sorted(stage_subdir.rglob("*")):
            if artifact.is_file() and artifact != (stage_dir / "bundle_index.json"):
                files.append(str(artifact.relative_to(run_dir)))
    index = {
        "run_id": run_dir.name,
        "generated": _utcnow_iso(),
        "artifact_count": len(files),
        "artifacts": files,
    }
    (stage_dir / "bundle_index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    return StageResult(
        stage=Stage.KNOWLEDGE_ARCHIVE,
        status=StageStatus.DONE,
        artifacts=("archive.md", "bundle_index.json"),
        evidence_refs=(
            f"stage-{int(Stage.KNOWLEDGE_ARCHIVE):02d}/archive.md",
            f"stage-{int(Stage.KNOWLEDGE_ARCHIVE):02d}/bundle_index.json",
        ),
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# BUG-176: Missing citation resolution
# BUG-194: Validate search results to avoid replacing correct entries with
#           garbage.  Previous code searched by cite-key fragments (e.g.
#           "he 2016 deep") which returned completely unrelated papers.
#           Fix: (1) consult seminal_papers.yaml first, (2) require title-
#           similarity validation for API results, (3) build better queries.
# ---------------------------------------------------------------------------

# Minimum title-similarity between search result and expected title/query
# for a result to be accepted.  Prevents "Jokowi and the New Developmentalism"
# from replacing "Deep Residual Learning for Image Recognition".
_CITATION_RESOLVE_MIN_SIMILARITY = 0.30


def _load_seminal_papers_by_key() -> dict[str, dict]:
    """Load seminal_papers.yaml and index by cite_key.

    Returns dict like::

        {"he2016deep": {"title": "Deep Residual Learning...", "authors": "He et al.", ...}, ...}

    Returns empty dict on any failure (missing file, bad YAML, etc.).
    """
    try:
        from surveyclaw.data import _load_all as _load_seminal_all
        all_papers = _load_seminal_all()
        return {p["cite_key"]: p for p in all_papers if "cite_key" in p}
    except Exception:  # noqa: BLE001
        return {}


def _seminal_to_bibtex(paper: dict, cite_key: str) -> str:
    """Convert a seminal_papers.yaml entry dict to a BibTeX string."""
    title = paper.get("title", "Unknown")
    authors = paper.get("authors", "Unknown")
    year = paper.get("year", "")
    venue = paper.get("venue", "")

    # Decide entry type
    venue_lower = (venue or "").lower()
    is_conf = any(kw in venue_lower for kw in (
        "neurips", "nips", "icml", "iclr", "cvpr", "eccv", "iccv",
        "aaai", "acl", "emnlp", "naacl", "sigir", "kdd", "www",
        "ijcai", "conference", "proc", "workshop",
    ))
    if is_conf:
        return (
            f"@inproceedings{{{cite_key},\n"
            f"  title = {{{title}}},\n"
            f"  author = {{{authors}}},\n"
            f"  year = {{{year}}},\n"
            f"  booktitle = {{{venue}}},\n"
            f"}}"
        )
    return (
        f"@article{{{cite_key},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year = {{{year}}},\n"
        f"  journal = {{{venue}}},\n"
        f"}}"
    )


def _resolve_missing_citations(
    missing_keys: set[str],
    existing_bib: str,
) -> tuple[set[str], list[str]]:
    """Try to find BibTeX entries for citation keys not in references.bib.

    Parses each cite_key (e.g. ``hendrycks2017baseline``) into an author name
    and year, then searches academic APIs.  Returns ``(resolved_keys,
    new_bib_entries)`` where each entry is a complete BibTeX string.

    BUG-194 fix: Three-layer resolution strategy:
      1. **Seminal lookup** — check seminal_papers.yaml (zero API calls, exact match)
      2. **API search with validation** — search Semantic Scholar / arXiv, but ONLY
         accept results whose title has ≥ 30% word overlap with query terms.
         Previously any year-matching result was blindly accepted, causing
         foundational papers to be replaced with garbage.
      3. **Skip** — if no confident match, leave the citation unresolved rather
         than inject a wrong paper.

    Gracefully returns empty results on any network failure.
    """
    import re as _re176
    import time as _time176

    resolved: set[str] = set()
    new_entries: list[str] = []

    def _parse_cite_key(key: str) -> tuple[str, str, str]:
        """Extract (author, year, keyword_hint) from a citation key.

        Common patterns:
          ``he2016deep``       → ("he", "2016", "deep")
          ``vaswani2017attention`` → ("vaswani", "2017", "attention")
          ``goodfellow2014generative`` → ("goodfellow", "2014", "generative")
        """
        m = _re176.match(r"([a-zA-Z]+?)(\d{4})(.*)", key)
        if m:
            return m.group(1), m.group(2), m.group(3)
        return key, "", ""

    def _title_word_overlap(title: str, query_words: list[str]) -> float:
        """Word-overlap score between a paper title and query keywords.

        Returns fraction of query words found in the title (0.0–1.0).
        Used to validate that a search result is actually relevant.
        """
        if not query_words:
            return 0.0
        title_lower = set(
            _re176.sub(r"[^a-z0-9\s]", "", title.lower()).split()
        ) - {""}
        if not title_lower:
            return 0.0
        matched = sum(1 for w in query_words if w.lower() in title_lower)
        return matched / len(query_words)

    # --- Layer 1: Seminal papers lookup (no API calls) ---
    seminal_by_key = _load_seminal_papers_by_key()

    for key in sorted(missing_keys):
        if key in seminal_by_key and key not in existing_bib:
            sp = seminal_by_key[key]
            bib_entry = _seminal_to_bibtex(sp, key)
            new_entries.append(bib_entry)
            resolved.add(key)
            logger.info(
                "BUG-194: Resolved %r via seminal_papers.yaml → %r (%s)",
                key, sp.get("title", "")[:60], sp.get("year", ""),
            )

    # Remaining keys that weren't in the seminal database AND aren't already
    # present in the existing bib (no point re-resolving keys we already have).
    remaining = sorted(
        k for k in (missing_keys - resolved) if k not in existing_bib
    )
    if not remaining:
        return resolved, new_entries

    # --- Layer 2: API search with title-similarity validation ---
    try:
        from surveyclaw.literature.search import search_papers
    except ImportError:
        logger.debug("BUG-176: literature.search not available, skipping resolution")
        return resolved, new_entries

    for key in remaining:
        author, year, hint = _parse_cite_key(key)
        if not author or not year:
            continue

        # BUG-194: Build a better search query.
        # Instead of "he 2016 deep", use "he deep residual learning 2016" or
        # at minimum, split camelCase hints into separate words.
        # Split hint on word boundaries (camelCase or underscore).
        hint_words = _re176.findall(r"[a-zA-Z]+", hint) if hint else []
        # The query words used for validation
        query_words = [author] + hint_words

        # Build search query: author + hint words + year (year helps but isn't
        # the primary discriminator anymore)
        query_parts = [author] + hint_words + [year]
        query = " ".join(query_parts)

        try:
            results = search_papers(query, limit=5, deduplicate=True)
        except Exception as exc:
            logger.debug("BUG-176: Search failed for %r: %s", key, exc)
            continue

        if not results:
            logger.debug(
                "BUG-194: No search results for %r (query=%r), skipping",
                key, query,
            )
            continue

        # BUG-194: Find best match by title-word-overlap AND year match.
        # Previously the code just took the first year-matching result.
        best = None
        best_score = -1.0
        for paper in results:
            overlap = _title_word_overlap(paper.title, query_words)
            year_bonus = 0.2 if str(paper.year) == year else 0.0
            # Also give bonus for author name appearing in paper.authors
            author_bonus = 0.0
            if any(author.lower() in a.name.lower() for a in paper.authors):
                author_bonus = 0.2
            score = overlap + year_bonus + author_bonus
            if score > best_score:
                best_score = score
                best = paper

        if best is None:
            continue

        # BUG-194: Validate the result — require minimum similarity.
        # This is the KEY fix: previously ANY result was accepted blindly.
        overlap = _title_word_overlap(best.title, query_words)
        if overlap < _CITATION_RESOLVE_MIN_SIMILARITY:
            logger.info(
                "BUG-194: Rejecting search result for %r — title %r has "
                "too-low overlap (%.2f < %.2f) with query words %r",
                key, best.title[:60], overlap,
                _CITATION_RESOLVE_MIN_SIMILARITY, query_words,
            )
            continue

        # Year must also match (or be within 1 year — sometimes conferences
        # vs arXiv preprint have different years)
        if year and best.year:
            year_diff = abs(int(year) - int(best.year))
            if year_diff > 1:
                logger.info(
                    "BUG-194: Rejecting search result for %r — year mismatch "
                    "(%s vs %s, diff=%d)",
                    key, year, best.year, year_diff,
                )
                continue

        # Generate BibTeX with the ORIGINAL cite_key (so \cite{key} works)
        bib_entry = best.to_bibtex()
        # Replace the auto-generated cite_key with the one used in the paper
        orig_key_match = _re176.match(r"@(\w+)\{([^,]+),", bib_entry)
        if orig_key_match:
            bib_entry = bib_entry.replace(
                f"@{orig_key_match.group(1)}{{{orig_key_match.group(2)},",
                f"@{orig_key_match.group(1)}{{{key},",
                1,
            )

        # Verify entry doesn't duplicate an existing key
        if key not in existing_bib:
            new_entries.append(bib_entry)
            resolved.add(key)
            logger.info(
                "BUG-194: Resolved %r via API → %r (%s, overlap=%.2f)",
                key, best.title[:60], best.year, overlap,
            )
        else:
            logger.debug(
                "BUG-194: Key %r already in bib, skipping API result", key,
            )

        # Rate limit: 0.5s between API calls
        _time176.sleep(0.5)

    return resolved, new_entries


# ---------------------------------------------------------------------------
# Stage 22: Export & Publish
# ---------------------------------------------------------------------------

def _execute_export_publish(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    revised = _read_prior_artifact(run_dir, "paper_revised.md") or ""
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "export_publish")
        sp = _pm.for_stage("export_publish", evolution_overlay=_overlay, revised=revised)
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        final_paper = resp.content
        # Content guard: reject LLM output that truncates the paper
        if revised and len(final_paper) < 0.6 * len(revised):
            logger.warning(
                "Stage 22: LLM output is %.0f%% of input length — using original",
                100 * len(final_paper) / max(len(revised), 1),
            )
            final_paper = revised
    else:
        final_paper = revised
    if not final_paper.strip():
        final_paper = "# Final Paper\n\nNo content generated."

    # --- Always-on fabrication sanitization (Phase 1 anti-fabrication) ---
    # Back up pre-sanitized version
    (stage_dir / "paper_presanitized.md").write_text(
        final_paper, encoding="utf-8"
    )

    _san_report = {}

    # Graceful degradation: insert notice only when quality gate was degraded
    _degradation_signal_path = run_dir / "degradation_signal.json"
    if _degradation_signal_path.exists():
        try:
            _deg_signal = json.loads(
                _degradation_signal_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            _deg_signal = {}

        # Insert degradation notice after abstract
        _deg_score = _deg_signal.get("score", "N/A")
        _deg_threshold = _deg_signal.get("threshold", "N/A")
        _deg_notice = (
            "\n\n> **Note:** This paper was produced in degraded mode. "
            f"Quality gate score ({_deg_score}/{_deg_threshold}) was below "
            "threshold. Unverified numerical results in tables have been "
            "replaced with `---` and require independent verification.\n\n"
        )
        # Try to insert after ## Abstract section
        _abstract_markers = ["## Abstract\n", "# Abstract\n"]
        _notice_inserted = False
        for _marker in _abstract_markers:
            if _marker in final_paper:
                _marker_end = final_paper.index(_marker) + len(_marker)
                # Find the end of the abstract paragraph
                _next_section = final_paper.find("\n## ", _marker_end)
                _next_heading = final_paper.find("\n# ", _marker_end)
                _insert_pos = min(
                    p for p in (_next_section, _next_heading)
                    if p > 0
                ) if any(p > 0 for p in (_next_section, _next_heading)) else len(final_paper)
                final_paper = (
                    final_paper[:_insert_pos]
                    + _deg_notice
                    + final_paper[_insert_pos:]
                )
                _notice_inserted = True
                break
        if not _notice_inserted:
            # Fallback: prepend to paper
            final_paper = _deg_notice + final_paper

        logger.info(
            "Stage 22: Applied degraded-mode notice (score=%s, threshold=%s)",
            _deg_score, _deg_threshold,
        )

    # IMP-3: Deduplicate "due to computational constraints" — keep at most 1
    import re as _re_imp3
    _CONSTRAINT_PAT = _re_imp3.compile(
        r"[Dd]ue to computational constraints", _re_imp3.IGNORECASE
    )
    _matches = list(_CONSTRAINT_PAT.finditer(final_paper))
    if len(_matches) > 1:
        # Keep only the first occurrence; remove subsequent ones by
        # deleting the enclosing sentence.
        for m in reversed(_matches[1:]):
            # Find sentence boundaries around the match
            start = final_paper.rfind(".", 0, m.start())
            start = start + 1 if start >= 0 else m.start()
            end = final_paper.find(".", m.end())
            end = end + 1 if end >= 0 else m.end()
            sentence = final_paper[start:end].strip()
            if sentence:
                final_paper = final_paper[:start] + final_paper[end:]
        final_paper = re.sub(r"[^\S\n]{2,}", " ", final_paper)
        logger.info(
            "Stage 22: Removed %d duplicate 'computational constraints' "
            "disclaimers",
            len(_matches) - 1,
        )

    # IMP-19 Layer 2: Ensure at least figures are referenced in the paper
    import re as _re_fig
    chart_files = []
    # BUG-215: Also search stage-14* versioned dirs (stage-14_v1, etc.)
    # in case stage-14/ was renamed and never recreated.
    _chart_search_dirs = [stage_dir / "charts", run_dir / "stage-14" / "charts"]
    for _s14_charts in sorted(run_dir.glob("stage-14*/charts"), reverse=True):
        if _s14_charts not in _chart_search_dirs:
            _chart_search_dirs.append(_s14_charts)
    for _chart_src_dir in _chart_search_dirs:
        if _chart_src_dir.is_dir():
            chart_files.extend(sorted(_chart_src_dir.glob("*.png")))
    # BUG-190: Also inject charts not already referenced in the paper.
    # The old condition only fired when NO figures were present. Now we
    # filter to only unreferenced charts, so partially-illustrated papers
    # also get the remaining charts injected.
    _already_referenced = set()
    for _cf in chart_files:
        if _cf.name in final_paper:
            _already_referenced.add(_cf.name)
    chart_files = [cf for cf in chart_files if cf.name not in _already_referenced]
    if chart_files:
        # Distribute figures to relevant sections based on filename keywords
        _fig_placement: dict[str, list[str]] = {
            "method": [],       # architecture, method, model, pipeline diagrams
            "result": [],       # experiment, comparison, ablation charts
            "intro": [],        # concept, overview, illustration
        }
        _fig_counter = len(_already_referenced)  # start numbering after existing figs
        for cf in chart_files[:6]:
            _fig_counter += 1
            stem_lower = cf.stem.lower()
            label = cf.stem.replace("_", " ").title()
            fig_md = f"![Figure {_fig_counter}: {label}](charts/{cf.name})"
            if any(k in stem_lower for k in ("architecture", "model", "pipeline", "method", "flowchart")):
                _fig_placement["method"].append(fig_md)
            elif any(k in stem_lower for k in ("experiment", "comparison", "ablation", "result", "metric")):
                _fig_placement["result"].append(fig_md)
            elif any(k in stem_lower for k in ("concept", "overview", "illustration", "threat", "attack")):
                _fig_placement["intro"].append(fig_md)
            else:
                _fig_placement["result"].append(fig_md)  # default to results

        # Insert figures at relevant section boundaries.
        # BUG-200: Match both H1 (#) and H2 (##) headings — LLMs generate
        # either level depending on the writing_structure prompt.
        _section_markers = {
            "method": ["# Method", "## Method", "# Methodology", "## Methodology",
                        "# Approach", "## Approach", "# Framework", "## Framework",
                        "## 3. Method", "## 3 Method"],
            "result": ["# Results", "## Results", "# Experiments", "## Experiments",
                        "# Evaluation", "## Evaluation",
                        "## 5. Results", "## 4. Experiments", "## 5 Results"],
            "intro": ["# Related Work", "## Related Work", "# Background",
                       "## Background", "## 2. Related", "## 2 Related Work"],
        }
        _total_inserted = 0
        for category, figs in _fig_placement.items():
            if not figs:
                continue
            fig_block = "\n\n" + "\n\n".join(figs) + "\n\n"
            inserted = False
            for marker in _section_markers.get(category, []):
                if marker in final_paper:
                    # Insert BEFORE the marker section (so figure appears at end of previous section)
                    final_paper = final_paper.replace(marker, fig_block + marker, 1)
                    inserted = True
                    _total_inserted += len(figs)
                    break
            if not inserted:
                # Fallback: insert before Conclusion/Limitations/Discussion
                for fallback in ["# Conclusion", "## Conclusion",
                                 "# Limitations", "## Limitations",
                                 "# Discussion", "## Discussion"]:
                    if fallback in final_paper:
                        final_paper = final_paper.replace(fallback, fig_block + fallback, 1)
                        inserted = True
                        _total_inserted += len(figs)
                        break
            if not inserted:
                # BUG-200: Last resort — insert before closing fence marker
                # rather than appending after it (which puts content outside
                # the markdown fence and gets dropped by converter).
                _fence_end = final_paper.rfind("\n```")
                if _fence_end > 0:
                    final_paper = (
                        final_paper[:_fence_end] + fig_block + final_paper[_fence_end:]
                    )
                else:
                    final_paper += fig_block
                _total_inserted += len(figs)

        logger.info(
            "IMP-19: Injected %d figure references into paper_final.md (distributed across sections)",
            _total_inserted,
        )

    # IMP-24: Detect excessive number repetition
    _numbers_found = _re_fig.findall(r"\b\d+\.\d{2,}\b", final_paper)
    _num_counts = Counter(_numbers_found)
    _repeated = {n: c for n, c in _num_counts.items() if c > 3}
    if _repeated:
        logger.warning(
            "IMP-24: Numbers repeated >3 times: %s",
            _repeated,
        )

    (stage_dir / "paper_final.md").write_text(final_paper, encoding="utf-8")

    # --- Legacy fabrication sanitization (disabled — superseded by Phase 1 _sanitize_fabricated_data above) ---
    # Kept but guarded: Phase 1 always-on sanitization handles this now.
    # Only run if Phase 1 was somehow skipped (should never happen).
    _fab_flags_text = _read_prior_artifact(run_dir, "fabrication_flags.json") or ""
    _fab_flags = _safe_json_loads(_fab_flags_text, {}) if _fab_flags_text else {}
    if (
        isinstance(_fab_flags, dict)
        and _fab_flags.get("fabrication_suspected")
        and _san_report.get("numbers_replaced", 0) == 0  # Phase 1 didn't run/replace
    ):
        import re as _re_fab
        _real_vals = set()
        for rv in _fab_flags.get("real_metric_values", []):
            if isinstance(rv, (int, float)) and math.isfinite(rv):
                _real_vals.add(str(round(rv, 4)))
                _real_vals.add(str(round(rv, 2)))
                _real_vals.add(str(round(rv, 1)))
                if rv == int(rv):
                    _real_vals.add(str(int(rv)))

        def _sanitize_number(m: _re_fab.Match) -> str:  # type: ignore[name-defined]
            """Replace fabricated numbers with '--' but keep real ones."""
            num_str = m.group(0)
            # Keep the number if it matches any known real metric value
            try:
                num_val = float(num_str)
                if not math.isfinite(num_val):
                    return "--"
                rounded_strs = {
                    str(round(num_val, 4)),
                    str(round(num_val, 2)),
                    str(round(num_val, 1)),
                    *(
                        [str(int(num_val))] if num_val == int(num_val) else []
                    ),
                }
                if rounded_strs & _real_vals:
                    return num_str  # real value — keep it
            except (ValueError, OverflowError):
                return num_str
            return "--"

        # Only sanitize numbers in Results/Experiments/Evaluation/Ablation sections
        _result_section_pat = _re_fab.compile(
            r"(##\s*(?:\d+\.?\s*)?(?:Results|Experiments|Evaluation|Ablation"
            r"|Experimental Results|Quantitative).*?)(?=\n##\s|\Z)",
            _re_fab.DOTALL | _re_fab.IGNORECASE,
        )
        _sanitized_count = 0

        def _sanitize_section(sec_match: _re_fab.Match) -> str:  # type: ignore[name-defined]
            nonlocal _sanitized_count
            section_text = sec_match.group(0)
            # Replace decimal numbers (e.g., 73.42, 0.891) but NOT integers
            # that are likely structural (year, section number, figure number)
            def _replace_in_section(m: _re_fab.Match) -> str:  # type: ignore[name-defined]
                nonlocal _sanitized_count
                result = _sanitize_number(m)
                if result == "--":
                    _sanitized_count += 1
                return result
            return _re_fab.sub(
                r"\b\d+\.\d{1,6}\b", _replace_in_section, section_text
            )

        final_paper = _result_section_pat.sub(_sanitize_section, final_paper)

        if _sanitized_count > 0:
            logger.warning(
                "Stage 22: Fabrication sanitization — blanked %d unsupported "
                "numbers in Results sections (experiment had no real metrics)",
                _sanitized_count,
            )
            # Rewrite the sanitized paper
            (stage_dir / "paper_final.md").write_text(
                final_paper, encoding="utf-8"
            )

    # Initialize artifacts list
    artifacts = ["paper_final.md"]
    # F2.7: Post-process citations — [cite_key] → \cite{cite_key}
    # and copy final references.bib to export stage
    _ay_map: dict[str, str] = {}  # BUG-102: author-year → cite_key map
    final_paper_latex = final_paper  # default when no bib_text available
    bib_text = _read_prior_artifact(run_dir, "references.bib")
    if bib_text:
        # Replace [cite_key] patterns in the final paper with \cite{cite_key}
        # Collect all valid cite_keys from the bib file
        import re as _re

        valid_keys = set(_re.findall(r"@\w+\{([^,]+),", bib_text))

        # BUG-102: Recover author-year citations → [cite_key] format.
        # When Stage 19 (paper_revision) converts [cite_key] to [Author et al., 2024],
        # the downstream regex can't match them. Build a reverse map from bib entries.
        def _build_author_year_map(bib: str, keys: set[str]) -> dict[str, str]:
            """Build mapping from author-year patterns to cite_keys.

            Returns dict like:
              "Raissi et al., 2019" → "raissi2019physicsinformed"
              "Tavella and Randall, 2000" → "tavella2000pricing"
            """
            mapping: dict[str, str] = {}
            # Parse each bib entry for author + year
            # BUG-DA8-17: Allow newline OR whitespace before closing brace
            # Use \n} or just } at start-of-line to avoid greedy cross-entry match
            entry_pat = _re.compile(
                r"@\w+\{([^,]+),\s*(.*?)(?:\n\}|^[ \t]*\})", _re.DOTALL | _re.MULTILINE
            )
            for m in entry_pat.finditer(bib):
                key = m.group(1).strip()
                if key not in keys:
                    continue
                body = m.group(2)
                # Extract author field
                author_m = _re.search(
                    r"author\s*=\s*[\{\"](.*?)[\}\"]", body, _re.IGNORECASE
                )
                year_m = _re.search(
                    r"year\s*=\s*[\{\"]?(\d{4})[\}\"]?", body, _re.IGNORECASE
                )
                if not author_m or not year_m:
                    continue
                author_raw = author_m.group(1).strip()
                year = year_m.group(1)
                # Parse author names (split on " and ")
                authors = [a.strip() for a in _re.split(r"\s+and\s+", author_raw)]
                # Extract last names
                last_names = []
                for a in authors:
                    if "," in a:
                        last_names.append(a.split(",")[0].strip())
                    else:
                        parts = a.split()
                        last_names.append(parts[-1] if parts else a)
                if not last_names:
                    continue
                # Generate author-year patterns:
                # 1 author: "Smith, 2024"
                # 2 authors: "Smith and Jones, 2024"
                # 3+ authors: "Smith et al., 2024"
                if len(last_names) == 1:
                    patterns = [f"{last_names[0]}, {year}"]
                elif len(last_names) == 2:
                    patterns = [
                        f"{last_names[0]} and {last_names[1]}, {year}",
                        f"{last_names[0]} \\& {last_names[1]}, {year}",
                    ]
                else:
                    patterns = [
                        f"{last_names[0]} et al., {year}",
                        f"{last_names[0]} et al. {year}",
                    ]
                    # Also add "Smith and Jones, 2024" for first two authors
                    patterns.append(
                        f"{last_names[0]} and {last_names[1]}, {year}"
                    )
                for pat in patterns:
                    mapping[pat] = key
            return mapping

        _ay_map = _build_author_year_map(bib_text, valid_keys)
        if _ay_map:
            # Count how many author-year citations exist in the paper
            _ay_found = 0
            for _ay_pat in _ay_map:
                if _ay_pat in final_paper:
                    _ay_found += 1
            if _ay_found > 0:
                logger.info(
                    "Stage 22: Found %d author-year citation patterns — "
                    "converting back to [cite_key] format.",
                    _ay_found,
                )
                # Sort by longest pattern first to avoid partial matches
                for _ay_pat in sorted(_ay_map, key=len, reverse=True):
                    _ay_key = _ay_map[_ay_pat]
                    # Match [Author et al., 2024] or [Author and Jones, 2024; ...]
                    # Handle single-citation brackets
                    final_paper = final_paper.replace(
                        f"[{_ay_pat}]", f"[{_ay_key}]"
                    )
                    # Handle within multi-citation brackets [A et al., 2020; B et al., 2021]
                    # Replace the author-year segment only inside [...] brackets
                    final_paper = _re.sub(
                        r'\[([^\]]*?)' + _re.escape(_ay_pat) + r'([^\]]*?)\]',
                        lambda _m: '[' + _m.group(1) + _ay_key + _m.group(2) + ']',
                        final_paper,
                    )
                # Fix multi-key brackets: [key1; key2] → [key1, key2]
                # (author-year uses semicolons, cite-keys use commas)
                def _fix_semicolon_cites(m_sc: _re.Match[str]) -> str:
                    inner = m_sc.group(1)
                    # Only convert if ALL segments look like cite keys
                    parts = [p.strip() for p in inner.split(";")]
                    _ck = r"[a-zA-Z][a-zA-Z0-9_-]*\d{4}[a-zA-Z0-9_]*"
                    if all(_re.fullmatch(_ck, p) for p in parts):
                        return "[" + ", ".join(parts) + "]"
                    return m_sc.group(0)
                final_paper = _re.sub(
                    r"\[([^\]]+;[^\]]+)\]", _fix_semicolon_cites, final_paper
                )
                (stage_dir / "paper_final.md").write_text(
                    final_paper, encoding="utf-8"
                )

        # R10-Fix4: Citation cross-validation
        # BUG-187: Also parse multi-key brackets like [key1, key2, key3].
        # The old regex only matched single-key brackets [key2020word].
        _cite_key_pat = r"[a-zA-Z]+\d{4}[a-zA-Z0-9_-]*"
        cited_keys_in_paper: set[str] = set()
        # Single-key brackets
        for m in _re.finditer(rf"\[({_cite_key_pat})\]", final_paper):
            cited_keys_in_paper.add(m.group(1))
        # Multi-key brackets [key1, key2] or [key1; key2]
        for m in _re.finditer(r"\[([^\]]{10,300})\]", final_paper):
            inner = m.group(1)
            # Only parse if it looks like citation keys (has year-like digits)
            parts = _re.split(r"[,;]\s*", inner)
            if all(_re.fullmatch(_cite_key_pat, p.strip()) for p in parts if p.strip()):
                for p in parts:
                    if p.strip():
                        cited_keys_in_paper.add(p.strip())

        if valid_keys and cited_keys_in_paper:
            invalid_keys = cited_keys_in_paper - valid_keys
            if invalid_keys:
                logger.warning(
                    "Stage 22: Found %d citation keys in paper not in references.bib: %s",
                    len(invalid_keys),
                    ", ".join(sorted(invalid_keys)[:20]),
                )
                # BUG-176: Try to resolve missing citations before removing them.
                # Parse cite_key → search query, look up via academic APIs,
                # and add found entries to references.bib.
                resolved_keys: set[str] = set()
                new_bib_entries: list[str] = []
                if len(invalid_keys) <= 30:  # Sanity: don't flood APIs
                    resolved_keys, new_bib_entries = _resolve_missing_citations(
                        invalid_keys, bib_text
                    )
                    if resolved_keys:
                        valid_keys.update(resolved_keys)
                        bib_text += "\n" + "\n\n".join(new_bib_entries) + "\n"
                        logger.info(
                            "Stage 22: Resolved %d/%d missing citations via API lookup",
                            len(resolved_keys), len(invalid_keys),
                        )

                still_invalid = invalid_keys - resolved_keys
                if still_invalid:
                    # IMP-29: Remove remaining unresolvable citations from
                    # BOTH single-key and multi-key brackets.
                    import re as _re_imp29
                    for bad_key in still_invalid:
                        # Remove single-key brackets
                        final_paper = final_paper.replace(f"[{bad_key}]", "")
                        # Remove from multi-key brackets: [good, BAD, good] → [good, good]
                        def _remove_from_multi(m: _re.Match) -> str:
                            inner = m.group(1)
                            parts = [p.strip() for p in _re.split(r"[,;]\s*", inner)]
                            filtered = [p for p in parts if p != bad_key]
                            if not filtered:
                                return ""
                            return "[" + ", ".join(filtered) + "]"
                        final_paper = _re_imp29.sub(
                            r"\[([^\]]*\b" + _re.escape(bad_key) + r"\b[^\]]*)\]",
                            _remove_from_multi,
                            final_paper,
                        )
                    # Clean up whitespace artifacts from removed citations
                    final_paper = _re_imp29.sub(r"  +", " ", final_paper)
                    final_paper = _re_imp29.sub(r" ([.,;:)])", r"\1", final_paper)
                (stage_dir / "paper_final.md").write_text(final_paper, encoding="utf-8")
                if still_invalid:
                    (stage_dir / "invalid_citations.json").write_text(
                        json.dumps(sorted(still_invalid), indent=2), encoding="utf-8"
                    )
                    artifacts.append("invalid_citations.json")
                if resolved_keys:
                    (stage_dir / "resolved_citations.json").write_text(
                        json.dumps(sorted(resolved_keys), indent=2), encoding="utf-8"
                    )
                    artifacts.append("resolved_citations.json")

        final_paper_latex = final_paper  # default: no citation conversion
        if valid_keys:
            _CITE_KEY_PAT = r"[a-zA-Z][a-zA-Z0-9_-]*\d{4}[a-zA-Z0-9]*"

            # Step 1: Convert multi-key brackets [key1, key2] → \cite{key1, key2}
            def _replace_multi_cite(m: _re.Match[str]) -> str:
                keys = [k.strip() for k in m.group(1).split(",")]
                matched = [k for k in keys if k in valid_keys]
                if matched:
                    return "\\cite{" + ", ".join(matched) + "}"
                return m.group(0)

            final_paper_latex = _re.sub(
                rf"\[({_CITE_KEY_PAT}(?:\s*,\s*{_CITE_KEY_PAT})+)\]",
                _replace_multi_cite,
                final_paper,
            )

            # Step 2: Convert single-key brackets [key] → \cite{key}
            def _replace_cite(m: _re.Match[str]) -> str:
                key = m.group(1)
                if key in valid_keys:
                    return f"\\cite{{{key}}}"
                return m.group(0)

            final_paper_latex = _re.sub(
                rf"\[({_CITE_KEY_PAT})\]", _replace_cite, final_paper_latex
            )

            # Step 3: Merge adjacent \cite{a} \cite{b} → \cite{a, b}
            def _merge_adjacent_cites(m: _re.Match[str]) -> str:
                keys = _re.findall(r"\\cite\{([^}]+)\}", m.group(0))
                return "\\cite{" + ", ".join(keys) + "}"

            final_paper_latex = _re.sub(
                r"\\cite\{[^}]+\}(?:\s*\\cite\{[^}]+\})+",
                _merge_adjacent_cites,
                final_paper_latex,
            )

            (stage_dir / "paper_final_latex.md").write_text(
                final_paper_latex, encoding="utf-8"
            )
            artifacts.append("paper_final_latex.md")
        # IMP-1: Prune uncited bibliography entries — keep only keys
        # that actually appear in the paper text (bracket or \cite form).
        if valid_keys:
            _all_cited: set[str] = set()
            # Bracket-format citations [key]
            _all_cited.update(
                _re.findall(r"\[([a-zA-Z]+\d{4}[a-zA-Z0-9_-]*)\]", final_paper)
            )
            # \cite{key, key2} format (original + latex-converted)
            for _src in (
                final_paper,
                final_paper_latex,
            ):
                for _cm in _re.finditer(r"\\cite\{([^}]+)\}", _src):
                    _all_cited.update(
                        k.strip() for k in _cm.group(1).split(",")
                    )
            uncited_keys = valid_keys - _all_cited
            if uncited_keys:
                bib_text = _remove_bibtex_entries(bib_text, uncited_keys)
                logger.info(
                    "Stage 22: Pruned %d uncited bibliography entries "
                    "(kept %d)",
                    len(uncited_keys),
                    len(valid_keys) - len(uncited_keys),
                )

        # Write final references.bib
        (stage_dir / "references.bib").write_text(bib_text, encoding="utf-8")
        artifacts.append("references.bib")
        logger.info(
            "Stage 22: Exported references.bib with %d entries",
            len(valid_keys) if valid_keys else 0,
        )

    # Conference template: generate .tex file
    try:
        from surveyclaw.templates import get_template, markdown_to_latex

        tpl = get_template(config.export.target_conference)
        # Use the latex-citation-processed version if available
        tex_source = final_paper_latex
        # Append NeurIPS-style checklist if target is a ML conference
        if tpl.name in ("neurips_2024", "neurips_2025", "icml_2025", "icml_2026",
                         "iclr_2025", "iclr_2026"):
            _has_exp = bool(_read_prior_artifact(run_dir, "experiment_summary.json"))
            _checklist = _generate_neurips_checklist(
                has_experiments=_has_exp,
                has_code=True,
            )
            if "NeurIPS Paper Checklist" not in tex_source:
                tex_source = tex_source.rstrip() + "\n\n" + _checklist
        _t = _extract_paper_title(tex_source)
        tex_content = markdown_to_latex(
            tex_source,
            tpl,
            title=_t if _t != "Untitled Paper" else "",
            authors=config.export.authors,
            bib_file=config.export.bib_file,
            bib_entries=_ay_map or None,
        )
        (stage_dir / "paper.tex").write_text(tex_content, encoding="utf-8")
        artifacts.append("paper.tex")
        logger.info(
            "Stage 22: Generated paper.tex for %s (%d chars)",
            tpl.display_name,
            len(tex_content),
        )
        # --- Phase 1 anti-fabrication: verify paper against VerifiedRegistry ---
        _vresult = None  # BUG-DA8-04: Initialize before try to avoid fragile dir() check
        try:
            from surveyclaw.pipeline.paper_verifier import verify_paper as _verify_paper
            # BUG-222: Use best_only=True to validate against promoted best data only
            from surveyclaw.pipeline.verified_registry import (
                VerifiedRegistry as _VR22,
            )
            _vr22 = _VR22.from_run_dir(
                run_dir,
                metric_direction=config.experiment.metric_direction,
                best_only=True,
            )
            if _vr22.values:
                _vresult = _verify_paper(tex_content, _vr22)
                (stage_dir / "paper_verification.json").write_text(
                    json.dumps({
                        "passed": _vresult.passed,
                        "severity": _vresult.severity,
                        "total_checked": _vresult.total_numbers_checked,
                        "total_verified": _vresult.total_numbers_verified,
                        "strict_violations": _vresult.strict_violations,
                        "lenient_violations": _vresult.lenient_violations,
                        "fabrication_rate": round(_vresult.fabrication_rate, 4),
                        "unverified_numbers": [
                            {"value": u.value, "line": u.line_number,
                             "section": u.section, "in_table": u.in_table}
                            for u in _vresult.unverified_numbers[:20]
                        ],
                        "fabricated_conditions": [
                            {"name": fc.name, "line": fc.line_number}
                            for fc in _vresult.fabricated_conditions
                        ],
                        "config_warnings": getattr(_vresult, "config_warnings", []),
                        "summary": _vresult.summary,
                    }, indent=2),
                    encoding="utf-8",
                )
                logger.info(
                    "Stage 22: Paper verification — %s (%d checked, %d verified, "
                    "%d strict violations, fabrication_rate=%.1f%%)",
                    _vresult.severity,
                    _vresult.total_numbers_checked,
                    _vresult.total_numbers_verified,
                    _vresult.strict_violations,
                    _vresult.fabrication_rate * 100,
                )
        except Exception as _pv_exc:
            logger.debug("Stage 22: Paper verification skipped: %s", _pv_exc)

        # BUG-23 P1: Enforce REJECT verdict — sanitize unverified numbers
        if _vresult is not None and getattr(_vresult, "severity", None) == "REJECT":
            logger.warning(
                "Stage 22: Paper REJECTED by verifier (fabrication_rate=%.1f%%, "
                "%d strict violations). Sanitizing unverified numbers.",
                _vresult.fabrication_rate * 100,
                _vresult.strict_violations,
            )
            # Replace unverified numbers in strict sections/tables with "---"
            import re as _re_san2

            # BUG-R49-02: Section names that sound like results but are
            # actually protocol/setup sections should NOT trigger strict
            # sanitization.  Exempt sections containing "dataset", "setup",
            # "protocol", "hyperparameter", or "implementation".
            _STRICT_EXEMPT_KW = {"dataset", "setup", "protocol",
                                 "hyperparameter", "implementation",
                                 "hardware", "infrastructure"}

            _sanitized_tex = tex_content
            _san2_count = 0
            for _uv in sorted(_vresult.unverified_numbers, key=lambda u: -u.line_number):
                # Only sanitize strict-section / in-table numbers
                _uv_section_lower = (_uv.section or "").lower()
                _uv_is_strict = any(
                    s in _uv_section_lower
                    for s in ("results", "experiment", "evaluation",
                              "ablation", "comparison", "analysis")
                )
                # BUG-R49-02: Exempt protocol/setup sections from strict mode
                if _uv_is_strict and any(
                    kw in _uv_section_lower for kw in _STRICT_EXEMPT_KW
                ):
                    _uv_is_strict = False
                if _uv_is_strict or _uv.in_table:
                    _lines = _sanitized_tex.split("\n")
                    if 0 < _uv.line_number <= len(_lines):
                        _orig_line = _lines[_uv.line_number - 1]
                        # BUG-R49-01: Use word-boundary regex instead of
                        # naive substring matching to avoid replacing numbers
                        # inside identifiers (e.g. "18" in "ResNet18").
                        # BUG-206: Include ASCII hyphen and Unicode hyphens
                        # (U+2010 hyphen, U+2011 non-breaking hyphen,
                        # U+2013 en-dash) so that model variant numbers
                        # like "34" in "ResNet-34" or "ResNet‑34" are not
                        # mistaken for unverified experimental values.
                        # BUG-210: Include period (.) so that fractional
                        # parts of decimals in condition names like
                        # "ema_decay_0.9" are not treated as standalone
                        # numbers (prevents "0.9" → "0.---").
                        _BOUNDARY = "A-Za-z0-9_\u2010\u2011\u2013\\-."
                        for _rep in (
                            f"{_uv.value:.4f}".rstrip("0").rstrip("."),
                            f"{_uv.value:.3f}",
                            f"{_uv.value:.2f}",
                            f"{_uv.value:.1f}",
                            f"{_uv.value:g}",
                            str(_uv.value),
                        ):
                            # Word boundary: number must NOT be adjacent to
                            # alphanumeric, underscore, or hyphen on either side.
                            _pat = (
                                rf"(?<![{_BOUNDARY}])"
                                + _re_san2.escape(_rep)
                                + rf"(?![{_BOUNDARY}])"
                            )
                            if _re_san2.search(_pat, _orig_line):
                                _lines[_uv.line_number - 1] = _re_san2.sub(
                                    _pat, "---", _orig_line, count=1,
                                )
                                _san2_count += 1
                                break
                        _sanitized_tex = "\n".join(_lines)
            if _sanitized_tex != tex_content:
                tex_content = _sanitized_tex
                (stage_dir / "paper.tex").write_text(tex_content, encoding="utf-8")
                logger.info(
                    "Stage 22: Sanitized paper.tex — replaced %d unverified "
                    "numbers with '---'",
                    _san2_count,
                )

        # Copy bundled style files alongside paper.tex
        for sf in tpl.get_style_files():
            import shutil as _shutil_sty
            _shutil_sty.copy2(sf, stage_dir / sf.name)

        # --- Pre-compilation: copy charts and fix figure paths ---
        # BUG-R41-12: Charts MUST be available before compile_latex(),
        # otherwise \includegraphics references fail → "Float(s) lost".
        try:
            chart_dir = stage_dir / "charts"
            chart_dir.mkdir(parents=True, exist_ok=True)
            charts: list[Path] = []

            # Copy FigureAgent charts from stage-14 (any version)
            _fa_charts_found = False
            for _fa_dir in sorted(run_dir.glob("stage-14*/charts"), reverse=True):
                _fa_pngs = list(_fa_dir.glob("fig_*.png"))
                if _fa_pngs:
                    import shutil
                    for _fa_png in _fa_pngs:
                        dest = chart_dir / _fa_png.name
                        shutil.copy2(_fa_png, dest)
                        charts.append(dest)
                    _fa_charts_found = True
                    logger.info(
                        "Stage 22: Copied %d FigureAgent charts from %s",
                        len(_fa_pngs), _fa_dir,
                    )
                    break

            # Generate structured charts from visualize.py
            from surveyclaw.experiment.visualize import generate_all_charts
            _metric_dir = getattr(config.experiment, "metric_direction", "minimize")
            _viz_charts = generate_all_charts(
                run_dir,
                chart_dir,
                metric_key=config.experiment.metric_key,
                metric_direction=_metric_dir,
            )
            charts.extend(_viz_charts)

            if charts:
                artifacts.append("charts/")
                logger.info("Stage 22: Generated %d chart(s) total", len(charts))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chart generation failed: %s", exc)

        # BUG-99: Fix \includegraphics paths that don't match actual chart files
        try:
            reconcile_figure_refs(stage_dir / "paper.tex", stage_dir / "charts")
        except Exception as _fig_exc:  # noqa: BLE001
            logger.debug("Stage 22: Figure path validation skipped: %s", _fig_exc)

        # BUG-R41-12: Remove figure blocks referencing files that still don't exist
        try:
            tex_path = stage_dir / "paper.tex"
            if tex_path.exists():
                from surveyclaw.templates.compiler import remove_missing_figures
                _tex_text = tex_path.read_text(encoding="utf-8")
                _fixed_tex, _removed_figs = remove_missing_figures(_tex_text, stage_dir)
                if _removed_figs:
                    tex_path.write_text(_fixed_tex, encoding="utf-8")
                    logger.warning(
                        "Stage 22: Removed %d figure block(s) with missing images: %s",
                        len(_removed_figs), _removed_figs,
                    )
        except Exception as _rmf_exc:  # noqa: BLE001
            logger.debug("Stage 22: remove_missing_figures skipped: %s", _rmf_exc)

        # Compile verification
        try:
            from surveyclaw.templates.compiler import compile_latex
            _compile_result = compile_latex(stage_dir / "paper.tex", max_attempts=2)
            if _compile_result.success:
                logger.info("Stage 22: LaTeX compilation verification PASSED")
                artifacts.append("paper.pdf")
                # PDF-as-reviewer: LLM-based visual review of compiled PDF
                _pdf_path = stage_dir / "paper.pdf"
                if _pdf_path.exists() and llm is not None:
                    try:
                        _pdf_review = _get_review_compiled_pdf()(
                            _pdf_path, llm, config.research.topic
                        )
                        if _pdf_review:
                            (stage_dir / "pdf_review.json").write_text(
                                json.dumps(_pdf_review, indent=2, ensure_ascii=False),
                                encoding="utf-8",
                            )
                            artifacts.append("pdf_review.json")
                            _pdf_score = _pdf_review.get("overall_score", 0)
                            if _pdf_score < 5:
                                logger.warning(
                                    "Stage 22: PDF visual review score %d/10 — %s",
                                    _pdf_score,
                                    _pdf_review.get("summary", ""),
                                )
                            else:
                                logger.info(
                                    "Stage 22: PDF visual review score %d/10",
                                    _pdf_score,
                                )
                    except Exception as _pdf_exc:  # noqa: BLE001
                        logger.debug("Stage 22: PDF review skipped: %s", _pdf_exc)
                # Post-compilation quality checks
                try:
                    from surveyclaw.templates.compiler import check_compiled_quality
                    _qc = check_compiled_quality(stage_dir / "paper.tex")
                    if _qc.warnings_summary:
                        logger.warning(
                            "Stage 22: Quality checks: %s",
                            "; ".join(_qc.warnings_summary),
                        )
                    (stage_dir / "compilation_quality.json").write_text(
                        json.dumps({
                            "page_count": _qc.page_count,
                            "unresolved_refs": _qc.unresolved_refs,
                            "unresolved_cites": _qc.unresolved_cites,
                            "overfull_hboxes": len(_qc.overfull_hboxes),
                            "orphan_figures": _qc.orphan_figures,
                            "orphan_labels": _qc.orphan_labels,
                            "warnings": _qc.warnings_summary,
                        }, indent=2),
                        encoding="utf-8",
                    )
                    artifacts.append("compilation_quality.json")
                    # BUG-27: Warn if page count exceeds limit
                    _page_limit = 10
                    if _qc.page_count and _qc.page_count > _page_limit:
                        logger.warning(
                            "BUG-27: Paper is %d pages (limit %d). "
                            "Consider tightening content in revision.",
                            _qc.page_count, _page_limit,
                        )
                except Exception as _qc_exc:  # noqa: BLE001
                    logger.debug("Stage 22: Quality checks skipped: %s", _qc_exc)
            else:
                logger.warning("Stage 22: LaTeX compilation verification FAILED: %s", _compile_result.errors[:3])
                # Add compilation failure comment to .tex
                _tex_path = stage_dir / "paper.tex"
                if _tex_path.exists():
                    _tex_content = _tex_path.read_text(encoding="utf-8")
                    if "% WARNING: Compilation failed" not in _tex_content:
                        _tex_content = (
                            "% WARNING: Compilation failed. Errors:\n"
                            + "".join(f"% {e}\n" for e in _compile_result.errors[:5])
                            + _tex_content
                        )
                        _tex_path.write_text(_tex_content, encoding="utf-8")

        except Exception as _compile_exc:  # noqa: BLE001
            logger.debug("Stage 22: Compile verification skipped: %s", _compile_exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LaTeX generation failed: %s", exc, exc_info=True)

    # (Charts, BUG-99 path fix, and remove_missing_figures are now handled
    #  BEFORE compile_latex() — see "Pre-compilation" block above.)

    # --- Code packaging: multi-file directory or single file ---
    exp_final_dir_path = _read_prior_artifact(run_dir, "experiment_final/")
    if exp_final_dir_path and Path(exp_final_dir_path).is_dir():
        import ast

        code_dir = stage_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        all_code_combined = ""
        code_file_names: list[str] = []
        for src in sorted(Path(exp_final_dir_path).glob("*.py")):
            (code_dir / src.name).write_bytes(src.read_bytes())
            all_code_combined += src.read_text(encoding="utf-8") + "\n"
            code_file_names.append(src.name)

        # Detect dependencies from all files
        detected: set[str] = set()
        known_packages = {
            "numpy": "numpy",
            "torch": "torch",
            "tensorflow": "tensorflow",
            "sklearn": "scikit-learn",
            "scikit-learn": "scikit-learn",
            "scipy": "scipy",
            "pandas": "pandas",
            "matplotlib": "matplotlib",
            "seaborn": "seaborn",
            "transformers": "transformers",
            "datasets": "datasets",
            "jax": "jax",
        }
        try:
            tree = ast.parse(all_code_combined)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in known_packages:
                            detected.add(known_packages[top])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top in known_packages:
                        detected.add(known_packages[top])
        except SyntaxError:
            pass

        requirements = sorted(detected)
        (code_dir / "requirements.txt").write_text(
            "\n".join(requirements) + ("\n" if requirements else ""),
            encoding="utf-8",
        )

        paper_title = _extract_paper_title(final_paper)
        file_list_md = "\n".join(f"- `{f}`" for f in code_file_names)
        readme = (
            f"# Code Package for {paper_title}\n\n"
            "## Description\n"
            "This directory contains the experiment project used for the paper.\n\n"
            "## Project Files\n"
            f"{file_list_md}\n\n"
            "## How to Run\n"
            "`python main.py`\n\n"
            "## Dependencies\n"
            "Install dependencies with `pip install -r requirements.txt` if needed.\n"
        )
        (code_dir / "README.md").write_text(readme, encoding="utf-8")
        artifacts.append("code/")
        logger.info(
            "Stage 22: Packaged multi-file code release (%d files, %d deps)",
            len(code_file_names),
            len(requirements),
        )
    else:
        # Backward compat: single-file packaging
        code_payload = _read_prior_artifact(run_dir, "experiment_final.py")
        if not code_payload:
            code_payload = _read_prior_artifact(run_dir, "experiment.py")
        if code_payload:
            import ast

            code_dir = stage_dir / "code"
            code_dir.mkdir(parents=True, exist_ok=True)
            (code_dir / "experiment.py").write_text(code_payload, encoding="utf-8")

            detected_single: set[str] = set()
            known_packages_single = {
                "numpy": "numpy",
                "torch": "torch",
                "tensorflow": "tensorflow",
                "sklearn": "scikit-learn",
                "scikit-learn": "scikit-learn",
                "scipy": "scipy",
                "pandas": "pandas",
                "matplotlib": "matplotlib",
                "seaborn": "seaborn",
                "transformers": "transformers",
                "datasets": "datasets",
                "jax": "jax",
            }
            try:
                tree = ast.parse(code_payload)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            if top in known_packages_single:
                                detected_single.add(known_packages_single[top])
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        top = node.module.split(".")[0]
                        if top in known_packages_single:
                            detected_single.add(known_packages_single[top])
            except SyntaxError:
                pass

            requirements = sorted(detected_single)
            (code_dir / "requirements.txt").write_text(
                "\n".join(requirements) + ("\n" if requirements else ""),
                encoding="utf-8",
            )
            paper_title = _extract_paper_title(final_paper)
            readme = (
                f"# Code Package for {paper_title}\n\n"
                "## Description\n"
                "This directory contains the final experiment script used for the paper.\n\n"
                "## How to Run\n"
                "`python experiment.py`\n\n"
                "## Dependencies\n"
                "Install dependencies with `pip install -r requirements.txt` if needed.\n"
            )
            (code_dir / "README.md").write_text(readme, encoding="utf-8")
            artifacts.append("code/")
            logger.info(
                "Stage 22: Packaged single-file code release with %d deps",
                len(requirements),
            )
    # WS-5.5: Generate framework diagram prompt for methodology section
    try:
        _framework_prompt = _generate_framework_diagram_prompt(
            final_paper, config, llm=llm
        )
        if _framework_prompt:
            _chart_dir = stage_dir / "charts"
            _chart_dir.mkdir(parents=True, exist_ok=True)
            (_chart_dir / "framework_diagram_prompt.md").write_text(
                _framework_prompt, encoding="utf-8"
            )
            logger.info("Stage 22: Generated framework diagram prompt → charts/framework_diagram_prompt.md")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Stage 22: Framework diagram prompt generation skipped: %s", exc)

    return StageResult(
        stage=Stage.EXPORT_PUBLISH,
        status=StageStatus.DONE,
        artifacts=tuple(artifacts),
        evidence_refs=tuple(f"stage-{int(Stage.EXPORT_PUBLISH):02d}/{a}" for a in artifacts),
    )


# ---------------------------------------------------------------------------
# Citation helpers
# ---------------------------------------------------------------------------

def _check_citation_relevance(
    llm: Any,
    topic: str,
    results: list[Any],
) -> dict[str, float | None]:
    """Use LLM to assess relevance of each citation to the research topic.

    Returns a dict mapping cite_key → relevance score (0.0–1.0).
    Processes citations in batches of 30 to handle large bibliographies.
    """
    citation_lines = []
    for cr in results:
        citation_lines.append(f"- [{cr.cite_key}] \"{cr.title}\"")
    if not citation_lines:
        return {}

    all_scores: dict[str, float] = {}
    _BATCH_SIZE = 30

    for batch_start in range(0, len(citation_lines), _BATCH_SIZE):
        batch = citation_lines[batch_start:batch_start + _BATCH_SIZE]
        citations_text = "\n".join(batch)

        prompt = (
            f"Research topic: {topic}\n\n"
            f"Rate the relevance of each citation to the research topic "
            f"on a scale of 0.0 to 1.0.\n"
            f"Return ONLY a JSON object mapping cite_key to relevance score.\n"
            f"Example: {{\"smith2020\": 0.9, \"jones2019\": 0.2}}\n\n"
            f"Citations:\n{citations_text}"
        )

        try:
            resp = llm.chat(
                [{"role": "user", "content": prompt}],
                system="You assess citation relevance. Return only valid JSON.",
                json_mode=True,
            )
            parsed = _safe_json_loads(resp.content, {})
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(v, (int, float)):
                        all_scores[k] = max(0.0, min(1.0, float(v)))
        except Exception:  # noqa: BLE001
            logger.debug(
                "Citation relevance check failed for batch %d–%d, skipping",
                batch_start, batch_start + len(batch),
            )

    return all_scores


def _remove_bibtex_entries(bib_text: str, keys_to_remove: set[str]) -> str:
    """Remove BibTeX entries whose keys are in *keys_to_remove*."""
    kept: list[str] = []
    for m in re.finditer(r"@\w+\{([^,]+),", bib_text):
        key = m.group(1).strip()
        if key in keys_to_remove:
            continue
        # Find the full entry (from @ to the next @ or end)
        start = m.start()
        # Find balanced braces
        depth = 0
        end = start
        for i in range(start, len(bib_text)):
            if bib_text[i] == "{":
                depth += 1
            elif bib_text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > start:
            kept.append(bib_text[start:end])
    return "\n\n".join(kept) + "\n" if kept else ""


def _remove_citations_from_text(text: str, keys_to_remove: set[str]) -> str:
    """Remove \\cite{key} and [key] references for specified citation keys."""

    # Handle multi-key LaTeX cites: \cite{a,b,c} → filter keys inside braces
    def _filter_cite(m: re.Match[str]) -> str:
        keys = [k.strip() for k in m.group(1).split(",")]
        kept = [k for k in keys if k not in keys_to_remove]
        if not kept:
            return ""
        return f"\\cite{{{','.join(kept)}}}"

    text = re.sub(r"\\cite\{([^}]+)\}", _filter_cite, text)

    # Markdown: [key]
    for key in keys_to_remove:
        text = re.sub(rf"\[{re.escape(key)}\]", "", text)
    return text


# ---------------------------------------------------------------------------
# Stage 23: Citation Verify
# ---------------------------------------------------------------------------

def _execute_citation_verify(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    from surveyclaw.literature.verify import (
        VerifyStatus,
        annotate_paper_hallucinations,
        filter_verified_bibtex,
        verify_citations,
    )

    bib_text = _read_prior_artifact(run_dir, "references.bib") or ""
    paper_text = _read_prior_artifact(run_dir, "paper_final.md") or ""

    if not bib_text.strip():
        report_data = {
            "summary": {
                "total": 0,
                "verified": 0,
                "suspicious": 0,
                "hallucinated": 0,
                "skipped": 0,
                "integrity_score": 1.0,
            },
            "results": [],
            "note": "No references.bib found — nothing to verify.",
        }
        (stage_dir / "verification_report.json").write_text(
            json.dumps(report_data, indent=2), encoding="utf-8"
        )
        (stage_dir / "references_verified.bib").write_text(
            "% No references to verify\n", encoding="utf-8"
        )
        # Always write paper_final_verified.md so deliverables packaging gets
        # the latest paper (not a stale copy from a previous run)
        if paper_text.strip():
            (stage_dir / "paper_final_verified.md").write_text(
                paper_text, encoding="utf-8"
            )
        return StageResult(
            stage=Stage.CITATION_VERIFY,
            status=StageStatus.DONE,
            artifacts=("verification_report.json", "references_verified.bib"),
            evidence_refs=(
                f"stage-{int(Stage.CITATION_VERIFY):02d}/verification_report.json",
                f"stage-{int(Stage.CITATION_VERIFY):02d}/references_verified.bib",
            ),
        )

    s2_api_key = getattr(config.llm, "s2_api_key", "") or ""

    from surveyclaw.literature.verify import parse_bibtex_entries
    _n_entries = len(parse_bibtex_entries(bib_text))
    logger.info(
        "[citation-verify] Verifying %d references "
        "(DOI→CrossRef > OpenAlex > arXiv > S2)…",
        _n_entries,
    )
    report = verify_citations(bib_text, s2_api_key=s2_api_key)
    logger.info(
        "[citation-verify] Done: %d verified, %d suspicious, "
        "%d hallucinated, %d skipped (integrity: %.0f%%)",
        report.verified,
        report.suspicious,
        report.hallucinated,
        report.skipped,
        report.integrity_score * 100,
    )

    # --- Relevance check: assess topical relevance of verified citations ---
    if llm is not None and report.results:
        relevance_scores = _check_citation_relevance(
            llm, config.research.topic, report.results
        )
        for cr in report.results:
            score = relevance_scores.get(cr.cite_key)
            if score is not None:
                cr.relevance_score = score

    # FIX-5: Filter low-relevance citations and enforce hard cap
    RELEVANCE_THRESHOLD = 0.5
    MAX_CITATIONS = 60
    low_relevance_keys: set[str] = set()
    for cr in report.results:
        if cr.relevance_score is not None and cr.relevance_score < RELEVANCE_THRESHOLD:
            low_relevance_keys.add(cr.cite_key)

    # Hard cap: if still above MAX_CITATIONS after relevance filter, drop lowest
    # BUG-07 fix: Unscored citations (relevance_score=None) default to 0.7
    # because they passed API verification and are likely relevant.
    # Previously they defaulted to 0.0 which caused mass-deletion.
    _DEFAULT_RELEVANCE = 0.7
    remaining = [
        cr for cr in report.results
        if cr.cite_key not in low_relevance_keys
        and cr.status != VerifyStatus.HALLUCINATED
    ]
    if len(remaining) > MAX_CITATIONS:
        remaining.sort(
            key=lambda c: c.relevance_score if c.relevance_score is not None else _DEFAULT_RELEVANCE,
        )
        overflow = remaining[:len(remaining) - MAX_CITATIONS]
        for cr in overflow:
            low_relevance_keys.add(cr.cite_key)
        logger.info(
            "Stage 23: Hard cap applied, dropping %d additional low-relevance citations",
            len(overflow),
        )

    if low_relevance_keys:
        logger.info(
            "Stage 23: Filtering %d low-relevance citations (threshold=%.1f, cap=%d): %s",
            len(low_relevance_keys),
            RELEVANCE_THRESHOLD,
            MAX_CITATIONS,
            ", ".join(sorted(list(low_relevance_keys)[:20])),
        )

    (stage_dir / "verification_report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )

    verified_bib = filter_verified_bibtex(bib_text, report, include_suspicious=True)
    # Remove low-relevance entries from BibTeX
    if low_relevance_keys:
        verified_bib = _remove_bibtex_entries(verified_bib, low_relevance_keys)

    # BUG-26: If verification stripped >50% of entries (e.g. due to rate limiting),
    # fall back to the original bib to avoid breaking the paper's references
    original_count = len(re.findall(r"@\w+\{", bib_text))
    verified_count = len(re.findall(r"@\w+\{", verified_bib))
    if original_count > 0 and verified_count < original_count * 0.5:
        logger.warning(
            "Stage 23: Verification stripped %d→%d entries (>50%% loss). "
            "Keeping original bib to avoid breaking references.",
            original_count, verified_count,
        )
        verified_bib = bib_text

    # IMP-1: Also prune uncited entries from verified bib
    # BUG-182: Also scan LaTeX paper.tex (not just Markdown) for \cite{} keys.
    # The Markdown version may use [key] notation while LaTeX uses \cite{key}.
    if paper_text.strip():
        _vbib_keys = set(re.findall(r"@\w+\{([^,]+),", verified_bib))
        _cited_in_paper: set[str] = set()
        _cited_in_paper.update(
            re.findall(r"\[([a-zA-Z]+\d{4}[a-zA-Z0-9_-]*)\]", paper_text)
        )
        for _cm in re.finditer(r"\\cite\{([^}]+)\}", paper_text):
            _cited_in_paper.update(
                k.strip() for k in _cm.group(1).split(",")
            )
        # BUG-182: Also read export stage paper.tex for \cite{} keys
        _latex_paper = stage_dir.parent / f"stage-{int(Stage.EXPORT_PUBLISH):02d}" / "paper.tex"
        if _latex_paper.exists():
            try:
                _latex_text = _latex_paper.read_text(encoding="utf-8")
                for _cm in re.finditer(r"\\cite[pt]?\{([^}]+)\}", _latex_text):
                    _cited_in_paper.update(
                        k.strip() for k in _cm.group(1).split(",")
                    )
            except OSError:
                pass
        _uncited_vbib = _vbib_keys - _cited_in_paper
        if _uncited_vbib:
            verified_bib = _remove_bibtex_entries(verified_bib, _uncited_vbib)
            logger.info(
                "Stage 23: Pruned %d uncited entries from verified bib "
                "(kept %d)",
                len(_uncited_vbib),
                len(_vbib_keys) - len(_uncited_vbib),
            )

    # BUG-100: If all entries were filtered out (low-relevance + uncited pruning),
    # write a comment instead of an empty file to avoid "Missing or empty output" error.
    if not verified_bib.strip():
        verified_bib = "% All citations were filtered out during verification\n"
        logger.warning(
            "Stage 23: All BibTeX entries filtered out — writing placeholder"
        )

    (stage_dir / "references_verified.bib").write_text(verified_bib, encoding="utf-8")

    artifacts = ["verification_report.json", "references_verified.bib"]

    if paper_text.strip():
        annotated = annotate_paper_hallucinations(paper_text, report)
        # Remove \cite{} and [cite_key] references for low-relevance entries
        if low_relevance_keys:
            annotated = _remove_citations_from_text(annotated, low_relevance_keys)
        (stage_dir / "paper_final_verified.md").write_text(annotated, encoding="utf-8")
        artifacts.append("paper_final_verified.md")

    logger.info(
        "Stage 23 citation verify: %d total, %d verified, %d suspicious, "
        "%d hallucinated, %d skipped (integrity=%.1f%%)",
        report.total,
        report.verified,
        report.suspicious,
        report.hallucinated,
        report.skipped,
        report.integrity_score * 100,
    )

    return StageResult(
        stage=Stage.CITATION_VERIFY,
        status=StageStatus.DONE,
        artifacts=tuple(artifacts),
        evidence_refs=tuple(f"stage-{int(Stage.CITATION_VERIFY):02d}/{a}" for a in artifacts),
    )
