"""Demo workflow for OrthoTwin Phase 3 digital twin version 1."""

from __future__ import annotations

from pathlib import Path

from comparison import compare_states, generate_change_report
from digital_twin import SpineDigitalTwin
from reports.phase3.report_generator import generate_digital_twin_report
from simulation.interventions.simulation_engine import simulate_disc_height_restoration
from simulation.propagation.state_transition import StateTransition
from state_builder import build_patient_state_vector
from visualization.state.visualization import (
    plot_alignment_changes,
    plot_disc_changes,
    plot_state_comparison,
)


PROJECT_ROOT = Path(__file__).resolve().parent


def run_demo() -> dict[str, Path]:
    state_path = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector.json"
    before_state = build_patient_state_vector(output_path=state_path)

    twin = SpineDigitalTwin(state_path)
    before_state = twin.clone_state()

    target_disc = "disc_6_206_207"
    transition = StateTransition(
        before_state=before_state,
        action={
            "type": "disc_height_restoration",
            "target": target_disc,
            "parameters": {"new_height": 18.0},
        },
    )
    after_state = transition.apply(
        simulate_disc_height_restoration,
        target_disc,
        new_height=18.0,
    )
    twin.update_state(after_state)

    after_path = PROJECT_ROOT / "state" / "patient_states" / "patient_state_after_intervention.json"
    twin.save_state(after_path)

    comparison = compare_states(before_state, after_state)
    change_report_path = PROJECT_ROOT / "reports" / "phase3" / "state_change_report.txt"
    change_report_path.write_text(generate_change_report(comparison), encoding="utf-8")

    digital_report_path = generate_digital_twin_report(before_state, after_state)
    disc_plot = plot_disc_changes(before_state, after_state)
    state_plot = plot_state_comparison(before_state, after_state)
    alignment_plot = plot_alignment_changes(before_state, after_state)

    return {
        "state_vector": state_path,
        "after_state": after_path,
        "change_report": change_report_path,
        "digital_twin_report": digital_report_path,
        "disc_plot": disc_plot,
        "state_plot": state_plot,
        "alignment_plot": alignment_plot,
    }


if __name__ == "__main__":
    outputs = run_demo()
    print("OrthoTwin demo complete.")
    for name, path in outputs.items():
        print(f"{name}: {path}")
