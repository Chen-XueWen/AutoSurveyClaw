"""Domain-specific prompt adapters.

Each adapter customizes prompt blocks for a specific research domain
while the ML adapter preserves existing behavior unchanged.
"""

from surveyclaw.domains.adapters.ml import MLPromptAdapter
from surveyclaw.domains.adapters.generic import GenericPromptAdapter
from surveyclaw.domains.adapters.physics import PhysicsPromptAdapter
from surveyclaw.domains.adapters.economics import EconomicsPromptAdapter
from surveyclaw.domains.adapters.biology import BiologyPromptAdapter
from surveyclaw.domains.adapters.chemistry import ChemistryPromptAdapter
from surveyclaw.domains.adapters.neuroscience import NeurosciencePromptAdapter
from surveyclaw.domains.adapters.robotics import RoboticsPromptAdapter

__all__ = [
    "MLPromptAdapter",
    "GenericPromptAdapter",
    "PhysicsPromptAdapter",
    "EconomicsPromptAdapter",
    "BiologyPromptAdapter",
    "ChemistryPromptAdapter",
    "NeurosciencePromptAdapter",
    "RoboticsPromptAdapter",
]
