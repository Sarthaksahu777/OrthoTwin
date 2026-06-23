"""Compare geometry-aware surgical outcomes against baseline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CLINICAL_STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "phase7"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def baseline_metrics(clinical: dict[str, Any]) -> dict[str, float]:
    return {
        "mean_disc_height": mean(
            [
                float(item.get("mean_height", 0.0))
                for item in clinical.get("disc_heights", {}).values()
                if isinstance(item.get("mean_height"), (int, float))
            ]
        ),
        "global_curvature": float(clinical.get("curvature", {}).get("global_curvature", 0.0)),
        "mean_alignment_tilt": mean(
            [
                float(item.get("disc_tilt_degrees", 0.0))
                for item in clinical.get("alignment", {}).get("disc_alignment", {}).values()
                if isinstance(item.get("disc_tilt_degrees"), (int, float))
            ]
        ),
        "mean_load": 1.0,
    }


def rebuilt_metrics(rebuilt: dict[str, Any]) -> dict[str, float]:
    clinical = rebuilt.get("clinical_state", {})
    loads = rebuilt.get("load_distribution", {}).get("structures", {})
    return {
        "mean_disc_height": mean(
            [
                float(item.get("mean_height", 0.0))
                for item in clinical.get("disc_heights", {}).values()
                if isinstance(item.get("mean_height"), (int, float))
            ]
        ),
        "global_curvature": float(rebuilt.get("curvature", {}).get("global_curvature", 0.0)),
        "mean_alignment_tilt": mean(
            [
                float(item.get("disc_tilt_degrees", 0.0))
                for item in rebuilt.get("alignment", {}).get("disc_alignment", {}).values()
                if isinstance(item.get("disc_tilt_degrees"), (int, float))
            ]
        ),
        "mean_load": mean(
            [
                float(item.get("relative_load_index", 0.0))
                for item in loads.values()
                if isinstance(item.get("relative_load_index"), (int, float))
            ]
        ),
    }


def metric_delta(before: float, after: float) -> dict[str, float | None]:
    delta = after - before
    return {
        "before": before,
        "after": after,
        "delta": delta,
        "percent_change": None if before == 0 else delta / before * 100.0,
    }


def affected_structures(result: dict[str, Any]) -> list[str]:
    latest = result.get("geometry_modification", {}).get("modification_history", [])
    if not latest:
        latest = [result.get("geometry_modification", {})]
    affected = set()
    for entry in latest:
        for change in entry.get("geometry_changes", []):
            if change.get("object_id"):
                affected.add(change["object_id"])
        for created in entry.get("created_objects", []):
            affected.add(created)
        target = entry.get("target")
        if target:
            affected.add(target)
    return sorted(affected)


def compare_surgical_outcomes(results: dict[str, dict[str, Any]], rebuilt_states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = baseline_metrics(load_json(BASE_CLINICAL_STATE_PATH))
    rows = []
    for name, result in results.items():
        rebuilt = rebuilt_states[name]
        metrics = rebuilt_metrics(rebuilt)
        rows.append(
            {
                "surgery": name,
                "scenario_id": result.get("scenario_id"),
                "structures_affected": affected_structures(result),
                "alignment_change": metric_delta(baseline["mean_alignment_tilt"], metrics["mean_alignment_tilt"]),
                "disc_height_change": metric_delta(baseline["mean_disc_height"], metrics["mean_disc_height"]),
                "curvature_change": metric_delta(baseline["global_curvature"], metrics["global_curvature"]),
                "load_redistribution": metric_delta(baseline["mean_load"], metrics["mean_load"]),
                "rebuilt_state_file": result.get("rebuilt_state_file"),
            }
        )
    matrix = {
        "generated_utc": utc_now(),
        "baseline": baseline,
        "rows": rows,
        "comparison_basis": "Geometry was modified first; measurements were rebuilt from modified geometry proxies.",
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    write_json(OUTPUT_DIR / "surgical_comparison_matrix.json", matrix)
    return matrix
