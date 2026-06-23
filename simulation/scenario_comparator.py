"""Phase 5 scenario comparison and internal ranking utilities.

Scores are deterministic digital-twin metrics only. They are not clinical
recommendations and do not claim treatment validity.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "state" / "scenarios"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase5"


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


def height_score(scenario: dict[str, Any]) -> float:
    changes = scenario.get("metrics_changed", {}).get("disc_height", {})
    return sum(float(change.get("percent_change") or 0.0) for change in changes.values())


def alignment_delta(scenario: dict[str, Any]) -> float:
    total = 0.0
    for change in scenario.get("metrics_changed", {}).get("alignment", {}).values():
        total += abs(float(change.get("disc_angle_degrees", {}).get("delta") or 0.0))
        total += abs(float(change.get("disc_tilt_degrees", {}).get("delta") or 0.0))
    return total


def load_delta(scenario: dict[str, Any]) -> float:
    return float(scenario.get("metrics_changed", {}).get("propagation_magnitude", 0.0))


def affected_count(scenario: dict[str, Any]) -> int:
    return int(scenario.get("metrics_changed", {}).get("affected_structure_count", 0))


def signed_alignment_improvement(scenario: dict[str, Any]) -> float:
    """Negative tilt/angle offset is treated as an internal improvement proxy."""
    total = 0.0
    for change in scenario.get("metrics_changed", {}).get("alignment", {}).values():
        total += float(change.get("disc_angle_degrees", {}).get("delta") or 0.0)
        total += float(change.get("disc_tilt_degrees", {}).get("delta") or 0.0)
    return -total


def scenario_row(scenario: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "baseline_id": baseline["id"],
        "intervention": scenario["intervention"],
        "target": scenario.get("target"),
        "disc_height_score": height_score(scenario),
        "alignment_delta_abs": alignment_delta(scenario),
        "alignment_improvement_proxy": signed_alignment_improvement(scenario),
        "load_impact": load_delta(scenario),
        "propagation_magnitude": load_delta(scenario),
        "affected_structure_count": affected_count(scenario),
        "future_state_file": scenario.get("future_state_file"),
        "not_medical_advice": True,
    }


def normalize(value: float, values: list[float], invert: bool = False) -> float:
    if not values:
        return 0.0
    low = min(values)
    high = max(values)
    if high == low:
        normalized = 1.0
    else:
        normalized = (value - low) / (high - low)
    return 1.0 - normalized if invert else normalized


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alignment_values = [float(row["alignment_improvement_proxy"]) for row in rows]
    height_values = [float(row["disc_height_score"]) for row in rows]
    propagation_values = [float(row["propagation_magnitude"]) for row in rows]
    affected_values = [float(row["affected_structure_count"]) for row in rows]

    ranked = []
    for row in rows:
        alignment_component = normalize(float(row["alignment_improvement_proxy"]), alignment_values)
        height_component = normalize(float(row["disc_height_score"]), height_values)
        propagation_component = normalize(float(row["propagation_magnitude"]), propagation_values, invert=True)
        stability_component = normalize(float(row["affected_structure_count"]), affected_values, invert=True)
        total = (
            alignment_component * 0.30
            + height_component * 0.30
            + propagation_component * 0.25
            + stability_component * 0.15
        )
        ranked.append(
            {
                "scenario_id": row["scenario_id"],
                "rank_basis": {
                    "alignment_improvement": alignment_component,
                    "height_restoration": height_component,
                    "minimal_propagation_damage": propagation_component,
                    "structural_stability": stability_component,
                },
                "total_score": total,
                "not_medical_advice": True,
                "clinical_validity_claim": "none",
            }
        )

    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def compare_and_rank(
    baseline: dict[str, Any] | None = None, scenarios: list[dict[str, Any]] | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    baseline = baseline or load_json(SCENARIO_DIR / "baseline_scenario.json", {})
    if scenarios is None:
        scenarios = []
        for path in sorted(SCENARIO_DIR.glob("*.json")):
            if path.name in {"baseline_scenario.json", "scenario_schema.json"}:
                continue
            scenarios.append(load_json(path, {}))

    rows = [scenario_row(scenario, baseline) for scenario in scenarios]
    rankings = rank_rows(rows)
    comparison = {
        "generated_utc": utc_now(),
        "baseline": baseline.get("id", "baseline"),
        "matrix": rows,
        "metric_definitions": {
            "disc_height_score": "Sum of scenario percent height changes.",
            "alignment_delta_abs": "Absolute deterministic alignment offset.",
            "load_impact": "Summed absolute load-index delta across changed structures.",
            "affected_structure_count": "Number of structures with changed height, load, or alignment.",
        },
        "not_medical_advice": True,
    }
    return comparison, rankings


def main() -> None:
    comparison, rankings = compare_and_rank()
    comparison_path = write_json(REPORT_DIR / "scenario_comparison_matrix.json", comparison)
    ranking_path = write_json(REPORT_DIR / "scenario_ranking.json", rankings)
    print(f"Wrote {comparison_path}")
    print(f"Wrote {ranking_path}")


if __name__ == "__main__":
    main()
