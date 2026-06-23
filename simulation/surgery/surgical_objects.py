"""Surgical object model for geometry-aware intervention simulation.

Objects represent anatomy and surgical constructs before metrics are rebuilt.
No diagnosis, treatment recommendation, inference, retraining, segmentation, or
mask modification is performed.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLINICAL_STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
OUTPUT_DIR = PROJECT_ROOT / "state" / "surgery"


@dataclass
class SurgicalObject:
    id: str
    object_type: str
    geometry: dict[str, Any]
    relationships: dict[str, Any]
    measurements: dict[str, Any]
    constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Disc(SurgicalObject):
    pass


class Vertebra(SurgicalObject):
    pass


class Implant(SurgicalObject):
    pass


class Spacer(SurgicalObject):
    pass


class FusionSegment(SurgicalObject):
    pass


class AlignmentCorrection(SurgicalObject):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def surgical_object_schema() -> dict[str, Any]:
    return {
        "schema_name": "orthtwin_surgical_object_v1",
        "generated_utc": utc_now(),
        "object_types": [
            "Disc",
            "Vertebra",
            "Implant",
            "Spacer",
            "FusionSegment",
            "AlignmentCorrection",
        ],
        "required_fields": {
            "id": "Stable object identifier.",
            "object_type": "Disc, Vertebra, Implant, Spacer, FusionSegment, or AlignmentCorrection.",
            "geometry": "Centroid, height, width/depth proxies, and local axes where available.",
            "relationships": "Graph neighbors, above/below structures, or attached structures.",
            "measurements": "Current measurement values derived from existing OrthoTwin state.",
            "constraints": "Motion locks, target height, material placeholder, correction vector, and other deterministic constraints.",
        },
        "scope": "Geometry-aware research representation only; no clinical validity claim.",
    }


def build_surgical_objects(
    clinical_state: dict[str, Any] | None = None, graph: dict[str, Any] | None = None
) -> dict[str, Any]:
    clinical_state = clinical_state or load_json(CLINICAL_STATE_PATH)
    graph = graph or load_json(GRAPH_PATH)
    objects: dict[str, Any] = {}

    for node_id, node in graph.get("nodes", {}).items():
        node_type = node.get("node_type", "")
        if node_type == "disc":
            measurements = deepcopy(clinical_state.get("disc_heights", {}).get(node_id, {}))
            geometry = {
                "centroid": node.get("centroid"),
                "height": measurements.get("mean_height"),
                "maximum_height": measurements.get("maximum_height"),
                "minimum_height": measurements.get("minimum_height"),
                "height_axis": measurements.get("height_axis"),
                "area": clinical_state.get("disc_areas", {}).get(node_id, {}),
            }
            relationships = {
                "neighbors": node.get("neighbors", []),
                "position_index": node.get("position_index"),
            }
            objects[node_id] = Disc(
                node_id,
                "Disc",
                geometry,
                relationships,
                measurements,
                {"preserve_connectivity": True},
            ).to_dict()
        elif node_type.startswith("vertebra"):
            relationships = {
                "neighbors": node.get("neighbors", []),
                "position_index": node.get("position_index"),
            }
            measurements = deepcopy(clinical_state.get("canal_areas", {}).get(node_id, {}))
            geometry = {
                "centroid": node.get("centroid"),
                "canal_proxy": measurements,
                "slippage_links": {
                    key: value
                    for key, value in clinical_state.get("slippage", {}).items()
                    if value.get("from") == node_id or value.get("to") == node_id
                },
            }
            objects[node_id] = Vertebra(
                node_id,
                "Vertebra",
                geometry,
                relationships,
                measurements,
                {"rigid_body": True},
            ).to_dict()

    return {
        "generated_utc": utc_now(),
        "patient_id": clinical_state.get("patient_id", "patient_alpha"),
        "objects": objects,
        "graph_state": deepcopy(graph),
        "clinical_state_reference": str(CLINICAL_STATE_PATH),
        "not_medical_advice": True,
    }


def main() -> None:
    write_json(OUTPUT_DIR / "surgical_object_schema.json", surgical_object_schema())
    write_json(OUTPUT_DIR / "surgical_objects.json", build_surgical_objects())
    print("Surgical object model generated.")


if __name__ == "__main__":
    main()
