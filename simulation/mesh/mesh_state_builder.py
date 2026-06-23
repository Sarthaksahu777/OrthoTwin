"""Build mesh-level state vectors from reconstructed OrthoTwin structures."""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MESH_PATH = PROJECT_ROOT / "measurements" / "geometry" / "reconstructed_structures.pkl"
OUTPUT_DIR = PROJECT_ROOT / "state" / "mesh"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def load_meshes(path: Path = MESH_PATH) -> dict[str, dict[str, Any]]:
    with path.open("rb") as handle:
        meshes = pickle.load(handle)
    return {item["name"]: {"vertices": np.asarray(item["verts"], dtype=float), "faces": np.asarray(item["faces"], dtype=int)} for item in meshes}


def structure_id(name: str) -> str:
    cleaned = (
        name.lower()
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )
    if cleaned.startswith("disc_"):
        return cleaned
    if cleaned.startswith("vertebra_"):
        return cleaned
    return cleaned


def pca_axes(vertices: np.ndarray) -> tuple[list[list[float]], list[float]]:
    centered = vertices - vertices.mean(axis=0)
    covariance = np.cov(centered.T)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    return vectors[:, order].T.tolist(), values[order].tolist()


def surface_area(vertices: np.ndarray, faces: np.ndarray) -> float:
    if faces.size == 0:
        return 0.0
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return float(np.linalg.norm(cross, axis=1).sum() * 0.5)


def mesh_metrics(vertices: np.ndarray, faces: np.ndarray) -> dict[str, Any]:
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    dims = maxs - mins
    axes, variances = pca_axes(vertices)
    projections = (vertices - vertices.mean(axis=0)) @ np.asarray(axes).T
    pca_lengths = (projections.max(axis=0) - projections.min(axis=0)).tolist()
    return {
        "vertex_count": int(vertices.shape[0]),
        "face_count": int(faces.shape[0]),
        "centroid": vertices.mean(axis=0).tolist(),
        "pca_axes": axes,
        "pca_variances": variances,
        "pca_lengths": pca_lengths,
        "bounding_box": {
            "min": mins.tolist(),
            "max": maxs.tolist(),
            "dimensions": dims.tolist(),
            "volume_estimate": float(np.prod(dims)),
        },
        "volume_estimate": float(np.prod(dims)),
        "surface_area": surface_area(vertices, faces),
        "height_estimate": float(min(pca_lengths)) if pca_lengths else 0.0,
    }


def build_mesh_state(meshes: dict[str, dict[str, Any]] | None = None, include_arrays: bool = False) -> dict[str, Any]:
    meshes = meshes or load_meshes()
    structures = {}
    for name, mesh in meshes.items():
        sid = structure_id(name)
        metrics = mesh_metrics(mesh["vertices"], mesh["faces"])
        record = {
            "id": sid,
            "name": name,
            "type": "disc" if name.lower().startswith("disc") else "vertebra",
            **metrics,
        }
        if include_arrays:
            record["vertices"] = mesh["vertices"].tolist()
            record["faces"] = mesh["faces"].tolist()
        structures[sid] = record
    return {
        "generated_utc": utc_now(),
        "source": str(MESH_PATH),
        "structure_count": len(structures),
        "structures": structures,
        "units": "voxel units; physical calibration remains blocked unless Patient Alpha spacing is proven",
        "not_medical_advice": True,
    }


def mesh_inventory(meshes: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    meshes = meshes or load_meshes()
    rows = []
    for name, mesh in meshes.items():
        rows.append(
            {
                "id": structure_id(name),
                "name": name,
                "type": "disc" if name.lower().startswith("disc") else "vertebra",
                "vertex_count": int(mesh["vertices"].shape[0]),
                "face_count": int(mesh["faces"].shape[0]),
            }
        )
    return {
        "generated_utc": utc_now(),
        "source": str(MESH_PATH),
        "total_structures": len(rows),
        "vertebra_meshes": len([row for row in rows if row["type"] == "vertebra"]),
        "disc_meshes": len([row for row in rows if row["type"] == "disc"]),
        "structures": rows,
    }


def main() -> None:
    meshes = load_meshes()
    write_json(OUTPUT_DIR / "mesh_inventory.json", mesh_inventory(meshes))
    write_json(OUTPUT_DIR / "mesh_state_vector.json", build_mesh_state(meshes, include_arrays=False))
    print("Mesh state generated.")


if __name__ == "__main__":
    main()
