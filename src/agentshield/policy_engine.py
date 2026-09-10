"""
Policy Engine
=============

Loads declarative YAML policies and evaluates a proposed Action against
them. Evaluation order (most specific wins first):

    1. tool-scoped rules   (policies["tools"][action_name])
    2. agent-scoped rules  (policies["agents"][agent_id])
    3. global rules        (policies["global"])

Within a scope, rules are evaluated in the order they are defined and the
FIRST matching rule short-circuits evaluation. If no rule matches in any
scope, the action defaults to ALLOW.

YAML shape:

    global:
      - field: amount
        operator: gt
        value: 500
        action_on_match: block

    agents:
      billing-bot:
        - field: currency
          operator: in_list
          value: ["USD", "INR"]
          action_on_match: allow

    tools:
      send_email:
        - field: recipient
          operator: regex
          value: ".*@internal\\.company\\.com$"
          action_on_match: allow
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

from .exceptions import PolicyConfigError
from .schemas import Action, Decision

_VALID_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq", "regex", "in_list", "contains"}
_VALID_ACTIONS = {"block", "flag", "allow"}


class PolicyRule:
    """A single evaluated condition -> outcome mapping."""

    __slots__ = ("field", "operator", "value", "action_on_match", "policy_name")

    def __init__(
        self,
        field: str,
        operator: str,
        value: Any,
        action_on_match: str,
        policy_name: str,
    ):
        if operator not in _VALID_OPERATORS:
            raise PolicyConfigError(
                f"Unknown operator '{operator}' in policy '{policy_name}'. "
                f"Valid operators: {sorted(_VALID_OPERATORS)}"
            )
        if action_on_match not in _VALID_ACTIONS:
            raise PolicyConfigError(
                f"Unknown action_on_match '{action_on_match}' in policy '{policy_name}'. "
                f"Valid values: {sorted(_VALID_ACTIONS)}"
            )
        self.field = field
        self.operator = operator
        self.value = value
        self.action_on_match = action_on_match
        self.policy_name = policy_name

    def matches(self, parameters: dict[str, Any]) -> bool:
        if self.field not in parameters:
            return False
        actual = parameters[self.field]

        try:
            if self.operator == "gt":
                return actual > self.value
            if self.operator == "gte":
                return actual >= self.value
            if self.operator == "lt":
                return actual < self.value
            if self.operator == "lte":
                return actual <= self.value
            if self.operator == "eq":
                return actual == self.value
            if self.operator == "neq":
                return actual != self.value
            if self.operator == "in_list":
                return actual in self.value
            if self.operator == "contains":
                return self.value in actual
            if self.operator == "regex":
                return re.match(str(self.value), str(actual)) is not None
        except TypeError:
            # Mismatched types (e.g. comparing str > int) never "match" —
            # fail closed to "no match" rather than raising mid-evaluation.
            return False

        return False  # pragma: no cover - unreachable, all operators handled above

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "action_on_match": self.action_on_match,
        }


class PolicyEngine:
    """Loads YAML policy definitions and evaluates actions against them."""

    def __init__(self, policy_path: Optional[str | Path] = None, dry_run: bool = False):
        self.dry_run = dry_run
        self._global_rules: list[PolicyRule] = []
        self._agent_rules: dict[str, list[PolicyRule]] = {}
        self._tool_rules: dict[str, list[PolicyRule]] = {}

        if policy_path is not None:
            self.load(policy_path)

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def load(self, policy_path: str | Path) -> None:
        path = Path(policy_path)
        if not path.exists():
            raise PolicyConfigError(f"Policy file not found: {path}")

        with path.open("r") as f:
            raw = yaml.safe_load(f) or {}

        self._global_rules = self._parse_rule_list(raw.get("global", []), "global")

        self._agent_rules = {
            agent_id: self._parse_rule_list(rules, f"agents.{agent_id}")
            for agent_id, rules in (raw.get("agents") or {}).items()
        }

        self._tool_rules = {
            tool_name: self._parse_rule_list(rules, f"tools.{tool_name}")
            for tool_name, rules in (raw.get("tools") or {}).items()
        }

    def load_from_dict(self, raw: dict[str, Any]) -> None:
        """Load policies directly from a dict (useful for tests / embedded configs)."""
        self._global_rules = self._parse_rule_list(raw.get("global", []), "global")
        self._agent_rules = {
            agent_id: self._parse_rule_list(rules, f"agents.{agent_id}")
            for agent_id, rules in (raw.get("agents") or {}).items()
        }
        self._tool_rules = {
            tool_name: self._parse_rule_list(rules, f"tools.{tool_name}")
            for tool_name, rules in (raw.get("tools") or {}).items()
        }

    @staticmethod
    def _parse_rule_list(rules: list[dict[str, Any]], policy_name: str) -> list[PolicyRule]:
        parsed = []
        for i, rule in enumerate(rules):
            try:
                parsed.append(
                    PolicyRule(
                        field=rule["field"],
                        operator=rule["operator"],
                        value=rule["value"],
                        action_on_match=rule["action_on_match"],
                        policy_name=policy_name,
                    )
                )
            except KeyError as exc:
                raise PolicyConfigError(
                    f"Rule #{i} in '{policy_name}' is missing required key: {exc}"
                ) from exc
        return parsed

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def evaluate(self, action: Action) -> tuple[Decision, str, Optional[str]]:
        """
        Evaluate an action against tool -> agent -> global rules, in that
        order of precedence. Returns (decision, reason, matched_policy_name).
        """
        for scope_name, rules in (
            (f"tools.{action.action_name}", self._tool_rules.get(action.action_name, [])),
            (f"agents.{action.agent_id}", self._agent_rules.get(action.agent_id, [])),
            ("global", self._global_rules),
        ):
            for rule in rules:
                if rule.matches(action.parameters):
                    decision = Decision(rule.action_on_match)
                    reason = (
                        f"Matched rule in '{scope_name}': "
                        f"{rule.field} {rule.operator} {rule.value!r} "
                        f"(actual: {action.parameters.get(rule.field)!r})"
                    )
                    return decision, reason, scope_name

        return Decision.ALLOW, "No policy rule matched — default allow.", None
