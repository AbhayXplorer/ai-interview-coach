"""
Rubric Definition and Scoring Engine for Technical Interview Evaluation.
Implements a 5-dimensional rubric modeled after FAANG/Tier-1 industry benchmarks.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

@dataclass
class RubricDimension:
    id: str
    name: str
    weight: float  # Value between 0.0 and 1.0 (sum of weights = 1.0)
    description: str
    max_score: int = 10
    levels: Dict[str, str] = field(default_factory=dict)

# Standard Industry Rubric Dimensions
DEFAULT_RUBRIC_DIMENSIONS: List[RubricDimension] = [
    RubricDimension(
        id="algorithmic_correctness",
        name="Algorithmic Correctness & Edge Cases",
        weight=0.30,
        description="Logical soundness, functional correctness, boundary conditions, edge case handling.",
        levels={
            "1-3 (Unsatisfactory)": "Fails basic test cases; severe logic flaws; uncaught exceptions on empty/null inputs.",
            "4-6 (Developing)": "Passes happy path; struggles with edge cases (empty list, duplicates, extreme values).",
            "7-8 (Proficient)": "Passes all public and edge cases; minor redundant operations or subtle boundary quirks.",
            "9-10 (Exemplary)": "Completely bug-free; proactive validation of edge cases; mathematically optimal logic."
        }
    ),
    RubricDimension(
        id="time_space_complexity",
        name="Time & Space Complexity Optimization",
        weight=0.20,
        description="Asymptotic Big-O optimality in execution time and memory space allocation.",
        levels={
            "1-3 (Unsatisfactory)": "Brute-force approach with O(N^2) or O(2^N) when linear or logarithmic is feasible.",
            "4-6 (Developing)": "Suboptimal auxiliary memory usage; understands Big-O theoretically but misses optimization.",
            "7-8 (Proficient)": "Meets target Big-O complexity; minor auxiliary space overhead.",
            "9-10 (Exemplary)": "Optimal time and space trade-off; in-place operations where appropriate; clear Big-O proof."
        }
    ),
    RubricDimension(
        id="code_quality_cleanliness",
        name="Code Quality, Modularity & Style",
        weight=0.20,
        description="Readability, variable naming, idiomatic syntax, modular decomposition, clean abstractions.",
        levels={
            "1-3 (Unsatisfactory)": "Cryptic naming (a, b, x1); monolithic unreadable blocks; lack of idiomatic constructs.",
            "4-6 (Developing)": "Readable but lacks modular helpers; inconsistent formatting or unnecessary code duplication.",
            "7-8 (Proficient)": "Clean variable naming; idiomatic constructs; good separation of concerns.",
            "9-10 (Exemplary)": "Production-grade cleanliness; self-documenting code; clean guard clauses and clean abstractions."
        }
    ),
    RubricDimension(
        id="problem_solving_approach",
        name="Problem Solving & Systematic Decomposition",
        weight=0.15,
        description="Structured breakdown of problem, pattern recognition (Two Pointers, DP, Graphs, Hash Map).",
        levels={
            "1-3 (Unsatisfactory)": "Jumps directly to coding without planning; random trial-and-error approach.",
            "4-6 (Developing)": "Recognizes general category but requires heavy hints to formulate invariant.",
            "7-8 (Proficient)": "Clearly identifies core pattern; evaluates trade-offs before typing code.",
            "9-10 (Exemplary)": "Exemplary architectural reasoning; proactively contrasts alternative algorithmic approaches."
        }
    ),
    RubricDimension(
        id="communication_articulation",
        name="Communication & Technical Articulation",
        weight=0.15,
        description="Clarity of explanation, active thinking aloud, responsiveness to interviewer hints.",
        levels={
            "1-3 (Unsatisfactory)": "Silent coding; defensive or unresponsive when hints are provided.",
            "4-6 (Developing)": "Explains code only when asked; difficulty explaining complex recursive logic.",
            "7-8 (Proficient)": "Thinks out loud clearly; walks through an example trace smoothly.",
            "9-10 (Exemplary)": "Masterful technical communication; proactive sanity tracing; interviewer collaboration."
        }
    )
]

@dataclass
class DimensionScore:
    dimension_id: str
    dimension_name: str
    raw_score: float        # 0.0 - 10.0
    weight: float           # e.g. 0.30
    weighted_score: float   # raw_score * weight
    level: str              # Exemplary, Proficient, Developing, Unsatisfactory
    feedback: str           # Specific observation and praise
    suggestions: List[str]  # Actionable improvement points

@dataclass
class RubricEvaluationResult:
    overall_score: float            # Out of 100
    recommendation: str             # "Strong Hire", "Hire", "Leaning Hire", "Leaning No Hire", "No Hire"
    verdict_summary: str            # High-level evaluation summary
    dimension_scores: Dict[str, DimensionScore]
    strengths: List[str]
    growth_areas: List[str]
    detected_time_complexity: str
    detected_space_complexity: str
    optimal_time_complexity: str
    optimal_space_complexity: str
    ast_metrics: Dict[str, Any] = field(default_factory=dict)
    test_suite_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1),
            "recommendation": self.recommendation,
            "verdict_summary": self.verdict_summary,
            "dimension_scores": {
                k: asdict(v) for k, v in self.dimension_scores.items()
            },
            "strengths": self.strengths,
            "growth_areas": self.growth_areas,
            "detected_time_complexity": self.detected_time_complexity,
            "detected_space_complexity": self.detected_space_complexity,
            "optimal_time_complexity": self.optimal_time_complexity,
            "optimal_space_complexity": self.optimal_space_complexity,
            "ast_metrics": self.ast_metrics,
            "test_suite_summary": self.test_suite_summary
        }


def get_recommendation_band(score_out_of_100: float) -> str:
    """Map weighted score to standard hiring committee recommendation."""
    if score_out_of_100 >= 88.0:
        return "Strong Hire (Top 5% Candidate)"
    elif score_out_of_100 >= 75.0:
        return "Hire (Solid Technical Bar Met)"
    elif score_out_of_100 >= 60.0:
        return "Leaning Hire (Borderline - Minor Polish Needed)"
    elif score_out_of_100 >= 45.0:
        return "Leaning No Hire (Gaps in Edge Cases or Efficiency)"
    else:
        return "No Hire (Substantial Conceptual Gaps)"
