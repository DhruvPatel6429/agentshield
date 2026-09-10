"""
Framework adapters.

Each adapter converts a specific agent framework's "tool call" shape into
AgentShield's generic `guard()` interception point. Adapters are optional
and imported lazily — `agentshield` core has zero dependency on any
specific agent framework.
"""

from .langchain_adapter import wrap_langchain_tool

__all__ = ["wrap_langchain_tool"]
