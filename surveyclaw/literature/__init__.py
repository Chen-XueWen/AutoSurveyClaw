"""Real literature search and citation management for SurveyClaw.

Provides API clients for Semantic Scholar and arXiv, plus unified search
with deduplication and BibTeX generation.  All network I/O uses stdlib
``urllib`` — **zero** extra pip dependencies.
"""

from surveyclaw.literature.models import Author, Paper
from surveyclaw.literature.search import search_papers
from surveyclaw.literature.verify import (
    CitationResult,
    VerificationReport,
    VerifyStatus,
    verify_citations,
)

__all__ = [
    "Author",
    "CitationResult",
    "Paper",
    "VerificationReport",
    "VerifyStatus",
    "search_papers",
    "verify_citations",
]
