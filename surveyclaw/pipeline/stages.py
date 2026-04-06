"""16-stage AutoSurveyClaw pipeline state machine.

Defines the stage sequence, status transitions, gate logic, and rollback rules.
Fully survey-oriented: no experiment/code-gen stages.

Stage flow:
  A (Scoping):      TOPIC_INIT → PROBLEM_DECOMPOSE
  B (Literature):   SEARCH_STRATEGY → LITERATURE_COLLECT → LITERATURE_SCREEN → KNOWLEDGE_EXTRACT
  C (Synthesis):    SYNTHESIS → TAXONOMY_BUILD
  D (Writing):      PAPER_OUTLINE → PAPER_DRAFT → PEER_REVIEW → PAPER_REVISION
  E (Finalization): QUALITY_GATE → KNOWLEDGE_ARCHIVE → EXPORT_PUBLISH → CITATION_VERIFY
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Iterable


class Stage(IntEnum):
    """16-stage survey pipeline."""

    # Phase A: Survey Scoping
    TOPIC_INIT = 1
    PROBLEM_DECOMPOSE = 2

    # Phase B: Literature Discovery
    SEARCH_STRATEGY = 3
    LITERATURE_COLLECT = 4
    LITERATURE_SCREEN = 5  # GATE
    KNOWLEDGE_EXTRACT = 6

    # Phase C: Survey Synthesis
    SYNTHESIS = 7
    TAXONOMY_BUILD = 8

    # Phase D: Paper Writing
    PAPER_OUTLINE = 9
    PAPER_DRAFT = 10
    PEER_REVIEW = 11
    PAPER_REVISION = 12

    # Phase E: Finalization
    QUALITY_GATE = 13  # GATE
    KNOWLEDGE_ARCHIVE = 14
    EXPORT_PUBLISH = 15
    CITATION_VERIFY = 16


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED_APPROVAL = "blocked_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"
    RETRYING = "retrying"
    FAILED = "failed"
    DONE = "done"


class TransitionEvent(str, Enum):
    START = "start"
    SUCCEED = "succeed"
    APPROVE = "approve"
    REJECT = "reject"
    TIMEOUT = "timeout"
    FAIL = "fail"
    RETRY = "retry"
    RESUME = "resume"
    PAUSE = "pause"


# ---------------------------------------------------------------------------
# Stage navigation
# ---------------------------------------------------------------------------

STAGE_SEQUENCE: tuple[Stage, ...] = tuple(Stage)

NEXT_STAGE: dict[Stage, Stage | None] = {
    stage: STAGE_SEQUENCE[idx + 1] if idx + 1 < len(STAGE_SEQUENCE) else None
    for idx, stage in enumerate(STAGE_SEQUENCE)
}

PREVIOUS_STAGE: dict[Stage, Stage | None] = {
    stage: STAGE_SEQUENCE[idx - 1] if idx > 0 else None
    for idx, stage in enumerate(STAGE_SEQUENCE)
}

# ---------------------------------------------------------------------------
# Gate stages — require approval before proceeding
# ---------------------------------------------------------------------------

GATE_STAGES: frozenset[Stage] = frozenset(
    {
        Stage.LITERATURE_SCREEN,
        Stage.QUALITY_GATE,
    }
)

# Gate rollback targets: when a gate rejects, where to roll back
GATE_ROLLBACK: dict[Stage, Stage] = {
    Stage.LITERATURE_SCREEN: Stage.LITERATURE_COLLECT,  # reject → re-collect
    Stage.QUALITY_GATE: Stage.PAPER_OUTLINE,  # reject → rewrite paper
}

# ---------------------------------------------------------------------------
# Noncritical stages — can be skipped on failure without aborting pipeline
# ---------------------------------------------------------------------------

NONCRITICAL_STAGES: frozenset[Stage] = frozenset(
    {
        Stage.QUALITY_GATE,       # 13: low quality should warn, not block deliverables
        Stage.KNOWLEDGE_ARCHIVE,  # 14: archival doesn't affect paper output
        # Hallucinated citations MUST block export
    }
)

# ---------------------------------------------------------------------------
# Phase groupings (for UI and reporting)
# ---------------------------------------------------------------------------

PHASE_MAP: dict[str, tuple[Stage, ...]] = {
    "A: Research Scoping": (Stage.TOPIC_INIT, Stage.PROBLEM_DECOMPOSE),
    "B: Literature Discovery": (
        Stage.SEARCH_STRATEGY,
        Stage.LITERATURE_COLLECT,
        Stage.LITERATURE_SCREEN,
        Stage.KNOWLEDGE_EXTRACT,
    ),
    "C: Survey Synthesis": (Stage.SYNTHESIS, Stage.TAXONOMY_BUILD),
    "D: Paper Writing": (
        Stage.PAPER_OUTLINE,
        Stage.PAPER_DRAFT,
        Stage.PEER_REVIEW,
        Stage.PAPER_REVISION,
    ),
    "E: Finalization": (
        Stage.QUALITY_GATE,
        Stage.KNOWLEDGE_ARCHIVE,
        Stage.EXPORT_PUBLISH,
        Stage.CITATION_VERIFY,
    ),
}


# ---------------------------------------------------------------------------
# Transition logic
# ---------------------------------------------------------------------------

TRANSITION_MAP: dict[StageStatus, frozenset[StageStatus]] = {
    StageStatus.PENDING: frozenset({StageStatus.RUNNING}),
    StageStatus.RUNNING: frozenset(
        {StageStatus.DONE, StageStatus.BLOCKED_APPROVAL, StageStatus.FAILED}
    ),
    StageStatus.BLOCKED_APPROVAL: frozenset(
        {StageStatus.APPROVED, StageStatus.REJECTED, StageStatus.PAUSED}
    ),
    StageStatus.APPROVED: frozenset({StageStatus.DONE}),
    StageStatus.REJECTED: frozenset({StageStatus.PENDING}),
    StageStatus.PAUSED: frozenset({StageStatus.RUNNING}),
    StageStatus.RETRYING: frozenset({StageStatus.RUNNING}),
    StageStatus.FAILED: frozenset({StageStatus.RETRYING, StageStatus.PAUSED}),
    StageStatus.DONE: frozenset(),
}


@dataclass(frozen=True)
class TransitionOutcome:
    stage: Stage
    status: StageStatus
    next_stage: Stage | None
    rollback_stage: Stage | None = None
    checkpoint_required: bool = False
    decision: str = "proceed"


def gate_required(
    stage: Stage,
    hitl_required_stages: Iterable[int] | None = None,
) -> bool:
    """Check whether a stage requires human-in-the-loop approval."""
    if stage not in GATE_STAGES:
        return False
    if hitl_required_stages is not None:
        return int(stage) in frozenset(hitl_required_stages)
    return True  # Default: all gate stages require approval


def default_rollback_stage(stage: Stage) -> Stage:
    """Return the configured rollback target, or the previous stage."""
    return GATE_ROLLBACK.get(stage) or PREVIOUS_STAGE.get(stage) or stage


def advance(
    stage: Stage,
    status: StageStatus,
    event: TransitionEvent | str,
    *,
    hitl_required_stages: Iterable[int] | None = None,
    rollback_stage: Stage | None = None,
) -> TransitionOutcome:
    """Compute the next state given current stage, status, and event.

    Raises ValueError on unsupported transitions.
    """
    event = TransitionEvent(event)
    target_rollback = rollback_stage or default_rollback_stage(stage)

    # START → RUNNING
    if event is TransitionEvent.START and status in {
        StageStatus.PENDING,
        StageStatus.RETRYING,
        StageStatus.PAUSED,
    }:
        return TransitionOutcome(
            stage=stage, status=StageStatus.RUNNING, next_stage=stage
        )

    # SUCCEED while RUNNING
    if event is TransitionEvent.SUCCEED and status is StageStatus.RUNNING:
        if gate_required(stage, hitl_required_stages):
            return TransitionOutcome(
                stage=stage,
                status=StageStatus.BLOCKED_APPROVAL,
                next_stage=stage,
                checkpoint_required=False,
                decision="block",
            )
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.DONE,
            next_stage=NEXT_STAGE[stage],
            checkpoint_required=True,
        )

    # APPROVE while BLOCKED
    if event is TransitionEvent.APPROVE and status is StageStatus.BLOCKED_APPROVAL:
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.DONE,
            next_stage=NEXT_STAGE[stage],
            checkpoint_required=True,
        )

    # REJECT while BLOCKED → rollback
    if event is TransitionEvent.REJECT and status is StageStatus.BLOCKED_APPROVAL:
        return TransitionOutcome(
            stage=target_rollback,
            status=StageStatus.PENDING,
            next_stage=target_rollback,
            rollback_stage=target_rollback,
            checkpoint_required=True,
            decision="pivot",
        )

    # TIMEOUT while BLOCKED → pause
    if event is TransitionEvent.TIMEOUT and status is StageStatus.BLOCKED_APPROVAL:
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.PAUSED,
            next_stage=stage,
            checkpoint_required=True,
            decision="block",
        )

    # FAIL while RUNNING
    if event is TransitionEvent.FAIL and status is StageStatus.RUNNING:
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.FAILED,
            next_stage=stage,
            checkpoint_required=True,
            decision="retry",
        )

    # RETRY while FAILED
    if event is TransitionEvent.RETRY and status is StageStatus.FAILED:
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.RETRYING,
            next_stage=stage,
            decision="retry",
        )

    # RESUME while PAUSED
    if event is TransitionEvent.RESUME and status is StageStatus.PAUSED:
        return TransitionOutcome(
            stage=stage, status=StageStatus.RUNNING, next_stage=stage
        )

    # PAUSE while FAILED
    if event is TransitionEvent.PAUSE and status is StageStatus.FAILED:
        return TransitionOutcome(
            stage=stage,
            status=StageStatus.PAUSED,
            next_stage=stage,
            checkpoint_required=True,
            decision="block",
        )

    raise ValueError(
        f"Unsupported transition: {status.value} + {event.value} for stage {int(stage)}"
    )
