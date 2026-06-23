"""Geometry-aware implant simulation for Phase 7."""

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


def simulate_implant_geometry(target_disc: str = "disc_6_206_207", height_multiplier: float = 1.2) -> dict[str, Any]:
    engine = AnatomicalModificationEngine()
    current_height = float(engine.state["objects"][target_disc]["geometry"]["height"])
    implant_height = current_height * height_multiplier
    modification = engine.insert_implant(target_disc, implant_height)
    rebuilt = rebuild_state(
        modification,
        scenario_id="implant_geometry_v2",
        output_path=OUTPUT_DIR / "rebuilt_state_implant.json",
    )
    result = {
        "scenario_id": "implant_geometry_v2",
        "workflow": [
            "Current Disc Geometry",
            "Apply Implant",
            "Increase Disc Space",
            "Update Adjacent Vertebra Positions",
            "Rebuild Local Relationships",
            "Recompute Measurements",
        ],
        "target_disc": target_disc,
        "implant_height": implant_height,
        "geometry_modification": modification,
        "rebuilt_state_file": str(OUTPUT_DIR / "rebuilt_state_implant.json"),
        "summary": summarize(rebuilt),
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    write_json(OUTPUT_DIR / "implant_geometry_result.json", result)
    return result


def summarize(rebuilt: dict[str, Any]) -> dict[str, Any]:
    return {
        "structures_affected": sorted({change["object_id"] for change in rebuilt["surgical_geometry"].get("modification_history", [])[-1].get("geometry_changes", []) if "object_id" in change}),
        "disc_spacing_records": len(rebuilt.get("relative_spacing", {})),
        "alignment_records": len(rebuilt.get("alignment", {}).get("disc_alignment", {})),
        "load_records": len(rebuilt.get("load_distribution", {}).get("structures", {})),
    }


if __name__ == "__main__":
    simulate_implant_geometry()
