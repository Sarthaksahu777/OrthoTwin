"""Compare deterministic patient states before and after interventions."""

from __future__ import annotations

from typing import Any


NUMERIC_TYPES = (int, float)


def _percent_change(before: float | int | None, after: float | int | None) -> float | None:
    if before is None or after is None:
        return None
    if float(before) == 0.0:
        return None
    return ((float(after) - float(before)) / float(before)) * 100.0


def _disc_metric_changes(
    before_disc: dict[str, Any], after_disc: dict[str, Any]
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    before_vars = before_disc.get("state_variables", {})
    after_vars = after_disc.get("state_variables", {})
    metrics = sorted(set(before_vars) | set(after_vars))
    for metric in metrics:
        before_value = before_vars.get(metric)
        after_value = after_vars.get(metric)
        if before_value == after_value:
            continue
        changes[metric] = {
            "before": before_value,
            "after": after_value,
            "percent_change": _percent_change(before_value, after_value)
            if isinstance(before_value, NUMERIC_TYPES)
            and isinstance(after_value, NUMERIC_TYPES)
            else None,
        }
    return changes


def compare_states(
    before_state: dict[str, Any], after_state: dict[str, Any]
) -> dict[str, Any]:
    """Return structured before/after/percent-change deltas."""

    disc_changes = {}
    for disc_key, before_disc in before_state.get("discs", {}).items():
        after_disc = after_state.get("discs", {}).get(disc_key)
        if not after_disc:
            continue
        changes = _disc_metric_changes(before_disc, after_disc)
        if changes:
            disc_changes[disc_key] = {
                "name": before_disc.get("name"),
                "changes": changes,
            }

    alignment_changes = {}
    before_axes = before_state.get("alignment", {}).get("axes", {})
    after_axes = after_state.get("alignment", {}).get("axes", {})
    for axis, before_vector in before_axes.items():
        after_vector = after_axes.get(axis)
        if before_vector != after_vector:
            alignment_changes[axis] = {
                "before": before_vector,
                "after": after_vector,
            }

    return {
        "patient_id": before_state.get("patient_id"),
        "before": {
            "num_interventions": len(before_state.get("intervention_history", []))
        },
        "after": {
            "num_interventions": len(after_state.get("intervention_history", []))
        },
        "disc_changes": disc_changes,
        "alignment_changes": alignment_changes,
        "intervention_applied": after_state.get("intervention_history", [])[-1:]
    }


def generate_change_report(comparison: dict[str, Any]) -> str:
    lines = [
        "ORTHOTWIN STATE CHANGE REPORT",
        "=" * 31,
        f"Patient: {comparison.get('patient_id')}",
        "",
        "Before",
        f"  Interventions: {comparison['before']['num_interventions']}",
        "After",
        f"  Interventions: {comparison['after']['num_interventions']}",
        "",
        "Predicted Changes",
    ]
    if not comparison.get("disc_changes"):
        lines.append("  No measurable disc state changes.")
    for disc in comparison.get("disc_changes", {}).values():
        lines.append(f"  {disc['name']}")
        for metric, change in disc["changes"].items():
            percent = change["percent_change"]
            percent_text = "n/a" if percent is None else f"{percent:.2f}%"
            lines.append(
                f"    {metric}: {change['before']} -> {change['after']} ({percent_text})"
            )
    if comparison.get("alignment_changes"):
        lines.append("")
        lines.append("Alignment Changes")
        for axis in comparison["alignment_changes"]:
            lines.append(f"  {axis}: changed")
    return "\n".join(lines)

