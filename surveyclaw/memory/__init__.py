"""Persistent evolutionary memory system for AutoSurveyClaw.

Provides three categories of memory:
- **Ideation**: Research topics, hypotheses, and their outcomes.
- **Experiment**: Hyperparameters, architectures, and training tricks.
- **Writing**: Review feedback, paper structure patterns.

Each category supports semantic retrieval via embeddings, time-decay
weighting, and confidence scoring.
"""

from surveyclaw.memory.store import MemoryEntry, MemoryStore
from surveyclaw.memory.retriever import MemoryRetriever
from surveyclaw.memory.decay import time_decay_weight, confidence_update

__all__ = [
    "MemoryEntry",
    "MemoryStore",
    "MemoryRetriever",
    "time_decay_weight",
    "confidence_update",
]
