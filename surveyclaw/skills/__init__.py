"""Dynamic skills library for AutoSurveyClaw.

Provides a registry of reusable research/engineering/writing skills
that can be automatically matched to pipeline stages and injected
into LLM prompts.
"""

from surveyclaw.skills.schema import Skill
from surveyclaw.skills.registry import SkillRegistry

__all__ = ["Skill", "SkillRegistry"]
