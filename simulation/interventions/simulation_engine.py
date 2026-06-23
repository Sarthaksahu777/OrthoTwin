"""Deterministic intervention rules for OrthoTwin version 1."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def _find_disc_key(state: dict[str, Any], disc_id: str) -> str:
    discs = state.get("discs", {})
    if disc_id in discs:
        return disc_id
    for key, disc in discs.items():
        if disc.get("name") == disc_id or str(disc.get("class_id")) == str(disc_id):
            return key
    raise KeyError(f"Disc {disc_id!r} not found.")


def _append_history(state: dict[str, Any], action: dict[str, Any]) -> None:
    state.setdefault("intervention_history", []).append(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **action,
        }
    )


def _scale_disc_volume(disc: dict[str, Any], scale: float) -> None:
    variables = disc.setdefault("state_variables", {})
    if variables.get("volume") is not None:
        variables["volume"] = max(0.0, float(variables["volume"]) * scale)
    if disc.get("approx_volume") is not None:
        disc["approx_volume"] = max(0.0, float(disc["approx_volume"]) * scale)


def _update_height(disc: dict[str, Any], new_height: float) -> tuple[float, float]:
    variables = disc.setdefault("state_variables", {})
    old_height = float(
        variables.get("height")
        or disc.get("bounding_box", {}).get("depth")
        or new_height
    )
    variables["height"] = float(new_height)
    disc.setdefault("bounding_box", {})["depth"] = float(new_height)
    pca_lengths = disc.setdefault("pca_lengths", [])
    if pca_lengths:
        pca_lengths[-1] = float(new_height)
    ratio = float(new_height) / old_height if old_height else 1.0
    _scale_disc_volume(disc, ratio)
    if variables.get("severity_score") is not None:
        reduction = max(0.0, ratio - 1.0) * 0.5
        variables["severity_score"] = max(
            0.0, float(variables["severity_score"]) - reduction
        )
    return old_height, float(new_height)


def simulate_disc_height_restoration(
    state: dict[str, Any],
    disc_id: str,
    new_height: float,
) -> dict[str, Any]:
    """Restore a disc to a target height using simple geometric scaling."""

    if new_height <= 0:
        raise ValueError("new_height must be positive.")
    next_state = copy.deepcopy(state)
    disc_key = _find_disc_key(next_state, disc_id)
    disc = next_state["discs"][disc_key]
    old_height, target_height = _update_height(disc, new_height)
    _append_history(
        next_state,
        {
            "type": "disc_height_restoration",
            "target": disc_key,
            "target_name": disc.get("name"),
            "parameters": {
                "old_height": old_height,
                "new_height": target_height,
            },
        },
    )
    return next_state


def simulate_disc_decompression(
    state: dict[str, Any],
    disc_id: str,
    decompression_percent: float = 20.0,
) -> dict[str, Any]:
    """Reduce disc pressure proxy and severity by a deterministic percentage."""

    if not 0 <= decompression_percent <= 100:
        raise ValueError("decompression_percent must be between 0 and 100.")
    next_state = copy.deepcopy(state)
    disc_key = _find_disc_key(next_state, disc_id)
    disc = next_state["discs"][disc_key]
    variables = disc.setdefault("state_variables", {})
    variables["decompression_percent"] = min(
        100.0,
        float(variables.get("decompression_percent", 0.0))
        + float(decompression_percent),
    )
    if variables.get("severity_score") is not None:
        variables["severity_score"] = max(
            0.0,
            float(variables["severity_score"])
            * (1.0 - float(decompression_percent) / 100.0),
        )
    _append_history(
        next_state,
        {
            "type": "disc_decompression",
            "target": disc_key,
            "target_name": disc.get("name"),
            "parameters": {"decompression_percent": decompression_percent},
        },
    )
    return next_state


def simulate_discectomy(
    state: dict[str, Any],
    disc_id: str,
    removed_fraction: float = 0.25,
) -> dict[str, Any]:
    """Remove a deterministic fraction of disc volume."""

    if not 0 <= removed_fraction <= 1:
        raise ValueError("removed_fraction must be between 0 and 1.")
    next_state = copy.deepcopy(state)
    disc_key = _find_disc_key(next_state, disc_id)
    disc = next_state["discs"][disc_key]
    variables = disc.setdefault("state_variables", {})
    previous_removed = float(variables.get("removed_fraction", 0.0))
    variables["removed_fraction"] = min(1.0, previous_removed + removed_fraction)
    _scale_disc_volume(disc, 1.0 - removed_fraction)
    _append_history(
        next_state,
        {
            "type": "discectomy",
            "target": disc_key,
            "target_name": disc.get("name"),
            "parameters": {"removed_fraction": removed_fraction},
        },
    )
    return next_state


def simulate_implant_insertion(
    state: dict[str, Any],
    disc_id: str,
    implant_height: float,
    implant_volume: float | None = None,
) -> dict[str, Any]:
    """Insert an implant and update height/volume proxies."""

    if implant_height <= 0:
        raise ValueError("implant_height must be positive.")
    next_state = copy.deepcopy(state)
    disc_key = _find_disc_key(next_state, disc_id)
    disc = next_state["discs"][disc_key]
    old_height, target_height = _update_height(disc, implant_height)
    variables = disc.setdefault("state_variables", {})
    variables["implant_inserted"] = True
    variables["implant_height"] = float(implant_height)
    if implant_volume is not None:
        variables["implant_volume"] = float(implant_volume)
        variables["volume"] = float(variables.get("volume", 0.0)) + float(
            implant_volume
        )
    _append_history(
        next_state,
        {
            "type": "implant_insertion",
            "target": disc_key,
            "target_name": disc.get("name"),
            "parameters": {
                "old_height": old_height,
                "implant_height": target_height,
                "implant_volume": implant_volume,
            },
        },
    )
    return next_state

