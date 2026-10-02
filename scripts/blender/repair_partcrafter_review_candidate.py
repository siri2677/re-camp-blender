#!/usr/bin/env python3
"""Repair a stored PartCrafter review mesh without rerunning the provider.

PartCrafter's inference is one-shot by contract.  This script is therefore a
bounded post-processing experiment: it joins the provider objects, adds a
measured review-only bridge only when components are close enough, applies a
triangle budget, and restores the coarse CH101 review palette.  It never
claims semantic correctness and never opens Production, Gate B, or Unity.
"""

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
ALGORITHM = "PARTCRAFTER_STORED_ARTIFACT_CONNECTIVITY_AND_BUDGET_REPAIR_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--character", default="CH101")
    parser.add_argument("--max-triangles", type=int, default=300000)
    parser.add_argument("--max-bridge-distance", type=float, default=0.12)
    parser.add_argument("--bridge-radius", type=float, default=0.007)
    parser.add_argument("--bridge-sides", type=int, default=6)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def topology(obj: bpy.types.Object) -> dict[str, int]:
    obj.data.calc_loop_triangles()
    return {
        "vertexCount": len(obj.data.vertices),
        "edgeCount": len(obj.data.edges),
        "triangleCount": len(obj.data.loop_triangles),
        "componentCount": len(components(obj)),
    }


def components(obj: bpy.types.Object) -> list[list[int]]:
    adjacency = [[] for _ in obj.data.vertices]
    for edge in obj.data.edges:
        left, right = edge.vertices
        adjacency[left].append(right)
        adjacency[right].append(left)
    unseen = set(range(len(adjacency)))
    groups: list[list[int]] = []
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
        groups.append(group)
    return sorted(groups, key=len, reverse=True)


def mesh_objects() -> list[bpy.types.Object]:
    objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not objects:
        raise ValueError("stored PartCrafter blend contains no mesh objects")
    return objects


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    if not points:
        raise ValueError("stored PartCrafter mesh has no vertices")
    return (
        Vector(tuple(min(point[index] for point in points) for index in range(3))),
        Vector(tuple(max(point[index] for point in points) for index in range(3))),
    )


def join_meshes(objects: list[bpy.types.Object]) -> bpy.types.Object:
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(False)
    active = objects[0]
    active.select_set(True)
    bpy.context.view_layer.objects.active = active
    if len(objects) > 1:
        for obj in objects[1:]:
            obj.select_set(True)
        bpy.ops.object.join()
    return active


def nearest_pair(
    main_group: list[int], target_group: list[int], world_vertices: list[Vector]
) -> dict[str, object]:
    tree = KDTree(len(main_group))
    for index in main_group:
        tree.insert(world_vertices[index], index)
    tree.balance()
    nearest: dict[str, object] | None = None
    for index in target_group:
        _, main_index, distance = tree.find(world_vertices[index])
        if nearest is None or distance < float(nearest["distance"]):
            nearest = {
                "componentVertexIndex": index,
                "largestComponentVertexIndex": main_index,
                "distance": float(distance),
            }
    if nearest is None:
        raise ValueError("component has no vertices")
    return nearest


def bridge_components(
    obj: bpy.types.Object,
    *,
    max_distance: float,
    radius: float,
    sides: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    groups = components(obj)
    if len(groups) <= 1:
        return [], []
    world_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    pairs = [nearest_pair(groups[0], group, world_vertices) for group in groups[1:]]
    blocked = [
        {
            "componentRank": rank,
            "nearestDistance": round(float(pair["distance"]), 8),
            "reason": "COMPONENT_GAP_EXCEEDS_SAFE_BRIDGE_DISTANCE",
        }
        for rank, pair in enumerate(pairs, start=1)
        if float(pair["distance"]) > max_distance
    ]
    if blocked:
        return [], blocked

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    inverse = obj.matrix_world.inverted()
    bridges: list[dict[str, object]] = []
    for rank, pair in enumerate(pairs, start=1):
        index_a = int(pair["largestComponentVertexIndex"])
        index_b = int(pair["componentVertexIndex"])
        point_a = world_vertices[index_a]
        point_b = world_vertices[index_b]
        direction = point_b - point_a
        distance = direction.length
        if distance <= 1e-6:
            continue
        direction.normalize()
        reference = Vector((0.0, 0.0, 1.0))
        if abs(direction.dot(reference)) > 0.9:
            reference = Vector((0.0, 1.0, 0.0))
        basis_u = direction.cross(reference).normalized()
        basis_v = direction.cross(basis_u).normalized()
        local_radius = min(max(radius, 0.0005), max(distance * 0.30, 0.0005))
        ring_a = []
        ring_b = []
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            offset = local_radius * (
                basis_u * math.cos(angle) + basis_v * math.sin(angle)
            )
            ring_a.append(bm.verts.new(inverse @ (point_a + offset)))
            ring_b.append(bm.verts.new(inverse @ (point_b + offset)))
        vertex_a = bm.verts[index_a]
        vertex_b = bm.verts[index_b]
        for index in range(sides):
            next_index = (index + 1) % sides
            bm.faces.new((ring_a[index], ring_a[next_index], ring_b[next_index], ring_b[index]))
            bm.faces.new((vertex_a, ring_a[next_index], ring_a[index]))
            bm.faces.new((vertex_b, ring_b[index], ring_b[next_index]))
        bridges.append(
            {
                "componentRank": rank,
                "nearestDistance": round(distance, 8),
                "bridgeRadius": round(local_radius, 8),
                "sides": sides,
                "componentVertexIndex": index_b,
                "largestComponentVertexIndex": index_a,
            }
        )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return bridges, []


def decimate_to_budget(obj: bpy.types.Object, maximum: int) -> dict[str, object]:
    obj.data.calc_loop_triangles()
    initial = len(obj.data.loop_triangles)
    before = initial
    passes = 0
    while before > maximum and passes < 4:
        ratio = max(0.01, min(0.98, (maximum / max(before, 1)) * 0.94))
        modifier = obj.modifiers.new(f"PartCrafterReviewBudget_{passes}", "DECIMATE")
        modifier.ratio = ratio
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except RuntimeError as exc:
            obj.modifiers.remove(modifier)
            return {
                "status": "TRIANGLE_BUDGET_REPAIR_FAILED",
                "before": before,
                "after": before,
                "passes": passes,
                "error": str(exc),
            }
        obj.data.calc_loop_triangles()
        after = len(obj.data.loop_triangles)
        passes += 1
        if after >= before:
            break
        before = after
    return {
        "status": "PASS" if before <= maximum else "TRIANGLE_BUDGET_REPAIR_FAILED",
        "before": int(initial),
        "after": int(before),
        "passes": passes,
        "maximum": maximum,
    }


def ensure_uv(obj: bpy.types.Object) -> bool:
    if obj.data.uv_layers:
        return False
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.03)
    bpy.ops.object.mode_set(mode="OBJECT")
    return True


def enforce_review_gate(obj: bpy.types.Object) -> None:
    scene = bpy.context.scene
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    for target in (scene, obj):
        target["source_status"] = SOURCE_STATUS
        target["gate_b"] = GATE_B
        target["unity_input_allowed"] = False
        target["production_promotion_allowed"] = False
        target["review_repair_algorithm"] = ALGORITHM


def validate_stored_review_gate() -> None:
    scene = bpy.context.scene
    if scene.get("source_status") not in (None, SOURCE_STATUS):
        raise ValueError("STORED_REVIEW_SOURCE_STATUS_IS_NOT_CANDIDATE")
    if scene.get("gate_b") not in (None, GATE_B):
        raise ValueError("STORED_REVIEW_GATE_B_IS_NOT_PENDING")
    if scene.get("unity_input_allowed") is True:
        raise ValueError("STORED_REVIEW_UNITY_INPUT_ALREADY_ENABLED")
    if scene.get("production_promotion_allowed") is True:
        raise ValueError("STORED_REVIEW_PRODUCTION_PROMOTION_ALREADY_ENABLED")


def export_transport(obj: bpy.types.Object, output_glb: Path) -> tuple[Path | None, str, str]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if tuple(bpy.app.version) >= (4, 0, 0):
        bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", export_apply=True)
        if output_glb.is_file():
            return output_glb, "GLB", ""
    output_obj = output_glb.with_suffix(".obj")
    try:
        if hasattr(bpy.ops.wm, "obj_export"):
            bpy.ops.wm.obj_export(filepath=str(output_obj), export_selected_objects=True, apply_modifiers=True)
        elif hasattr(bpy.ops.export_scene, "obj"):
            bpy.ops.export_scene.obj(filepath=str(output_obj), use_selection=True, use_mesh_modifiers=True)
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {exc}"
    if output_obj.is_file():
        return output_obj, "OBJ", ""
    return None, "", "TRANSPORT_EXPORT_DID_NOT_CREATE_FILE"


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output_blend == source:
        raise ValueError("output blend must not overwrite the input")
    if args.max_triangles < 1 or args.max_bridge_distance <= 0 or args.bridge_radius <= 0 or args.bridge_sides < 3:
        raise ValueError("review repair bounds are invalid")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    validate_stored_review_gate()
    objects = mesh_objects()
    before_objects = len(objects)
    primary = join_meshes(objects)
    before = topology(primary)
    bridges, blocked = bridge_components(
        primary,
        max_distance=args.max_bridge_distance,
        radius=args.bridge_radius,
        sides=args.bridge_sides,
    )
    if blocked:
        report = {
            "algorithm": ALGORITHM,
            "status": "REVIEW_REPAIR_BLOCKED_UNSAFE_GAPS",
            "sourceBlend": str(source),
            "sourceBlendSha256": source_sha256,
            "inputObjectCount": before_objects,
            "topologyBefore": before,
            "maxBridgeDistance": args.max_bridge_distance,
            "blockedComponents": blocked,
            "sourceStatus": SOURCE_STATUS,
            "gateB": GATE_B,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
            "warnings": [
                "No partial repair was saved because at least one component gap exceeded the safe review limit.",
                "A new provider or semantic Blender authoring is required for the unresolved geometry.",
            ],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    budget = decimate_to_budget(primary, args.max_triangles)
    uv_generated = ensure_uv(primary)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import refine_ai3d_candidate as refine

    minimum, maximum = world_bounds([primary])
    material_names = refine.apply_palette_review_materials(
        primary, args.character, minimum, maximum
    )
    bmesh_data = bmesh.new()
    bmesh_data.from_mesh(primary.data)
    bmesh.ops.remove_doubles(bmesh_data, verts=bmesh_data.verts, dist=0.00001)
    bmesh.ops.recalc_face_normals(bmesh_data, faces=bmesh_data.faces)
    bmesh_data.to_mesh(primary.data)
    bmesh_data.free()
    primary.data.update()
    after = topology(primary)
    enforce_review_gate(primary)
    if budget["status"] != "PASS":
        report = {
            "algorithm": ALGORITHM,
            "status": "REVIEW_REPAIR_BLOCKED_TRIANGLE_BUDGET",
            "sourceBlend": str(source),
            "sourceBlendSha256": source_sha256,
            "inputObjectCount": before_objects,
            "topologyBefore": before,
            "topologyAfter": after,
            "bridges": bridges,
            "triangleBudget": budget,
            "sourceStatus": SOURCE_STATUS,
            "gateB": GATE_B,
            "unityInputAllowed": False,
            "productionPromotionAllowed": False,
            "warnings": ["The repaired mesh still exceeds the review triangle budget; no output was saved."],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    transport_path, transport_format, transport_error = export_transport(primary, output_glb)
    status = "REVIEW_REPAIR_APPLIED" if transport_path else "REVIEW_REPAIR_TRANSPORT_EXPORT_FAILED"
    report = {
        "algorithm": ALGORITHM,
        "status": status,
        "sourceBlend": str(source),
        "sourceBlendSha256": source_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb) if output_glb.is_file() else "",
        "transportPath": str(transport_path) if transport_path else "",
        "transportFormat": transport_format,
        "transportSha256": sha256_file(transport_path) if transport_path else "",
        "inputObjectCount": before_objects,
        "topologyBefore": before,
        "topologyAfter": after,
        "bridges": bridges,
        "maxBridgeDistance": args.max_bridge_distance,
        "triangleBudget": budget,
        "uvGenerated": uv_generated,
        "materialMode": "palette",
        "materialNames": material_names,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "This is a stored-artifact review repair; PartCrafter inference was not rerun.",
            "Bridges and decimation are heuristic and may damage anatomy or design detail.",
            "Provider semantic labels remain unverified; this output is not a Production Mesh.",
            "Human Gate B review and strict visual QA remain mandatory.",
        ] + ([f"Transport export diagnostic: {transport_error}"] if transport_error else []),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "REVIEW_REPAIR_APPLIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
