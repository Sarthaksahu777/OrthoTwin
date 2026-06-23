"""Generate text reports for deterministic OrthoTwin interventions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from comparison import compare_states, generate_change_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports" / "phase3"


def _format_summary(state: dict[str, Any]) -> list[str]:
    return [
        f"Patient ID: {state.get('patient_id')}",
        f"Structures: {state.get('segmentation', {}).get('num_structures')}",
        f"Discs: {len(state.get('discs', {}))}",
        f"Vertebrae: {len(state.get('vertebrae', {}))}",
        "Quality Flags: "
        f"{state.get('quality_metrics', {}).get('total_flagged_structures')}",
    ]


def generate_digital_twin_report(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    comparison = compare_states(before_state, after_state)
    latest_action = (
        after_state.get("intervention_history", [])[-1]
        if after_state.get("intervention_history")
        else {}
    )
    lines = [
        "ORTHOTWIN DIGITAL TWIN REPORT",
        "=" * 30,
        "",
        "Current State",
        *[f"  {line}" for line in _format_summary(before_state)],
        "",
        "Intervention Applied",
        f"  Type: {latest_action.get('type', 'none')}",
        f"  Target: {latest_action.get('target_name', latest_action.get('target', 'n/a'))}",
        f"  Parameters: {latest_action.get('parameters', {})}",
        "",
        "Predicted Changes",
        generate_change_report(comparison),
        "",
        "Geometry Differences",
    ]
    for disc in comparison.get("disc_changes", {}).values():
        lines.append(f"  {disc['name']}")
        for metric, change in disc["changes"].items():
            if metric in {"height", "volume"}:
                lines.append(
                    f"    {metric}: {change['before']} -> {change['after']}"
                )
    lines.extend(
        [
            "",
            "Version 1 Notes",
            "  Deterministic geometric rules only.",
            "  No AI models, neural networks, inference, or LLM calls are used.",
        ]
    )

    destination = Path(output_path or REPORTS_DIR / "digital_twin_report.txt")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination
