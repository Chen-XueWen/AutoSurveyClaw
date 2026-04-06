"""Stages 1-2: Topic initialization and problem decomposition."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from surveyclaw.adapters import AdapterBundle
from surveyclaw.config import RCConfig
from surveyclaw.llm.client import LLMClient
from surveyclaw.pipeline._domain import _detect_domain
from surveyclaw.pipeline._helpers import (
    StageResult,
    _get_evolution_overlay,
    _read_prior_artifact,
    _safe_json_loads,
    _utcnow_iso,
)
from surveyclaw.pipeline.stages import Stage, StageStatus
from surveyclaw.prompts import PromptManager

logger = logging.getLogger(__name__)


def _execute_topic_init(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    topic = config.research.topic
    domains = (
        ", ".join(config.research.domains) if config.research.domains else "general"
    )
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "topic_init")
        sp = _pm.for_stage(
            "topic_init",
            evolution_overlay=_overlay,
            topic=topic,
            domains=domains,
            project_name=config.project.name,
            quality_threshold=config.research.quality_threshold,
        )
        resp = llm.chat(
            [{"role": "user", "content": sp.user}],
            system=sp.system,
        )
        goal_md = resp.content
    else:
        goal_md = f"""# Survey Goal

## Topic
{topic}

## Scope
Conduct a comprehensive literature survey of {topic}, covering foundational methods,
recent advances, taxonomic organization, and open challenges.

## SMART Goal
- Specific: Produce a comprehensive survey paper on {topic}
- Measurable: Literature shortlist with ≥15 papers, structured taxonomy, and full draft
- Achievable: Complete through staged pipeline with gate checks
- Relevant: Aligned with project {config.project.name}
- Time-bound: Constrained by pipeline execution budget

## Constraints
- Quality threshold: {config.research.quality_threshold}
- Daily paper target: {config.research.daily_paper_count}

## Inclusion Criteria
- Peer-reviewed papers directly relevant to {topic}
- Papers from the last 10 years prioritized; seminal older works included

## Success Criteria
- Comprehensive literature coverage with taxonomy
- Comparative analysis across reviewed methods
- Identified open challenges and future directions
- Publication-ready survey paper

## Generated
{_utcnow_iso()}
"""
    (stage_dir / "goal.md").write_text(goal_md, encoding="utf-8")

    return StageResult(
        stage=Stage.TOPIC_INIT,
        status=StageStatus.DONE,
        artifacts=("goal.md",),
        evidence_refs=("stage-01/goal.md",),
    )


def _execute_problem_decompose(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    goal_text = _read_prior_artifact(run_dir, "goal.md") or ""
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "problem_decompose")
        sp = _pm.for_stage(
            "problem_decompose",
            evolution_overlay=_overlay,
            topic=config.research.topic,
            goal_text=goal_text,
        )
        resp = llm.chat(
            [{"role": "user", "content": sp.user}],
            system=sp.system,
        )
        body = resp.content
    else:
        body = f"""# Survey Decomposition

## Source
Derived from `goal.md` for topic: {config.research.topic}

## Key Survey Questions
1. What are the main categories and sub-fields within {config.research.topic}?
2. What are the foundational and seminal works that define the field?
3. What evaluation benchmarks and metrics are commonly used?
4. What are the current state-of-the-art methods and their relative strengths?
5. What open challenges and research gaps remain unresolved?

## Search Themes
1. Foundational methods and theoretical frameworks
2. Recent advances and state-of-the-art techniques
3. Benchmark datasets and evaluation protocols
4. Application domains and practical deployments
5. Limitations, failure cases, and open problems

## Risks
- Incomplete coverage of niche sub-fields
- Rapidly evolving field with very recent work

## Generated
{_utcnow_iso()}
"""
    (stage_dir / "problem_tree.md").write_text(body, encoding="utf-8")

    # IMP-35: Topic/title quality pre-evaluation
    # Quick LLM check: is the topic well-scoped for a survey paper?
    if llm is not None:
        try:
            _eval_resp = llm.chat(
                [
                    {
                        "role": "user",
                        "content": (
                            "Evaluate this survey topic for a comprehensive academic survey paper. "
                            "Score 1-10 on: (a) scope_clarity, (b) literature_richness, (c) relevance. "
                            "If overall score < 5, suggest a refined topic.\n\n"
                            f"Topic: {config.research.topic}\n\n"
                            "Reply as JSON: {\"scope_clarity\": N, \"literature_richness\": N, "
                            "\"relevance\": N, \"overall\": N, \"suggestion\": \"...\"}"
                        ),
                    }
                ],
                system=(
                    f"You are a senior {_detect_domain(config.research.topic, config.research.domains)[1]} "
                    f"researcher evaluating survey topic quality."
                ),
            )
            _eval_data = _safe_json_loads(_eval_resp.content, {})
            if isinstance(_eval_data, dict):
                overall = _eval_data.get("overall", 10)
                if isinstance(overall, (int, float)) and overall < 5:
                    logger.warning(
                        "IMP-35: Survey topic score %s/10 — consider refining: %s",
                        overall,
                        _eval_data.get("suggestion", ""),
                    )
                else:
                    logger.info("IMP-35: Survey topic score %s/10", overall)
                (stage_dir / "topic_evaluation.json").write_text(
                    json.dumps(_eval_data, indent=2), encoding="utf-8"
                )
        except Exception:  # noqa: BLE001
            logger.debug("IMP-35: Topic evaluation skipped (non-blocking)")

    return StageResult(
        stage=Stage.PROBLEM_DECOMPOSE,
        status=StageStatus.DONE,
        artifacts=("problem_tree.md",),
        evidence_refs=("stage-02/problem_tree.md",),
    )
