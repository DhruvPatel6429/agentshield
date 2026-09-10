"""
Core data structures shared across the policy engine, risk scorer,
interceptor, and audit log. Kept as plain dataclasses (no pydantic
dependency) so the package installs with zero heavyweight requirements.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Decision(str, Enum):
    """Possible outcomes of evaluating a proposed agent action."""

    ALLOW = "allow"
    BLOCK = "block"
    FLAG = "flag"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Action:
    """A single proposed action captured by the interceptor before execution."""

    action_name: str
    parameters: dict[str, Any]
    agent_id: str = "default-agent"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class RiskScoreResult:
    """Output of the risk scoring engine for a single action."""

    score: float  # 0.0 (normal) -> 1.0 (highly anomalous)
    top_factors: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Full result of evaluating an Action against policies + risk scoring."""

    action: Action
    decision: Decision
    reason: str
    matched_policy_name: Optional[str] = None
    risk: Optional[RiskScoreResult] = None
    latency_ms: float = 0.0
