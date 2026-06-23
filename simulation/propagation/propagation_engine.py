"""Deterministic Stage 3 graph propagation engine.

This is not a physics simulator. It converts local intervention actions into
system-wide state transitions by propagating rule-based effects through the
Stage 2 spine graph.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


PROPAGATION_RULES: dict[str, Any] = {
    "model": "deterministic_graph_propagation_v1",
    "physics_claim": "Not physics; graph-based geometric state propagation.",
    "max_depth": 3,
    "depth_weights": {
        "direct": 1.0,
        "secondary": 0.55,
        "tertiary": 0.25,
    },
    "rules": [
        "Direct target receives full action effect.",
        "First-hop graph neighbors receive secondary effects.",
        "Second-hop graph neighbors receive tertiary effects.",
        "Loads and stress scores are bounded at zero and risk is capped at one.",
        "Alignment changes are deterministic scalar offsets, not measured geometry recomputation.",
    ],
}


@dataclass
class PropagationResult:
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    action: dict[str, Any]
    affected_neighbors: list[dict[str, Any]]
    direct_effects: list[dict[str, Any]]
    secondary_effects: list[dict[str, Any]]
    tertiary_effects: list[dict[str, Any]]
    graph_updates: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "action": self.action,
            "affected_neighbors": self.affected_neighbors,
            "direct_effects": self.direct_effects,
            "secondary_effects": self.secondary_effects,
            "tertiary_effects": self.tertiary_effects,
            "graph_updates": self.graph_updates,
            "before_state_summary": summarize_state(self.before_state),
            "after_state_summary": summarize_state(self.after_state),
            "after_state": self.after_state,
        }


class PropagationEngine:
    """Apply deterministic intervention effects through the spine graph."""

    def __init__(self, state: dict[str, Any], graph: dict[str, Any]) -> None:
        self.state = copy.deepcopy(state)
        self.graph = copy.deepcopy(graph)

    def affected_neighbors(
        self, affected_structure: str, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        if affected_structure not in self.graph.get("nodes", {}):
            raise KeyError(f"Unknown graph node: {affected_structure}")
        visited = {affected_structure}
        queue: deque[tuple[str, int, str | None]] = deque(
            [(affected_structure, 0, None)]
        )
        affected = []
        while queue:
            node_id, depth, parent = queue.popleft()
            if depth > 0:
                affected.append(
                    {
                        "node_id": node_id,
                        "depth": depth,
                        "effect_tier": effect_tier(depth),
                        "parent": parent,
                        "node_type": self.graph["nodes"][node_id]["node_type"],
                    }
                )
            if depth >= max_depth:
                continue
            for neighbor in self.graph["nodes"][node_id].get("neighbors", []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1, node_id))
        return affected

    def simulate_disc_collapse(
        self, disc: str, collapse_percent: float
    ) -> PropagationResult:
        if not 0 <= collapse_percent <= 100:
            raise ValueError("collapse_percent must be between 0 and 100.")
        before_state = copy.deepcopy(self.state)
        after_state = copy.deepcopy(self.state)
        action = {
            "type": "disc_collapse",
            "target": disc,
            "parameters": {"collapse_percent": collapse_percent},
        }
        direct_effects = []
        disc_state = _disc(after_state, disc)
        variables = disc_state.setdefault("state_variables", {})
        old_height = float(variables.get("height") or disc_state["bounding_box"]["depth"])
        new_height = old_height * (1.0 - collapse_percent / 100.0)
        variables["height"] = new_height
        disc_state["bounding_box"]["depth"] = new_height
        if disc_state.get("pca_lengths"):
            disc_state["pca_lengths"][-1] = new_height
        direct_effects.append(effect(disc, "height", old_height, new_height))
        direct_effects.extend(
            self._adjust_load(after_state, disc, collapse_percent / 100.0 * 0.7)
        )
        direct_effects.extend(
            self._adjust_disc_alignment(after_state, disc, collapse_percent * 0.08)
        )
        affected = self._propagate_load(
            after_state, disc, collapse_percent / 100.0, direction="increase"
        )
        self._append_history(after_state, action, affected)
        return PropagationResult(
            before_state,
            after_state,
            action,
            affected,
            direct_effects,
            [item for item in affected if item["effect_tier"] == "secondary"],
            [item for item in affected if item["effect_tier"] == "tertiary"],
            [],
        )

    def simulate_disc_restoration(
        self, disc: str, restoration_percent: float
    ) -> PropagationResult:
        if restoration_percent < 0:
            raise ValueError("restoration_percent must be non-negative.")
        before_state = copy.deepcopy(self.state)
        after_state = copy.deepcopy(self.state)
        action = {
            "type": "disc_restoration",
            "target": disc,
            "parameters": {"restoration_percent": restoration_percent},
        }
        direct_effects = []
        disc_state = _disc(after_state, disc)
        variables = disc_state.setdefault("state_variables", {})
        old_height = float(variables.get("height") or disc_state["bounding_box"]["depth"])
        new_height = old_height * (1.0 + restoration_percent / 100.0)
        variables["height"] = new_height
        disc_state["bounding_box"]["depth"] = new_height
        if disc_state.get("pca_lengths"):
            disc_state["pca_lengths"][-1] = new_height
        direct_effects.append(effect(disc, "height", old_height, new_height))
        direct_effects.extend(
            self._adjust_load(after_state, disc, -restoration_percent / 100.0 * 0.5)
        )
        direct_effects.extend(
            self._adjust_disc_alignment(after_state, disc, -restoration_percent * 0.05)
        )
        affected = self._propagate_load(
            after_state, disc, restoration_percent / 100.0, direction="decrease"
        )
        self._append_history(after_state, action, affected)
        return PropagationResult(
            before_state,
            after_state,
            action,
            affected,
            direct_effects,
            [item for item in affected if item["effect_tier"] == "secondary"],
            [item for item in affected if item["effect_tier"] == "tertiary"],
            [],
        )

    def simulate_implant(
        self, target_disc: str, implant_height: float
    ) -> PropagationResult:
        if implant_height <= 0:
            raise ValueError("implant_height must be positive.")
        before_state = copy.deepcopy(self.state)
        after_state = copy.deepcopy(self.state)
        action = {
            "type": "implant_insertion",
            "target": target_disc,
            "parameters": {"implant_height": implant_height},
        }
        direct_effects = []
        disc_state = _disc(after_state, target_disc)
        variables = disc_state.setdefault("state_variables", {})
        old_height = float(variables.get("height") or disc_state["bounding_box"]["depth"])
        variables["height"] = implant_height
        variables["implant_inserted"] = True
        variables["implant_height"] = implant_height
        disc_state["bounding_box"]["depth"] = implant_height
        if disc_state.get("pca_lengths"):
            disc_state["pca_lengths"][-1] = implant_height
        direct_effects.append(effect(target_disc, "height", old_height, implant_height))
        direct_effects.append(effect(target_disc, "implant_inserted", False, True))
        load_delta = -0.25 if implant_height >= old_height else 0.2
        direct_effects.extend(self._adjust_load(after_state, target_disc, load_delta))
        direct_effects.extend(self._adjust_disc_alignment(after_state, target_disc, -1.5))
        affected = self._propagate_load(after_state, target_disc, abs(load_delta), direction="decrease")
        self._append_history(after_state, action, affected)
        return PropagationResult(
            before_state,
            after_state,
            action,
            affected,
            direct_effects,
            [item for item in affected if item["effect_tier"] == "secondary"],
            [item for item in affected if item["effect_tier"] == "tertiary"],
            [],
        )

    def simulate_fusion(
        self, vertebra_a: str, vertebra_b: str
    ) -> PropagationResult:
        before_state = copy.deepcopy(self.state)
        after_state = copy.deepcopy(self.state)
        graph = copy.deepcopy(self.graph)
        action = {
            "type": "fusion",
            "target": f"{vertebra_a}__{vertebra_b}",
            "parameters": {"vertebra_a": vertebra_a, "vertebra_b": vertebra_b},
        }
        if vertebra_a not in graph["nodes"] or vertebra_b not in graph["nodes"]:
            raise KeyError("Fusion vertebrae must exist in graph.")
        common_discs = sorted(
            set(graph["nodes"][vertebra_a]["neighbors"])
            & set(graph["nodes"][vertebra_b]["neighbors"])
        )
        fused_disc = common_discs[0] if common_discs else None
        graph_updates = [
            {
                "type": "fusion_edge_added",
                "source": vertebra_a,
                "target": vertebra_b,
                "motion_segment_removed": fused_disc,
            }
        ]
        graph["edges"].append(
            {
                "source": vertebra_a,
                "target": vertebra_b,
                "edge_type": "fusion_lock",
                "motion_segment_removed": fused_disc,
            }
        )
        for node_id in (vertebra_a, vertebra_b):
            graph["nodes"][node_id].setdefault("fusion", {})["fused_with"] = (
                vertebra_b if node_id == vertebra_a else vertebra_a
            )
            graph["nodes"][node_id]["motion_segment_removed"] = True
        direct_effects = []
        for node_id in (vertebra_a, vertebra_b):
            record = _structure_load(after_state, node_id)
            old_load = record["relative_load_index"]
            record["relative_load_index"] = max(0.0, old_load * 0.85)
            direct_effects.append(
                effect(node_id, "relative_load_index", old_load, record["relative_load_index"])
            )
        if fused_disc and fused_disc in after_state.get("disc_features", {}):
            after_state["disc_features"][fused_disc].setdefault("state_variables", {})[
                "motion_segment_removed"
            ] = True
            direct_effects.append(effect(fused_disc, "motion_segment_removed", False, True))
        affected = self._propagate_load(after_state, vertebra_a, 0.16, direction="increase", graph=graph)
        affected += [
            item
            for item in self._propagate_load(after_state, vertebra_b, 0.16, direction="increase", graph=graph)
            if item["node_id"] not in {entry["node_id"] for entry in affected}
        ]
        after_state["graph_structure"] = graph
        self._append_history(after_state, action, affected)
        return PropagationResult(
            before_state,
            after_state,
            action,
            affected,
            direct_effects,
            [item for item in affected if item["effect_tier"] == "secondary"],
            [item for item in affected if item["effect_tier"] == "tertiary"],
            graph_updates,
        )

    def _append_history(
        self, state: dict[str, Any], action: dict[str, Any], affected: list[dict[str, Any]]
    ) -> None:
        state.setdefault("intervention_history", []).append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **action,
                "affected_structure_count": 1 + len(affected),
            }
        )

    def _propagate_load(
        self,
        state: dict[str, Any],
        target: str,
        magnitude: float,
        direction: str,
        graph: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        graph = graph or self.graph
        affected = []
        for entry in self.affected_neighbors_from_graph(graph, target):
            depth = entry["depth"]
            weight = depth_weight(depth)
            signed_delta = magnitude * weight
            if direction == "decrease":
                signed_delta *= -0.65
            load_effects = self._adjust_load(state, entry["node_id"], signed_delta)
            entry["load_delta"] = signed_delta
            entry["effects"] = load_effects
            affected.append(entry)
        return affected

    def affected_neighbors_from_graph(
        self, graph: dict[str, Any], affected_structure: str, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        original = self.graph
        self.graph = graph
        try:
            return self.affected_neighbors(affected_structure, max_depth=max_depth)
        finally:
            self.graph = original

    def _adjust_load(
        self, state: dict[str, Any], node_id: str, delta: float
    ) -> list[dict[str, Any]]:
        record = _structure_load(state, node_id)
        changes = []
        old_load = float(record.get("relative_load_index", 1.0))
        new_load = max(0.0, old_load + delta)
        record["relative_load_index"] = new_load
        changes.append(effect(node_id, "relative_load_index", old_load, new_load))
        old_stress = float(record.get("stress_score", 0.0))
        stress_delta = delta * 0.6 if delta >= 0 else delta * 0.35
        new_stress = max(0.0, min(1.0, old_stress + stress_delta))
        record["stress_score"] = new_stress
        record["risk_score"] = max(0.0, min(1.0, new_stress * max(new_load, 0.1)))
        changes.append(effect(node_id, "stress_score", old_stress, new_stress))
        return changes

    def _adjust_disc_alignment(
        self, state: dict[str, Any], disc_id: str, delta_degrees: float
    ) -> list[dict[str, Any]]:
        alignment = state.setdefault("alignment_metrics", {}).setdefault("disc_alignment", {})
        if disc_id not in alignment:
            return []
        changes = []
        for metric in ("disc_angle_degrees", "disc_tilt_degrees"):
            old_value = float(alignment[disc_id].get(metric, 0.0))
            new_value = old_value + delta_degrees
            alignment[disc_id][metric] = new_value
            changes.append(effect(disc_id, metric, old_value, new_value))
        return changes


def simulate_disc_collapse(
    state: dict[str, Any], graph: dict[str, Any], disc: str, collapse_percent: float
) -> PropagationResult:
    return PropagationEngine(state, graph).simulate_disc_collapse(disc, collapse_percent)


def simulate_disc_restoration(
    state: dict[str, Any], graph: dict[str, Any], disc: str, restoration_percent: float
) -> PropagationResult:
    return PropagationEngine(state, graph).simulate_disc_restoration(disc, restoration_percent)


def simulate_fusion(
    state: dict[str, Any], graph: dict[str, Any], vertebra_a: str, vertebra_b: str
) -> PropagationResult:
    return PropagationEngine(state, graph).simulate_fusion(vertebra_a, vertebra_b)


def simulate_implant(
    state: dict[str, Any], graph: dict[str, Any], target_disc: str, implant_height: float
) -> PropagationResult:
    return PropagationEngine(state, graph).simulate_implant(target_disc, implant_height)


def effect(node_id: str, metric: str, before: Any, after: Any) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "metric": metric,
        "before": before,
        "after": after,
        "delta": (after - before) if isinstance(before, (int, float)) and isinstance(after, (int, float)) else None,
    }


def effect_tier(depth: int) -> str:
    if depth == 1:
        return "secondary"
    if depth == 2:
        return "tertiary"
    return "background"


def depth_weight(depth: int) -> float:
    if depth == 1:
        return float(PROPAGATION_RULES["depth_weights"]["secondary"])
    if depth == 2:
        return float(PROPAGATION_RULES["depth_weights"]["tertiary"])
    return 0.1


def _disc(state: dict[str, Any], disc_id: str) -> dict[str, Any]:
    discs = state.get("disc_features", {})
    if disc_id not in discs:
        raise KeyError(f"Unknown disc: {disc_id}")
    return discs[disc_id]


def _structure_load(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    structures = state.setdefault("load_metrics", {}).setdefault("structures", {})
    if node_id not in structures:
        structures[node_id] = {
            "structure_name": node_id,
            "structure_type": "unknown",
            "relative_load_index": 1.0,
            "stress_score": 0.0,
            "risk_score": 0.0,
            "rule_basis": {},
        }
    return structures[node_id]


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    loads = state.get("load_metrics", {}).get("structures", {})
    load_values = [float(item.get("relative_load_index", 1.0)) for item in loads.values()]
    stress_values = [float(item.get("stress_score", 0.0)) for item in loads.values()]
    return {
        "patient_id": state.get("patient_id"),
        "disc_count": len(state.get("disc_features", {})),
        "vertebra_count": len(state.get("vertebral_features", {})),
        "mean_load_index": sum(load_values) / len(load_values) if load_values else None,
        "max_stress_score": max(stress_values) if stress_values else None,
        "intervention_count": len(state.get("intervention_history", [])),
    }
