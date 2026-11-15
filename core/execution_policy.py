"""Safety and loop-control policy for autonomous/background tool execution."""
from __future__ import annotations
import json
from dataclasses import dataclass, field


def call_signature(name: str, args: dict | None) -> str:
    return str(name) + ":" + json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)


@dataclass
class ExecutionPolicy:
    """Tracks repeated calls and prevents autonomous agents from getting stuck.

    Exact duplicate calls are safe to replay from cache. Repeated duplicate
    *requests* still count as a stalled plan and eventually force a wrap-up.
    """
    max_duplicate_requests: int = 3
    _requests: dict[str, int] = field(default_factory=dict)

    def observe(self, name: str, args: dict | None) -> tuple[str, int]:
        sig = call_signature(name, args)
        count = self._requests.get(sig, 0) + 1
        self._requests[sig] = count
        return sig, count

    def stalled(self, name: str, args: dict | None) -> bool:
        sig = call_signature(name, args)
        return self._requests.get(sig, 0) >= self.max_duplicate_requests
