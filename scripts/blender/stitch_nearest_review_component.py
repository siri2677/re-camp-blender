#!/usr/bin/env python3
"""Weld one nearby detached review component at its nearest surface point.

This is a conservative review-only repair.  It moves only the selected
component by the measured nearest-point gap and then welds coincident vertices;
it does not invent semantic landmarks or enable any production gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "BLENDER_NEAREST_COMPONENT_WELD_REVIEW_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--component-rank", type=int, default=1)
    parser.add_argument("--merge-distance", type=float, default=0.0015)
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
    scene["nearest_component_weld_algorithm"] = ALGORITHM


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if args.component_rank < 1:
        raise ValueError("component-rank must select a detached component")
    if args.merge_distance <= 0:
        raise ValueError("merge-distance must be positive")
    if output_blend == source:
        raise ValueError("output blend must not overwrite the input")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise ValueError("review weld requires exactly one mesh object")
    obj = meshes[0]
    groups = components(obj)
    if args.component_rank >= len(groups):
        raise ValueError(
            f"component-rank {args.component_rank} is unavailable; component count is {len(groups)}"
        )
    main_group = groups[0]
    target_group = groups[args.component_rank]
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
    before = topology(obj)
    target_point = world_vertices[nearest["componentVertexIndex"]]
    main_point = world_vertices[nearest["largestComponentVertexIndex"]]
    delta_world = main_point - target_point
    delta_local = obj.matrix_world.inverted().to_3x3() @ delta_world
    for vertex_index in target_group:
        obj.data.vertices[vertex_index].co += delta_local
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    vertices_before_weld = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=args.merge_distance)
    merged_vertex_count = max(0, vertices_before_weld - len(bm.verts))
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
        "status": "REVIEW_COMPONENT_WELD_APPLIED",
        "sourceBlend": str(source),
        "sourceBlendSha256": source_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb),
        "componentRank": args.component_rank,
        "targetVertexCount": len(target_group),
        "nearestDistance": round(nearest["distance"], 8),
        "translationWorld": [round(float(value), 8) for value in delta_world],
        "mergeDistance": args.merge_distance,
        "mergedVertexCount": merged_vertex_count,
        "topologyBefore": before,
        "topologyAfter": after,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "This weld moves one nearby detached review component and is not final art repair.",
            "A connected graph does not prove semantic correctness or production topology.",
            "Re-render, score, and human Gate B review remain mandatory.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
