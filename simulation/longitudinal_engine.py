"""Phase 6 longitudinal digital twin and evidence engine.

Uses existing OrthoTwin outputs only. The longitudinal model is deterministic,
configurable, and assumption-explicit. It is not a clinical predictor, medical
advice system, regulatory product, or validated biomechanics engine.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLINICAL_STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
STATE_V2_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector_v2.json"
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
PHASE5_DASHBOARD_PATH = PROJECT_ROOT / "reports" / "phase5" / "dashboard_state.json"
PHASE5_RANKING_PATH = PROJECT_ROOT / "reports" / "phase5" / "scenario_ranking.json"
PHASE45_CALIBRATION_PATH = PROJECT_ROOT / "measurements" / "calibration" / "physical_calibration.json"
PROJECT_INVENTORY_PATH = PROJECT_ROOT / "manifests" / "project_inventory.json"

LONGITUDINAL_DIR = PROJECT_ROOT / "state" / "longitudinal"
EVIDENCE_DIR = PROJECT_ROOT / "reports" / "phase6" / "evidence"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase6"
VIS_DIR = PROJECT_ROOT / "visualization" / "longitudinal"
MANIFEST_DIR = PROJECT_ROOT / "manifests"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def time_model() -> dict[str, Any]:
    return {
        "model": "orthtwin_longitudinal_time_model_v1",
        "generated_utc": utc_now(),
        "timelines": [
            {"id": "0_months", "months": 0, "years": 0.0, "label": "0 months"},
            {"id": "6_months", "months": 6, "years": 0.5, "label": "6 months"},
            {"id": "1_year", "months": 12, "years": 1.0, "label": "1 year"},
            {"id": "2_years", "months": 24, "years": 2.0, "label": "2 years"},
            {"id": "5_years", "months": 60, "years": 5.0, "label": "5 years"},
            {"id": "10_years", "months": 120, "years": 10.0, "label": "10 years"},
        ],
        "notes": [
            "Time points are simulation checkpoints, not predicted clinical visits.",
            "No patient-specific temporal imaging exists in this repository.",
        ],
    }


def natural_progression_rules() -> dict[str, Any]:
    return {
        "model": "configurable_deterministic_progression_v1",
        "generated_utc": utc_now(),
        "physics_claim": "None. This is a rule-based state evolution scaffold.",
        "rules": {
            "disc_height_loss_per_year_fraction": 0.006,
            "disc_volume_loss_per_year_fraction": 0.004,
            "foraminal_area_loss_coupled_to_disc_height": 0.65,
            "canal_area_change_per_year_fraction": -0.001,
            "alignment_change_degrees_per_year": 0.12,
            "curvature_change_per_year_fraction": 0.008,
            "load_increase_per_disc_height_loss_fraction": 0.85,
            "stress_increase_per_load_delta": 0.45,
            "risk_score_cap": 1.0,
        },
        "configuration_policy": "All coefficients are stored here; no hidden progression constants are used by the engine.",
        "confidence": "LOW",
        "reason": "No longitudinal patient-specific follow-up data or validated biomechanics model is available.",
    }


def evolve_state(
    clinical_state: dict[str, Any],
    state_v2: dict[str, Any],
    graph: dict[str, Any],
    timeline: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    years = float(timeline["years"])
    output = {
        "patient_id": clinical_state.get("patient_id", "patient_alpha"),
        "schema_version": "longitudinal_future_state_v1",
        "generated_utc": utc_now(),
        "timeline": timeline,
        "clinical_state": deepcopy(clinical_state),
        "graph_state": deepcopy(graph),
        "progression_model": rules["model"],
        "not_diagnosis": True,
        "clinical_validity_claim": "none",
    }
    if years == 0:
        output["progression_delta"] = empty_delta()
        return output

    coeffs = rules["rules"]
    clinical = output["clinical_state"]

    height_factor = max(0.0, 1.0 - coeffs["disc_height_loss_per_year_fraction"] * years)
    volume_factor = max(0.0, 1.0 - coeffs["disc_volume_loss_per_year_fraction"] * years)
    curvature_factor = 1.0 + coeffs["curvature_change_per_year_fraction"] * years

    for disc in clinical.get("disc_heights", {}).values():
        for field in (
            "mean_height",
            "maximum_height",
            "minimum_height",
            "anterior_height",
            "posterior_height",
            "left_height",
            "right_height",
        ):
            if isinstance(disc.get(field), (int, float)):
                disc[field] *= height_factor
        disc["longitudinal_height_factor"] = height_factor

    for disc in clinical.get("disc_areas", {}).values():
        for field in (
            "average_cross_sectional_area",
            "projected_disc_footprint_area",
            "superior_surface_area",
            "inferior_surface_area",
        ):
            if isinstance(disc.get(field), (int, float)):
                disc[field] *= volume_factor
        disc["longitudinal_area_factor"] = volume_factor

    foraminal_factor = max(
        0.0,
        1.0
        - coeffs["disc_height_loss_per_year_fraction"]
        * years
        * coeffs["foraminal_area_loss_coupled_to_disc_height"],
    )
    for disc in clinical.get("foraminal_areas", {}).values():
        for field in ("left_foraminal_area", "right_foraminal_area"):
            if isinstance(disc.get(field), (int, float)):
                disc[field] *= foraminal_factor
        disc["longitudinal_area_factor"] = foraminal_factor

    canal_factor = max(0.0, 1.0 + coeffs["canal_area_change_per_year_fraction"] * years)
    for vertebra in clinical.get("canal_areas", {}).values():
        for field in ("canal_width", "canal_depth", "canal_area"):
            if isinstance(vertebra.get(field), (int, float)):
                vertebra[field] *= canal_factor
        vertebra["longitudinal_area_factor"] = canal_factor

    curvature = clinical.get("curvature", {})
    for field in ("global_curvature", "maximum_local_curvature"):
        if isinstance(curvature.get(field), (int, float)):
            curvature[field] *= curvature_factor
    for item in curvature.get("local_curvature", []):
        if isinstance(item.get("curvature_estimate"), (int, float)):
            item["curvature_estimate"] *= curvature_factor

    alignment_delta = coeffs["alignment_change_degrees_per_year"] * years
    for item in clinical.get("alignment", {}).get("disc_alignment", {}).values():
        for field in ("disc_angle_degrees", "disc_tilt_degrees"):
            if isinstance(item.get(field), (int, float)):
                item[field] += alignment_delta

    load_state = deepcopy(state_v2.get("load_metrics", {}))
    load_delta = (1.0 - height_factor) * coeffs["load_increase_per_disc_height_loss_fraction"]
    for item in load_state.get("structures", {}).values():
        old_load = float(item.get("relative_load_index", 1.0))
        old_stress = float(item.get("stress_score", 0.0))
        item["relative_load_index"] = old_load + load_delta
        item["stress_score"] = min(
            coeffs["risk_score_cap"], old_stress + load_delta * coeffs["stress_increase_per_load_delta"]
        )
        item["risk_score"] = min(coeffs["risk_score_cap"], item["relative_load_index"] * max(item["stress_score"], 0.01))
    output["load_distribution"] = load_state

    for disc in clinical.get("degeneration_features", {}).values():
        if isinstance(disc.get("height_loss_percent"), (int, float)):
            disc["height_loss_percent"] = min(100.0, disc["height_loss_percent"] + (1.0 - height_factor) * 100.0)
        if isinstance(disc.get("volume_loss_percent"), (int, float)):
            disc["volume_loss_percent"] = min(100.0, disc["volume_loss_percent"] + (1.0 - volume_factor) * 100.0)

    output["progression_delta"] = {
        "years": years,
        "disc_height_factor": height_factor,
        "disc_volume_factor": volume_factor,
        "foraminal_area_factor": foraminal_factor,
        "canal_area_factor": canal_factor,
        "curvature_factor": curvature_factor,
        "alignment_delta_degrees": alignment_delta,
        "load_delta": load_delta,
    }
    return output


def empty_delta() -> dict[str, Any]:
    return {
        "years": 0.0,
        "disc_height_factor": 1.0,
        "disc_volume_factor": 1.0,
        "foraminal_area_factor": 1.0,
        "canal_area_factor": 1.0,
        "curvature_factor": 1.0,
        "alignment_delta_degrees": 0.0,
        "load_delta": 0.0,
    }


def future_state_filename(timeline_id: str) -> str:
    if timeline_id == "0_months":
        return "future_state_0_months.json"
    return f"future_state_{timeline_id}.json"


def generate_visualizations(future_states: list[dict[str, Any]]) -> list[Path]:
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    labels = [state["timeline"]["label"] for state in future_states]
    x = [state["timeline"]["years"] for state in future_states]

    curvature = [
        float(state["clinical_state"].get("curvature", {}).get("global_curvature", 0.0))
        for state in future_states
    ]
    mean_heights = [mean_disc_height(state["clinical_state"]) for state in future_states]
    mean_loads = [mean_load(state.get("load_distribution", {})) for state in future_states]
    mean_alignment = [mean_alignment_tilt(state["clinical_state"]) for state in future_states]

    outputs = []
    outputs.append(line_plot(x, curvature, labels, "Progression Curvature", "Years", "Global curvature", "progression_curvature.png"))
    outputs.append(line_plot(x, mean_heights, labels, "Progression Disc Height", "Years", "Mean height (voxel units)", "progression_disc_height.png"))
    outputs.append(line_plot(x, mean_loads, labels, "Progression Load Distribution", "Years", "Mean relative load index", "progression_load_distribution.png"))
    outputs.append(line_plot(x, mean_alignment, labels, "Progression Alignment", "Years", "Mean disc tilt degrees", "progression_alignment.png"))
    return outputs


def line_plot(x: list[float], y: list[float], labels: list[str], title: str, xlabel: str, ylabel: str, filename: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, y, marker="o", linewidth=2)
    for x_value, y_value, label in zip(x, y, labels):
        ax.text(x_value, y_value, label, fontsize=8, va="bottom")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    path = VIS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def mean_disc_height(clinical_state: dict[str, Any]) -> float:
    values = [
        float(item.get("mean_height", 0.0))
        for item in clinical_state.get("disc_heights", {}).values()
        if isinstance(item.get("mean_height"), (int, float))
    ]
    return sum(values) / len(values) if values else 0.0


def mean_load(load_state: dict[str, Any]) -> float:
    values = [
        float(item.get("relative_load_index", 0.0))
        for item in load_state.get("structures", {}).values()
        if isinstance(item.get("relative_load_index"), (int, float))
    ]
    return sum(values) / len(values) if values else 0.0


def mean_alignment_tilt(clinical_state: dict[str, Any]) -> float:
    values = [
        float(item.get("disc_tilt_degrees", 0.0))
        for item in clinical_state.get("alignment", {}).get("disc_alignment", {}).values()
        if isinstance(item.get("disc_tilt_degrees"), (int, float))
    ]
    return sum(values) / len(values) if values else 0.0


def evidence_rule_registry() -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "registry_scope": "Internal deterministic OrthoTwin rules. External clinical validation not claimed.",
        "rules": [
            rule("R001", "disc_height_loss_over_time", "assumption", "LOW", "Disc height decreases as a configurable fraction per simulated year.", "natural_progression_rules.json"),
            rule("R002", "disc_volume_loss_over_time", "assumption", "LOW", "Disc projected area/volume proxies decrease as a configurable fraction per simulated year.", "natural_progression_rules.json"),
            rule("R003", "disc_height_loss_to_foraminal_area_reduction", "geometric_proxy", "LOW", "Foraminal area scales with disc-height factor using a configurable coupling coefficient.", "natural_progression_rules.json"),
            rule("R004", "height_loss_to_load_increase", "geometric_proxy", "LOW", "Reduced disc height increases relative load index through a deterministic coefficient.", "natural_progression_rules.json"),
            rule("R005", "load_to_stress_risk_update", "geometric_proxy", "LOW", "Stress and risk are bounded scalar approximations, not physical stress tensors.", "natural_progression_rules.json"),
            rule("R006", "curvature_progression", "assumption", "LOW", "Curvature changes by configurable fraction per simulated year.", "natural_progression_rules.json"),
            rule("R007", "alignment_progression", "assumption", "LOW", "Disc angle and tilt receive deterministic yearly offsets.", "natural_progression_rules.json"),
            rule("R008", "scenario_graph_propagation", "internal_prior_phase", "MEDIUM", "Phase 5 scenarios use deterministic graph propagation from Stage 3.", "propagation_rules.json"),
        ],
    }


def rule(rule_id: str, name: str, source_type: str, confidence: str, assumption: str, ref: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_name": name,
        "source_type": source_type,
        "confidence": confidence,
        "assumption": assumption,
        "supporting_reference": ref,
        "not_clinically_validated": True,
    }


def assumption_registry(rules: dict[str, Any]) -> dict[str, Any]:
    assumptions = []
    for name, value in rules["rules"].items():
        assumptions.append(
            {
                "assumption_id": f"A{len(assumptions)+1:03d}",
                "name": name,
                "value": value,
                "category": "hardcoded_configurable_parameter",
                "source": "natural_progression_rules.json",
                "confidence": "LOW",
                "impact": "Changes longitudinal trajectory; not patient-calibrated.",
            }
        )
    assumptions.extend(
        [
            {
                "assumption_id": "A999",
                "name": "physical_spacing_missing",
                "value": "Physical calibration blocked",
                "category": "known_limitation",
                "source": "phase4_5/missing_spacing_report.txt",
                "confidence": "HIGH",
                "impact": "Measurements remain voxel-space; radiology-grade physical claims cannot be made.",
            },
            {
                "assumption_id": "A998",
                "name": "no_longitudinal_patient_followup",
                "value": True,
                "category": "known_limitation",
                "source": "available repository state",
                "confidence": "HIGH",
                "impact": "Progression cannot be validated against observed Patient Alpha timepoints.",
            },
        ]
    )
    return {"generated_utc": utc_now(), "assumptions": assumptions}


def traceability_map() -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "metrics": [
            trace("disc_heights", CLINICAL_STATE_PATH, "clinical_state_vector.disc_heights + progression height factor", "future_state_*"),
            trace("disc_areas", CLINICAL_STATE_PATH, "clinical_state_vector.disc_areas + progression area factor", "future_state_*"),
            trace("foraminal_areas", CLINICAL_STATE_PATH, "clinical_state_vector.foraminal_areas + disc-height coupling", "future_state_*"),
            trace("canal_areas", CLINICAL_STATE_PATH, "clinical_state_vector.canal_areas + configurable area factor", "future_state_*"),
            trace("alignment", CLINICAL_STATE_PATH, "clinical_state_vector.alignment + yearly angle offset", "future_state_*"),
            trace("curvature", CLINICAL_STATE_PATH, "clinical_state_vector.curvature + yearly curvature factor", "future_state_*"),
            trace("load_distribution", STATE_V2_PATH, "patient_state_vector_v2.load_metrics + height-loss load rule", "future_state_*"),
            trace("scenario_rankings", PHASE5_RANKING_PATH, "Phase 5 comparator scoring", "master_dashboard.json"),
            trace("confidence_scores", REPORT_DIR / "confidence_scoring.json", "manual evidence-aware scoring", "master_digital_twin_state.json"),
        ],
    }


def trace(metric: str, source: Path, calculation: str, output: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "source_file": str(source),
        "input_data": source.name,
        "calculation_path": calculation,
        "output_file": output,
    }


def confidence_scoring() -> dict[str, Any]:
    scores = {
        "segmentation": score(6.0, "Existing masks and QC artifacts exist, but no independent clinical validation is present."),
        "measurements": score(5.0, "Rich geometric measurements exist; Phase 4.5 physical calibration is blocked."),
        "state_vector": score(7.0, "Patient state v2 and clinical state are structured and reusable."),
        "graph": score(7.0, "Spine graph is connected and used by propagation/scenario layers."),
        "propagation": score(4.0, "Deterministic graph propagation exists, but it is explicitly not physics."),
        "scenario_engine": score(6.0, "Scenarios and future states are generated consistently from existing state."),
        "longitudinal_engine": score(3.0, "Configurable time evolution exists, but no patient-specific temporal validation exists."),
    }
    readiness = sum(item["score"] for item in scores.values()) / len(scores)
    return {
        "generated_utc": utc_now(),
        "scale": "0-10",
        "scores": scores,
        "digital_twin_readiness_score": readiness,
        "research_readiness_score": 6.0,
        "engineering_readiness_score": 7.0,
        "not_clinically_validated": True,
    }


def score(value: float, rationale: str) -> dict[str, Any]:
    return {"score": value, "rationale": rationale}


def failure_modes() -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "failure_modes": [
            failure("missing_spacing", "HIGH", "Physical mm/mm2/mm3 calibration remains blocked.", "Attach source image/DICOM spacing to Patient Alpha reconstruction."),
            failure("poor_segmentation", "MEDIUM", "Geometry depends on segmentation quality.", "Add expert-reviewed segmentation QC and inter-rater validation."),
            failure("invalid_graph", "MEDIUM", "Broken adjacency would corrupt propagation.", "Run graph connectivity validation before scenarios."),
            failure("missing_disc", "MEDIUM", "Scenario targets may not exist in alternate patients.", "Add target existence checks and patient-specific scenario selection."),
            failure("broken_state", "HIGH", "Missing state keys can break downstream engines.", "Schema validation and migration tests."),
            failure("unvalidated_progression_rules", "HIGH", "Longitudinal trajectories are assumptions, not observed outcomes.", "Fit rules to longitudinal imaging cohorts."),
            failure("no_physics_engine", "HIGH", "No finite element or tissue model exists.", "Integrate validated biomechanics module with boundary conditions."),
        ],
    }


def failure(name: str, severity: str, description: str, mitigation: str) -> dict[str, Any]:
    return {"failure_mode": name, "severity": severity, "description": description, "mitigation": mitigation}


def master_state(
    clinical_state: dict[str, Any],
    state_v2: dict[str, Any],
    graph: dict[str, Any],
    dashboard: dict[str, Any],
    future_states: list[Path],
    confidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "patient_id": clinical_state.get("patient_id", "patient_alpha"),
        "current_state": state_v2,
        "clinical_state": clinical_state,
        "graph_state": graph,
        "scenario_state": dashboard,
        "future_state_files": [str(path) for path in future_states],
        "confidence_scores": confidence,
        "warnings": [
            "No diagnosis.",
            "No treatment recommendation.",
            "No clinical validity claim.",
            "Physical calibration is blocked until trusted Patient Alpha spacing is available.",
        ],
    }


def master_dashboard(
    clinical_state: dict[str, Any],
    dashboard: dict[str, Any],
    confidence: dict[str, Any],
    future_states: list[Path],
) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "patient_summary": {
            "patient_id": clinical_state.get("patient_id", "patient_alpha"),
            "disc_count": len(clinical_state.get("disc_heights", {})),
            "canal_levels": len(clinical_state.get("canal_areas", {})),
            "scenario_count": len(dashboard.get("available_scenarios", [])),
            "longitudinal_future_state_count": len(future_states),
        },
        "measurements": {
            "disc_heights": clinical_state.get("disc_heights", {}),
            "curvature": clinical_state.get("curvature", {}),
            "slippage": clinical_state.get("slippage", {}),
        },
        "scenarios": dashboard.get("available_scenarios", []),
        "future_states": [str(path) for path in future_states],
        "confidence": confidence,
        "warnings": [
            "Voxel units remain active where spacing is missing.",
            "Progression rules are configurable assumptions.",
            "This dashboard is a research backend, not clinical software.",
        ],
    }


def repository_knowledge_graph() -> dict[str, Any]:
    inventory = load_json(PROJECT_INVENTORY_PATH, [])
    if isinstance(inventory, dict):
        inventory = inventory.get("files", [])
    selected = []
    for item in inventory:
        rel = item.get("relative_path", "")
        if any(prefix in rel.replace("\\", "/") for prefix in ("state/", "simulation/", "reports/phase", "measurements/")):
            selected.append(item)
        if len(selected) >= 250:
            break
    nodes = [
        {
            "id": item.get("relative_path") or item.get("full_path"),
            "type": "file",
            "extension": item.get("extension"),
            "category": item.get("category"),
        }
        for item in selected
    ]
    edges = [
        {"source": "simulation/longitudinal_engine.py", "target": "state/patient_states/clinical_state_vector.json", "relationship": "consumes"},
        {"source": "simulation/longitudinal_engine.py", "target": "state/longitudinal/future_state_*.json", "relationship": "produces"},
        {"source": "simulation/scenario_engine.py", "target": "reports/phase5/dashboard_state.json", "relationship": "produces"},
        {"source": "reports/phase6/confidence_scoring.json", "target": "state/master_digital_twin_state.json", "relationship": "supports"},
    ]
    return {"generated_utc": utc_now(), "nodes": nodes, "edges": edges, "note": "Compact knowledge graph; full inventory remains in project_inventory.json."}


def research_summary(classification: str, confidence: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# OrthoTwin Research Summary",
            "",
            "## What Has Been Built",
            "OrthoTwin now includes segmentation-derived geometry, clinical state vectors, a spine graph, deterministic propagation, scenario comparison, and longitudinal state evolution.",
            "",
            "## What Is Scientifically Validated",
            "The repository does not contain evidence of independent clinical, biomechanical, or regulatory validation. The system should be treated as a research prototype.",
            "",
            "## What Remains Estimated",
            "Canal/foraminal measurements, degeneration features, propagation, scenario scoring, and longitudinal progression remain geometric or deterministic estimates.",
            "",
            "## Assumptions",
            "The longitudinal rules use configurable coefficients for height loss, volume loss, alignment drift, curvature drift, and load redistribution. These are not patient-calibrated.",
            "",
            "## What OrthoTwin Currently Can Do",
            "It can organize a patient state, connect structures through a graph, run deterministic intervention scenarios, compare future states, and trace rules to internal assumptions.",
            "",
            "## What It Cannot Do",
            "It cannot diagnose, recommend treatment, predict outcomes clinically, claim physical mm accuracy without spacing, or replace biomechanical simulation.",
            "",
            "## Research Directions",
            "Needed next: trusted image spacing, longitudinal follow-up data, radiologist measurement validation, finite element modeling, boundary conditions, tissue properties, and prospective validation.",
            "",
            f"## System Classification",
            f"{classification}",
            "",
            f"Digital twin readiness score: {confidence['digital_twin_readiness_score']:.2f}/10.",
        ]
    )


def system_assessment(confidence: dict[str, Any]) -> dict[str, Any]:
    readiness = confidence["digital_twin_readiness_score"]
    classification = "Digital Twin Prototype"
    if readiness < 4:
        classification = "Simulation Framework"
    elif readiness >= 7:
        classification = "Research Platform"
    return {
        "generated_utc": utc_now(),
        "classification": classification,
        "available_classes": [
            "Data Pipeline",
            "Measurement Engine",
            "Simulation Framework",
            "Digital Twin Prototype",
            "Advanced Digital Twin",
            "Research Platform",
        ],
        "justification": [
            "The system has structured patient state, graph connectivity, deterministic propagation, scenario comparison, and longitudinal evolution.",
            "It lacks trusted physical calibration, validated biomechanics, patient-specific longitudinal data, and clinical validation.",
            "Therefore it is stronger than a measurement-only pipeline but not an advanced or clinically validated digital twin.",
        ],
        "digital_twin_readiness_score": readiness,
        "research_readiness_score": confidence["research_readiness_score"],
        "engineering_readiness_score": confidence["engineering_readiness_score"],
        "regulatory_readiness_claim": "none",
        "clinical_validity_claim": "none",
    }


def write_manifest(paths: list[Path], summary: dict[str, Any]) -> Path:
    return write_json(
        MANIFEST_DIR / "phase6_manifest.json",
        {
            "generated_utc": utc_now(),
            "phase": "phase6_longitudinal_evidence_engine",
            "summary": summary,
            "files": [
                {"path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() else None}
                for path in paths
            ],
            "all_files_exist": all(path.exists() for path in paths),
        },
    )


def main() -> None:
    for directory in (LONGITUDINAL_DIR, EVIDENCE_DIR, REPORT_DIR, VIS_DIR, MANIFEST_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    clinical_state = load_json(CLINICAL_STATE_PATH, {})
    state_v2 = load_json(STATE_V2_PATH, {})
    graph = load_json(GRAPH_PATH, {})
    dashboard = load_json(PHASE5_DASHBOARD_PATH, {})
    calibration = load_json(PHASE45_CALIBRATION_PATH, {})

    tm = time_model()
    rules = natural_progression_rules()
    time_model_path = write_json(LONGITUDINAL_DIR / "time_model.json", tm)
    rules_path = write_json(LONGITUDINAL_DIR / "natural_progression_rules.json", rules)

    future_paths = []
    future_states = []
    for timeline in tm["timelines"]:
        evolved = evolve_state(clinical_state, state_v2, graph, timeline, rules)
        path = write_json(LONGITUDINAL_DIR / future_state_filename(timeline["id"]), evolved)
        future_paths.append(path)
        future_states.append(evolved)

    visualization_paths = generate_visualizations(future_states)

    evidence_path = write_json(EVIDENCE_DIR / "evidence_rule_registry.json", evidence_rule_registry())
    assumptions_path = write_json(EVIDENCE_DIR / "assumption_registry.json", assumption_registry(rules))
    traceability_path = write_json(EVIDENCE_DIR / "traceability_map.json", traceability_map())

    confidence = confidence_scoring()
    if calibration.get("calibration_status") == "blocked":
        confidence["scores"]["measurements"]["score"] = 4.0
        confidence["scores"]["measurements"]["rationale"] += " Physical calibration file explicitly reports blocked status."
        confidence["digital_twin_readiness_score"] = sum(item["score"] for item in confidence["scores"].values()) / len(confidence["scores"])
    confidence_path = write_json(REPORT_DIR / "confidence_scoring.json", confidence)
    failure_path = write_json(REPORT_DIR / "failure_modes.json", failure_modes())

    master_state_path = write_json(
        PROJECT_ROOT / "state" / "master_digital_twin_state.json",
        master_state(clinical_state, state_v2, graph, dashboard, future_paths, confidence),
    )
    master_dashboard_path = write_json(
        REPORT_DIR / "master_dashboard.json",
        master_dashboard(clinical_state, dashboard, confidence, future_paths),
    )
    repo_graph_path = write_json(REPORT_DIR / "repository_knowledge_graph.json", repository_knowledge_graph())

    assessment = system_assessment(confidence)
    summary_path = write_text(REPORT_DIR / "orthotwin_research_summary.md", research_summary(assessment["classification"], confidence))
    assessment_path = write_json(REPORT_DIR / "orthotwin_system_assessment.json", assessment)

    generated_paths = [
        time_model_path,
        rules_path,
        *future_paths,
        *visualization_paths,
        evidence_path,
        assumptions_path,
        traceability_path,
        confidence_path,
        failure_path,
        master_state_path,
        master_dashboard_path,
        repo_graph_path,
        summary_path,
        assessment_path,
    ]
    counts = {
        "total_files_generated": len(generated_paths) + 1,
        "total_states": len(future_paths) + 2,
        "total_scenarios": len(dashboard.get("available_scenarios", [])),
        "total_future_states": len(future_paths) + len(dashboard.get("future_states", [])),
        "digital_twin_readiness_score": confidence["digital_twin_readiness_score"],
        "research_readiness_score": confidence["research_readiness_score"],
        "engineering_readiness_score": confidence["engineering_readiness_score"],
        "most_important_remaining_limitation": "Trusted Patient Alpha physical spacing and patient-specific longitudinal validation are missing.",
    }
    manifest_path = write_manifest(generated_paths, counts)

    print("ORTHOTWIN PHASE 6 COMPLETE")
    print(f"Total Files Generated: {counts['total_files_generated']}")
    print(f"Total States: {counts['total_states']}")
    print(f"Total Scenarios: {counts['total_scenarios']}")
    print(f"Total Future States: {counts['total_future_states']}")
    print(f"Digital Twin Readiness Score: {counts['digital_twin_readiness_score']:.2f}")
    print(f"Research Readiness Score: {counts['research_readiness_score']:.2f}")
    print(f"Engineering Readiness Score: {counts['engineering_readiness_score']:.2f}")
    print(f"Most Important Remaining Limitation: {counts['most_important_remaining_limitation']}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
