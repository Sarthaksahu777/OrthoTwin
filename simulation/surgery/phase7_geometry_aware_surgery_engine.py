"""Phase 7 geometry-aware surgery engine runner."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_PARENT = Path(__file__).resolve().parents[3]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from OrthoTwin.simulation.surgery.anatomical_modification_engine import AnatomicalModificationEngine
from OrthoTwin.simulation.surgery.fusion_simulation_v2 import simulate_fusion_geometry
from OrthoTwin.simulation.surgery.implant_simulation_v2 import simulate_implant_geometry
from OrthoTwin.simulation.surgery.spacer_simulation import simulate_spacer_geometry
from OrthoTwin.simulation.surgery.state_rebuilder import rebuild_state
from OrthoTwin.simulation.surgery.surgical_objects import build_surgical_objects, surgical_object_schema
from OrthoTwin.simulation.surgery.surgical_outcome_comparator import compare_surgical_outcomes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state" / "surgery"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase7"
VIS_DIR = PROJECT_ROOT / "visualization" / "surgery"
MANIFEST_DIR = PROJECT_ROOT / "manifests"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_alignment_correction() -> dict[str, Any]:
    engine = AnatomicalModificationEngine()
    modification = engine.correct_alignment("vertebra_6", [-1.5, 0.75, 0.0])
    rebuilt = rebuild_state(
        modification,
        scenario_id="alignment_correction_geometry_v2",
        output_path=STATE_DIR / "rebuilt_state_alignment_correction.json",
    )
    result = {
        "scenario_id": "alignment_correction_geometry_v2",
        "workflow": [
            "Select Vertebra",
            "Apply Geometry Translation",
            "Rebuild Local Relationships",
            "Recompute Alignment",
            "Recompute State",
        ],
        "target_vertebra": "vertebra_6",
        "correction_vector": [-1.5, 0.75, 0.0],
        "geometry_modification": modification,
        "rebuilt_state_file": str(STATE_DIR / "rebuilt_state_alignment_correction.json"),
        "summary": {
            "created_objects": modification.get("created_objects", []),
            "alignment_records": len(rebuilt.get("alignment", {}).get("disc_alignment", {})),
            "load_records": len(rebuilt.get("load_distribution", {}).get("structures", {})),
        },
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    write_json(STATE_DIR / "alignment_geometry_result.json", result)
    return result


def load_rebuilt(result: dict[str, Any]) -> dict[str, Any]:
    return load_json(Path(result["rebuilt_state_file"]))


def centroid_pairs(result: dict[str, Any]) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    surgical_state = result["geometry_modification"]["surgical_state"]
    objects = surgical_state["objects"]
    before = {}
    after = {}
    for obj_id, obj in objects.items():
        if obj.get("object_type") != "Vertebra":
            continue
        centroid = obj.get("geometry", {}).get("centroid")
        if centroid:
            after[obj_id] = (float(centroid[0]), float(centroid[1]))
    for change in result["geometry_modification"].get("geometry_changes", []):
        if change.get("field") == "centroid" and change.get("before") and change.get("object_id"):
            before[change["object_id"]] = (float(change["before"][0]), float(change["before"][1]))
    for obj_id, coords in after.items():
        before.setdefault(obj_id, coords)
    return before, after


def plot_before_after(result: dict[str, Any], title: str, filename: str) -> Path:
    before, after = centroid_pairs(result)
    fig, ax = plt.subplots(figsize=(7, 7))
    for obj_id in sorted(after):
        bx, by = before[obj_id]
        ax.scatter(bx, by, color="#6f7d8f", s=60, label="Before" if obj_id == sorted(after)[0] else None)
        ax.scatter(after[obj_id][0], after[obj_id][1], color="#c84b31", s=60, label="After" if obj_id == sorted(after)[0] else None)
        ax.plot([bx, after[obj_id][0]], [by, after[obj_id][1]], color="#222222", linewidth=1)
        ax.text(after[obj_id][0] + 0.4, after[obj_id][1] + 0.4, obj_id, fontsize=7)
    ax.set_title(title)
    ax.set_xlabel("Centroid X")
    ax.set_ylabel("Centroid Y")
    ax.legend()
    path = VIS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_heatmap(matrix: dict[str, Any]) -> Path:
    labels = [row["surgery"] for row in matrix["rows"]]
    values = [
        [
            abs(float(row["disc_height_change"]["percent_change"] or 0.0)),
            abs(float(row["alignment_change"]["delta"] or 0.0)),
            abs(float(row["curvature_change"]["percent_change"] or 0.0)),
            abs(float(row["load_redistribution"]["percent_change"] or 0.0)),
            len(row["structures_affected"]),
        ]
        for row in matrix["rows"]
    ]
    columns = ["Height %", "Align", "Curv %", "Load %", "Affected"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.imshow(values, cmap="magma", aspect="auto")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xticks(range(len(columns)), labels=columns)
    for y, row in enumerate(values):
        for x, value in enumerate(row):
            ax.text(x, y, f"{value:.2f}", ha="center", va="center", color="white", fontsize=8)
    ax.set_title("Surgical Geometry-Aware Comparison")
    path = VIS_DIR / "surgical_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def phase7_limitations(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entries = {}
    for name, result in results.items():
        entries[name] = {
            "what_is_geometric": [
                "Disc height/space change",
                "Adjacent vertebra centroid translation",
                "Graph relationship or surgical object creation",
                "Measurement rebuild from modified geometry proxies",
            ],
            "what_is_estimated": [
                "Load redistribution proxy",
                "Stress/risk scalar proxy",
                "Curvature from centroid angles",
                "Foraminal/canal consequences through simplified geometry",
            ],
            "what_is_unknown": [
                "Material properties",
                "Patient-specific tissue response",
                "Implant/device physics",
                "True post-operative biomechanics",
            ],
            "what_requires_biomechanics": [
                "Finite element stress/strain",
                "Boundary conditions",
                "Muscle/ligament forces",
                "Contact mechanics",
            ],
            "what_requires_clinical_validation": [
                "Measurement accuracy",
                "Surgical outcome realism",
                "Longitudinal progression",
                "Decision support validity",
            ],
            "clinical_validity_claim": "none",
        }
    return {
        "generated_utc": utc_now(),
        "scope": "Honesty check for geometry-aware surgery simulations.",
        "surgeries": entries,
        "not_medical_advice": True,
    }


def dashboard(results: dict[str, dict[str, Any]], matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "current_state": "clinical_state_vector.json",
        "surgery_options": [
            {"id": key, "scenario_id": value["scenario_id"], "workflow": value["workflow"]}
            for key, value in results.items()
        ],
        "predicted_outcomes": matrix["rows"],
        "affected_structures": {
            row["surgery"]: row["structures_affected"] for row in matrix["rows"]
        },
        "confidence": {
            "geometry_rebuild": "MEDIUM",
            "load_proxy": "LOW",
            "clinical_realism": "LOW",
            "reason": "Anatomy changes precede metric rebuild, but no physical calibration, FE model, or clinical validation exists.",
        },
        "warnings": [
            "No diagnosis.",
            "No treatment recommendation.",
            "No clinical claims.",
            "Geometry-aware does not mean biomechanically validated.",
        ],
    }


def report(results: dict[str, dict[str, Any]], matrix: dict[str, Any]) -> str:
    surgeries = ", ".join(results.keys())
    structures = sorted({s for row in matrix["rows"] for s in row["structures_affected"]})
    return "\n".join(
        [
            "ORTHOTWIN PHASE 7 GEOMETRY-AWARE SURGERY REPORT",
            "",
            "1. Supported surgeries:",
            surgeries,
            "",
            "2. Structures modified:",
            ", ".join(structures),
            "",
            "3. Measurements recomputed:",
            "disc heights, relative spacing, alignment, slippage, curvature, load distribution, clinical state vector, graph metrics.",
            "",
            "4. Assumptions remaining:",
            "Rigid vertebra centroid proxies, simplified disc-space expansion, placeholder implant/spacer objects, and deterministic load proxies.",
            "",
            "5. Still not physically validated:",
            "No trusted spacing calibration, no finite element model, no material model, no boundary conditions, no clinical outcome validation.",
            "",
            "6. Required for clinical realism:",
            "Validated image spacing, radiologist-reviewed measurements, device geometry, tissue/material properties, finite element/contact mechanics, and prospective outcome validation.",
            "",
            "Architecture upgrade summary:",
            "Phase 7 changes the causal order from metric edits to anatomy edits followed by metric rebuild.",
            "",
            "No diagnosis. No treatment recommendation. No clinical claims.",
        ]
    )


def validate(module_paths: list[Path], output_paths: list[Path], rebuilt_paths: list[Path], visualization_paths: list[Path]) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "all_modules_exist": all(path.exists() for path in module_paths),
        "all_outputs_exist": all(path.exists() for path in output_paths),
        "all_rebuilt_states_generated": all(path.exists() for path in rebuilt_paths),
        "all_visualizations_generated": all(path.exists() for path in visualization_paths),
        "modules": [{"path": str(path), "exists": path.exists()} for path in module_paths],
        "outputs": [{"path": str(path), "exists": path.exists()} for path in output_paths],
        "rebuilt_states": [{"path": str(path), "exists": path.exists()} for path in rebuilt_paths],
        "visualizations": [{"path": str(path), "exists": path.exists()} for path in visualization_paths],
    }


def main() -> None:
    for path in (STATE_DIR, REPORT_DIR, VIS_DIR, MANIFEST_DIR):
        path.mkdir(parents=True, exist_ok=True)

    schema_path = write_json(STATE_DIR / "surgical_object_schema.json", surgical_object_schema())
    objects_path = write_json(STATE_DIR / "surgical_objects.json", build_surgical_objects())

    implant = simulate_implant_geometry()
    fusion = simulate_fusion_geometry()
    spacer = simulate_spacer_geometry()
    alignment = run_alignment_correction()
    results = {
        "implant": implant,
        "fusion": fusion,
        "spacer": spacer,
        "alignment_correction": alignment,
    }
    rebuilt = {name: load_rebuilt(result) for name, result in results.items()}
    matrix = compare_surgical_outcomes(results, rebuilt)

    implant_plot = plot_before_after(implant, "Implant Before/After Geometry", "implant_before_after.png")
    fusion_plot = plot_before_after(fusion, "Fusion Before/After Geometry", "fusion_before_after.png")
    spacer_plot = plot_before_after(spacer, "Spacer Before/After Geometry", "spacer_before_after.png")
    alignment_plot = plot_before_after(alignment, "Alignment Before/After Geometry", "alignment_before_after.png")
    heatmap_plot = plot_heatmap(matrix)
    visualizations = [implant_plot, fusion_plot, spacer_plot, alignment_plot, heatmap_plot]

    limitations_path = write_json(REPORT_DIR / "phase7_limitations.json", phase7_limitations(results))
    dashboard_path = write_json(REPORT_DIR / "surgical_dashboard.json", dashboard(results, matrix))
    report_path = write_text(REPORT_DIR / "phase7_geometry_aware_surgery_report.txt", report(results, matrix))
    validation_path = REPORT_DIR / "phase7_validation_report.json"

    module_paths = [
        PROJECT_ROOT / "simulation" / "surgery" / "__init__.py",
        PROJECT_ROOT / "simulation" / "surgery" / "surgical_objects.py",
        PROJECT_ROOT / "simulation" / "surgery" / "anatomical_modification_engine.py",
        PROJECT_ROOT / "simulation" / "surgery" / "implant_simulation_v2.py",
        PROJECT_ROOT / "simulation" / "surgery" / "fusion_simulation_v2.py",
        PROJECT_ROOT / "simulation" / "surgery" / "spacer_simulation.py",
        PROJECT_ROOT / "simulation" / "surgery" / "state_rebuilder.py",
        PROJECT_ROOT / "simulation" / "surgery" / "surgical_outcome_comparator.py",
        PROJECT_ROOT / "simulation" / "surgery" / "phase7_geometry_aware_surgery_engine.py",
    ]
    rebuilt_paths = [Path(result["rebuilt_state_file"]) for result in results.values()]
    output_paths = [
        schema_path,
        objects_path,
        STATE_DIR / "implant_geometry_result.json",
        STATE_DIR / "fusion_geometry_result.json",
        STATE_DIR / "spacer_geometry_result.json",
        STATE_DIR / "alignment_geometry_result.json",
        REPORT_DIR / "surgical_comparison_matrix.json",
        dashboard_path,
        limitations_path,
        report_path,
    ]
    validation = validate(module_paths, output_paths, rebuilt_paths, visualizations)
    write_json(validation_path, validation)
    manifest_path = write_json(
        MANIFEST_DIR / "phase7_manifest.json",
        {
            "generated_utc": utc_now(),
            "phase": "phase7_geometry_aware_surgery_engine",
            "files": [{"path": str(path), "exists": path.exists()} for path in output_paths + rebuilt_paths + visualizations + [validation_path]],
            "all_files_exist": all(path.exists() for path in output_paths + rebuilt_paths + visualizations + [validation_path]),
        },
    )

    print("ORTHOTWIN PHASE 7 COMPLETE")
    print("Supported Surgeries: implant, fusion, spacer, alignment_correction")
    print("Affected Structures:")
    for row in matrix["rows"]:
        print(f"- {row['surgery']}: {', '.join(row['structures_affected'])}")
    print("Recomputed Measurements: disc heights, relative spacing, alignment, slippage, curvature, load distribution, clinical state vector, graph metrics")
    print("Architecture Upgrade Summary: interventions now modify surgical geometry first, then rebuild downstream measurements.")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
