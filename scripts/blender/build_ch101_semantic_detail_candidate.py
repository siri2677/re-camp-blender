#!/usr/bin/env python3
"""Build a review-only CH101 semantic-detail candidate.

V003 keeps the primary body shell connected, but deliberately preserves face
features, hair, outfit, and equipment as separate authored groups.  It is a
manual-Blender authoring aid after the V002 quality plateau, not a production
mesh or an automatic Gate B approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_ai3d_review_asset as review  # type: ignore
import build_ch101_base_mesh_wip as base  # type: ignore
import build_ch101_semantic_proxy as proxy  # type: ignore
import build_ch101_unified_semantic_mesh as unified  # type: ignore


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
STRATEGY_ID = "SEMANTIC_DETAIL_AUTHORING_V003"
FACE_STATUS = "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER"
SOCKET_STATUS = "AUTO_ESTIMATED_NOT_APPROVED"
COLLECTIONS = (
    "REF_CH101_SEMANTIC_INPUTS",
    "MODEL_HIGH_BODY",
    "MODEL_CLOTH_OUTFIT",
    "MODEL_HAIR",
    "MODEL_EQUIPMENT",
    "AI_REVIEW_LOD0_NOT_PRODUCTION",
    "AI_REVIEW_LOD1_NOT_PRODUCTION",
    "AI_REVIEW_LOD2_NOT_PRODUCTION",
    "AI_REVIEW_RIG_NOT_PRODUCTION",
    "AI_REVIEW_SOCKETS_NOT_PRODUCTION",
    "AI_REVIEW_SEMANTIC_LABELS_NOT_PRODUCTION",
)
FACE_DETAIL_PREFIXES = (
    "EyeWhite",
    "Iris",
    "Pupil",
    "EyeHighlight",
    "Brow",
    "Nose",
    "Mouth",
)
FACE_PLACEHOLDERS = proxy.FACE_PLACEHOLDERS


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reference-report", required=True, type=Path)
    parser.add_argument("--art-root", required=True, type=Path)
    parser.add_argument("--socket-contract", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_face_detail(name: str) -> bool:
    return name.startswith(FACE_DETAIL_PREFIXES)


def mark_group(obj: bpy.types.Object, semantic_part: str) -> bpy.types.Object:
    obj["sourceStatus"] = SOURCE_STATUS
    obj["gateB"] = GATE_B
    obj["unityInputAllowed"] = False
    obj["productionPromotionAllowed"] = False
    obj["semanticPart"] = semantic_part
    obj["strategyId"] = STRATEGY_ID
    return obj


def move_group(obj: bpy.types.Object, collection: bpy.types.Collection, semantic_part: str) -> None:
    review.move_to_collection(obj, collection)
    mark_group(obj, semantic_part)


def main() -> int:
    options = parse_args()
    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "renders").mkdir(parents=True, exist_ok=True)
    reference_report = proxy.read_and_verify_references(
        options.reference_report.resolve(), options.art_root.resolve()
    )
    socket_contract = json.loads(options.socket_contract.resolve().read_text(encoding="utf-8"))
    if socket_contract.get("contractVersion") != "current-roster-socket-contract-v001":
        raise ValueError("unexpected socket contract version")
    if not any(entry.get("code") == "CH101" for entry in socket_contract.get("characters", [])):
        raise ValueError("socket contract has no CH101 entry")

    base.clear()
    materials = proxy.make_materials()
    semantic_collections = {
        "body_face": review.ensure_collection("MODEL_HIGH_BODY"),
        "outfit": review.ensure_collection("MODEL_CLOTH_OUTFIT"),
        "hair": review.ensure_collection("MODEL_HAIR"),
        "equipment": review.ensure_collection("MODEL_EQUIPMENT"),
    }
    for name in COLLECTIONS:
        review.ensure_collection(name)

    root = base.character(0.0, "A", materials)
    root.name = "CH101_SEMANTIC_DETAIL_AUTHORING_ROOT_NOT_PRODUCTION"
    for key, value in {
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "strategyId": STRATEGY_ID,
    }.items():
        root[key] = value

    generated = [obj for obj in list(bpy.data.objects) if obj.parent is root]
    generated = proxy.convert_curves_to_mesh(generated)
    generated = [obj for obj in generated if obj.type == "MESH"]
    if not generated:
        raise ValueError("semantic detail authoring produced no mesh objects")
    bridges = unified.add_connectivity_bridges(root, materials)
    generated.extend(bridges)
    for obj in generated:
        unified.detach_from_root(obj, root)

    body_parts = [
        obj
        for obj in generated
        if proxy.classify(obj.name) == "body_face" and not is_face_detail(obj.name)
    ]
    face_parts = [obj for obj in generated if proxy.classify(obj.name) == "body_face" and is_face_detail(obj.name)]
    hair_parts = [obj for obj in generated if proxy.classify(obj.name) == "hair"]
    outfit_parts = [
        obj
        for obj in generated
        if proxy.classify(obj.name) == "outfit"
        and not obj.name.startswith("UnifiedBridge_")
    ]
    equipment_parts = [obj for obj in generated if proxy.classify(obj.name) == "equipment"]
    if not all((body_parts, face_parts, hair_parts, outfit_parts, equipment_parts)):
        raise ValueError("semantic detail authoring is missing one or more required groups")

    shell = unified.join_objects(body_parts + bridges, "CH101_V003_PRIMARY_BODY_SHELL_NOT_PRODUCTION")
    shell, remesh_report = unified.apply_connectivity_remesh(shell)
    face_detail = unified.join_objects(face_parts, "CH101_V003_FACE_DETAIL_NOT_PRODUCTION")
    hair_group = unified.join_objects(hair_parts, "CH101_V003_HAIR_GROUP_NOT_PRODUCTION")
    # The proxy bangs are intentionally pulled behind the eye plane for this
    # review candidate so the preserved anime face landmarks remain legible.
    # This is a presentation adjustment only; it does not claim authored hair
    # topology or production grooming.
    hair_group.location.y += 0.08
    hair_group["faceReadabilityAdjustment"] = "BANGS_RECESSED_0_08Y_REVIEW_ONLY"
    outfit_group = unified.join_objects(outfit_parts, "CH101_V003_OUTFIT_GROUP_NOT_PRODUCTION")
    equipment_group = unified.join_objects(equipment_parts, "CH101_V003_EQUIPMENT_GROUP_NOT_PRODUCTION")

    groups = [shell, face_detail, hair_group, outfit_group, equipment_group]
    uv_report = unified.ensure_review_uv(groups)
    move_group(shell, semantic_collections["body_face"], "body_face")
    move_group(face_detail, semantic_collections["body_face"], "face_detail")
    move_group(hair_group, semantic_collections["hair"], "hair")
    move_group(outfit_group, semantic_collections["outfit"], "outfit")
    move_group(equipment_group, semantic_collections["equipment"], "equipment")

    labels = unified.mark_semantic_labels(semantic_collections, shell, equipment_group)
    source_meshes = groups
    lods, triangle_counts = unified.duplicate_lods(source_meshes)
    armature = review.build_humanoid_rig(lods["LOD0"], "CH101")
    weight_status, weight_error, weight_audit = review.auto_weight(lods["LOD0"], armature, "CH101")
    socket_report = review.build_sockets(armature, socket_contract, "CH101")
    socket_report["status"] = SOCKET_STATUS

    scene = bpy.context.scene
    scene["re_camp_status"] = SOURCE_STATUS
    scene["re_camp_character"] = "CH101"
    scene["strategy_id"] = STRATEGY_ID
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["face_driver_status"] = FACE_STATUS
    scene["face_blendshape_placeholders"] = json.dumps(FACE_PLACEHOLDERS)
    scene["socket_status"] = SOCKET_STATUS
    scene["semantic_representation"] = "CONNECTED_BODY_WITH_PRESERVED_DETAIL_GROUPS"
    scene["auto_weight_status"] = weight_status

    renders = proxy.build_review_scene(output_dir, materials, options.render)
    blend_path = output_dir / "CH101_SEMANTIC_DETAIL_AUTHORING_NOT_PRODUCTION.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.object.select_all(action="DESELECT")
    for obj in lods["LOD0"]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = lods["LOD0"][0]
    mesh_path = output_dir / "CH101_SEMANTIC_DETAIL_AUTHORING_NOT_PRODUCTION.glb"
    mesh_format = "GLB"
    export_diagnostic = ""
    if tuple(bpy.app.version) >= (4, 0, 0):
        try:
            bpy.ops.export_scene.gltf(filepath=str(mesh_path), export_format="GLB", use_selection=True, export_apply=True)
        except Exception as exc:
            export_diagnostic = f"{type(exc).__name__}: {exc}"
    else:
        export_diagnostic = f"GLB export skipped for Blender {bpy.app.version_string}; using OBJ transport"
    if not mesh_path.is_file():
        mesh_path = output_dir / "CH101_SEMANTIC_DETAIL_AUTHORING_NOT_PRODUCTION.obj"
        mesh_format = "OBJ"
        proxy.export_obj_compat(mesh_path)
    if not mesh_path.is_file():
        raise RuntimeError("semantic detail mesh export did not create a transport file")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    report = {
        "schemaVersion": "ch101-semantic-detail-authoring-report-v001",
        "character": "CH101",
        "subject": reference_report.get("subject", "AmasawaRin"),
        "strategyId": STRATEGY_ID,
        "status": "SEMANTIC_DETAIL_REVIEW_CANDIDATE_NOT_PRODUCTION",
        "sourceStatus": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "referenceReport": str(options.reference_report.resolve()),
        "referenceInputHashes": {
            str(reference["id"]): reference["sha256"]
            for reference in reference_report.get("references", [])
            if isinstance(reference, dict) and reference.get("id") and reference.get("sha256")
        },
        "artCommit": reference_report.get("artCommitExpected", ""),
        "collections": list(COLLECTIONS),
        "semanticRepresentation": "CONNECTED_BODY_WITH_PRESERVED_DETAIL_GROUPS",
        "semanticLabelObjects": labels,
        "primaryBodyShell": shell.name,
        "faceDetailGroup": face_detail.name,
        "hairGroup": hair_group.name,
        "outfitGroup": outfit_group.name,
        "equipmentGroup": equipment_group.name,
        "connectivityMethod": "ANALYTIC_BRIDGE_CAPSULES",
        "connectivityRemesh": remesh_report,
        "uvReport": uv_report,
        "sourceMeshObjectCount": len(source_meshes),
        "triangleCounts": triangle_counts,
        "blend": str(blend_path),
        "blendSha256": sha256_file(blend_path),
        "mesh": str(mesh_path),
        "meshFormat": mesh_format,
        "meshSha256": sha256_file(mesh_path),
        "renders": renders,
        "faceDriver": {"status": FACE_STATUS, "blendShapeCount": 0, "placeholders": list(FACE_PLACEHOLDERS)},
        "semanticComponentAudit": {
            "status": "PASS" if remesh_report.get("status") == "PASS" else "FAIL",
            "partObjectCountsLOD0": {
                "body_face": 2,
                "hair": 1,
                "outfit": 1,
                "equipment": 1,
            },
            "primaryShellObject": shell.name,
            "faceDetailObject": face_detail.name,
            "connectedPrimaryShell": remesh_report.get("status") == "PASS",
            "preservedFaceDetail": True,
            "slabGrayboxAccepted": False,
        },
        "socketReport": socket_report,
        "weightStatus": weight_status,
        "weightError": weight_error,
        "weightAudit": weight_audit,
        "exportDiagnostic": export_diagnostic,
        "promotion": "NEVER_AUTOMATIC; HUMAN_GATE_B_AND_PRODUCTION_INTAKE_REQUIRED",
    }
    (output_dir / "semantic-detail-authoring-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
