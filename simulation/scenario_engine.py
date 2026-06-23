"""Phase 5 deterministic scenario generation engine.

Transforms the existing OrthoTwin state, graph, and propagation outputs into a
scenario comparison archive. This is internal twin scoring only; it does not
diagnose, recommend treatment, retrain models, run inference, or modify masks.
"""

from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from OrthoTwin.simulation.propagation.propagation_engine import (
    PropagationResult,
    simulate_disc_collapse,
    simulate_disc_restoration,
    simulate_fusion,
    simulate_implant,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector_v2.json"
CLINICAL_STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
LOAD_MODEL_PATH = PROJECT_ROOT / "measurements" / "alignment" / "load_path_model.json"
PROPAGATION_RULES_PATH = PROJECT_ROOT / "simulation" / "propagation" / "propagation_rules.json"

SCENARIO_DIR = PROJECT_ROOT / "state" / "scenarios"
FUTURE_STATE_DIR = PROJECT_ROOT / "state" / "future_states"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase5"
VIS_DIR = PROJECT_ROOT / "visualization" / "simulation"
MANIFEST_DIR = PROJECT_ROOT / "manifests"

TARGET_DISC = "disc_6_206_207"
SECONDARY_DISC = "disc_5_205"


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


def scenario_schema() -> dict[str, Any]:
    return {
        "schema_name": "orthtwin_scenario_v1",
        "not_medical_advice": True,
        "required_fields": {
            "id": "Stable scenario identifier.",
            "name": "Human-readable scenario name.",
            "intervention": "Deterministic intervention type.",
            "parameters": "Intervention parameters.",
            "before_state": "Pre-action state summary.",
            "after_state": "Post-action state summary.",
            "affected_structures": "Direct and propagated structures.",
            "metrics_changed": "Changed metrics with deltas.",
        },
        "optional_fields": {
            "future_state_file": "Path to full simulated future state.",
            "graph_updates": "Graph changes for scenarios such as fusion.",
            "scoring": "Internal scenario comparison scores.",
        },
    }


def node_name(graph: dict[str, Any], node_id: str) -> str:
    return graph.get("nodes", {}).get(node_id, {}).get("name", node_id)


def state_summary(state: dict[str, Any]) -> dict[str, Any]:
    discs = state.get("disc_features", {})
    loads = state.get("load_metrics", {}).get("structures", {})
    alignment = state.get("alignment_metrics", {}).get("disc_alignment", {})
    centerline = state.get("centerline", {})
    return {
        "patient_id": state.get("patient_id", "patient_alpha"),
        "disc_count": len(discs),
        "vertebra_count": len(state.get("vertebral_features", {})),
        "mean_disc_height": mean(
            [
                float(record.get("state_variables", {}).get("height") or record.get("bounding_box", {}).get("depth", 0))
                for record in discs.values()
            ]
        ),
        "mean_relative_load_index": mean([float(item.get("relative_load_index", 0)) for item in loads.values()]),
        "mean_stress_score": mean([float(item.get("stress_score", 0)) for item in loads.values()]),
        "mean_disc_angle_degrees": mean([float(item.get("disc_angle_degrees", 0)) for item in alignment.values()]),
        "centerline_length": centerline.get("centerline_length"),
        "intervention_history_count": len(state.get("intervention_history", [])),
    }


def mean(values: list[float]) -> float | None:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return None
    return sum(values) / len(values)


def numeric_delta(before: Any, after: Any) -> dict[str, Any]:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return {"before": before, "after": after, "delta": None, "percent_change": None}
    delta = after - before
    percent = None if before == 0 else delta / before * 100.0
    return {"before": before, "after": after, "delta": delta, "percent_change": percent}


def extract_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    disc_height_changes = {}
    for disc_id, before_disc in before.get("disc_features", {}).items():
        after_disc = after.get("disc_features", {}).get(disc_id, {})
        before_height = before_disc.get("state_variables", {}).get("height") or before_disc.get("bounding_box", {}).get("depth")
        after_height = after_disc.get("state_variables", {}).get("height") or after_disc.get("bounding_box", {}).get("depth")
        change = numeric_delta(before_height, after_height)
        if change["delta"] not in (None, 0):
            disc_height_changes[disc_id] = change

    load_changes = {}
    before_loads = before.get("load_metrics", {}).get("structures", {})
    after_loads = after.get("load_metrics", {}).get("structures", {})
    for node_id, before_load in before_loads.items():
        after_load = after_loads.get(node_id, {})
        node_changes = {
            "relative_load_index": numeric_delta(
                before_load.get("relative_load_index"), after_load.get("relative_load_index")
            ),
            "stress_score": numeric_delta(before_load.get("stress_score"), after_load.get("stress_score")),
            "risk_score": numeric_delta(before_load.get("risk_score"), after_load.get("risk_score")),
        }
        if any(item["delta"] not in (None, 0) for item in node_changes.values()):
            load_changes[node_id] = node_changes

    alignment_changes = {}
    before_alignment = before.get("alignment_metrics", {}).get("disc_alignment", {})
    after_alignment = after.get("alignment_metrics", {}).get("disc_alignment", {})
    for disc_id, before_record in before_alignment.items():
        after_record = after_alignment.get(disc_id, {})
        node_changes = {
            "disc_angle_degrees": numeric_delta(
                before_record.get("disc_angle_degrees"), after_record.get("disc_angle_degrees")
            ),
            "disc_tilt_degrees": numeric_delta(
                before_record.get("disc_tilt_degrees"), after_record.get("disc_tilt_degrees")
            ),
        }
        if any(item["delta"] not in (None, 0) for item in node_changes.values()):
            alignment_changes[disc_id] = node_changes

    propagation_magnitude = sum(
        abs(float(change["relative_load_index"]["delta"] or 0)) for change in load_changes.values()
    )
    affected_structures = sorted(set(disc_height_changes) | set(load_changes) | set(alignment_changes))
    return {
        "disc_height": disc_height_changes,
        "alignment": alignment_changes,
        "load_distribution": load_changes,
        "curvature": {
            "centerline_length": numeric_delta(
                before.get("centerline", {}).get("centerline_length"),
                after.get("centerline", {}).get("centerline_length"),
            ),
            "note": "Curvature is tracked from existing state; no geometric centerline recomputation is performed.",
        },
        "propagation_magnitude": propagation_magnitude,
        "affected_structure_count": len(affected_structures),
        "affected_structures": affected_structures,
    }


def create_baseline(state: dict[str, Any], clinical_state: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "baseline",
        "name": "Baseline: no intervention",
        "intervention": "none",
        "parameters": {},
        "before_state": state_summary(state),
        "after_state": state_summary(state),
        "affected_structures": [],
        "metrics_changed": {},
        "current_clinical_state_vector": clinical_state,
        "current_graph_state": graph,
        "current_propagation_state": {
            "load_model": load_json(LOAD_MODEL_PATH, {}),
            "propagation_rules": load_json(PROPAGATION_RULES_PATH, {}),
        },
        "not_medical_advice": True,
    }


def result_to_scenario(
    scenario_id: str,
    name: str,
    result: PropagationResult,
    graph: dict[str, Any],
    output_filename: str,
    extra_parameters: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    metrics = extract_metrics(result.before_state, result.after_state)
    future_path = FUTURE_STATE_DIR / output_filename
    future_state = deepcopy(result.after_state)
    future_state["scenario_id"] = scenario_id
    future_state["scenario_generated_utc"] = utc_now()
    write_json(future_path, future_state)

    affected = [
        {
            "node_id": node_id,
            "name": node_name(graph, node_id),
            "node_type": graph.get("nodes", {}).get(node_id, {}).get("node_type"),
        }
        for node_id in metrics["affected_structures"]
    ]
    action = result.action
    scenario = {
        "id": scenario_id,
        "name": name,
        "intervention": action["type"],
        "parameters": {**action.get("parameters", {}), **(extra_parameters or {})},
        "target": action.get("target"),
        "before_state": state_summary(result.before_state),
        "after_state": state_summary(result.after_state),
        "affected_structures": affected,
        "metrics_changed": metrics,
        "direct_effects": result.direct_effects,
        "secondary_effects": result.secondary_effects,
        "tertiary_effects": result.tertiary_effects,
        "graph_updates": result.graph_updates,
        "future_state_file": str(future_path),
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    return scenario, future_path


def build_scenarios(state: dict[str, Any], graph: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Path]]:
    scenario_specs = []
    for percent in (10, 20, 30):
        scenario_specs.append(
            (
                f"disc_collapse_{percent}",
                f"Disc collapse {percent}% ({TARGET_DISC})",
                simulate_disc_collapse(state, graph, TARGET_DISC, percent),
                f"future_state_disc_collapse_{percent}.json",
                {},
            )
        )
    for percent in (10, 20, 30):
        scenario_specs.append(
            (
                f"disc_restoration_{percent}",
                f"Disc restoration {percent}% ({TARGET_DISC})",
                simulate_disc_restoration(state, graph, TARGET_DISC, percent),
                f"future_state_disc_restore_{percent}.json",
                {},
            )
        )

    scenario_specs.extend(
        [
            (
                "fusion_l4_l5",
                "Fusion L4-L5 internal graph mapping",
                simulate_fusion(state, graph, "vertebra_4", "vertebra_5"),
                "future_state_fusion_l4_l5.json",
                {"internal_mapping": {"L4": "vertebra_4", "L5": "vertebra_5"}},
            ),
            (
                "fusion_l5_s1",
                "Fusion L5-S1 internal graph mapping",
                simulate_fusion(state, graph, "vertebra_5", "vertebra_6"),
                "future_state_fusion_l5_s1.json",
                {"internal_mapping": {"L5": "vertebra_5", "S1_proxy": "vertebra_6"}},
            ),
            (
                "implant_disc_6",
                "Implant insertion at Disc 6",
                simulate_implant(state, graph, TARGET_DISC, implant_height_for(state, TARGET_DISC, 1.2)),
                "future_state_implant_disc_6.json",
                {"height_rule": "current_height_x_1.20"},
            ),
            (
                "implant_disc_5",
                "Implant insertion at Disc 5",
                simulate_implant(state, graph, SECONDARY_DISC, implant_height_for(state, SECONDARY_DISC, 1.2)),
                "future_state_implant_disc_5.json",
                {"height_rule": "current_height_x_1.20"},
            ),
        ]
    )

    scenarios = []
    future_paths = []
    for scenario_id, name, result, future_filename, extra in scenario_specs:
        scenario, future_path = result_to_scenario(scenario_id, name, result, graph, future_filename, extra)
        scenarios.append(scenario)
        future_paths.append(future_path)
    return scenarios, future_paths


def implant_height_for(state: dict[str, Any], disc_id: str, multiplier: float) -> float:
    disc = state["disc_features"][disc_id]
    current = disc.get("state_variables", {}).get("height") or disc.get("bounding_box", {}).get("depth")
    return float(current) * multiplier


def write_scenario_files(baseline: dict[str, Any], scenarios: list[dict[str, Any]]) -> list[Path]:
    paths = [
        write_json(SCENARIO_DIR / "scenario_schema.json", scenario_schema()),
        write_json(SCENARIO_DIR / "baseline_scenario.json", baseline),
    ]
    for scenario in scenarios:
        paths.append(write_json(SCENARIO_DIR / f"{scenario['id']}.json", scenario))
    return paths


def generate_visualizations(scenarios: list[dict[str, Any]], graph: dict[str, Any]) -> list[Path]:
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    labels = [scenario["id"] for scenario in scenarios]
    heatmap_metrics = [
        [
            scenario["metrics_changed"]["affected_structure_count"],
            scenario["metrics_changed"]["propagation_magnitude"],
            abs(alignment_score(scenario)),
            height_restoration_score(scenario),
        ]
        for scenario in scenarios
    ]
    metric_names = ["Affected", "Propagation", "Alignment", "Height"]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.imshow(heatmap_metrics, cmap="viridis", aspect="auto")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xticks(range(len(metric_names)), labels=metric_names)
    ax.set_title("Scenario Heatmap")
    for y, row in enumerate(heatmap_metrics):
        for x, value in enumerate(row):
            ax.text(x, y, f"{value:.2f}", ha="center", va="center", color="white", fontsize=8)
    heatmap_path = VIS_DIR / "scenario_heatmap.png"
    fig.tight_layout()
    fig.savefig(heatmap_path, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(labels, [height_restoration_score(scenario) for scenario in scenarios], label="Height restoration")
    ax.plot(labels, [abs(alignment_score(scenario)) for scenario in scenarios], color="black", marker="o", label="Alignment change")
    ax.set_title("Intervention Comparison")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    comparison_path = VIS_DIR / "intervention_comparison.png"
    fig.tight_layout()
    fig.savefig(comparison_path, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(labels, [scenario["metrics_changed"]["propagation_magnitude"] for scenario in scenarios], color="#9c5b2e")
    ax.set_title("Propagation Comparison")
    ax.set_ylabel("Summed absolute load-index delta")
    ax.tick_params(axis="x", rotation=45)
    propagation_path = VIS_DIR / "propagation_comparison.png"
    fig.tight_layout()
    fig.savefig(propagation_path, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 9))
    nodes = graph.get("nodes", {})
    positions = {
        node_id: (
            float(record.get("centroid", [0, 0, 0])[0]),
            float(record.get("centroid", [0, 0, 0])[1]),
        )
        for node_id, record in nodes.items()
    }
    sensitivity = structure_sensitivity(scenarios)
    max_sensitivity = max(sensitivity.values() or [1])
    for edge in graph.get("edges", []):
        a = edge.get("source")
        b = edge.get("target")
        if a in positions and b in positions:
            ax.plot([positions[a][0], positions[b][0]], [positions[a][1], positions[b][1]], color="#b8b8b8", linewidth=1)
    for node_id, (x, y) in positions.items():
        size = 80 + 380 * sensitivity.get(node_id, 0) / max_sensitivity
        color = "#c94c4c" if nodes[node_id].get("node_type") == "disc" else "#4c7ac9"
        ax.scatter(x, y, s=size, color=color, alpha=0.8)
        ax.text(x + 1, y + 1, node_id.replace("_", " "), fontsize=7)
    ax.set_title("Future State Graph: Scenario Sensitivity")
    ax.set_xlabel("Centroid X")
    ax.set_ylabel("Centroid Y")
    graph_path = VIS_DIR / "future_state_graph.png"
    fig.tight_layout()
    fig.savefig(graph_path, dpi=160)
    plt.close(fig)

    return [heatmap_path, comparison_path, propagation_path, graph_path]


def height_restoration_score(scenario: dict[str, Any]) -> float:
    changes = scenario["metrics_changed"].get("disc_height", {})
    return sum(float(item.get("percent_change") or 0) for item in changes.values())


def alignment_score(scenario: dict[str, Any]) -> float:
    total = 0.0
    for values in scenario["metrics_changed"].get("alignment", {}).values():
        total += float(values.get("disc_angle_degrees", {}).get("delta") or 0)
        total += float(values.get("disc_tilt_degrees", {}).get("delta") or 0)
    return total


def load_impact_score(scenario: dict[str, Any]) -> float:
    return float(scenario["metrics_changed"].get("propagation_magnitude", 0.0))


def stability_score(scenario: dict[str, Any]) -> float:
    propagation = load_impact_score(scenario)
    affected = scenario["metrics_changed"].get("affected_structure_count", 0)
    return max(0.0, 100.0 - propagation * 25.0 - affected * 2.0)


def structure_sensitivity(scenarios: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for scenario in scenarios:
        for item in scenario.get("affected_structures", []):
            counts[item["node_id"]] = counts.get(item["node_id"], 0) + 1
    return counts


def build_dashboard(
    baseline: dict[str, Any],
    scenarios: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    future_paths: list[Path],
) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "patient_id": "patient_alpha",
        "not_medical_advice": True,
        "current_state": baseline["before_state"],
        "available_scenarios": [
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "intervention": scenario["intervention"],
                "parameters": scenario["parameters"],
                "affected_structure_count": scenario["metrics_changed"]["affected_structure_count"],
            }
            for scenario in scenarios
        ],
        "scenario_rankings": rankings,
        "key_metrics": {
            "scenario_count": len(scenarios),
            "most_sensitive_structures": sorted(structure_sensitivity(scenarios).items(), key=lambda item: item[1], reverse=True),
            "largest_propagation": max(scenarios, key=load_impact_score)["id"],
            "smallest_propagation": min(scenarios, key=load_impact_score)["id"],
        },
        "future_states": [str(path) for path in future_paths],
    }


def report_text(scenarios: list[dict[str, Any]], rankings: list[dict[str, Any]]) -> str:
    sensitivity = sorted(structure_sensitivity(scenarios).items(), key=lambda item: item[1], reverse=True)
    largest = max(scenarios, key=load_impact_score)
    smallest = min(scenarios, key=load_impact_score)
    most_affected = max(scenarios, key=lambda item: item["metrics_changed"]["affected_structure_count"])
    best_alignment = min(scenarios, key=lambda item: abs(alignment_score(item)))
    return "\n".join(
        [
            "ORTHOTWIN PHASE 5 SCENARIO REPORT",
            "",
            "Scope: deterministic digital twin scenario comparison only.",
            "Clinical validity claim: none. This is not diagnosis or treatment advice.",
            "",
            f"1. How many scenarios exist? {len(scenarios)} generated scenarios plus one baseline.",
            f"2. Most sensitive structures: {', '.join(f'{node} ({count})' for node, count in sensitivity[:5])}.",
            f"3. Largest change scenario: {largest['id']} by propagation magnitude {load_impact_score(largest):.4f}.",
            f"4. Smallest change scenario: {smallest['id']} by propagation magnitude {load_impact_score(smallest):.4f}.",
            f"5. Scenario affecting most structures: {most_affected['id']} with {most_affected['metrics_changed']['affected_structure_count']} structures.",
            f"6. Alignment-preserving scenario: {best_alignment['id']} with absolute alignment delta {abs(alignment_score(best_alignment)):.4f}.",
            "",
            "Top internal rankings:",
            *[
                f"- {item['rank']}. {item['scenario_id']} score={item['total_score']:.3f}"
                for item in rankings[:5]
            ],
            "",
            "Limitations:",
            "- Propagation uses graph rules, not physics.",
            "- Curvature is tracked from existing state and not recomputed geometrically.",
            "- Physical calibration remains blocked until trusted Patient Alpha spacing metadata is linked.",
        ]
    )


def validate_outputs(
    scenario_paths: list[Path],
    future_paths: list[Path],
    report_paths: list[Path],
    visualization_paths: list[Path],
) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "all_scenarios_generated": all(path.exists() for path in scenario_paths),
        "all_future_states_generated": all(path.exists() for path in future_paths),
        "all_reports_exist": all(path.exists() for path in report_paths),
        "all_visualizations_exist": all(path.exists() for path in visualization_paths),
        "scenario_files": [{"path": str(path), "exists": path.exists()} for path in scenario_paths],
        "future_state_files": [{"path": str(path), "exists": path.exists()} for path in future_paths],
        "report_files": [{"path": str(path), "exists": path.exists()} for path in report_paths],
        "visualization_files": [{"path": str(path), "exists": path.exists()} for path in visualization_paths],
        "not_medical_advice": True,
    }


def manifest(paths: list[Path]) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "phase": "phase5_scenario_decision_engine",
        "files": [
            {
                "path": str(path),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else None,
            }
            for path in paths
        ],
        "all_files_exist": all(path.exists() for path in paths),
    }


def main() -> None:
    state = load_json(STATE_PATH, {})
    clinical_state = load_json(CLINICAL_STATE_PATH, {})
    graph = load_json(GRAPH_PATH, {})

    for directory in (SCENARIO_DIR, FUTURE_STATE_DIR, REPORT_DIR, VIS_DIR, MANIFEST_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    baseline = create_baseline(state, clinical_state, graph)
    scenarios, future_paths = build_scenarios(state, graph)
    scenario_paths = write_scenario_files(baseline, scenarios)

    from OrthoTwin.simulation.scenario_comparator import compare_and_rank

    comparison, rankings = compare_and_rank(baseline, scenarios)
    comparison_path = write_json(REPORT_DIR / "scenario_comparison_matrix.json", comparison)
    ranking_path = write_json(REPORT_DIR / "scenario_ranking.json", rankings)

    visualization_paths = generate_visualizations(scenarios, graph)
    dashboard_path = write_json(REPORT_DIR / "dashboard_state.json", build_dashboard(baseline, scenarios, rankings, future_paths))
    report_path = write_text(REPORT_DIR / "phase5_scenario_report.txt", report_text(scenarios, rankings))
    validation_path = write_json(
        REPORT_DIR / "phase5_validation_report.json",
        validate_outputs(
            scenario_paths,
            future_paths,
            [comparison_path, ranking_path, dashboard_path, report_path],
            visualization_paths,
        ),
    )
    manifest_path = write_json(
        MANIFEST_DIR / "phase5_manifest.json",
        manifest(scenario_paths + future_paths + [comparison_path, ranking_path, dashboard_path, report_path, validation_path] + visualization_paths),
    )

    print("ORTHOTWIN PHASE 5 COMPLETE")
    print("Scenarios:")
    for scenario in scenarios:
        print(f"- {scenario['id']}")
    print("Future states:")
    for path in future_paths:
        print(f"- {path}")
    print("Reports:")
    for path in (comparison_path, ranking_path, dashboard_path, report_path, validation_path, manifest_path):
        print(f"- {path}")


if __name__ == "__main__":
    main()
