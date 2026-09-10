"""
Interceptor
===========

`AgentShield` is the main runtime object a developer instantiates once and
uses to guard any callable an agent might invoke (a LangChain tool, a
plain function, an API-calling wrapper, etc.).

    shield = AgentShield(policy_path="policies/default.yaml")

    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float, currency: str, recipient: str) -> str:
        ...

    send_payment(amount=1200, currency="USD", recipient="acme@example.com")
    # -> raises AgentShieldBlockedAction if a policy blocks it

Fail-safe behavior: if the policy engine or risk scorer raises an
unexpected internal error during evaluation, AgentShield defaults to
BLOCK (configurable via `fail_safe_default`) rather than silently letting
a potentially-dangerous action through.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from .audit_log import AuditLog
from .exceptions import AgentShieldBlockedAction
from .policy_engine import PolicyEngine
from .risk_scoring import BaselineRiskScorer, RiskScorer
from .schemas import Action, Decision, EvaluationResult, RiskScoreResult

logger = logging.getLogger("agentshield")

F = TypeVar("F", bound=Callable[..., Any])

# Risk score at or above this threshold auto-escalates an otherwise-ALLOWed
# action to FLAG, even with no explicit policy rule matching it.
DEFAULT_RISK_FLAG_THRESHOLD = 0.75


class AgentShield:
    """Main entry point: wires together the policy engine, risk scorer, and audit log."""

    def __init__(
        self,
        policy_path: Optional[str | Path] = None,
        risk_scorer: Optional[RiskScorer] = None,
        audit_log_path: Optional[str | Path] = None,
        fail_safe_default: Decision = Decision.BLOCK,
        risk_flag_threshold: float = DEFAULT_RISK_FLAG_THRESHOLD,
        raise_on_block: bool = True,
    ):
        self.policy_engine = PolicyEngine(policy_path=policy_path)
        self.risk_scorer = risk_scorer or BaselineRiskScorer()
        self.audit_log = AuditLog(file_path=audit_log_path)
        self.fail_safe_default = fail_safe_default
        self.risk_flag_threshold = risk_flag_threshold
        self.raise_on_block = raise_on_block

    # ------------------------------------------------------------------ #
    # Core evaluation
    # ------------------------------------------------------------------ #

    def evaluate(self, action: Action) -> EvaluationResult:
        """Evaluate a single Action through the policy engine + risk scorer."""
        start = time.perf_counter()

        try:
            decision, reason, matched_policy = self.policy_engine.evaluate(action)
            risk: Optional[RiskScoreResult] = self.risk_scorer.score(action)

            # An action the policy engine allowed can still be escalated to
            # FLAG if the risk scorer considers it highly anomalous.
            if decision == Decision.ALLOW and risk.score >= self.risk_flag_threshold:
                decision = Decision.FLAG
                reason = (
                    f"No policy rule blocked this action, but risk score "
                    f"{risk.score:.2f} exceeded the flag threshold "
                    f"({self.risk_flag_threshold}). Factors: {'; '.join(risk.top_factors)}"
                )

            self.risk_scorer.observe(action)

        except Exception:
            logger.exception(
                "AgentShield: internal evaluation error — failing safe to %s",
                self.fail_safe_default.value,
            )
            decision = self.fail_safe_default
            reason = "Internal evaluation error — fail-safe default applied."
            matched_policy = None
            risk = None

        latency_ms = (time.perf_counter() - start) * 1000

        result = EvaluationResult(
            action=action,
            decision=decision,
            reason=reason,
            matched_policy_name=matched_policy,
            risk=risk,
            latency_ms=round(latency_ms, 3),
        )
        self.audit_log.record(result)
        return result

    # ------------------------------------------------------------------ #
    # Decorator API
    # ------------------------------------------------------------------ #

    def guard(
        self,
        agent_id: str = "default-agent",
        action_name: Optional[str] = None,
    ) -> Callable[[F], F]:
        """
        Decorator that wraps a callable so every invocation is evaluated
        by AgentShield before the underlying function actually runs.

        On BLOCK: raises AgentShieldBlockedAction (if raise_on_block=True)
                  or returns None (if raise_on_block=False), and the
                  wrapped function body never executes.
        On FLAG:  the function executes normally; the flagged event is
                  recorded in the audit log for review.
        On ALLOW: the function executes normally.
        """

        def decorator(func: F) -> F:
            resolved_action_name = action_name or func.__name__
            signature = inspect.signature(func)

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                bound = signature.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                parameters = dict(bound.arguments)

                action = Action(
                    action_name=resolved_action_name,
                    parameters=parameters,
                    agent_id=agent_id,
                )
                result = self.evaluate(action)

                if result.decision == Decision.BLOCK:
                    logger.warning(
                        "AgentShield BLOCKED '%s' for agent '%s': %s",
                        resolved_action_name,
                        agent_id,
                        result.reason,
                    )
                    if self.raise_on_block:
                        raise AgentShieldBlockedAction(result)
                    return None

                if result.decision == Decision.FLAG:
                    logger.warning(
                        "AgentShield FLAGGED '%s' for agent '%s' (executing anyway): %s",
                        resolved_action_name,
                        agent_id,
                        result.reason,
                    )

                return func(*args, **kwargs)

            wrapper.__agentshield_guarded__ = True  # type: ignore[attr-defined]
            return wrapper  # type: ignore[return-value]

        return decorator
