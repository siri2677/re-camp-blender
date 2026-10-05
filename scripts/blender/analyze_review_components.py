#!/usr/bin/env python3
"""Analyze detached review-candidate mesh components without changing the blend."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

import bpy
from mathutils.kdtree import KDTree


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "BLENDER_REVIEW_COMPONENT_ANALYSIS_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
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
        component = [seed]
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
                    component.append(neighbor)
        result.append(component)
    return sorted(result, key=len, reverse=True)


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    report_path = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("blend contains no mesh objects")
    objects_report = []
    for obj in meshes:
        obj.data.calc_loop_triangles()
        groups = components(obj)
        world_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        largest = groups[0]
        largest_tree = KDTree(len(largest))
        for vertex_index in largest:
            largest_tree.insert(world_vertices[vertex_index], vertex_index)
        largest_tree.balance()
        component_report = []
        for rank, group in enumerate(groups):
            points = [world_vertices[index] for index in group]
            minimum = [min(point[axis] for point in points) for axis in range(3)]
            maximum = [max(point[axis] for point in points) for axis in range(3)]
            nearest = None
            if rank:
                for vertex_index in group:
                    _, main_index, distance = largest_tree.find(world_vertices[vertex_index])
                    if nearest is None or distance < nearest["distance"]:
                        nearest = {
                            "distance": round(float(distance), 8),
                            "componentVertexIndex": vertex_index,
                            "largestComponentVertexIndex": main_index,
                        }
            component_report.append(
                {
                    "rank": rank,
                    "vertexCount": len(group),
                    "boundsMin": [round(float(value), 8) for value in minimum],
                    "boundsMax": [round(float(value), 8) for value in maximum],
                    "nearestToLargest": nearest,
                }
            )
        objects_report.append(
            {
                "object": obj.name,
                "vertexCount": len(obj.data.vertices),
                "edgeCount": len(obj.data.edges),
                "triangleCount": len(obj.data.loop_triangles),
                "componentCount": len(groups),
                "components": component_report,
            }
        )
    report = {
        "algorithm": ALGORITHM,
        "status": "REVIEW_COMPONENT_ANALYSIS",
        "sourceBlend": str(source),
        "sourceBlendSha256": sha256_file(source),
        "objects": objects_report,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "This report is read-only and does not repair, merge, or promote geometry.",
            "Nearest-component distance is a heuristic for review-only repair planning.",
            "Human Gate B review remains required and Unity input remains disabled.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
