#!/usr/bin/env python3
"""Repair detached review-candidate components with Blender voxel remesh.

Voxel remesh is intentionally an opt-in review experiment.  It changes the
surface topology and can remove fine detail, so the output remains a
non-production AI candidate and must be re-rendered and re-scored.  This tool
never adds rig data or enables Unity/Production gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ALGORITHM = "BLENDER_VOXEL_REMESH_REVIEW_COMPONENT_REPAIR_V001"


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--output-glb", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--voxel-size", type=float, default=0.008)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def topology(objects: list[bpy.types.Object]) -> dict[str, int]:
    vertices = sum(len(obj.data.vertices) for obj in objects)
    triangles = sum(len(obj.data.loop_triangles) for obj in objects)
    return {"objectCount": len(objects), "vertexCount": vertices, "triangleCount": triangles}


def enforce_review_gate() -> None:
    scene = bpy.context.scene
    scene["source_status"] = SOURCE_STATUS
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["review_component_repair_algorithm"] = ALGORITHM


def main() -> int:
    args = parse_args()
    source = args.blend.resolve()
    output_blend = args.output_blend.resolve()
    output_glb = args.output_glb.resolve()
    report_path = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if args.voxel_size <= 0.0:
        raise ValueError("voxel-size must be positive")
    if output_blend == source:
        raise ValueError("output blend must not overwrite the input")
    for path in (output_blend, output_glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("blend contains no mesh objects")
    for obj in meshes:
        obj.select_set(obj is meshes[0])
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
        meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    primary = meshes[0]
    before = topology(meshes)
    if hasattr(primary.data, "remesh_voxel_size"):
        primary.data.remesh_voxel_size = args.voxel_size
    bpy.ops.object.mode_set(mode="SCULPT")
    try:
        if not hasattr(bpy.ops.sculpt, "voxel_remesh"):
            raise RuntimeError("BLENDER_VOXEL_REMESH_OPERATOR_UNAVAILABLE")
        bpy.ops.sculpt.voxel_remesh()
    finally:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new()
    bm.from_mesh(primary.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=min(args.voxel_size * 0.2, 0.0015))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(primary.data)
    bm.free()
    primary.data.update()
    primary.data.calc_loop_triangles()
    after = topology([primary])
    enforce_review_gate()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.object.select_all(action="DESELECT")
    primary.select_set(True)
    bpy.context.view_layer.objects.active = primary
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", export_apply=True)
    report = {
        "algorithm": ALGORITHM,
        "status": "REVIEW_COMPONENT_REPAIR_APPLIED",
        "sourceBlend": str(source),
        "sourceBlendSha256": source_sha256,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "outputGlb": str(output_glb),
        "outputGlbSha256": sha256_file(output_glb),
        "voxelSize": args.voxel_size,
        "topologyBefore": before,
        "topologyAfter": after,
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "warnings": [
            "Voxel remesh changes topology and may remove fine design detail.",
            "This is a review-only repair and is not a Production Mesh.",
            "Re-render, score, and human Gate B review remain mandatory.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
