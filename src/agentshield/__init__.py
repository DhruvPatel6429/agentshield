"""
AgentShield
===========

An open-source safety and audit firewall for autonomous AI agents.

Public API:
    - AgentShield: the main runtime object (policy engine + risk scorer + audit log)
    - Decision: enum of possible outcomes (ALLOW, BLOCK, FLAG)
    - AgentShieldBlockedAction: exception raised when a guarded call is blocked
"""

from .interceptor import AgentShield
from .schemas import Decision, Action, EvaluationResult
from .exceptions import AgentShieldBlockedAction

__version__ = "0.1.0"

__all__ = [
    "AgentShield",
    "Decision",
    "Action",
    "EvaluationResult",
    "AgentShieldBlockedAction",
]
