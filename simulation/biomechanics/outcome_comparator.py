"""Stage 3 outcome comparator interface.

Placeholder only. No clinical outcome prediction is implemented in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class OutcomeComparisonInput:
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    expected_targets: dict[str, Any]


@dataclass
class OutcomeComparisonOutput:
    geometric_deltas: dict[str, Any]
    load_deltas: dict[str, Any]
    unmet_targets: list[str]


class OutcomeComparator(Protocol):
    """Interface expected from future deterministic outcome comparison."""

    def compare(self, inputs: OutcomeComparisonInput) -> OutcomeComparisonOutput:
        """Compare before/after digital twin states when implemented."""
