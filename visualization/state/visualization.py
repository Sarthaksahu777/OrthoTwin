"""Plot deterministic state changes for OrthoTwin."""

from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VISUALIZATION_DIR = PROJECT_ROOT / "visualization" / "state"


def _load_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for visualization. Install project requirements "
            "or run non-visual reports only."
        ) from exc
    return plt


def plot_disc_changes(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    plt = _load_pyplot()
    names = []
    before_heights = []
    after_heights = []
    for key, before_disc in before_state.get("discs", {}).items():
        after_disc = after_state.get("discs", {}).get(key)
        if not after_disc:
            continue
        names.append(before_disc.get("name", key))
        before_heights.append(before_disc.get("state_variables", {}).get("height", 0))
        after_heights.append(after_disc.get("state_variables", {}).get("height", 0))

    x_positions = range(len(names))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([x - 0.2 for x in x_positions], before_heights, width=0.4, label="Before")
    ax.bar([x + 0.2 for x in x_positions], after_heights, width=0.4, label="After")
    ax.set_ylabel("Disc height (voxel units)")
    ax.set_title("Disc Height Changes")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.legend()
    fig.tight_layout()
    destination = Path(output_path or VISUALIZATION_DIR / "disc_changes.png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)
    return destination


def plot_state_comparison(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    plt = _load_pyplot()
    names = []
    before_volumes = []
    after_volumes = []
    for key, before_disc in before_state.get("discs", {}).items():
        after_disc = after_state.get("discs", {}).get(key)
        if not after_disc:
            continue
        names.append(before_disc.get("name", key))
        before_volumes.append(before_disc.get("state_variables", {}).get("volume", 0))
        after_volumes.append(after_disc.get("state_variables", {}).get("volume", 0))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(names, before_volumes, marker="o", label="Before")
    ax.plot(names, after_volumes, marker="o", label="After")
    ax.set_ylabel("Volume (voxel units)")
    ax.set_title("Disc Volume State Comparison")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    destination = Path(output_path or VISUALIZATION_DIR / "state_comparison.png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)
    return destination


def plot_alignment_changes(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    plt = _load_pyplot()
    before_axes = before_state.get("alignment", {}).get("axes", {})
    after_axes = after_state.get("alignment", {}).get("axes", {})
    labels = list(before_axes)
    before_values = [before_axes[label][1] for label in labels]
    after_values = [after_axes.get(label, before_axes[label])[1] for label in labels]

    x_positions = range(len(labels))
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([x - 0.2 for x in x_positions], before_values, width=0.4, label="Before")
    ax.bar([x + 0.2 for x in x_positions], after_values, width=0.4, label="After")
    ax.set_ylabel("Axis Y component")
    ax.set_title("Alignment Axis Comparison")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend()
    fig.tight_layout()
    destination = Path(output_path or VISUALIZATION_DIR / "alignment_changes.png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)
    return destination
