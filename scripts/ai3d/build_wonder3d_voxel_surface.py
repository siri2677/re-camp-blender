#!/usr/bin/env python3
"""Build a review-only voxel surface from Wonder3D six-view masks.

This is a deterministic fallback for runtimes where the legacy NeuS extractor
does not finish.  It is intentionally a coarse visual-hull surface, not a
replacement for a neural reconstruction or a Production Mesh.  The OBJ is
written with an adjacent MTL so the generated RGB appearance can survive the
candidate registration step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageFilter

try:
    from .common import DEFAULT_CONTRACT_PATH, candidate_gate_fields, load_contract
except ImportError:
    from common import DEFAULT_CONTRACT_PATH, candidate_gate_fields, load_contract  # type: ignore


VIEW_NAMES = ("front", "front_right", "right", "back", "left", "front_left")
VIEW_AZIMUTHS = (0, 45, 90, 180, -90, -45)


@dataclass
class View:
    name: str
    theta: float
    mask: np.ndarray
    rgb: np.ndarray
    center_x: float
    center_y: float
    scale: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_view(rgb_dir: Path, normal_dir: Path, name: str, theta: int, dilation: int) -> View:
    normal_path = normal_dir / f"normals_000_{name}.png"
    rgb_path = rgb_dir / f"rgb_000_{name}.png"
    if not normal_path.is_file() or not rgb_path.is_file():
        raise FileNotFoundError(f"Wonder3D view pair is incomplete: {normal_path} / {rgb_path}")
    rgba = np.asarray(Image.open(normal_path).convert("RGBA"))
    mask = rgba[:, :, 3] > 128
    if dilation > 0:
        kernel = dilation * 2 + 1
        mask = np.asarray(
            Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(kernel))
        ) > 0
    ys, xs = np.where(mask)
    if xs.size < 100:
        raise ValueError(f"Wonder3D mask is too small: {name} ({xs.size} pixels)")
    return View(
        name=name,
        theta=math.radians(theta),
        mask=mask,
        rgb=np.asarray(Image.open(rgb_path).convert("RGB")),
        center_x=float((xs.min() + xs.max()) / 2),
        center_y=float((ys.min() + ys.max()) / 2),
        scale=float(ys.max() - ys.min() + 1),
    )


def load_views(rgb_dir: Path, normal_dir: Path, dilation: int = 2) -> list[View]:
    return [
        _load_view(rgb_dir, normal_dir, name, theta, dilation)
        for name, theta in zip(VIEW_NAMES, VIEW_AZIMUTHS)
    ]


def build_occupancy(views: list[View], resolution: int = 96) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if resolution < 16:
        raise ValueError("resolution must be at least 16")
    x_edges = np.linspace(-0.68, 0.68, resolution + 1)
    y_edges = np.linspace(-0.55, 0.55, resolution + 1)
    z_edges = np.linspace(-0.68, 0.68, resolution + 1)
    x_centers = (x_edges[:-1] + x_edges[1:]) / 2
    y_centers = (y_edges[:-1] + y_edges[1:]) / 2
    z_centers = (z_edges[:-1] + z_edges[1:]) / 2
    y_grid, x_grid, z_grid = np.meshgrid(y_centers, x_centers, z_centers, indexing="ij")
    occupancy = np.ones(y_grid.shape, dtype=bool)
    for view in views:
        horizontal = x_grid * math.cos(view.theta) + z_grid * math.sin(view.theta)
        px = np.rint(view.center_x + horizontal * view.scale).astype(np.int32)
        py = np.rint(view.center_y - y_grid * view.scale).astype(np.int32)
        valid = (px >= 0) & (px < 256) & (py >= 0) & (py < 256)
        occupancy &= valid & view.mask[np.clip(py, 0, 255), np.clip(px, 0, 255)]
    if not occupancy.any():
        raise ValueError("Wonder3D visual hull is empty")
    return occupancy, x_edges, y_edges, z_edges


def _surface_faces(occupancy: np.ndarray) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    vertex_map: dict[tuple[int, int, int], int] = {}
    vertices: list[tuple[int, int, int]] = []
    faces: list[tuple[int, int, int]] = []

    def vertex_id(key: tuple[int, int, int]) -> int:
        if key not in vertex_map:
            vertex_map[key] = len(vertices)
            vertices.append(key)
        return vertex_map[key]

    def add_quad(corners: list[tuple[int, int, int]]) -> None:
        a, b, c, d = (vertex_id(corner) for corner in corners)
        faces.extend(((a, b, c), (a, c, d)))

    directions = (
        (np.pad(occupancy[:, 1:, :], ((0, 0), (0, 1), (0, 0))), lambda y, x, z: [(x + 1, y, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x + 1, y, z + 1)]),
        (np.pad(occupancy[:, :-1, :], ((0, 0), (1, 0), (0, 0))), lambda y, x, z: [(x, y, z), (x, y, z + 1), (x, y + 1, z + 1), (x, y + 1, z)]),
        (np.pad(occupancy[1:, :, :], ((0, 1), (0, 0), (0, 0))), lambda y, x, z: [(x, y + 1, z), (x, y + 1, z + 1), (x + 1, y + 1, z + 1), (x + 1, y + 1, z)]),
        (np.pad(occupancy[:-1, :, :], ((1, 0), (0, 0), (0, 0))), lambda y, x, z: [(x, y, z), (x + 1, y, z), (x + 1, y, z + 1), (x, y, z + 1)]),
        (np.pad(occupancy[:, :, 1:], ((0, 0), (0, 0), (0, 1))), lambda y, x, z: [(x, y, z + 1), (x + 1, y, z + 1), (x + 1, y + 1, z + 1), (x, y + 1, z + 1)]),
        (np.pad(occupancy[:, :, :-1], ((0, 0), (0, 0), (1, 0))), lambda y, x, z: [(x, y, z), (x, y + 1, z), (x + 1, y + 1, z), (x + 1, y, z)]),
    )
    for neighbor, corner_builder in directions:
        for y, x, z in np.argwhere(occupancy & ~neighbor):
            add_quad(corner_builder(int(y), int(x), int(z)))
    return vertices, faces


def _sample_colors(vertices: np.ndarray, views: list[View]) -> np.ndarray:
    colors = np.zeros((len(vertices), 3), dtype=np.float32)
    counts = np.zeros(len(vertices), dtype=np.float32)
    for view in views:
        horizontal = vertices[:, 0] * math.cos(view.theta) + vertices[:, 2] * math.sin(view.theta)
        px = np.rint(view.center_x + horizontal * view.scale).astype(np.int32)
        py = np.rint(view.center_y - vertices[:, 1] * view.scale).astype(np.int32)
        valid = (px >= 0) & (px < 256) & (py >= 0) & (py < 256)
        indices = np.where(valid)[0]
        if indices.size:
            indices = indices[view.mask[py[indices], px[indices]]]
            if indices.size:
                colors[indices] += view.rgb[py[indices], px[indices]].astype(np.float32)
                counts[indices] += 1
    colors = np.divide(colors, np.maximum(counts[:, None], 1))
    colors[counts == 0] = 180
    return np.clip(colors, 0, 255).astype(np.uint8)


def write_obj_with_materials(
    output_obj: Path,
    vertices: list[tuple[int, int, int]],
    faces: list[tuple[int, int, int]],
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    z_edges: np.ndarray,
    colors: np.ndarray,
) -> tuple[Path, dict[str, int]]:
    world = np.asarray(
        [(x_edges[x], y_edges[y], z_edges[z]) for x, y, z in vertices], dtype=np.float32
    )
    material_groups: dict[tuple[int, int, int], int] = {}
    face_materials: list[int] = []
    for triangle in faces:
        average = np.clip(np.mean(colors[np.asarray(triangle, dtype=int)], axis=0), 0, 255).astype(int)
        key = tuple((average // 32) * 32)
        material_groups.setdefault(key, len(material_groups) + 1)
        face_materials.append(material_groups[key])
    output_obj.parent.mkdir(parents=True, exist_ok=True)
    output_mtl = output_obj.with_suffix(".mtl")
    with output_mtl.open("w", encoding="utf-8") as stream:
        for color, index in material_groups.items():
            stream.write(
                "newmtl color_%03d\nKd %.6f %.6f %.6f\nKa 0 0 0\nNs 20\n"
                % (index, color[0] / 255, color[1] / 255, color[2] / 255)
            )
    with output_obj.open("w", encoding="utf-8") as stream:
        stream.write(f"mtllib {output_mtl.name}\n")
        for point in world:
            stream.write("v %.6f %.6f %.6f\n" % (point[0], point[1], point[2]))
        last_material = None
        for triangle, material_index in zip(faces, face_materials):
            if material_index != last_material:
                stream.write(f"usemtl color_{material_index:03d}\n")
                last_material = material_index
            stream.write("f %d %d %d\n" % tuple(index + 1 for index in triangle))
    return output_mtl, {"vertexCount": len(world), "triangleCount": len(faces), "materialCount": len(material_groups)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rgb-dir", required=True, type=Path)
    parser.add_argument("--normal-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--dilation", type=int, default=2)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--character", default="CH101")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, args.character)
    views = load_views(args.rgb_dir.resolve(), args.normal_dir.resolve(), args.dilation)
    occupancy, x_edges, y_edges, z_edges = build_occupancy(views, args.resolution)
    vertices, faces = _surface_faces(occupancy)
    world = np.asarray([(x_edges[x], y_edges[y], z_edges[z]) for x, y, z in vertices], dtype=np.float32)
    colors = _sample_colors(world, views)
    output_obj = args.output_dir.resolve() / f"{args.character}_wonder3D_voxel_surface_v001.obj"
    output_mtl, metrics = write_obj_with_materials(
        output_obj, vertices, faces, x_edges, y_edges, z_edges, colors
    )
    report = {
        "status": "EXPERIMENTAL_VOXEL_SURFACE_MESH",
        "character": args.character,
        "provider": "wonder3D",
        "meshExtraction": "VISUAL_HULL_VOXEL_SURFACE_FALLBACK",
        "rgbDir": str(args.rgb_dir.resolve()),
        "normalDir": str(args.normal_dir.resolve()),
        "mesh": str(output_obj),
        "meshSha256": sha256_file(output_obj),
        "materialFile": str(output_mtl),
        "materialSha256": sha256_file(output_mtl),
        "resolution": args.resolution,
        "dilation": args.dilation,
        "viewCount": len(views),
        "viewNames": list(VIEW_NAMES),
        **metrics,
        "maskSource": "Wonder3D normal alpha",
        "colorSource": "Wonder3D RGB multi-view projection",
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "gateB": "PENDING_HUMAN_REVIEW",
        "sourceStatus": "AI_GENERATED_CANDIDATE_NOT_PRODUCTION",
        "warnings": [
            "Voxel surface is a fallback for a NeuS runtime timeout.",
            "The result is review-only and is not a Production Mesh.",
        ],
    }
    if args.reference_manifest and args.reference_manifest.is_file():
        report["referenceManifest"] = str(args.reference_manifest.resolve())
        report["referenceManifestSha256"] = sha256_file(args.reference_manifest.resolve())
    report.update(candidate_gate_fields(contract))
    report_path = args.output_dir.resolve() / "voxel-surface-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
