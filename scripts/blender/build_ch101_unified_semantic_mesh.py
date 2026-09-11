#!/usr/bin/env python3
"""Build a connected, review-only CH101 semantic authoring candidate.

This is a new strategy after the primitive semantic proxy plateaued.  It keeps
semantic labels and review collections, but builds one connected primary shell
using analytic bridge volumes so the geometry hard gate can measure a real
character surface instead of dozens of disconnected primitives.  It is still
not a Production Mesh: face drivers remain blocked, sockets are estimated, and
all Unity/production gates stay false.
"""

from __future__ import annotations

import argparse
import bmesh
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


SOURCE_STATUS = "AI_GENERATED_CANDIDATE_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
STRATEGY_ID = "UNIFIED_SEMANTIC_AUTHORING_V002"
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


def detach_from_root(obj: bpy.types.Object, root: bpy.types.Object) -> None:
    if obj.parent is not root:
        return
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world


def add_connectivity_bridges(root: bpy.types.Object, materials: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    """Add hidden-under-surface volumes that make the primary shell connected.

    The bridge geometry is deliberately simple and is reported as an
    authoring aid.  It is not a claim of anatomically correct topology.
    """

    skin = materials["skin"]
    bridges = [
        ("Spine", (0.0, 0.0, 0.34), (0.0, 0.0, 3.02), 0.20),
        ("Leg_L", (-0.18, 0.0, 1.38), (-0.18, 0.0, 0.08), 0.14),
        ("Leg_R", (0.18, 0.0, 1.38), (0.18, 0.0, 0.08), 0.14),
        ("Arm_L", (-0.27, 0.0, 2.30), (-0.66, -0.05, 1.58), 0.105),
        ("Arm_R", (0.27, 0.0, 2.30), (0.66, -0.05, 1.58), 0.105),
        ("HairAttach", (0.08, 0.02, 2.82), (0.48, 0.10, 2.54), 0.105),
    ]
    created = []
    for name, start, end, radius in bridges:
        obj = base.capsule(f"UnifiedBridge_{name}", start, end, radius, skin, root)
        obj["semanticPart"] = "primary_shell_bridge"
        obj["sourceStatus"] = SOURCE_STATUS
        created.append(obj)
    return created


def join_objects(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    if not objects:
        raise ValueError(f"cannot join empty semantic group: {name}")
    # A previous join/remesh can leave another semantic group selected. Blender
    # joins every selected object, so clear selection before selecting this
    # group or the shell/equipment boundary is silently destroyed.
    bpy.ops.object.select_all(action="DESELECT")
    for existing in bpy.context.view_layer.objects:
        existing.select_set(False)
    for obj in objects:
        detach_from_root(obj, obj.parent) if obj.parent else None
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.object
    joined.name = name
    joined["sourceStatus"] = SOURCE_STATUS
    joined["gateB"] = GATE_B
    joined["unityInputAllowed"] = False
    joined["productionPromotionAllowed"] = False
    return joined


def _active_mesh_object(expected_name: str) -> bpy.types.Object | None:
    """Return the current active mesh, tolerating sculpt remesh object swaps."""

    try:
        active = bpy.context.view_layer.objects.active
        if active is not None and active.type == "MESH":
            return active
    except ReferenceError:
        # Blender 4.x can invalidate the Python wrapper for the pre-remesh
        # object while keeping the replacement selected.
        pass
    replacement = bpy.data.objects.get(expected_name)
    return replacement if replacement is not None and replacement.type == "MESH" else None


def apply_connectivity_remesh(obj: bpy.types.Object) -> tuple[bpy.types.Object, dict[str, Any]]:
    """Fuse overlapping authoring volumes into one actual mesh component.

    Joining Blender objects only changes object bookkeeping; it does not join
    vertices.  The strict visual QA gate measures mesh connectivity, so this
    explicit voxel remesh is required for V002.  If the installed Blender
    lacks the modifier mode, the report records a failure instead of claiming
    that a connected shell was produced.
    """

    original_name = obj.name
    result: dict[str, Any] = {
        "status": "BLOCKED_REMESH_OPERATOR_UNAVAILABLE",
        "method": "SCULPT_VOXEL_REMESH_OR_MODIFIER_FALLBACK",
        "voxelSize": 0.035,
    }
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(obj.data, "remesh_voxel_size"):
        obj.data.remesh_voxel_size = result["voxelSize"]
    try:
        bpy.ops.object.mode_set(mode="SCULPT")
        if not hasattr(bpy.ops.sculpt, "voxel_remesh"):
            raise RuntimeError("BLENDER_VOXEL_REMESH_OPERATOR_UNAVAILABLE")
        bpy.ops.sculpt.voxel_remesh()
        # Sculpt voxel remesh may replace the underlying Object and invalidate
        # the original StructRNA wrapper. Re-acquire the selected replacement
        # before touching mesh data or returning to the caller.
        remeshed = _active_mesh_object(original_name)
        if remeshed is None:
            raise RuntimeError("BLENDER_VOXEL_REMESH_DID_NOT_RETURN_ACTIVE_MESH")
        obj = remeshed
        result["method"] = "SCULPT_VOXEL_REMESH"
    except (AttributeError, RuntimeError):
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        modifier = obj.modifiers.new(name="UnifiedConnectivityVoxelRemesh", type="REMESH")
        try:
            modifier.mode = "VOXEL"
            modifier.voxel_size = result["voxelSize"]
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            result["method"] = "REMESH_MODIFIER_VOXEL"
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            if modifier.name in obj.modifiers:
                obj.modifiers.remove(modifier)
            result["status"] = "REMESH_FAILED"
            result["error"] = f"{type(exc).__name__}: {exc}"
            return result
    finally:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    remeshed = _active_mesh_object(original_name)
    if remeshed is None:
        result["status"] = "REMESH_FAILED"
        result["error"] = "BLENDER_VOXEL_REMESH_DID_NOT_RETURN_ACTIVE_MESH"
        raise RuntimeError(result["error"])
    obj = remeshed
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(
            bm, verts=bm.verts, dist=min(result["voxelSize"] * 0.2, 0.0015)
        )
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()
    result["status"] = "PASS"
    result["vertexCount"] = len(obj.data.vertices)
    result["triangleCount"] = review.triangle_count([obj])
    return obj, result


def ensure_review_uv(meshes: list[bpy.types.Object]) -> dict[str, Any]:
    """Create deterministic review UVs before duplicating LOD meshes."""

    missing_before = [obj.name for obj in meshes if not obj.data.uv_layers]
    for obj in meshes:
        if obj.data.uv_layers:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.03)
        bpy.ops.object.mode_set(mode="OBJECT")
    return {
        "status": "PASS" if all(obj.data.uv_layers for obj in meshes) else "FAIL",
        "createdFor": missing_before,
        "missingAfter": [obj.name for obj in meshes if not obj.data.uv_layers],
    }


def mark_semantic_labels(
    collections: dict[str, bpy.types.Collection], shell: bpy.types.Object, equipment: bpy.types.Object | None
) -> dict[str, Any]:
    labels = {}
    for part, collection in collections.items():
        marker = bpy.data.objects.new(f"SEMANTIC_{part.upper()}_LABEL_NOT_PRODUCTION", None)
        collection.objects.link(marker)
        marker["semanticPart"] = part
        marker["meshObject"] = shell.name if part != "equipment" else (equipment.name if equipment else "")
        marker["sourceStatus"] = SOURCE_STATUS
        marker["gateB"] = GATE_B
        marker["unityInputAllowed"] = False
        labels[part] = marker.name
    shell["semanticGroups"] = json.dumps(list(collections), ensure_ascii=False)
    shell["semanticRepresentation"] = "UNIFIED_PRIMARY_SHELL_WITH_SEMANTIC_LABELS"
    shell["semanticLabelObjects"] = json.dumps(labels, ensure_ascii=False)
    return labels


def duplicate_lods(source_meshes: list[bpy.types.Object]) -> tuple[dict[str, list[bpy.types.Object]], dict[str, int]]:
    for source in source_meshes:
        source.hide_render = True
        source.hide_set(True)
    source_triangles = review.triangle_count(source_meshes)
    lod0_ratio = min(1.0, 20000 / max(source_triangles, 1))
    ratios = {"LOD0": lod0_ratio, "LOD1": lod0_ratio * 0.55, "LOD2": lod0_ratio * 0.30}
    lods: dict[str, list[bpy.types.Object]] = {}
    counts = {"SOURCE": source_triangles}
    for lod_name, ratio in ratios.items():
        collection = review.ensure_collection(f"AI_REVIEW_{lod_name}_NOT_PRODUCTION")
        copies = []
        for source in source_meshes:
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = f"AI3D_{lod_name}_{source.name}"
            for modifier in list(duplicate.modifiers):
                duplicate.modifiers.remove(modifier)
            collection.objects.link(duplicate)
            duplicate.hide_render = lod_name != "LOD0"
            duplicate.hide_set(False)
            duplicate["lod_level"] = lod_name
            duplicate["sourceStatus"] = SOURCE_STATUS
            duplicate["gateB"] = GATE_B
            duplicate["unityInputAllowed"] = False
            duplicate["semanticRepresentation"] = source.get(
                "semanticRepresentation", "UNIFIED_PRIMARY_SHELL_WITH_SEMANTIC_LABELS"
            )
            review.apply_decimate(duplicate, ratio)
            copies.append(duplicate)
        lods[lod_name] = copies
        counts[lod_name] = review.triangle_count(copies)
    return lods, counts


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
    root.name = "CH101_UNIFIED_SEMANTIC_AUTHORING_ROOT_NOT_PRODUCTION"
    root["sourceStatus"] = SOURCE_STATUS
    root["gateB"] = GATE_B
    root["unityInputAllowed"] = False
    root["productionPromotionAllowed"] = False
    root["strategyId"] = STRATEGY_ID

    generated = [obj for obj in list(bpy.data.objects) if obj.parent is root]
    generated = proxy.convert_curves_to_mesh(generated)
    generated = [obj for obj in generated if obj.type == "MESH"]
    if not generated:
        raise ValueError("unified semantic authoring produced no mesh objects")
    bridges = add_connectivity_bridges(root, materials)
    generated.extend(bridges)
    for obj in generated:
        detach_from_root(obj, root)

    shell_parts = [obj for obj in generated if proxy.classify(obj.name) != "equipment"]
    equipment_parts = [obj for obj in generated if proxy.classify(obj.name) == "equipment"]
    shell = join_objects(shell_parts, "CH101_UNIFIED_PRIMARY_SHELL_NOT_PRODUCTION")
    shell, remesh_report = apply_connectivity_remesh(shell)
    equipment = join_objects(equipment_parts, "CH101_UNIFIED_EQUIPMENT_GROUP_NOT_PRODUCTION") if equipment_parts else None
    uv_report = ensure_review_uv([shell] + ([equipment] if equipment else []))
    review.move_to_collection(shell, semantic_collections["body_face"])
    shell["semanticPart"] = "body_face|outfit|hair"
    if equipment:
        review.move_to_collection(equipment, semantic_collections["equipment"])
        equipment["semanticPart"] = "equipment"
    labels = mark_semantic_labels(semantic_collections, shell, equipment)
    source_meshes = [shell] + ([equipment] if equipment else [])

    lods, triangle_counts = duplicate_lods(source_meshes)
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
    scene["semantic_representation"] = "UNIFIED_PRIMARY_SHELL_WITH_SEMANTIC_LABELS"
    scene["auto_weight_status"] = weight_status
    renders = proxy.build_review_scene(output_dir, materials, options.render)
    blend_path = output_dir / "CH101_UNIFIED_SEMANTIC_AUTHORING_NOT_PRODUCTION.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in lods["LOD0"]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = shell
    mesh_path = output_dir / "CH101_UNIFIED_SEMANTIC_AUTHORING_NOT_PRODUCTION.glb"
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
        mesh_path = output_dir / "CH101_UNIFIED_SEMANTIC_AUTHORING_NOT_PRODUCTION.obj"
        mesh_format = "OBJ"
        proxy.export_obj_compat(mesh_path)
    if not mesh_path.is_file():
        raise RuntimeError("unified semantic mesh export did not create a transport file")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "schemaVersion": "ch101-unified-semantic-authoring-report-v001",
        "character": "CH101",
        "subject": reference_report.get("subject", "AmasawaRin"),
        "strategyId": STRATEGY_ID,
        "status": "UNIFIED_SEMANTIC_REVIEW_CANDIDATE_NOT_PRODUCTION",
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
        "referenceManifestSha256": reference_report.get("referenceManifestSha256", ""),
        "artCommit": reference_report.get("artCommitExpected", ""),
        "collections": list(COLLECTIONS),
        "semanticRepresentation": "UNIFIED_PRIMARY_SHELL_WITH_SEMANTIC_LABELS",
        "semanticLabelObjects": labels,
        "primaryShell": shell.name,
        "equipmentGroup": equipment.name if equipment else None,
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
            "status": "PASS" if equipment and remesh_report.get("status") == "PASS" else "FAIL",
            "partObjectCountsLOD0": {
                "body_face": 1,
                "hair": 1,
                "outfit": 1,
                "equipment": 1 if equipment else 0,
            },
            "primaryShellObject": shell.name,
            "equipmentObject": equipment.name if equipment else None,
            "connectedPrimaryShell": remesh_report.get("status") == "PASS",
            "slabGrayboxAccepted": False,
        },
        "socketReport": socket_report,
        "weightStatus": weight_status,
        "weightError": weight_error,
        "weightAudit": weight_audit,
        "exportDiagnostic": export_diagnostic,
        "promotion": "NEVER_AUTOMATIC; HUMAN_GATE_B_AND_PRODUCTION_INTAKE_REQUIRED",
    }
    (output_dir / "unified-semantic-authoring-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
