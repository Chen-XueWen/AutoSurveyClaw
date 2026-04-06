"""Paper quality assessment and venue recommendation."""

from surveyclaw.assessor.rubrics import RUBRICS, Rubric
from surveyclaw.assessor.scorer import PaperScorer
from surveyclaw.assessor.venue_recommender import VenueRecommender
from surveyclaw.assessor.comparator import HistoryComparator

__all__ = [
    "RUBRICS",
    "HistoryComparator",
    "PaperScorer",
    "Rubric",
    "VenueRecommender",
]
