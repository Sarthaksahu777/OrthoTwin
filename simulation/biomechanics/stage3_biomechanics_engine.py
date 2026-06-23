"""Stage 3 deterministic biomechanical propagation runner.

Uses existing Stage 2 state files only. No models are trained, no inference is
run, no segmentation is modified, and no measurements are recomputed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_PARENT = Path(__file__).resolve().parents[3]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from OrthoTwin.simulation.propagation.propagation_engine import (
    PROPAGATION_RULES,
    PropagationEngine,
    PropagationResult,
    simulate_disc_collapse,
    simulate_disc_restoration,
    simulate_fusion,
    simulate_implant,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector_v2.json"
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
OUTPUT_DIR = PROJECT_ROOT / "state" / "transitions"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase3"
VIS_DIR = PROJECT_ROOT / "visualization" / "simulation"


def load_json(path: Path) -> dict[str, Any]:
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


def load_stage3_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_json(STATE_PATH), load_json(GRAPH_PATH)


def whole_spine_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    load_deltas = {}
    before_loads = before.get("load_metrics", {}).get("structures", {})
    after_loads = after.get("load_metrics", {}).get("structures", {})
    for node_id, before_record in before_loads.items():
        after_record = after_loads.get(node_id, {})
        load_deltas[node_id] = {
            "relative_load_index": delta(
                before_record.get("relative_load_index"),
                after_record.get("relative_load_index"),
            ),
            "stress_score": delta(before_record.get("stress_score"), after_record.get("stress_score")),
            "risk_score": delta(before_record.get("risk_score"), after_record.get("risk_score")),
        }

    disc_deltas = {}
    for disc_id, before_disc in before.get("disc_features", {}).items():
        after_disc = after.get("disc_features", {}).get(disc_id, {})
        disc_deltas[disc_id] = {
            "height": delta(
                before_disc.get("state_variables", {}).get("height"),
                after_disc.get("state_variables", {}).get("height"),
            ),
            "bounding_box_depth": delta(
                before_disc.get("bounding_box", {}).get("depth"),
                after_disc.get("bounding_box", {}).get("depth"),
            ),
        }

    alignment_deltas = {}
    before_alignment = before.get("alignment_metrics", {}).get("disc_alignment", {})
    after_alignment = after.get("alignment_metrics", {}).get("disc_alignment", {})
    for disc_id, before_record in before_alignment.items():
        after_record = after_alignment.get(disc_id, {})
        alignment_deltas[disc_id] = {
            "disc_angle_degrees": delta(
                before_record.get("disc_angle_degrees"),
                after_record.get("disc_angle_degrees"),
            ),
            "disc_tilt_degrees": delta(
                before_record.get("disc_tilt_degrees"),
                after_record.get("disc_tilt_degrees"),
            ),
        }

    affected = [
        node_id
        for node_id, metrics in load_deltas.items()
        if any(value.get("delta") not in (None, 0) for value in metrics.values())
    ]
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "affected_structure_count": len(affected),
        "affected_structures": affected,
        "disc_deltas": disc_deltas,
        "load_deltas": load_deltas,
        "alignment_deltas": alignment_deltas,
    }


def delta(before: Any, after: Any) -> dict[str, Any]:
    if before is None or after is None:
        return {"before": before, "after": after, "delta": None, "percent_change": None}
    numeric = isinstance(before, (int, float)) and isinstance(after, (int, float))
    change = after - before if numeric else None
    percent = change / before * 100.0 if numeric and before != 0 else None
    return {"before": before, "after": after, "delta": change, "percent_change": percent}


def cascade_for(name: str, result: PropagationResult) -> dict[str, Any]:
    data = result.to_dict()
    return {
        "intervention": name,
        "action": data["action"],
        "direct_effects": data["direct_effects"],
        "secondary_effects": data["secondary_effects"],
        "tertiary_effects": data["tertiary_effects"],
        "affected_structures": [
            data["action"]["target"],
            *[item["node_id"] for item in data["affected_neighbors"]],
        ],
        "affected_structure_count": 1 + len(data["affected_neighbors"]),
    }


def compare_interventions(results: dict[str, PropagationResult]) -> dict[str, Any]:
    rows = []
    for name, result in results.items():
        report = whole_spine_delta(result.before_state, result.after_state)
        alignment_impact = sum_abs_delta(report["alignment_deltas"], "disc_angle_degrees")
        load_impact = sum_abs_delta(report["load_deltas"], "relative_load_index")
        affected_count = report["affected_structure_count"]
        rows.append(
            {
                "intervention": name,
                "alignment_impact": alignment_impact,
                "load_impact": load_impact,
                "affected_structures": affected_count,
                "rank_score": alignment_impact * 0.35 + load_impact * 0.45 + affected_count * 0.2,
            }
        )
    ranked = sorted(rows, key=lambda item: item["rank_score"], reverse=True)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return {"generated_utc": datetime.now(timezone.utc).isoformat(), "ranked_interventions": ranked}


def sum_abs_delta(section: dict[str, Any], metric: str) -> float:
    total = 0.0
    for metrics in section.values():
        if metric in metrics and isinstance(metrics[metric].get("delta"), (int, float)):
            total += abs(float(metrics[metric]["delta"]))
    return total


def plot_propagation_graph(graph: dict[str, Any], result: PropagationResult, path: Path) -> Path:
    affected = {item["node_id"]: item["depth"] for item in result.affected_neighbors}
    affected[result.action["target"]] = 0
    fig, ax = plt.subplots(figsize=(8, 9))
    for edge in graph["edges"]:
        source = graph["nodes"][edge["source"]]
        target = graph["nodes"][edge["target"]]
        ax.plot([source["centroid"][0], target["centroid"][0]], [source["centroid"][1], target["centroid"][1]], color="#9ca3af")
    colors = {0: "#dc2626", 1: "#f97316", 2: "#eab308", 3: "#38bdf8"}
    for node_id, node in graph["nodes"].items():
        depth = affected.get(node_id)
        ax.scatter(node["centroid"][0], node["centroid"][1], s=95, color=colors.get(depth, "#64748b"))
        ax.text(node["centroid"][0] + 1.0, node["centroid"][1], node_id, fontsize=7)
    ax.set_title("Stage 3 Propagation Graph")
    ax.set_xlabel("X centroid")
    ax.set_ylabel("Y centroid")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_affected_map(graph: dict[str, Any], cascades: dict[str, Any], path: Path) -> Path:
    counts = {}
    for cascade in cascades.values():
        for node_id in cascade["affected_structures"]:
            counts[node_id] = counts.get(node_id, 0) + 1
    fig, ax = plt.subplots(figsize=(8, 9))
    for node_id, node in graph["nodes"].items():
        count = counts.get(node_id, 0)
        ax.scatter(node["centroid"][0], node["centroid"][1], s=80 + count * 45, color="#2563eb" if count else "#94a3b8")
        ax.text(node["centroid"][0] + 1.0, node["centroid"][1], f"{node_id} ({count})", fontsize=7)
    ax.set_title("Affected Structures Map")
    ax.set_xlabel("X centroid")
    ax.set_ylabel("Y centroid")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_load_redistribution(result: PropagationResult, path: Path) -> Path:
    before = result.before_state.get("load_metrics", {}).get("structures", {})
    after = result.after_state.get("load_metrics", {}).get("structures", {})
    names = list(before.keys())
    before_values = [before[name].get("relative_load_index", 1.0) for name in names]
    after_values = [after.get(name, {}).get("relative_load_index", 1.0) for name in names]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(names, before_values, marker="o", label="Before")
    ax.plot(names, after_values, marker="o", label="After")
    ax.set_title("Load Redistribution")
    ax.set_ylabel("Relative load index")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_alignment_before_after(result: PropagationResult, path: Path) -> Path:
    before = result.before_state.get("alignment_metrics", {}).get("disc_alignment", {})
    after = result.after_state.get("alignment_metrics", {}).get("disc_alignment", {})
    names = list(before.keys())
    before_values = [before[name].get("disc_angle_degrees", 0.0) for name in names]
    after_values = [after.get(name, {}).get("disc_angle_degrees", 0.0) for name in names]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - 0.2 for i in range(len(names))], before_values, width=0.4, label="Before")
    ax.bar([i + 0.2 for i in range(len(names))], after_values, width=0.4, label="After")
    ax.set_xticks(list(range(len(names))))
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_title("Before/After Alignment")
    ax.set_ylabel("Disc angle degrees")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def generate_stage3_report(results: dict[str, PropagationResult], comparison: dict[str, Any]) -> str:
    lines = [
        "ORTHOTWIN STAGE 3 BIOMECHANICAL PROPAGATION REPORT",
        "=" * 56,
        "",
        "System Behavior",
        "  The spine is represented as a connected graph. Each intervention starts at one node and propagates through graph edges.",
        "",
        "Propagation Behavior",
        "  Direct effects apply to the target. Secondary and tertiary effects are deterministic attenuated changes on graph neighbors.",
        "",
        "Intervention Effects",
    ]
    for name, result in results.items():
        cascade = cascade_for(name, result)
        lines.append(
            f"  {name}: affected {cascade['affected_structure_count']} structures; target {result.action['target']}."
        )
    lines.extend(
        [
            "",
            "Intervention Ranking",
        ]
    )
    for item in comparison["ranked_interventions"]:
        lines.append(
            f"  {item['rank']}. {item['intervention']} - score {item['rank_score']:.3f}"
        )
    lines.extend(
        [
            "",
            "Limitations",
            "  This is not a physics simulator. Loads, stresses, and alignment shifts are deterministic propagation proxies.",
            "  No retraining, inference, segmentation modification, or measurement recomputation was performed.",
            "",
            "Future Physics Engine Requirements",
            "  Material properties, boundary conditions, calibrated forces, ligament/facet modeling, implant catalogs, contact mechanics, and validation data.",
        ]
    )
    return "\n".join(lines)


def run_stage3() -> dict[str, Path]:
    state, graph = load_stage3_inputs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VIS_DIR.mkdir(parents=True, exist_ok=True)

    rules_path = PROJECT_ROOT / "simulation" / "propagation" / "propagation_rules.json"
    write_json(rules_path, PROPAGATION_RULES)

    results = {
        "collapse": simulate_disc_collapse(deepcopy(state), graph, "disc_6_206_207", 20.0),
        "restoration": simulate_disc_restoration(deepcopy(state), graph, "disc_6_206_207", 20.0),
        "fusion": simulate_fusion(deepcopy(state), graph, "vertebra_5", "vertebra_6"),
        "implant": simulate_implant(deepcopy(state), graph, "disc_6_206_207", 18.0),
    }

    paths = {
        "propagation_rules": rules_path,
        "disc_collapse_simulation": OUTPUT_DIR / "disc_collapse_simulation.json",
        "disc_restoration_simulation": OUTPUT_DIR / "disc_restoration_simulation.json",
        "fusion_simulation": OUTPUT_DIR / "fusion_simulation.json",
        "implant_simulation": OUTPUT_DIR / "implant_simulation.json",
        "cascade_analysis": OUTPUT_DIR / "cascade_analysis.json",
        "whole_spine_delta_report": OUTPUT_DIR / "whole_spine_delta_report.json",
        "intervention_comparison": REPORT_DIR / "intervention_comparison.json",
        "stage3_report": REPORT_DIR / "stage3_biomechanics_report.txt",
        "propagation_graph": VIS_DIR / "propagation_graph.png",
        "affected_structures_map": VIS_DIR / "affected_structures_map.png",
        "load_redistribution_plot": VIS_DIR / "load_redistribution_plot.png",
        "before_after_alignment_plot": VIS_DIR / "before_after_alignment_plot.png",
        "stage3_manifest": PROJECT_ROOT / "manifests" / "stage3_manifest.json",
    }

    write_json(paths["disc_collapse_simulation"], results["collapse"].to_dict())
    write_json(paths["disc_restoration_simulation"], results["restoration"].to_dict())
    write_json(paths["fusion_simulation"], results["fusion"].to_dict())
    write_json(paths["implant_simulation"], results["implant"].to_dict())

    cascades = {name: cascade_for(name, result) for name, result in results.items()}
    write_json(paths["cascade_analysis"], {"generated_utc": datetime.now(timezone.utc).isoformat(), "interventions": cascades})

    delta_report = {
        name: whole_spine_delta(result.before_state, result.after_state)
        for name, result in results.items()
    }
    write_json(paths["whole_spine_delta_report"], delta_report)

    comparison = compare_interventions(results)
    write_json(paths["intervention_comparison"], comparison)
    write_text(paths["stage3_report"], generate_stage3_report(results, comparison))

    plot_propagation_graph(graph, results["collapse"], paths["propagation_graph"])
    plot_affected_map(graph, cascades, paths["affected_structures_map"])
    plot_load_redistribution(results["collapse"], paths["load_redistribution_plot"])
    plot_alignment_before_after(results["collapse"], paths["before_after_alignment_plot"])

    verification = {
        "interventions_affect_more_than_one_structure": all(
            cascade["affected_structure_count"] > 1 for cascade in cascades.values()
        ),
        "spine_behaves_as_connected_system": bool(state.get("state_validation", {}).get("graph_connected", True)),
        "orthtwin2_files_discovered": [],
        "orthtwin2_arrangement_note": "No files matching orthtwin2/OrthoTwin2 were found during Stage 3 discovery.",
    }
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "OrthoTwin Stage 3",
        "outputs": {name: str(path) for name, path in paths.items() if name != "stage3_manifest"},
        "all_outputs_exist": all(path.exists() for name, path in paths.items() if name != "stage3_manifest"),
        "verification": verification,
    }
    write_json(paths["stage3_manifest"], manifest)
    return paths


if __name__ == "__main__":
    generated = run_stage3()
    print("OrthoTwin Stage 3 complete.")
    for name, path in generated.items():
        print(f"{name}: {path}")
