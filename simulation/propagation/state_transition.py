"""State transition record for deterministic digital twin actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class StateTransition:
    before_state: dict[str, Any]
    action: dict[str, Any]
    after_state: dict[str, Any] | None = None
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def apply(
        self,
        simulation_function: Callable[..., dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.after_state = simulation_function(self.before_state, *args, **kwargs)
        return self.after_state

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_utc": self.created_utc,
            "action": self.action,
            "before_state": self.before_state,
            "after_state": self.after_state,
        }

