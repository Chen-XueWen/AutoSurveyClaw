"""Survey paper quality assessment rubrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rubric:
    """A single evaluation dimension rubric."""

    name: str
    criteria: str
    scale: str
    weight: float = 1.0


RUBRICS: dict[str, Rubric] = {
    "coverage": Rubric(
        name="Coverage",
        criteria=(
            "Comprehensiveness of literature coverage. "
            "Are major sub-fields, seminal works, and recent advances included?"
        ),
        scale="1=highly incomplete, 3=partial, 5=adequate, 7=comprehensive, 10=exhaustive",
        weight=1.5,
    ),
    "depth": Rubric(
        name="Depth",
        criteria=(
            "Analytical depth. Does the survey go beyond listing papers "
            "to provide synthesis, comparison, and insight?"
        ),
        scale="1=list only, 3=basic analysis, 5=adequate synthesis, 7=deep insight, 10=exceptional",
        weight=1.5,
    ),
    "taxonomy_quality": Rubric(
        name="Taxonomy Quality",
        criteria=(
            "Quality of the proposed taxonomy. "
            "Is it well-motivated, internally consistent, and collectively exhaustive?"
        ),
        scale="1=no taxonomy, 3=weak, 5=adequate, 7=well-structured, 10=innovative taxonomy",
    ),
    "clarity": Rubric(
        name="Clarity",
        criteria="Writing quality. Is the survey well-organized, readable, and academically rigorous?",
        scale="1=incomprehensible, 3=poor, 5=adequate, 7=clear, 10=excellent",
    ),
    "citation_quality": Rubric(
        name="Citation Quality",
        criteria=(
            "Accuracy and completeness of citations. "
            "Are cited papers real, accurately described, and well-integrated?"
        ),
        scale="1=hallucinated/missing, 3=sparse, 5=adequate, 7=well-cited, 10=exemplary",
        weight=1.2,
    ),
}
