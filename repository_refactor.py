"""Repository audit, refactor, and Stage 3 foundation builder.

This script reorganizes existing OrthoTwin artifacts into a cleaner architecture
without retraining, inference, segmentation recomputation, mask modification, or
data deletion. Moves are conservative and never overwrite existing paths.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ORTHOTWIN_ROOT = Path(__file__).resolve().parent
REPO_ROOT = ORTHOTWIN_ROOT.parent


FOLDER_STRUCTURE = [
    "data/raw",
    "data/processed",
    "data/cleaned",
    "models/checkpoints",
    "models/configs",
    "measurements/geometry",
    "measurements/alignment",
    "measurements/discs",
    "measurements/vertebrae",
    "state/patient_states",
    "state/graphs",
    "state/transitions",
    "simulation/interventions",
    "simulation/propagation",
    "simulation/biomechanics",
    "visualization/segmentation",
    "visualization/reconstruction",
    "visualization/state",
    "visualization/simulation",
    "reports/phase1",
    "reports/phase2",
    "reports/phase3",
    "archive",
    "docs",
    "manifests",
]


SCRIPT_DESTINATIONS = {
    "simulation_engine.py": "simulation/interventions/simulation_engine.py",
    "state_transition.py": "simulation/propagation/state_transition.py",
    "stage2_engine.py": "simulation/propagation/stage2_engine.py",
    "visualization.py": "visualization/state/visualization.py",
    "report_generator.py": "reports/phase3/report_generator.py",
}


ROOT_SCRIPT_DESTINATIONS = {
    "test_ct.py": "archive/test_ct.py",
    "test_mha.py": "archive/test_mha.py",
    "app.py": "archive/app.py",
}


EXPECTED_PIPELINE = [
    "MRI",
    "Segmentation",
    "Cleanup",
    "Measurements",
    "State Vector",
    "Graph",
    "Simulation",
]


@dataclass
class MoveRecord:
    source: str
    destination: str
    status: str
    reason: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def safe_move(source: Path, destination: Path) -> MoveRecord:
    if not source.exists():
        return MoveRecord(str(source), str(destination), "skipped", "source_missing")
    if destination.exists():
        return MoveRecord(str(source), str(destination), "skipped", "destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return MoveRecord(str(source), str(destination), "moved", "ok")


def create_folder_structure() -> None:
    for folder in FOLDER_STRUCTURE:
        (ORTHOTWIN_ROOT / folder).mkdir(parents=True, exist_ok=True)


def file_extension(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".nii.gz"):
        return ".nii.gz"
    return path.suffix.lower()


def categorize(path: Path) -> str:
    name = path.name.lower()
    ext = file_extension(path)
    parts = [part.lower() for part in path.parts]
    if ext == ".dcm":
        return "raw_dicom"
    if ext in {".nii.gz", ".mha", ".bmp"}:
        return "raw_image"
    if ext in {".pth", ".pt"}:
        return "model_checkpoint"
    if ext in {".npy"} or "clean" in name and ext in {".json", ".pkl"}:
        return "cleaned_data"
    if "spine_coordinate_system" in name:
        return "alignment_measurement"
    if "disc" in name and ext == ".json":
        return "disc_measurement"
    if "vertebr" in name and ext == ".json":
        return "vertebral_measurement"
    if "measurement" in name or "reconstructed_structures" in name or "mesh" in name or "pca" in name:
        return "geometry_measurement"
    if "patient_state_vector" in name or "patient_state_after" in name:
        return "patient_state"
    if "spine_graph" in name or "relationship" in name or "centerline" in name:
        return "state_graph"
    if "transition" in name:
        return "state_transition"
    if "report" in name or ext in {".txt", ".md"}:
        return "report_or_doc"
    if ext == ".png":
        if "loss" in name or "dice" in name or "seg" in name or "candidate" in name:
            return "segmentation_visualization"
        if "graph" in name or "centerline" in name or "alignment" in name or "load" in name or "relative" in name:
            return "state_visualization"
        return "visualization"
    if ext == ".py":
        if "simulation" in parts or "engine" in name or "digital_twin" in name:
            return "source_code"
        return "script"
    if ext in {".csv", ".json"}:
        return "tabular_or_metadata"
    if ext in {".zip", ".pdf"}:
        return "archive_reference"
    return "other"


def scan_inventory() -> list[dict[str, Any]]:
    inventory = []
    for root, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in {"__pycache__", ".git"} and dirname != ".codex"
        ]
        for filename in filenames:
            path = Path(root) / filename
            try:
                stat = path.stat()
            except OSError:
                continue
            inventory.append(
                {
                    "filename": path.name,
                    "extension": file_extension(path),
                    "full_path": str(path.resolve()),
                    "relative_path": rel(path),
                    "size": stat.st_size,
                    "creation_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "last_modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "category": categorize(path),
                }
            )
    return inventory


def target_for_file(path: Path) -> Path | None:
    name = path.name
    lower = name.lower()
    ext = file_extension(path)
    parent_parts = [part.lower() for part in path.parts]

    if ORTHOTWIN_ROOT in path.parents:
        if "stage2" in parent_parts:
            if ext == ".png":
                return ORTHOTWIN_ROOT / "visualization/state" / name
            if "spine_graph" in lower or "relationship" in lower or "centerline" in lower:
                return ORTHOTWIN_ROOT / "state/graphs" / name
            if "patient_state_vector_v2" in lower:
                return ORTHOTWIN_ROOT / "state/patient_states" / name
            if "validation" in lower or "manifest" in lower:
                return ORTHOTWIN_ROOT / "manifests" / name
            if "readiness_report" in lower:
                return ORTHOTWIN_ROOT / "reports/phase2" / name
            if "relative_disc" in lower:
                return ORTHOTWIN_ROOT / "measurements/discs" / name
            if "relative_vertebral" in lower:
                return ORTHOTWIN_ROOT / "measurements/vertebrae" / name
            if "alignment" in lower or "load_path" in lower:
                return ORTHOTWIN_ROOT / "measurements/alignment" / name
        if path.parent == ORTHOTWIN_ROOT and name in SCRIPT_DESTINATIONS:
            return ORTHOTWIN_ROOT / SCRIPT_DESTINATIONS[name]
        if path.parent == ORTHOTWIN_ROOT and lower in {"digital_twin.py", "state_builder.py", "comparison.py", "demo.py", "__init__.py"}:
            return None

    if path.parent == REPO_ROOT and name in ROOT_SCRIPT_DESTINATIONS:
        return ORTHOTWIN_ROOT / ROOT_SCRIPT_DESTINATIONS[name]
    if ext in {".pth", ".pt"}:
        return ORTHOTWIN_ROOT / "models/checkpoints" / name
    if ext == ".json" and "weighted" in lower:
        return ORTHOTWIN_ROOT / "reports/phase1" / name
    if ext == ".png" and ("loss" in lower or "dice" in lower or "candidate" in lower):
        return ORTHOTWIN_ROOT / "visualization/segmentation" / name
    if ext == ".pkl" and "reconstructed_structures" in lower:
        return ORTHOTWIN_ROOT / "measurements/geometry" / name
    if ext == ".json" and "spine_coordinate_system" in lower:
        return ORTHOTWIN_ROOT / "measurements/alignment" / name
    if ext == ".json" and "disc" in lower:
        return ORTHOTWIN_ROOT / "measurements/discs" / name
    if ext == ".json" and "vertebr" in lower:
        return ORTHOTWIN_ROOT / "measurements/vertebrae" / name
    if ext == ".json" and any(token in lower for token in ["measurement", "component", "mesh", "pca", "findings"]):
        return ORTHOTWIN_ROOT / "measurements/geometry" / name
    if ext == ".json" and "patient_state" in lower:
        return ORTHOTWIN_ROOT / "state/patient_states" / name
    if ext == ".txt" and "report" in lower:
        return ORTHOTWIN_ROOT / "reports/phase3" / name
    if ext == ".md":
        return ORTHOTWIN_ROOT / "docs" / name
    if ext in {".csv", ".nii.gz", ".mha", ".bmp"}:
        return ORTHOTWIN_ROOT / "data/raw" / name
    if ext == ".zip":
        return ORTHOTWIN_ROOT / "archive" / name
    if ext == ".pdf":
        return ORTHOTWIN_ROOT / "docs" / name
    return None


def move_known_directories() -> list[MoveRecord]:
    records = []
    raw_root = ORTHOTWIN_ROOT / "data/raw"
    for entry in REPO_ROOT.iterdir():
        if not entry.is_dir() or entry == ORTHOTWIN_ROOT:
            continue
        if re.fullmatch(r"\d+", entry.name):
            records.append(safe_move(entry, raw_root / "dicom_series" / entry.name))
        elif entry.name == "spine_segmentation_dataset":
            records.append(safe_move(entry, raw_root / "spine_segmentation_dataset"))
        elif entry.name in {"OrthoTwin_Final_Archive", "OrthoTwin_Showcase"}:
            records.append(safe_move(entry, ORTHOTWIN_ROOT / "archive" / entry.name))
        elif entry.name in {"Spine_Project", "Colab Notebooks", "Research paper"}:
            records.append(safe_move(entry, ORTHOTWIN_ROOT / "archive" / entry.name))
    return records


def move_known_files() -> list[MoveRecord]:
    records = []
    candidates = []
    for root, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in {"__pycache__", ".git"} and dirname != ".codex"
        ]
        for filename in filenames:
            path = Path(root) / filename
            target = target_for_file(path)
            if target and path.resolve() != target.resolve():
                if target.resolve().is_relative_to(path.resolve()) if hasattr(Path, "is_relative_to") else False:
                    continue
                candidates.append((path, target))

    for source, destination in sorted(candidates, key=lambda pair: len(pair[0].parts)):
        if source.exists() and source.resolve() != destination.resolve():
            records.append(safe_move(source, destination))
    return records


def purpose_for(path: Path, category: str) -> str:
    name = path.name.lower()
    if category == "model_checkpoint":
        return "Stored segmentation/model checkpoint artifact from Phase 1."
    if category == "raw_dicom":
        return "Raw imaging input used before segmentation."
    if category == "raw_image":
        return "Raw or reference image volume used for ingestion/testing."
    if category == "geometry_measurement":
        return "Geometry, reconstruction, component, mesh, or PCA measurement artifact."
    if category == "alignment_measurement":
        return "Spine coordinate system or local/global alignment measurement."
    if category == "disc_measurement":
        return "Disc-specific measurement or ranking artifact."
    if category == "vertebral_measurement":
        return "Vertebra-specific measurement artifact."
    if category == "patient_state":
        return "Digital twin patient state representation."
    if category == "state_graph":
        return "Connected state graph, centerline, or relationship artifact."
    if "engine.py" in name:
        return "Pipeline engine or deterministic state transformation module."
    if category.endswith("visualization") or category == "visualization":
        return "Visualization output for segmentation, reconstruction, state, or simulation."
    if category == "report_or_doc":
        return "Human-readable report or documentation."
    return "Indexed project artifact."


def phase_for(path: Path, category: str) -> str:
    text = str(path).lower()
    if category in {"raw_dicom", "raw_image", "model_checkpoint", "segmentation_visualization"}:
        return "phase1"
    if category in {"geometry_measurement", "alignment_measurement", "disc_measurement", "vertebral_measurement"}:
        return "phase2"
    if category in {"patient_state", "state_graph", "state_transition"} or "digital_twin" in text or "stage2" in text:
        return "phase3"
    if "biomechanics" in text or "propagation" in text:
        return "stage3_foundation"
    return "unknown"


def generated_by(path: Path, category: str) -> str | None:
    name = path.name.lower()
    if "patient_state_vector_v2" in name or "spine_graph" in name or "centerline" in name or "relationship" in name or "load_path" in name:
        return "stage2_engine.py"
    if "patient_state_vector" in name:
        return "state_builder.py"
    if "digital_twin_report" in name:
        return "report_generator.py"
    if "state_change_report" in name:
        return "comparison.py"
    if category == "model_checkpoint":
        return "Phase 1 training pipeline"
    if category in {"geometry_measurement", "alignment_measurement", "disc_measurement", "vertebral_measurement"}:
        return "Phase 2 measurement pipeline"
    return None


def consumed_by(path: Path, category: str) -> list[str]:
    name = path.name.lower()
    consumers = []
    if category in {"geometry_measurement", "alignment_measurement", "disc_measurement", "vertebral_measurement"}:
        consumers.extend(["state_builder.py", "stage2_engine.py"])
    if "patient_state_vector" in name:
        consumers.extend(["digital_twin.py", "stage2_engine.py", "propagation_engine.py"])
    if "spine_graph" in name:
        consumers.append("propagation_engine.py")
    if "load_path_model" in name:
        consumers.append("biomechanics_engine.py")
    if category == "model_checkpoint":
        consumers.append("archived inference/training scripts")
    return consumers


def dependencies_for(path: Path, category: str) -> list[str]:
    name = path.name.lower()
    if "patient_state_vector_v2" in name:
        return [
            "patient_state_vector.json",
            "spine_graph.json",
            "disc_relationships.json",
            "relative_disc_metrics.json",
            "local_alignment_metrics.json",
            "load_path_model.json",
        ]
    if "spine_graph" in name:
        return ["patient_state_vector.json"]
    if "load_path_model" in name:
        return ["relative_disc_metrics.json", "local_alignment_metrics.json"]
    if "patient_state_vector" in name:
        return [
            "patient_alpha_clean_measurements.json",
            "patient_alpha_disc_ranking.json",
            "patient_alpha_component_analysis.json",
            "spine_coordinate_system.json",
        ]
    if category in {"disc_measurement", "vertebral_measurement", "geometry_measurement", "alignment_measurement"}:
        return ["reconstructed_structures.pkl or Phase 2 measurement inputs"]
    return []


def build_master_index(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = []
    for item in inventory:
        path = Path(item["full_path"])
        category = item["category"]
        index.append(
            {
                **item,
                "purpose": purpose_for(path, category),
                "phase_created": phase_for(path, category),
                "dependencies": dependencies_for(path, category),
                "generated_by": generated_by(path, category),
                "consumed_by": consumed_by(path, category),
            }
        )
    return index


def build_dataflow(master_index: list[dict[str, Any]]) -> dict[str, Any]:
    stage_files: dict[str, list[str]] = {stage: [] for stage in EXPECTED_PIPELINE}
    for item in master_index:
        category = item["category"]
        rel_path = item["relative_path"]
        if category in {"raw_dicom", "raw_image"}:
            stage_files["MRI"].append(rel_path)
        elif category == "model_checkpoint" or "segmentation" in category:
            stage_files["Segmentation"].append(rel_path)
        elif category == "cleaned_data":
            stage_files["Cleanup"].append(rel_path)
        elif "measurement" in category:
            stage_files["Measurements"].append(rel_path)
        elif category == "patient_state":
            stage_files["State Vector"].append(rel_path)
        elif category == "state_graph":
            stage_files["Graph"].append(rel_path)
        elif "simulation" in rel_path.lower() or "biomechanics" in rel_path.lower():
            stage_files["Simulation"].append(rel_path)
    return {
        "pipeline": EXPECTED_PIPELINE,
        "dependencies": [
            {"from": EXPECTED_PIPELINE[index], "to": EXPECTED_PIPELINE[index + 1]}
            for index in range(len(EXPECTED_PIPELINE) - 1)
        ],
        "stage_files": stage_files,
    }


def build_project_graph(master_index: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    edges = []
    by_filename = defaultdict(list)
    for item in master_index:
        by_filename[item["filename"]].append(item["relative_path"])
        node_type = "file"
        if item["extension"] == ".py":
            node_type = "script"
        elif item["category"] == "report_or_doc":
            node_type = "report"
        elif "measurement" in item["category"]:
            node_type = "measurement"
        elif item["category"] == "patient_state":
            node_type = "state"
        nodes.append(
            {
                "id": item["relative_path"],
                "label": item["filename"],
                "type": node_type,
                "category": item["category"],
            }
        )
    for item in master_index:
        source = item["relative_path"]
        generator = item.get("generated_by")
        if generator and generator in by_filename:
            for script_path in by_filename[generator]:
                edges.append({"source": script_path, "target": source, "type": "produces"})
        for dependency in item.get("dependencies", []):
            for dep_path in by_filename.get(Path(dependency).name, []):
                edges.append({"source": source, "target": dep_path, "type": "depends_on"})
        for consumer in item.get("consumed_by", []):
            for consumer_path in by_filename.get(Path(consumer).name, []):
                edges.append({"source": source, "target": consumer_path, "type": "consumed_by"})
    return {"nodes": nodes, "edges": edges}


def write_stage3_placeholders() -> list[Path]:
    biomech = ORTHOTWIN_ROOT / "simulation/biomechanics"
    propagation = ORTHOTWIN_ROOT / "simulation/propagation"
    files = {
        biomech / "biomechanics_engine.py": '''"""Stage 3 biomechanics engine interface.

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
''',
        propagation / "propagation_engine.py": '''"""Stage 3 propagation engine interface.

Placeholder only. No intervention propagation is implemented in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class PropagationInput:
    before_state: dict[str, Any]
    action: dict[str, Any]
    graph: dict[str, Any]
    local_metrics: dict[str, Any]
    load_model: dict[str, Any]


@dataclass
class PropagationOutput:
    after_state: dict[str, Any]
    affected_nodes: list[str]
    transition_log: dict[str, Any]


class PropagationEngine(Protocol):
    """Interface expected from future neighbor-aware state propagation."""

    def propagate(self, inputs: PropagationInput) -> PropagationOutput:
        """Apply a deterministic action to connected structures when implemented."""
''',
        biomech / "outcome_comparator.py": '''"""Stage 3 outcome comparator interface.

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
''',
    }
    written = []
    for path, content in files.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def validate_pipeline(master_index: list[dict[str, Any]], dataflow: dict[str, Any]) -> dict[str, Any]:
    stage_counts = {stage: len(paths) for stage, paths in dataflow["stage_files"].items()}
    missing_links = []
    for stage in EXPECTED_PIPELINE:
        if stage_counts.get(stage, 0) == 0:
            missing_links.append(f"No indexed files found for stage: {stage}")
    dependency_issues = []
    filenames = {item["filename"] for item in master_index}
    for item in master_index:
        for dependency in item.get("dependencies", []):
            dep_name = Path(dependency).name
            if dep_name not in filenames and " or " not in dependency:
                dependency_issues.append(
                    {
                        "file": item["relative_path"],
                        "missing_dependency": dependency,
                    }
                )
    score = 100
    score -= len(missing_links) * 12
    score -= min(30, len(dependency_issues) * 2)
    return {
        "validated_utc": utc_now(),
        "pipeline": EXPECTED_PIPELINE,
        "stage_counts": stage_counts,
        "complete_chain_available": not missing_links,
        "missing_links": missing_links,
        "dependency_issues": dependency_issues,
        "digital_twin_readiness_score": max(0, score),
    }


def architecture_report(dataflow: dict[str, Any], validation: dict[str, Any]) -> str:
    folder_lines = "\n".join(f"- `{folder}/`" for folder in FOLDER_STRUCTURE)
    flow_lines = "\n".join(f"- {edge['from']} -> {edge['to']}" for edge in dataflow["dependencies"])
    missing = validation["missing_links"] or ["None"]
    missing_lines = "\n".join(f"- {item}" for item in missing)
    return f"""# OrthoTwin System Architecture

Generated: {utc_now()}

## Project Overview

OrthoTwin is organized as a deterministic digital twin pipeline. The repository
keeps raw imaging, trained checkpoint artifacts, measurement outputs, patient
state vectors, graph representations, reports, and future simulation interfaces
in separate folders.

No retraining, inference, segmentation recomputation, mask editing, diagnosis,
or surgery simulation is performed by the refactor.

## Folder Structure

{folder_lines}

## Data Flow

{flow_lines}

## Digital Twin Design

The current digital twin state is built from cleaned geometry, disc ranking,
component analysis, and spine coordinate measurements. Stage 2 adds graph
structure, disc-vertebra relationships, relative metrics, centerline geometry,
local alignment metrics, and a rule-based load approximation layer.

## Future Simulation Design

Stage 3 starts with interfaces for biomechanics, graph-based propagation, and
outcome comparison. These interfaces define expected inputs and outputs only;
they intentionally do not implement biomechanics or surgical simulation.

## Biomechanics Roadmap

Required future inputs include material properties, calibrated loads, boundary
conditions, ligament/facet data, patient scale, solver settings, and validation
targets. Until those are available, load values remain deterministic geometric
approximations rather than physics.

## Pipeline Validation

- Readiness score: {validation['digital_twin_readiness_score']}
- Complete chain available: {validation['complete_chain_available']}

## Missing Links

{missing_lines}
"""


def final_manifest(master_index: list[dict[str, Any]], pipeline_validation: dict[str, Any]) -> dict[str, Any]:
    files = []
    filenames = {item["filename"] for item in master_index}
    broken_refs = []
    for item in master_index:
        exists = Path(item["full_path"]).exists()
        files.append(
            {
                "path": item["full_path"],
                "relative_path": item["relative_path"],
                "exists": exists,
                "category": item["category"],
            }
        )
        for dependency in item.get("dependencies", []):
            dep_name = Path(dependency).name
            if dep_name not in filenames and " or " not in dependency:
                broken_refs.append({"file": item["relative_path"], "dependency": dependency})
    return {
        "generated_utc": utc_now(),
        "file_count": len(files),
        "all_files_exist": all(item["exists"] for item in files),
        "dependency_resolution": {
            "all_dependencies_resolve": not broken_refs,
            "broken_references": broken_refs,
        },
        "pipeline_validation": pipeline_validation,
        "files": files,
    }


def summarize(master_index: list[dict[str, Any]], pipeline_validation: dict[str, Any]) -> dict[str, Any]:
    category_counts = Counter(item["category"] for item in master_index)
    total_states = sum(1 for item in master_index if item["category"] in {"patient_state", "state_graph", "state_transition"})
    total_measurements = sum(1 for item in master_index if "measurement" in item["category"])
    total_reports = sum(1 for item in master_index if item["category"] == "report_or_doc" or "reports" in item["relative_path"].lower())
    problems = []
    problems.extend(pipeline_validation["missing_links"])
    problems.extend(
        f"Missing dependency: {issue['file']} -> {issue['missing_dependency']}"
        for issue in pipeline_validation["dependency_issues"]
    )
    return {
        "total_files": len(master_index),
        "total_states": total_states,
        "total_measurement_files": total_measurements,
        "total_reports": total_reports,
        "digital_twin_readiness_score": pipeline_validation["digital_twin_readiness_score"],
        "category_counts": dict(category_counts),
        "architectural_problems": problems,
    }


def run_refactor() -> dict[str, Any]:
    create_folder_structure()
    initial_inventory = scan_inventory()
    (ORTHOTWIN_ROOT / "manifests").mkdir(parents=True, exist_ok=True)
    (ORTHOTWIN_ROOT / "manifests/project_inventory_initial.json").write_text(
        json.dumps(initial_inventory, indent=2), encoding="utf-8"
    )

    moves = move_known_directories()
    moves.extend(move_known_files())
    write_stage3_placeholders()

    final_inventory = scan_inventory()
    project_inventory_path = ORTHOTWIN_ROOT / "manifests/project_inventory.json"
    project_inventory_path.write_text(json.dumps(final_inventory, indent=2), encoding="utf-8")

    master_index = build_master_index(final_inventory)
    master_index_path = ORTHOTWIN_ROOT / "manifests/master_index.json"
    master_index_path.write_text(json.dumps(master_index, indent=2), encoding="utf-8")

    dataflow = build_dataflow(master_index)
    dataflow_path = ORTHOTWIN_ROOT / "manifests/dataflow.json"
    dataflow_path.write_text(json.dumps(dataflow, indent=2), encoding="utf-8")

    project_graph = build_project_graph(master_index)
    project_graph_path = ORTHOTWIN_ROOT / "manifests/project_graph.json"
    project_graph_path.write_text(json.dumps(project_graph, indent=2), encoding="utf-8")

    pipeline_validation = validate_pipeline(master_index, dataflow)
    pipeline_validation_path = ORTHOTWIN_ROOT / "manifests/pipeline_validation.json"
    pipeline_validation_path.write_text(json.dumps(pipeline_validation, indent=2), encoding="utf-8")

    architecture_path = ORTHOTWIN_ROOT / "docs/system_architecture.md"
    architecture_path.write_text(architecture_report(dataflow, pipeline_validation), encoding="utf-8")

    manifest = final_manifest(master_index, pipeline_validation)
    manifest_path = ORTHOTWIN_ROOT / "manifests/final_repository_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    move_log_path = ORTHOTWIN_ROOT / "manifests/refactor_move_log.json"
    move_log_path.write_text(
        json.dumps([record.__dict__ for record in moves], indent=2), encoding="utf-8"
    )

    summary = summarize(master_index, pipeline_validation)
    summary_path = ORTHOTWIN_ROOT / "manifests/refactor_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "summary": summary,
        "paths": {
            "project_inventory": str(project_inventory_path),
            "master_index": str(master_index_path),
            "dataflow": str(dataflow_path),
            "project_graph": str(project_graph_path),
            "pipeline_validation": str(pipeline_validation_path),
            "system_architecture": str(architecture_path),
            "final_manifest": str(manifest_path),
            "move_log": str(move_log_path),
            "summary": str(summary_path),
        },
    }


def finalize_current_layout() -> dict[str, Any]:
    create_folder_structure()
    write_stage3_placeholders()

    final_inventory = scan_inventory()
    project_inventory_path = ORTHOTWIN_ROOT / "manifests/project_inventory.json"
    project_inventory_path.write_text(json.dumps(final_inventory, indent=2), encoding="utf-8")

    master_index = build_master_index(final_inventory)
    master_index_path = ORTHOTWIN_ROOT / "manifests/master_index.json"
    master_index_path.write_text(json.dumps(master_index, indent=2), encoding="utf-8")

    dataflow = build_dataflow(master_index)
    dataflow_path = ORTHOTWIN_ROOT / "manifests/dataflow.json"
    dataflow_path.write_text(json.dumps(dataflow, indent=2), encoding="utf-8")

    project_graph = build_project_graph(master_index)
    project_graph_path = ORTHOTWIN_ROOT / "manifests/project_graph.json"
    project_graph_path.write_text(json.dumps(project_graph, indent=2), encoding="utf-8")

    pipeline_validation = validate_pipeline(master_index, dataflow)
    pipeline_validation_path = ORTHOTWIN_ROOT / "manifests/pipeline_validation.json"
    pipeline_validation_path.write_text(json.dumps(pipeline_validation, indent=2), encoding="utf-8")

    architecture_path = ORTHOTWIN_ROOT / "docs/system_architecture.md"
    architecture_path.write_text(architecture_report(dataflow, pipeline_validation), encoding="utf-8")

    manifest = final_manifest(master_index, pipeline_validation)
    manifest_path = ORTHOTWIN_ROOT / "manifests/final_repository_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = summarize(master_index, pipeline_validation)
    summary_path = ORTHOTWIN_ROOT / "manifests/refactor_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "summary": summary,
        "paths": {
            "project_inventory": str(project_inventory_path),
            "master_index": str(master_index_path),
            "dataflow": str(dataflow_path),
            "project_graph": str(project_graph_path),
            "pipeline_validation": str(pipeline_validation_path),
            "system_architecture": str(architecture_path),
            "final_manifest": str(manifest_path),
            "summary": str(summary_path),
        },
    }


if __name__ == "__main__":
    result = finalize_current_layout() if os.environ.get("ORTHOTWIN_FINALIZE_ONLY") else run_refactor()
    summary = result["summary"]
    print("Repository Audit Complete")
    print(f"Total Files: {summary['total_files']}")
    print(f"Total States: {summary['total_states']}")
    print(f"Total Measurement Files: {summary['total_measurement_files']}")
    print(f"Total Reports: {summary['total_reports']}")
    print(f"Digital Twin Readiness Score: {summary['digital_twin_readiness_score']}")
    print("Architectural Problems:")
    if summary["architectural_problems"]:
        for problem in summary["architectural_problems"]:
            print(f"- {problem}")
    else:
        print("- None")
