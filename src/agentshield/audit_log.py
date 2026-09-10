"""
Audit Log
=========

Append-only record of every evaluated action, regardless of decision
outcome. v1 ships a lightweight implementation: in-memory list (always
available) plus optional JSONL file persistence for durability across
process restarts. This intentionally mirrors the "events" table described
in the Backend Schema doc (organization_id/agent_id/action_name/decision/
created_at) so migrating to Postgres later is a straightforward swap of
the storage backend behind the same `AuditLog` interface.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .schemas import EvaluationResult


class AuditLog:
    """Append-only store for EvaluationResults."""

    def __init__(self, file_path: Optional[str | Path] = None):
        self.file_path = Path(file_path) if file_path else None
        self._events: list[EvaluationResult] = []

        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_path.touch(exist_ok=True)

    def record(self, result: EvaluationResult) -> None:
        self._events.append(result)
        if self.file_path:
            with self.file_path.open("a") as f:
                f.write(json.dumps(self._to_jsonable(result)) + "\n")

    def all_events(self) -> list[EvaluationResult]:
        return list(self._events)

    def events_for_agent(self, agent_id: str) -> list[EvaluationResult]:
        return [e for e in self._events if e.action.agent_id == agent_id]

    def events_by_decision(self, decision: str) -> list[EvaluationResult]:
        return [e for e in self._events if e.decision.value == decision]

    def __len__(self) -> int:
        return len(self._events)

    @staticmethod
    def _to_jsonable(result: EvaluationResult) -> dict:
        payload = asdict(result)
        payload["action"]["created_at"] = result.action.created_at.isoformat()
        payload["decision"] = result.decision.value
        return payload
