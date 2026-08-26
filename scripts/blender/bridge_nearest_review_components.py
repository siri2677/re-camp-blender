#!/usr/bin/env python3
"""Add a tiny review-only surface bridge between nearby mesh components."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "BLENDER_NEAREST_COMPONENT_SURFACE_BRIDGE_REVIEW_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--component-rank", type=int, default=1)
    parser.add_argument("--sides", type=int, default=6)
    parser.add_argument("--radius", type=float, default=0.002)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def components(obj: bpy.types.Object) -> list[list[int]]:
    adjacency = [[] for _ in obj.data.vertices]
    for edge in obj.data.edges:
        a, b = edge.vertices
        adjacency[a].append(b)
        adjacency[b].append(a)
    unseen = set(range(len(adjacency)))
    result: list[list[int]] = []
    while unseen:
        seed = unseen.pop()
        queue = deque([seed])
        group = [seed]
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
                    group.append(neighbor)
        result.append(group)
    return sorted(result, key=len, reverse=True)


def topology(obj: bpy.types.Object) -> dict[str, int]:
    obj.data.calc_loop_triangles()
    return {
        "vertexCount": len(obj.data.vertices),
        "edgeCount": len(obj.data.edges),
        "triangleCount": len(obj.data.loop_triangles),
        "componentCount": len(components(obj)),
    }


def enforce_review_gate() -> None:
    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["surface_bridge_algorithm"] = ALGORITHM


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if args.component_rank < 1 or args.sides < 3 or args.radius <= 0:
        raise ValueError("component-rank, sides, and radius are invalid")
    if output_blend == source:
        raise ValueError("output blend must not overwrite the input")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise ValueError("review bridge requires exactly one mesh object")
    obj = meshes[0]
    groups = components(obj)
    if args.component_rank >= len(groups):
        raise ValueError("selected component rank is unavailable")
    main_group, target_group = groups[0], groups[args.component_rank]
    world_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    tree = KDTree(len(main_group))
    for vertex_index in main_group:
        tree.insert(world_vertices[vertex_index], vertex_index)
    tree.balance()
    nearest = None
    for vertex_index in target_group:
        _, main_index, distance = tree.find(world_vertices[vertex_index])
        if nearest is None or distance < nearest["distance"]:
            nearest = {
                "distance": float(distance),
                "componentVertexIndex": vertex_index,
                "largestComponentVertexIndex": main_index,
            }
    assert nearest is not None
    point_a = world_vertices[nearest["largestComponentVertexIndex"]]
    point_b = world_vertices[nearest["componentVertexIndex"]]
    direction = point_b - point_a
    distance = direction.length
    if distance <= 1e-6:
        raise ValueError("nearest component points already overlap")
    direction.normalize()
    reference = Vector((0.0, 0.0, 1.0))
    if abs(direction.dot(reference)) > 0.9:
        reference = Vector((0.0, 1.0, 0.0))
    basis_u = direction.cross(reference).normalized()
    basis_v = direction.cross(basis_u).normalized()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = topology(obj)
    vertex_a = bm.verts[nearest["largestComponentVertexIndex"]]
    vertex_b = bm.verts[nearest["componentVertexIndex"]]
    ring_a = []
    ring_b = []
    local_matrix = obj.matrix_world.inverted()
    for index in range(args.sides):
        angle = 2.0 * 3.141592653589793 * index / args.sides
        offset = args.radius * (basis_u * math.cos(angle) + basis_v * math.sin(angle))
        ring_a.append(bm.verts.new(local_matrix @ (point_a + offset)))
        ring_b.append(bm.verts.new(local_matrix @ (point_b + offset)))
    for index in range(args.sides):
        next_index = (index + 1) % args.sides
        bm.faces.new((ring_a[index], ring_a[next_index], ring_b[next_index], ring_b[index]))
        bm.faces.new((vertex_a, ring_a[next_index], ring_a[index]))
        bm.faces.new((vertex_b, ring_b[index], ring_b[next_index]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    after = topology(obj)
    enforce_review_gate()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", export_apply=True)
    report = {
        "algorithm": ALGORITHM,
        "status": "REVIEW_COMPONENT_SURFACE_BRIDGE_APPLIED",
        "sourceBlend": str(source),
        "sourceBlendSha256": source_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb),
        "componentRank": args.component_rank,
        "sides": args.sides,
        "radius": args.radius,
        "nearestDistance": round(distance, 8),
        "topologyBefore": before,
        "topologyAfter": after,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "The bridge is a tiny review-only repair and may not be semantically correct.",
            "This output is not a Production Mesh and cannot enter Unity.",
            "Re-render, score, and human Gate B review remain mandatory.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
