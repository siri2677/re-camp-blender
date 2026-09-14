#!/usr/bin/env python3
"""Build a non-production Blender review scene from the ranked AI candidate.

The result contains heuristic LODs, a humanoid review rig, and estimated roster
sockets. It intentionally omits production collection names and export steps,
so the production intake validator cannot mistake this scene for final work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SOURCE_STATUS = "AI_GENERATED_REVIEW_NOT_PRODUCTION"
GATE_B = "PENDING_HUMAN_REVIEW"
ROTATION_BY_FRONT_VIEW = {
    "neg_y": 0.0,
    "pos_x": math.radians(-90.0),
    "pos_y": math.radians(180.0),
    "neg_x": math.radians(90.0),
}


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranking-manifest", required=True, type=Path)
    parser.add_argument("--socket-contract", required=True, type=Path)
    parser.add_argument("--output-blend", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(raw)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_candidate(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        if hasattr(bpy.ops.wm, "fbx_import"):
            bpy.ops.wm.fbx_import(filepath=str(path))
        else:
            bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"unsupported candidate format: {suffix}")
    imported = [obj for obj in bpy.data.objects if obj not in before]
    for obj in list(imported):
        if obj.type in {"CAMERA", "LIGHT"} or obj.name.startswith("Socket_"):
            bpy.data.objects.remove(obj, do_unlink=True)
            imported.remove(obj)
    return imported


def mesh_bounds(meshes: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not corners:
        raise ValueError("candidate contains no mesh bounds")
    minimum = Vector(tuple(min(point[index] for point in corners) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in corners) for index in range(3)))
    return minimum, maximum


def normalize_import(
    imported: list[bpy.types.Object],
    front_view: str,
    character: str,
    target_height: float = 1.68,
) -> bpy.types.Object:
    if front_view not in ROTATION_BY_FRONT_VIEW:
        raise ValueError(f"unsupported selected front orientation: {front_view}")
    root = bpy.data.objects.new(f"{character}_AI_Review_Root", None)
    bpy.context.scene.collection.objects.link(root)
    for obj in imported:
        if obj.parent is None:
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = world
    root.rotation_euler.z = ROTATION_BY_FRONT_VIEW[front_view]
    bpy.context.view_layer.update()
    meshes = [obj for obj in imported if obj.type == "MESH"]
    minimum, maximum = mesh_bounds(meshes)
    height = maximum.z - minimum.z
    if height <= 1e-6:
        raise ValueError("candidate has zero height")
    center = (minimum + maximum) * 0.5
    scale = target_height / height
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -minimum.z * scale)
    root["source_status"] = SOURCE_STATUS
    root["gate_b"] = GATE_B
    root["unity_input_allowed"] = False
    bpy.context.view_layer.update()
    return root


def ensure_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if collection.name not in {child.name for child in bpy.context.scene.collection.children}:
        bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def triangle_count(objects: list[bpy.types.Object]) -> int:
    total = 0
    for obj in objects:
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def apply_decimate(obj: bpy.types.Object, ratio: float) -> None:
    if ratio >= 0.999:
        return
    modifier = obj.modifiers.new(name="AI3D_AutoDecimate", type="DECIMATE")
    modifier.ratio = max(0.02, min(1.0, ratio))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    except RuntimeError:
        obj.modifiers.remove(modifier)


def build_lods(source_meshes: list[bpy.types.Object]) -> tuple[dict[str, list[bpy.types.Object]], dict[str, int]]:
    source_collection = ensure_collection("AI_SOURCE_ORIGINAL_NOT_PRODUCTION")
    for obj in source_meshes:
        move_to_collection(obj, source_collection)
        obj.hide_render = True
        obj.hide_set(True)
    source_triangles = triangle_count(source_meshes)
    lod0_ratio = min(1.0, 20000 / max(source_triangles, 1))
    ratios = {"LOD0": lod0_ratio, "LOD1": lod0_ratio * 0.55, "LOD2": lod0_ratio * 0.3}
    lod_objects: dict[str, list[bpy.types.Object]] = {}
    counts = {"SOURCE": source_triangles}
    for lod_name, ratio in ratios.items():
        collection = ensure_collection(f"AI_REVIEW_{lod_name}_NOT_PRODUCTION")
        copies = []
        for source in source_meshes:
            source_world = source.matrix_world.copy()
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = f"AI3D_{lod_name}_{source.name}"
            for modifier in list(duplicate.modifiers):
                duplicate.modifiers.remove(modifier)
            for vertex_group in list(duplicate.vertex_groups):
                duplicate.vertex_groups.remove(vertex_group)
            duplicate.hide_render = lod_name != "LOD0"
            collection.objects.link(duplicate)
            duplicate.parent = None
            duplicate.matrix_parent_inverse = Matrix.Identity(4)
            duplicate.matrix_world = source_world
            duplicate.hide_set(False)
            duplicate["lod_level"] = lod_name
            duplicate["source_status"] = SOURCE_STATUS
            apply_decimate(duplicate, ratio)
            copies.append(duplicate)
        lod_objects[lod_name] = copies
        counts[lod_name] = triangle_count(copies)
    return lod_objects, counts


def build_humanoid_rig(
    meshes: list[bpy.types.Object], character: str
) -> bpy.types.Object:
    minimum, maximum = mesh_bounds(meshes)
    height = maximum.z - minimum.z
    width = maximum.x - minimum.x
    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5

    def point(x: float, y: float, z: float) -> tuple[float, float, float]:
        return (center_x + x * width, center_y + y * height, minimum.z + z * height)

    bones = {
        "Root": (point(0, 0, 0), point(0, 0, 0.05), None),
        "Hips": (point(0, 0, 0.50), point(0, 0, 0.59), "Root"),
        "Spine": (point(0, 0, 0.59), point(0, 0, 0.69), "Hips"),
        "Chest": (point(0, 0, 0.69), point(0, 0, 0.77), "Spine"),
        "Neck": (point(0, 0, 0.77), point(0, 0, 0.82), "Chest"),
        "Head": (point(0, 0, 0.82), point(0, 0, 0.97), "Neck"),
        "LeftShoulder": (point(-0.05, 0, 0.75), point(-0.16, 0, 0.74), "Chest"),
        "LeftUpperArm": (point(-0.16, 0, 0.74), point(-0.34, 0, 0.66), "LeftShoulder"),
        "LeftLowerArm": (point(-0.34, 0, 0.66), point(-0.45, 0, 0.58), "LeftUpperArm"),
        "LeftHand": (point(-0.45, 0, 0.58), point(-0.49, 0, 0.55), "LeftLowerArm"),
        "RightShoulder": (point(0.05, 0, 0.75), point(0.16, 0, 0.74), "Chest"),
        "RightUpperArm": (point(0.16, 0, 0.74), point(0.34, 0, 0.66), "RightShoulder"),
        "RightLowerArm": (point(0.34, 0, 0.66), point(0.45, 0, 0.58), "RightUpperArm"),
        "RightHand": (point(0.45, 0, 0.58), point(0.49, 0, 0.55), "RightLowerArm"),
        "LeftUpperLeg": (point(-0.08, 0, 0.52), point(-0.09, 0, 0.29), "Hips"),
        "LeftLowerLeg": (point(-0.09, 0, 0.29), point(-0.09, 0, 0.09), "LeftUpperLeg"),
        "LeftFoot": (point(-0.09, 0, 0.09), point(-0.09, -0.08, 0.03), "LeftLowerLeg"),
        "LeftToes": (point(-0.09, -0.08, 0.03), point(-0.09, -0.14, 0.025), "LeftFoot"),
        "RightUpperLeg": (point(0.08, 0, 0.52), point(0.09, 0, 0.29), "Hips"),
        "RightLowerLeg": (point(0.09, 0, 0.29), point(0.09, 0, 0.09), "RightUpperLeg"),
        "RightFoot": (point(0.09, 0, 0.09), point(0.09, -0.08, 0.03), "RightLowerLeg"),
        "RightToes": (point(0.09, -0.08, 0.03), point(0.09, -0.14, 0.025), "RightFoot"),
    }
    armature_data = bpy.data.armatures.new(f"{character}_AI_AutoRig_Armature")
    armature = bpy.data.objects.new(f"{character}_AI_AutoRig_Armature", armature_data)
    ensure_collection("AI_REVIEW_RIG_NOT_PRODUCTION").objects.link(armature)
    armature["rig_status"] = "HEURISTIC_AUTO_RIG_NOT_PRODUCTION"
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    created = {}
    for name, (head, tail, parent_name) in bones.items():
        bone = armature_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent_name:
            bone.parent = created[parent_name]
        created[name] = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone in armature_data.bones:
        bone["humanoid_role"] = bone.name
    return armature


def audit_weights(
    meshes: list[bpy.types.Object], armature: bpy.types.Object
) -> dict[str, object]:
    bone_names = {bone.name for bone in armature.data.bones}
    object_reports = []
    total_vertices = 0
    weighted_vertices = 0
    for obj in meshes:
        deform_group_indices = {
            group.index for group in obj.vertex_groups if group.name in bone_names
        }
        object_weighted = sum(
            1
            for vertex in obj.data.vertices
            if any(
                membership.group in deform_group_indices and membership.weight > 1e-6
                for membership in vertex.groups
            )
        )
        armature_modifiers = [
            modifier
            for modifier in obj.modifiers
            if modifier.type == "ARMATURE" and modifier.object == armature
        ]
        object_vertices = len(obj.data.vertices)
        total_vertices += object_vertices
        weighted_vertices += object_weighted
        object_reports.append(
            {
                "object": obj.name,
                "vertexCount": object_vertices,
                "weightedVertexCount": object_weighted,
                "unweightedVertexCount": object_vertices - object_weighted,
                "deformGroupCount": len(deform_group_indices),
                "armatureModifierCount": len(armature_modifiers),
            }
        )
    return {
        "status": (
            "PASS"
            if total_vertices > 0
            and weighted_vertices == total_vertices
            and all(report["armatureModifierCount"] > 0 for report in object_reports)
            else "FAIL"
        ),
        "totalVertexCount": total_vertices,
        "weightedVertexCount": weighted_vertices,
        "unweightedVertexCount": total_vertices - weighted_vertices,
        "objects": object_reports,
    }


def point_segment_distance_squared(point: Vector, head: Vector, tail: Vector) -> float:
    segment = tail - head
    length_squared = segment.length_squared
    if length_squared <= 1e-12:
        return (point - head).length_squared
    amount = max(0.0, min(1.0, (point - head).dot(segment) / length_squared))
    return (point - (head + segment * amount)).length_squared


def apply_nearest_bone_fallback(
    meshes: list[bpy.types.Object], armature: bpy.types.Object, character: str
) -> None:
    bones = [bone for bone in armature.data.bones if bone.name != "Root"]
    bone_segments = {
        bone.name: (
            armature.matrix_world @ bone.head_local,
            armature.matrix_world @ bone.tail_local,
        )
        for bone in bones
    }
    for obj in meshes:
        for group in list(obj.vertex_groups):
            obj.vertex_groups.remove(group)
        groups = {bone.name: obj.vertex_groups.new(name=bone.name) for bone in bones}
        assignments: dict[str, list[int]] = {bone.name: [] for bone in bones}
        for vertex in obj.data.vertices:
            world_point = obj.matrix_world @ vertex.co
            nearest_name = min(
                bone_segments,
                key=lambda name: point_segment_distance_squared(
                    world_point, *bone_segments[name]
                ),
            )
            assignments[nearest_name].append(vertex.index)
        for name, indices in assignments.items():
            if indices:
                groups[name].add(indices, 1.0, "REPLACE")
        modifier = next(
            (modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"),
            None,
        )
        if modifier is None:
            modifier = obj.modifiers.new(name=f"{character}_AI_AutoRig", type="ARMATURE")
        modifier.object = armature
        obj.parent = armature


def auto_weight(
    meshes: list[bpy.types.Object], armature: bpy.types.Object, character: str
) -> tuple[str, str, dict[str, object]]:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.hide_set(False)
        obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    operator_error = ""
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError as exc:
        operator_error = str(exc)
    audit = audit_weights(meshes, armature)
    if audit["status"] == "PASS":
        return "AUTO_WEIGHTED_FOR_REVIEW", operator_error, audit
    fallback_reason = operator_error or (
        "Blender bone heat operator returned without assigning every LOD0 vertex."
    )
    apply_nearest_bone_fallback(meshes, armature, character)
    fallback_audit = audit_weights(meshes, armature)
    if fallback_audit["status"] != "PASS":
        return "AUTO_WEIGHT_FAILED", fallback_reason, fallback_audit
    return "FALLBACK_NEAREST_BONE_WEIGHTED_FOR_REVIEW", fallback_reason, fallback_audit


def bone_tail_world(armature: bpy.types.Object, bone_name: str) -> Vector:
    bone = armature.data.bones.get(bone_name)
    if bone is None:
        raise ValueError(f"missing rig bone for socket: {bone_name}")
    return armature.matrix_world @ bone.tail_local


def create_socket(
    name: str,
    armature: bpy.types.Object,
    bone_name: str,
    world_location: Vector,
) -> bpy.types.Object:
    desired_world = Matrix.Translation(world_location)
    socket = bpy.data.objects.new(name, None)
    ensure_collection("AI_REVIEW_SOCKETS_NOT_PRODUCTION").objects.link(socket)
    socket.empty_display_type = "ARROWS"
    socket.empty_display_size = 0.06
    socket.parent = armature
    socket.parent_type = "BONE"
    socket.parent_bone = bone_name
    bpy.context.view_layer.update()
    socket.matrix_world = desired_world
    bpy.context.view_layer.update()
    socket["socket_status"] = "AUTO_ESTIMATED_NOT_APPROVED"
    socket["rig_parent_bone"] = bone_name
    return socket


def socket_locations(
    armature: bpy.types.Object, character_code: str
) -> dict[str, tuple[str, Vector]]:
    left_hand = bone_tail_world(armature, "LeftHand")
    right_hand = bone_tail_world(armature, "RightHand")
    hips = bone_tail_world(armature, "Hips")
    head = bone_tail_world(armature, "Head")
    left_shoulder = bone_tail_world(armature, "LeftShoulder")
    right_shoulder = bone_tail_world(armature, "RightShoulder")
    locations: dict[str, tuple[str, Vector]] = {
        "Socket_Equipment_Primary": ("RightHand", right_hand),
        "Socket_VFXCenter": ("Hips", hips),
        "Socket_CameraFocus": ("Head", head),
    }
    character_locations = {
        "CH101": {
            "Socket_Weapon_R": ("RightHand", right_hand),
            "Socket_BladeTip": ("RightHand", right_hand + Vector((0.0, -0.55, -0.2))),
            "Socket_Ribbon_L": ("Hips", hips + Vector((-0.12, 0.0, 0.0))),
            "Socket_Ribbon_R": ("Hips", hips + Vector((0.12, 0.0, 0.0))),
        },
        "CH102": {
            "Socket_Weapon_R": ("RightHand", right_hand),
            "Socket_BowRoot": ("RightHand", right_hand),
            "Socket_BowGrip_L": ("LeftHand", left_hand),
            "Socket_BowGrip_R": ("RightHand", right_hand),
        },
        "CH103": {
            "Socket_Equipment_R": ("RightHand", right_hand),
            "Socket_BatonGrip": ("RightHand", right_hand),
            "Socket_BatonOrb": ("RightHand", right_hand + Vector((0.0, -0.45, -0.12))),
            "Socket_VeilRoot_L": ("LeftShoulder", left_shoulder),
            "Socket_VeilRoot_R": ("RightShoulder", right_shoulder),
            "Socket_VeilWaist_L": ("Hips", hips + Vector((-0.15, 0.0, -0.08))),
            "Socket_VeilWaist_R": ("Hips", hips + Vector((0.15, 0.0, -0.08))),
        },
        "CH104": {
            "Socket_FanGrip": ("RightHand", right_hand),
            "Socket_FanPivot": ("RightHand", right_hand + Vector((0.0, -0.08, 0.0))),
            "Socket_FanBeam": ("RightHand", right_hand + Vector((0.0, -0.42, 0.0))),
            "Socket_MapRing_Carry": ("Hips", hips + Vector((-0.18, 0.0, -0.12))),
            "Socket_MapRingCore": ("RightHand", right_hand + Vector((0.0, -0.22, 0.0))),
        },
        "CH105": {
            "Socket_Gauntlet_L_Wrist": ("LeftHand", left_hand),
            "Socket_Gauntlet_R_Wrist": ("RightHand", right_hand),
            "Socket_Gauntlet_L_Knuckle": ("LeftHand", left_hand + Vector((0.0, -0.08, 0.0))),
            "Socket_Gauntlet_R_Knuckle": ("RightHand", right_hand + Vector((0.0, -0.08, 0.0))),
            "Socket_AnchorRing_Carry": ("Hips", hips + Vector((0.18, 0.0, -0.12))),
            "Socket_AnchorRing_Active": ("RightHand", right_hand + Vector((0.0, -0.30, 0.0))),
            "Socket_AnchorRing_CableAttach": ("RightHand", right_hand + Vector((0.0, -0.36, -0.04))),
        },
    }
    if character_code not in character_locations:
        raise ValueError(f"unsupported socket character: {character_code}")
    locations.update(character_locations[character_code])
    return locations


def build_sockets(
    armature: bpy.types.Object,
    socket_contract: dict[str, object],
    character_code: str,
) -> dict[str, object]:
    character = next(
        entry
        for entry in socket_contract["characters"]
        if entry["code"] == character_code
    )
    detail_names = character["detailSockets"]
    runtime_map = character["runtimeSocketMap"]
    locations = socket_locations(armature, character_code)
    sockets = {}
    for name in detail_names:
        if name not in locations:
            raise ValueError(f"no estimated socket location for {character_code}: {name}")
        bone_name, location = locations[name]
        sockets[name] = create_socket(name, armature, bone_name, location)
    effective_runtime_map = {
        name: runtime_map.get(name, name)
        for name in socket_contract["commonRuntimeSockets"]
    }
    effective_runtime_map.update(runtime_map)
    for runtime_name, source_name in effective_runtime_map.items():
        if source_name not in sockets:
            if source_name not in locations:
                raise ValueError(
                    f"no estimated socket location for {character_code}: {source_name}"
                )
            bone_name, location = locations[source_name]
            sockets[source_name] = create_socket(
                source_name, armature, bone_name, location
            )
        if runtime_name == source_name:
            continue
        source = sockets[source_name]
        if runtime_name not in sockets:
            alias = create_socket(
                runtime_name,
                armature,
                source.parent_bone,
                source.matrix_world.translation.copy(),
            )
            alias.matrix_world = source.matrix_world.copy()
            sockets[runtime_name] = alias
    bpy.context.view_layer.update()
    for runtime_name, source_name in effective_runtime_map.items():
        if runtime_name == source_name:
            continue
        alias = sockets[runtime_name]
        source = sockets[source_name]
        alias.matrix_parent_inverse = source.matrix_parent_inverse.copy()
        alias.matrix_basis = source.matrix_basis.copy()
    bpy.context.view_layer.update()
    return {
        "socketNames": sorted(sockets),
        "runtimeSocketMap": effective_runtime_map,
        "status": "AUTO_ESTIMATED_NOT_APPROVED",
    }


def main() -> int:
    args = parse_args()
    ranking_path = args.ranking_manifest.resolve()
    ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
    if ranking.get("unityInputAllowed") is not False:
        raise ValueError("ranking manifest cannot enable Unity input")
    selected = ranking.get("selectedCandidate")
    if not isinstance(selected, dict):
        raise ValueError("ranking manifest has no candidate eligible for human review")
    candidate = Path(selected["candidatePath"]).resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    if selected.get("candidateSha256") != sha256_file(candidate):
        raise ValueError("selected candidate hash mismatch")
    front_view = selected.get("selectedOrientation", {}).get("front")
    character_code = ranking.get("character")
    if not isinstance(character_code, str) or not character_code:
        raise ValueError("ranking manifest has no character code")

    socket_contract = json.loads(args.socket_contract.resolve().read_text(encoding="utf-8"))
    clear_scene()
    imported = import_candidate(candidate)
    source_meshes = [obj for obj in imported if obj.type == "MESH"]
    if not source_meshes:
        raise ValueError("selected candidate contains no mesh")
    normalize_import(imported, front_view, character_code)
    lods, triangle_counts = build_lods(source_meshes)
    armature = build_humanoid_rig(lods["LOD0"], character_code)
    weight_status, weight_error, weight_audit = auto_weight(
        lods["LOD0"], armature, character_code
    )
    socket_report = build_sockets(armature, socket_contract, character_code)

    scene = bpy.context.scene
    scene["re_camp_status"] = SOURCE_STATUS
    scene["source_candidate_id"] = selected["candidateId"]
    scene["source_candidate_sha256"] = selected["candidateSha256"]
    scene["gate_b"] = GATE_B
    scene["unity_input_allowed"] = False
    scene["production_promotion_allowed"] = False
    scene["face_driver_status"] = "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER"
    scene["socket_status"] = socket_report["status"]
    scene["auto_weight_status"] = weight_status

    output_blend = args.output_blend.resolve()
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    report = {
        "character": character_code,
        "candidateId": selected["candidateId"],
        "candidatePath": str(candidate),
        "candidateSha256": selected["candidateSha256"],
        "status": SOURCE_STATUS,
        "gateB": GATE_B,
        "unityInputAllowed": False,
        "productionPromotionAllowed": False,
        "outputBlend": str(output_blend),
        "outputBlendSha256": sha256_file(output_blend),
        "selectedOrientation": selected["selectedOrientation"],
        "triangleCounts": triangle_counts,
        "rig": {
            "name": armature.name,
            "boneCount": len(armature.data.bones),
            "weightStatus": weight_status,
            "weightError": weight_error,
            "weightAudit": weight_audit,
        },
        "sockets": socket_report,
        "faceDriver": {
            "status": "BLOCKED_NO_RELIABLE_FREE_FACE_LANDMARK_TRANSFER",
            "requiredShapes": [
                "Blink_L",
                "Blink_R",
                "Face_Smile",
                "Viseme_A",
                "Viseme_E",
                "Viseme_I",
                "Viseme_O",
                "Viseme_U",
            ],
        },
        "warnings": [
            "Heuristic bone positions and automatic weights require deformation review.",
            "Bone heat weighting is audited; deterministic nearest-bone weights are used only as a review fallback.",
            "Sockets are estimated from body proportions, not detected equipment geometry.",
            "No FBX/GLB Unity package is exported before human Gate B approval.",
        ],
    }
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
