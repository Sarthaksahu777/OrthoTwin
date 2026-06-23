"""Stage 3 biomechanics engine interface.

Placeholder only. No physics or simulation is implemented in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class BiomechanicsInput:
    patient_state: dict[str, Any]
    graph: dict[str, Any]
    load_model: dict[str, Any]
    material_properties: dict[str, Any] | None = None
    boundary_conditions: dict[str, Any] | None = None


@dataclass
class BiomechanicsOutput:
    updated_state: dict[str, Any]
    load_distribution: dict[str, Any]
    validation_report: dict[str, Any]


class BiomechanicsEngine(Protocol):
    """Interface expected from a future deterministic biomechanics solver."""

    def prepare(self, inputs: BiomechanicsInput) -> None:
        """Validate and stage inputs for a future solver."""

    def run(self) -> BiomechanicsOutput:
        """Return deterministic biomechanical outputs when implemented."""
