"""Stages 7-8: Synthesis and taxonomy building."""

from __future__ import annotations

import logging
from pathlib import Path

from surveyclaw.adapters import AdapterBundle
from surveyclaw.config import RCConfig
from surveyclaw.llm.client import LLMClient
from surveyclaw.pipeline._helpers import (
    StageResult,
    _default_taxonomy,
    _get_evolution_overlay,
    _read_prior_artifact,
    _utcnow_iso,
)
from surveyclaw.pipeline.stages import Stage, StageStatus
from surveyclaw.prompts import PromptManager

logger = logging.getLogger(__name__)


def _execute_synthesis(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    cards_path = _read_prior_artifact(run_dir, "cards/") or ""
    cards_context = ""

    # Include Stage 6 cross-paper synthesis note if available (enriches cards context)
    stage6_synthesis = _read_prior_artifact(run_dir, "synthesis.md") or ""
    if stage6_synthesis:
        cards_context += f"## Pre-computed Cross-Paper Synthesis\n\n{stage6_synthesis}\n\n---\n\n"

    if cards_path:
        snippets: list[str] = []
        for path in sorted(Path(cards_path).glob("*.md"))[:24]:
            snippets.append(path.read_text(encoding="utf-8"))
        cards_context += "\n\n".join(snippets)
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "synthesis")
        sp = _pm.for_stage(
            "synthesis",
            evolution_overlay=_overlay,
            topic=config.research.topic,
            cards_context=cards_context,
        )
        resp = llm.chat(
            [{"role": "user", "content": sp.user}],
            system=sp.system,
            max_tokens=sp.max_tokens or 128_000,
        )
        synthesis_md = resp.content
    else:
        synthesis_md = f"""# Synthesis

## Cluster Overview
- Cluster A: Representation methods
- Cluster B: Training strategies
- Cluster C: Evaluation robustness

## Gap 1
Limited consistency across benchmark protocols.

## Gap 2
Under-reported failure behavior under distribution shift.

## Prioritized Opportunities
1. Unified experimental protocol
2. Robustness-aware evaluation suite

## Generated
{_utcnow_iso()}
"""
    (stage_dir / "synthesis.md").write_text(synthesis_md, encoding="utf-8")
    return StageResult(
        stage=Stage.SYNTHESIS,
        status=StageStatus.DONE,
        artifacts=("synthesis.md",),
        evidence_refs=("stage-07/synthesis.md",),
    )


def _execute_taxonomy_build(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    synthesis = _read_prior_artifact(run_dir, "synthesis.md") or ""
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "taxonomy_build")
        sp = _pm.for_stage(
            "taxonomy_build",
            evolution_overlay=_overlay,
            topic=config.research.topic,
            synthesis=synthesis,
        )
        resp = llm.chat(
            [{"role": "user", "content": sp.user}],
            system=sp.system,
            max_tokens=sp.max_tokens or 128_000,
        )
        taxonomy_md = resp.content
    else:
        taxonomy_md = _default_taxonomy(config.research.topic)

    # --- HITL: Read human guidance if available ---
    guidance_file = stage_dir / "hitl_guidance.md"
    if guidance_file.exists():
        try:
            guidance = guidance_file.read_text(encoding="utf-8").strip()
            if guidance and llm is not None:
                logger.info("Applying HITL guidance to taxonomy")
                resp = llm.chat(
                    [{"role": "user", "content": (
                        f"Refine the following taxonomy based on this human guidance.\n\n"
                        f"## Current Taxonomy\n{taxonomy_md}\n\n"
                        f"## Human Guidance\n{guidance}\n\n"
                        f"Produce an improved taxonomy that incorporates the guidance."
                    )}],
                    max_tokens=128_000,
                )
                taxonomy_md = resp.content
        except Exception:
            logger.debug("HITL guidance application failed (non-blocking)")

    (stage_dir / "taxonomy.md").write_text(taxonomy_md, encoding="utf-8")

    return StageResult(
        stage=Stage.TAXONOMY_BUILD,
        status=StageStatus.DONE,
        artifacts=("taxonomy.md",),
        evidence_refs=("stage-08/taxonomy.md",),
    )
