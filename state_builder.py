"""Build a unified deterministic patient state vector from Phase 2 artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
MEASUREMENTS_DIR = PROJECT_ROOT / "measurements"
STATE_DIR = PROJECT_ROOT / "state" / "patient_states"


DEFAULT_INPUTS = {
    "measurements": MEASUREMENTS_DIR / "geometry" / "patient_alpha_clean_measurements.json",
    "disc_ranking": MEASUREMENTS_DIR / "discs" / "patient_alpha_disc_ranking.json",
    "component_analysis": MEASUREMENTS_DIR / "geometry" / "patient_alpha_component_analysis.json",
    "coordinate_system": MEASUREMENTS_DIR / "alignment" / "spine_coordinate_system.json",
}


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_name_key(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
    )


def _structure_type(name: str) -> str:
    lowered = name.lower()
    if "disc" in lowered:
        return "disc"
    if "vertebra" in lowered:
        return "vertebra"
    return "other"


def _build_geometry(entry: dict[str, Any]) -> dict[str, Any]:
    box = entry.get("bounding_box", {})
    return {
        "class_id": entry.get("class_id"),
        "name": entry.get("name"),
        "voxel_count": entry.get("voxel_count"),
        "approx_volume": entry.get("approx_volume"),
        "centroid": entry.get("centroid"),
        "bounding_box": {
            "width": box.get("width"),
            "height": box.get("height"),
            "depth": box.get("depth"),
        },
        "pca_lengths": entry.get("pca_lengths", []),
        "principal_axes": entry.get("principal_axes", []),
        "pc_explained_variance_ratios": entry.get(
            "pc_explained_variance_ratios", []
        ),
    }


def build_patient_state_vector(
    patient_id: str = "patient_alpha",
    input_paths: dict[str, Path] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Create and persist the unified patient state vector.

    The builder does not infer from images or models. It only consolidates
    deterministic Phase 2 measurements into a state representation that can be
    transformed by intervention rules.
    """

    paths = {**DEFAULT_INPUTS, **(input_paths or {})}
    measurements = _load_json(paths["measurements"])
    disc_ranking = _load_json(paths["disc_ranking"])
    component_analysis = _load_json(paths["component_analysis"])
    coordinate_system = _load_json(paths["coordinate_system"])

    components_by_name = {item["name"]: item for item in component_analysis}
    ranking_by_name = {item["name"]: item for item in disc_ranking}

    discs: dict[str, Any] = {}
    vertebrae: dict[str, Any] = {}

    for entry in measurements:
        name = entry.get("name", f"class_{entry.get('class_id', 'unknown')}")
        key = _safe_name_key(name)
        geometry = _build_geometry(entry)
        component = components_by_name.get(name, {})

        record = {
            **geometry,
            "quality": {
                "component_count": component.get("component_count"),
                "largest_component_percent": component.get(
                    "largest_component_percent"
                ),
                "flagged": component.get("flagged", False),
                "reason": component.get("reason"),
            },
        }

        if _structure_type(name) == "disc":
            ranking = ranking_by_name.get(name, {})
            record["state_variables"] = {
                "height": ranking.get(
                    "height", geometry["bounding_box"].get("depth")
                ),
                "volume": ranking.get("volume", geometry.get("approx_volume")),
                "severity_score": ranking.get("severity_score"),
                "height_zscore": ranking.get("height_zscore"),
                "volume_zscore": ranking.get("volume_zscore"),
                "decompression_percent": 0.0,
                "implant_inserted": False,
                "removed_fraction": 0.0,
            }
            discs[key] = record
        elif _structure_type(name) == "vertebra":
            record["state_variables"] = {
                "alignment_offset": 0.0,
                "relative_load_index": 1.0,
            }
            vertebrae[key] = record

    total_flagged = sum(
        1 for item in component_analysis if bool(item.get("flagged", False))
    )
    state_vector = {
        "patient_id": patient_id,
        "schema_version": "1.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "segmentation": {
            "num_structures": len(measurements),
            "num_discs": len(discs),
            "num_vertebrae": len(vertebrae),
            "source_files": {key: str(path) for key, path in paths.items()},
        },
        "discs": discs,
        "vertebrae": vertebrae,
        "alignment": {
            "description": coordinate_system.get("description"),
            "methodology": coordinate_system.get("methodology"),
            "axes": coordinate_system.get("axes", {}),
            "explained_variance_ratios": coordinate_system.get(
                "explained_variance_ratios", {}
            ),
            "vertebra_names_used": coordinate_system.get(
                "vertebra_names_used", []
            ),
        },
        "quality_metrics": {
            "total_flagged_structures": total_flagged,
            "flagged_structure_names": [
                item["name"]
                for item in component_analysis
                if bool(item.get("flagged", False))
            ],
            "component_analysis": component_analysis,
        },
        "intervention_history": [],
    }

    destination = output_path or STATE_DIR / "patient_state_vector.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(state_vector, handle, indent=2)
    return state_vector


def main() -> None:
    state = build_patient_state_vector()
    print(
        "Built patient state vector for "
        f"{state['patient_id']} with {state['segmentation']['num_structures']} structures."
    )


if __name__ == "__main__":
    main()
