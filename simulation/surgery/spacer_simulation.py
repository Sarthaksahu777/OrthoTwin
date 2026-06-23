"""Geometry-aware spacer insertion simulation for Phase 7."""

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


def simulate_spacer_geometry(target_disc: str = "disc_5_205", expansion_percent: float = 15.0) -> dict[str, Any]:
    engine = AnatomicalModificationEngine()
    modification = engine.insert_spacer(target_disc, expansion_percent)
    rebuilt = rebuild_state(
        modification,
        scenario_id="spacer_geometry_v2",
        output_path=OUTPUT_DIR / "rebuilt_state_spacer.json",
    )
    result = {
        "scenario_id": "spacer_geometry_v2",
        "workflow": [
            "Insert Spacer",
            "Expand Disc Space",
            "Update Adjacent Vertebra Positions",
            "Recompute Local Alignment",
            "Recompute State",
        ],
        "target_disc": target_disc,
        "expansion_percent": expansion_percent,
        "geometry_modification": modification,
        "rebuilt_state_file": str(OUTPUT_DIR / "rebuilt_state_spacer.json"),
        "summary": {
            "created_objects": modification.get("created_objects", []),
            "disc_spacing_records": len(rebuilt.get("relative_spacing", {})),
            "alignment_records": len(rebuilt.get("alignment", {}).get("disc_alignment", {})),
            "load_records": len(rebuilt.get("load_distribution", {}).get("structures", {})),
        },
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    write_json(OUTPUT_DIR / "spacer_geometry_result.json", result)
    return result


if __name__ == "__main__":
    simulate_spacer_geometry()
