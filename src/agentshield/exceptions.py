"""Exceptions raised by AgentShield."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import EvaluationResult


class AgentShieldError(Exception):
    """Base class for all AgentShield errors."""


class AgentShieldBlockedAction(AgentShieldError):
    """Raised (in synchronous/blocking mode) when a guarded action is blocked."""

    def __init__(self, result: "EvaluationResult"):
        self.result = result
        message = (
            f"Action '{result.action.action_name}' was BLOCKED by AgentShield "
            f"(policy: {result.matched_policy_name or 'n/a'}). Reason: {result.reason}"
        )
        super().__init__(message)


class PolicyConfigError(AgentShieldError):
    """Raised when a policy file is malformed or fails validation on load."""
