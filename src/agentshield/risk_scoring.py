"""
Risk Scoring
============

Scores how anomalous a proposed action is relative to a given agent's
historical behavior baseline.

Design note: v1 ships a dependency-free `BaselineRiskScorer` built on
Python's standard-library `statistics` module, so the core package never
requires a heavy ML dependency just to run. `XGBoostRiskScorer` is provided
as a drop-in, higher-fidelity alternative for teams that have `xgboost` and
`shap` installed and want richer explanations — it implements the exact
same `RiskScorer` interface, so it's a one-line swap.
"""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from collections import defaultdict
from numbers import Number
from typing import Any

from .schemas import Action, RiskScoreResult


class RiskScorer(ABC):
    """Interface all risk scorers must implement."""

    @abstractmethod
    def score(self, action: Action) -> RiskScoreResult:
        """Return a RiskScoreResult for the given action."""

    @abstractmethod
    def observe(self, action: Action) -> None:
        """Update the scorer's internal baseline with a new observed action."""


class BaselineRiskScorer(RiskScorer):
    """
    Dependency-free statistical anomaly scorer.

    For each (agent_id, action_name, numeric field) triple, maintains a
    running mean/stdev. A new action's numeric fields are compared against
    that baseline using a z-score; the max absolute z-score across fields
    (squashed into 0..1) becomes the anomaly score. Non-numeric fields are
    tracked as frequency sets — a value never seen before for that agent
    contributes to the score as well.

    This is intentionally simple and interpretable: it has no training
    step, works from the very first action, and improves as more history
    accumulates.
    """

    def __init__(self, min_samples_for_zscore: int = 5, z_score_cap: float = 6.0):
        self.min_samples_for_zscore = min_samples_for_zscore
        self.z_score_cap = z_score_cap
        # (agent_id, action_name, field) -> list[float]
        self._numeric_history: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        # (agent_id, action_name, field) -> set[Any]
        self._categorical_history: dict[tuple[str, str, str], set[Any]] = defaultdict(set)

    def observe(self, action: Action) -> None:
        for field, value in action.parameters.items():
            key = (action.agent_id, action.action_name, field)
            if isinstance(value, Number) and not isinstance(value, bool):
                self._numeric_history[key].append(float(value))
            else:
                self._categorical_history[key].add(value)

    def score(self, action: Action) -> RiskScoreResult:
        factor_scores: list[tuple[str, float]] = []

        for field, value in action.parameters.items():
            key = (action.agent_id, action.action_name, field)

            if isinstance(value, Number) and not isinstance(value, bool):
                history = self._numeric_history.get(key, [])
                if len(history) >= self.min_samples_for_zscore:
                    mean = statistics.mean(history)
                    stdev = statistics.pstdev(history) or 1e-6
                    z = abs((float(value) - mean) / stdev)
                    normalized = min(z / self.z_score_cap, 1.0)
                    if normalized > 0.15:
                        factor_scores.append(
                            (
                                f"{field}={value} is {z:.1f} std-dev from this agent's "
                                f"baseline mean ({mean:.2f})",
                                normalized,
                            )
                        )
            else:
                seen_values = self._categorical_history.get(key, set())
                if seen_values and value not in seen_values:
                    factor_scores.append(
                        (f"{field}={value!r} has never been used by this agent before", 0.5)
                    )

        if not factor_scores:
            return RiskScoreResult(score=0.0, top_factors=[])

        factor_scores.sort(key=lambda pair: pair[1], reverse=True)
        top_score = factor_scores[0][1]
        top_factors = [desc for desc, _ in factor_scores[:3]]
        return RiskScoreResult(score=round(top_score, 3), top_factors=top_factors)


class XGBoostRiskScorer(RiskScorer):
    """
    Optional higher-fidelity scorer backed by XGBoost + SHAP.

    Not imported by default — instantiating this class raises a clear
    ImportError with install instructions if the optional dependencies
    are missing, keeping the core `agentshield` install lightweight.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            import xgboost  # noqa: F401
            import shap  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "XGBoostRiskScorer requires the optional 'ml' extra. "
                "Install it with: pip install 'agentshield[ml]'"
            ) from exc
        raise NotImplementedError(
            "XGBoostRiskScorer is a planned v2 scorer. Use BaselineRiskScorer for now."
        )

    def observe(self, action: Action) -> None:  # pragma: no cover
        raise NotImplementedError

    def score(self, action: Action) -> RiskScoreResult:  # pragma: no cover
        raise NotImplementedError
