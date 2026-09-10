"""
LangChain Adapter
=================

Wraps a LangChain `Tool` / `StructuredTool` (or any plain callable used as
an agent tool) so that every invocation is routed through AgentShield's
`guard()` interceptor before it executes.

This module does NOT import `langchain` at module load time — it works by
duck-typing (checking for a `.func` attribute, which both `Tool` and
`StructuredTool` expose) so `agentshield` never forces LangChain as a hard
dependency on users who don't need this adapter.

Usage:

    from agentshield import AgentShield
    from agentshield.adapters import wrap_langchain_tool

    shield = AgentShield(policy_path="policies/default.yaml")

    # `payment_tool` is any LangChain Tool/StructuredTool instance
    guarded_tool = wrap_langchain_tool(payment_tool, shield, agent_id="billing-bot")

    # or wrap several at once:
    from agentshield.adapters import guard_langchain_tools
    guarded_tools = guard_langchain_tools([tool_a, tool_b], shield, agent_id="research-bot")
"""

from __future__ import annotations

from typing import Any, Iterable, TypeVar

from ..interceptor import AgentShield

T = TypeVar("T")


def wrap_langchain_tool(tool: T, shield: AgentShield, agent_id: str = "default-agent") -> T:
    """
    Wrap a single LangChain tool (or plain callable) in place with an
    AgentShield guard. Returns the same object for convenient chaining.
    """
    action_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unnamed_tool")
    guard_decorator = shield.guard(agent_id=agent_id, action_name=action_name)

    if hasattr(tool, "func") and callable(tool.func):
        # LangChain Tool / StructuredTool convention: the callable lives on `.func`
        tool.func = guard_decorator(tool.func)
        return tool

    if callable(tool):
        # Plain function being used directly as a tool
        return guard_decorator(tool)  # type: ignore[return-value]

    raise TypeError(
        f"Cannot guard object of type {type(tool)!r} — expected a LangChain "
        f"Tool/StructuredTool (with a callable `.func`) or a plain callable."
    )


def guard_langchain_tools(
    tools: Iterable[T], shield: AgentShield, agent_id: str = "default-agent"
) -> list[T]:
    """Convenience helper to wrap a whole list of tools in one call."""
    return [wrap_langchain_tool(tool, shield, agent_id=agent_id) for tool in tools]
