"""Core digital twin object for deterministic spine state management."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class SpineDigitalTwin:
    """Container and access API for a single patient's spine state."""

    def __init__(self, state_path: str | Path | None = None) -> None:
        self.state_path = Path(state_path) if state_path else None
        self.state: dict[str, Any] = {}
        if self.state_path:
            self.load_state(self.state_path)

    def load_state(self, path: str | Path | None = None) -> dict[str, Any]:
        state_path = Path(path or self.state_path or "")
        if not state_path:
            raise ValueError("A state path is required.")
        with state_path.open("r", encoding="utf-8") as handle:
            self.state = json.load(handle)
        self.state_path = state_path
        return self.state

    def save_state(self, path: str | Path | None = None) -> Path:
        destination = Path(path or self.state_path or "")
        if not destination:
            raise ValueError("A destination path is required.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2)
        self.state_path = destination
        return destination

    def get_disc(self, disc_id: str) -> dict[str, Any]:
        return self._get_structure("discs", disc_id)

    def get_vertebra(self, vertebra_id: str) -> dict[str, Any]:
        return self._get_structure("vertebrae", vertebra_id)

    def get_summary(self) -> dict[str, Any]:
        discs = self.state.get("discs", {})
        worst_disc = None
        if discs:
            worst_disc = max(
                discs.values(),
                key=lambda item: item.get("state_variables", {}).get(
                    "severity_score", -1
                )
                or -1,
            )
        return {
            "patient_id": self.state.get("patient_id"),
            "schema_version": self.state.get("schema_version"),
            "num_structures": self.state.get("segmentation", {}).get(
                "num_structures"
            ),
            "num_discs": len(discs),
            "num_vertebrae": len(self.state.get("vertebrae", {})),
            "worst_disc": worst_disc.get("name") if worst_disc else None,
            "interventions_applied": len(
                self.state.get("intervention_history", [])
            ),
            "quality_flags": self.state.get("quality_metrics", {}).get(
                "total_flagged_structures"
            ),
        }

    def update_state(self, new_state: dict[str, Any]) -> None:
        self.state = copy.deepcopy(new_state)

    def clone_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def _get_structure(self, section: str, structure_id: str) -> dict[str, Any]:
        structures = self.state.get(section, {})
        if structure_id in structures:
            return structures[structure_id]
        matches = [
            item
            for item in structures.values()
            if item.get("name") == structure_id
            or str(item.get("class_id")) == str(structure_id)
        ]
        if not matches:
            raise KeyError(f"{structure_id!r} not found in {section}.")
        return matches[0]

