"""Geometry-aware fusion simulation for Phase 7."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from OrthoTwin.simulation.surgery.anatomical_modification_engine import AnatomicalModificationEngine
from OrthoTwin.simulation.surgery.state_rebuilder import rebuild_state


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "state" / "surgery"


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def simulate_fusion_geometry(vertebra_a: str = "vertebra_5", vertebra_b: str = "vertebra_6") -> dict[str, Any]:
    engine = AnatomicalModificationEngine()
    modification = engine.apply_fusion(vertebra_a, vertebra_b)
    rebuilt = rebuild_state(
        modification,
        scenario_id="fusion_geometry_v2",
        output_path=OUTPUT_DIR / "rebuilt_state_fusion.json",
    )
    result = {
        "scenario_id": "fusion_geometry_v2",
        "workflow": [
            "Fuse Vertebra A + B",
            "Remove Relative Motion",
            "Update Graph Relationship",
            "Recompute Connected Structures",
            "Recompute Load Transfer Proxy",
        ],
        "vertebra_a": vertebra_a,
        "vertebra_b": vertebra_b,
        "geometry_modification": modification,
        "rebuilt_state_file": str(OUTPUT_DIR / "rebuilt_state_fusion.json"),
        "summary": {
            "fusion_objects": [item for item in rebuilt["surgical_geometry"]["objects"] if item.startswith("fusion_")],
            "graph_edges": len(rebuilt["graph_state"].get("edges", [])),
            "load_records": len(rebuilt.get("load_distribution", {}).get("structures", {})),
        },
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    write_json(OUTPUT_DIR / "fusion_geometry_result.json", result)
    return result


if __name__ == "__main__":
    simulate_fusion_geometry()
