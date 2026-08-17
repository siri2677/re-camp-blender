#!/usr/bin/env python3
"""Build the CH101 art-directed skinned blockout review variants.

This is a procedural, documentation-grade 3D blockout based on the locked
CH101 production sheet. It is not a final sculpt, rig, animation, Unity
import proof, Android performance result, or Gate B approval.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SOCKETS = {
    "Socket_Equipment_Primary": (0.58, -0.18, 1.92),
    "Socket_Gauntlet_L": (-0.74, -0.02, 2.06),
    "Socket_Gauntlet_R": (0.74, -0.02, 2.06),
    "Socket_AnchorRing_Carry": (0.0, -0.52, 2.38),
    "Socket_AnchorRing_Active": (0.0, -0.68, 2.38),
    "Socket_LineAttach": (0.0, -0.72, 2.38),
    "Socket_VFXCenter": (0.0, -0.24, 1.92),
    "Socket_CameraFocus": (0.0, 0.0, 2.55),
}


RIG_BONES = {
    "Root": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.20), None),
    "Hips": ((0.0, 0.0, 1.28), (0.0, 0.0, 1.55), "Root"),
    "Spine": ((0.0, 0.0, 1.55), (0.0, 0.0, 2.05), "Hips"),
    "Chest": ((0.0, 0.0, 2.05), (0.0, 0.0, 2.40), "Spine"),
    "Neck": ((0.0, 0.0, 2.40), (0.0, 0.0, 2.58), "Chest"),
    "Head": ((0.0, 0.0, 2.58), (0.0, 0.0, 3.12), "Neck"),
    "LeftShoulder": ((-0.12, 0.0, 2.35), (-0.31, 0.0, 2.31), "Chest"),
    "LeftUpperArm": ((-0.31, 0.0, 2.31), (-0.64, -0.01, 1.99), "LeftShoulder"),
    "LeftLowerArm": ((-0.64, -0.01, 1.99), (-0.80, -0.07, 1.72), "LeftUpperArm"),
    "LeftHand": ((-0.80, -0.07, 1.72), (-0.81, -0.08, 1.58), "LeftLowerArm"),
    "RightShoulder": ((0.12, 0.0, 2.35), (0.31, 0.0, 2.31), "Chest"),
    "RightUpperArm": ((0.31, 0.0, 2.31), (0.64, -0.01, 1.99), "RightShoulder"),
    "RightLowerArm": ((0.64, -0.01, 1.99), (0.80, -0.07, 1.72), "RightUpperArm"),
    "RightHand": ((0.80, -0.07, 1.72), (0.81, -0.08, 1.58), "RightLowerArm"),
    "LeftUpperLeg": ((-0.20, 0.0, 1.40), (-0.224, 0.0, 0.70), "Hips"),
    "LeftLowerLeg": ((-0.224, 0.0, 0.70), (-0.236, -0.04, 0.43), "LeftUpperLeg"),
    "LeftFoot": ((-0.236, -0.04, 0.43), (-0.236, -0.22, 0.15), "LeftLowerLeg"),
    "LeftToes": ((-0.236, -0.22, 0.15), (-0.236, -0.40, 0.12), "LeftFoot"),
    "RightUpperLeg": ((0.20, 0.0, 1.40), (0.224, 0.0, 0.70), "Hips"),
    "RightLowerLeg": ((0.224, 0.0, 0.70), (0.236, -0.04, 0.43), "RightUpperLeg"),
    "RightFoot": ((0.236, -0.04, 0.43), (0.236, -0.22, 0.15), "RightLowerLeg"),
    "RightToes": ((0.236, -0.22, 0.15), (0.236, -0.40, 0.12), "RightFoot"),
}


SOCKET_BONE_MAP = {
    "Socket_Equipment_Primary": "RightHand",
    "Socket_Gauntlet_L": "LeftHand",
    "Socket_Gauntlet_R": "RightHand",
    "Socket_AnchorRing_Carry": "Chest",
    "Socket_AnchorRing_Active": "Chest",
    "Socket_LineAttach": "Chest",
    "Socket_VFXCenter": "Hips",
    "Socket_CameraFocus": "Head",
}


MOTION_CLIPS = {
    "CH101_Idle": 48,
    "CH101_Run": 24,
    "CH101_Attack": 24,
    "CH101_A_Pose_Check": 2,
}

BODY_TRIANGLE_BUDGET = 18_000
EQUIPMENT_TRIANGLE_BUDGET = 2_000
COMBINED_TRIANGLE_BUDGET = BODY_TRIANGLE_BUDGET + EQUIPMENT_TRIANGLE_BUDGET


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    script_args = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", default="CH101")
    parser.add_argument("--source-asset", default="")
    parser.add_argument(
        "--source-commit",
        default="b6c9b3128358e061eee6184230929413eba84101",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--export-fbx", action="store_true")
    parser.add_argument(
        "--optimize-budget",
        action="store_true",
        help="Create the budget-review variant by simplifying LOD0 meshes.",
    )
    parser.add_argument(
        "--generate-lods",
        action="store_true",
        help="Create hidden LOD1/LOD2 review meshes from the optimized LOD0.",
    )
    parser.add_argument(
        "--production-skinning-review",
        action="store_true",
        help="Replace rigid blockout weights with deterministic blended review weights.",
    )
    return parser.parse_args(script_args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def material(
    name: str,
    color: tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.58,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.metallic = metallic
    mat.roughness = roughness
    mat["art_token"] = name.replace("MAT_CH101_", "")
    return mat


def apply_material(obj: bpy.types.Object, mat: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.append(mat)
    return obj


def smooth_mesh(obj: bpy.types.Object) -> bpy.types.Object:
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def add_uv_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return smooth_mesh(apply_material(obj, mat))


def add_cylinder_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    start_vec = Vector(start)
    end_vec = Vector(end)
    direction = end_vec - start_vec
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20,
        radius=radius,
        depth=direction.length,
        location=(start_vec + end_vec) / 2,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return smooth_mesh(apply_material(obj, mat))


def add_cube(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if bevel:
        modifier = obj.modifiers.new(name="SoftEdges", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return apply_material(obj, mat)


def add_curve(
    name: str,
    points: list[tuple[float, float, float]],
    bevel_depth: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 12
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 3
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    return apply_material(obj, mat)


def add_socket(name: str, location: tuple[float, float, float], root: bpy.types.Object) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.12
    obj.location = location
    obj.parent = root
    bpy.context.collection.objects.link(obj)
    return obj


def add_camera(name: str, location: tuple[float, float, float], target: Vector) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 58
    return camera


def configure_render(scene: bpy.types.Scene, output_dir: Path) -> None:
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except (RuntimeError, TypeError, ValueError):
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.025, 0.035, 0.05)
    output_dir.mkdir(parents=True, exist_ok=True)


def add_area_light(
    name: str,
    location: tuple[float, float, float],
    target: Vector,
    energy: float,
    color: tuple[float, float, float],
    size: float,
) -> bpy.types.Object:
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = energy
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    return light


def add_saber(root: bpy.types.Object, mats: dict[str, bpy.types.Material]) -> None:
    """Add the single canonical gold/graphite/cyan saber and sheath cues."""
    x, y, z = SOCKETS["Socket_Equipment_Primary"]
    handle = add_cylinder_between("Saber_Handle", (x, y, z - 0.42), (x, y, z + 0.08), 0.055, mats["graphite"])
    guard = add_cube("Saber_Guard", (x, y - 0.01, z + 0.10), (0.18, 0.06, 0.045), mats["gold"], bevel=0.025)
    blade = add_cube("Saber_Blade_Cyan", (x, y, z + 0.58), (0.055, 0.035, 0.46), mats["cyan"], bevel=0.025)
    blade_core = add_cube("Saber_Blade_Core", (x, y - 0.038, z + 0.58), (0.018, 0.012, 0.40), mats["cyan"], bevel=0.008)
    pommel = add_uv_sphere("Saber_Pommel", (x, y, z - 0.47), (0.09, 0.07, 0.07), mats["gold"])
    sheath = add_cylinder_between("Saber_Sheath", (x + 0.14, y + 0.18, z - 0.36), (x + 0.14, y + 0.18, z + 0.74), 0.075, mats["graphite"])
    sheath_band = add_cube("Saber_Sheath_GoldBand", (x + 0.14, y + 0.18, z + 0.43), (0.10, 0.09, 0.035), mats["gold"], bevel=0.018)
    blade_stripes = []
    for index, stripe_z in enumerate((z + 0.36, z + 0.60, z + 0.84), start=1):
        stripe = add_cube(f"Saber_Blade_Stripe_{index}", (x - 0.045, y - 0.045, stripe_z), (0.012, 0.008, 0.09), mats["cyan"], bevel=0.006)
        stripe.rotation_euler[1] = math.radians(-28)
        blade_stripes.append(stripe)
    for obj in (handle, guard, blade, blade_core, pommel, sheath, sheath_band, *blade_stripes):
        obj.parent = root


def add_boot(root: bpy.types.Object, side: str, x: float, mats: dict[str, bpy.types.Material]) -> None:
    upper = add_cube(f"Boot_{side}_WhiteUpper", (x, -0.03, 0.20), (0.18, 0.25, 0.18), mats["white"], bevel=0.06)
    ankle = add_cube(f"Boot_{side}_GraphiteAnkle", (x, -0.08, 0.39), (0.16, 0.20, 0.12), mats["graphite"], bevel=0.04)
    sole = add_cube(f"Boot_{side}_CyanSole", (x, -0.07, 0.035), (0.21, 0.29, 0.035), mats["cyan"], bevel=0.025)
    toe = add_cube(f"Boot_{side}_GraphiteToe", (x, -0.28, 0.15), (0.18, 0.10, 0.12), mats["graphite"], bevel=0.04)
    side_stripe = add_cube(f"Boot_{side}_CyanSideStripe", (x, -0.385, 0.27), (0.035, 0.012, 0.10), mats["cyan"], bevel=0.012)
    lace = add_cube(f"Boot_{side}_GoldLace", (x, -0.395, 0.38), (0.08, 0.012, 0.018), mats["gold"], bevel=0.008)
    for obj in (upper, ankle, sole, toe, side_stripe, lace):
        obj.parent = root


def prepare_technical_asset(root: bpy.types.Object) -> dict[str, int]:
    """Convert procedural curves and make the v005 export technically inspectable."""
    for obj in list(bpy.context.scene.objects):
        if obj.type != "CURVE":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    uv_missing = 0
    materialless = 0
    triangle_count = 0
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for modifier in list(obj.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            except RuntimeError:
                obj["modifier_status"] = "PENDING / APPLY FAILED"
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if not obj.data.uv_layers:
            uv_missing += 1
            try:
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.03)
                bpy.ops.object.mode_set(mode="OBJECT")
            except (RuntimeError, TypeError):
                if bpy.context.object and bpy.context.object.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
        if not obj.data.materials:
            materialless += 1
        obj.data.update()
        obj.data.calc_loop_triangles()
        triangle_count += len(obj.data.loop_triangles)
        obj["technical_revision"] = "v005"
        obj["uv_status"] = "PASS" if obj.data.uv_layers else "FAIL"
        obj["material_slot_status"] = "PASS" if obj.data.materials else "FAIL"
        obj["lod_level"] = "LOD0"
        obj["lod_status"] = "LOD0 ONLY / LOD PENDING"
    bpy.ops.object.select_all(action="DESELECT")
    root["technical_prepared"] = True
    root["uv_missing_before_prepare"] = uv_missing
    root["materialless_mesh_count"] = materialless
    root["triangle_count"] = triangle_count
    root["lod_status"] = "LOD0 ONLY / LOD PENDING"
    return {
        "mesh_object_count": len(meshes),
        "uv_missing_after_prepare": sum(1 for obj in meshes if not obj.data.uv_layers),
        "materialless_mesh_count": sum(1 for obj in meshes if not obj.data.materials),
        "triangle_count": triangle_count,
    }


def optimize_lod0_budget(root: bpy.types.Object) -> dict[str, int | str]:
    """Simplify the review LOD0 without changing object names, sockets, or materials."""
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]

    def triangle_count() -> int:
        count = 0
        for obj in meshes:
            obj.data.calc_loop_triangles()
            count += len(obj.data.loop_triangles)
        return count

    initial = triangle_count()
    before = initial
    iterations = 0
    while before > COMBINED_TRIANGLE_BUDGET and iterations < 3:
        ratio = max(0.25, min(0.92, (COMBINED_TRIANGLE_BUDGET / before) * 0.96))
        for obj in meshes:
            obj.data.calc_loop_triangles()
            if len(obj.data.loop_triangles) <= 12:
                continue
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new(name="CH101_LOD0_BudgetSimplify", type="DECIMATE")
            modifier.decimate_type = "COLLAPSE"
            modifier.ratio = ratio
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            except RuntimeError:
                obj["lod_simplify_status"] = "PENDING / APPLY FAILED"
        before = triangle_count()
        iterations += 1

    after = triangle_count()
    status = "PASS" if after <= COMBINED_TRIANGLE_BUDGET else "FAIL / SIMPLIFICATION REQUIRED"
    for obj in meshes:
        obj["lod_status"] = "LOD0 OPTIMIZED / LOD1-2 PENDING"
        obj["triangle_budget_status"] = status
    root["triangle_count_before_optimization"] = initial
    root["triangle_count_after_optimization"] = after
    root["triangle_budget_status"] = status
    root["lod_status"] = "LOD0 OPTIMIZED / LOD1-2 PENDING"
    return {
        "triangle_count_before": initial,
        "triangle_count_after": after,
        "triangle_budget_status": status,
        "iterations": iterations,
    }


def generate_lod_variants(root: bpy.types.Object) -> dict[str, object]:
    """Create hidden LOD1/LOD2 review meshes with stable source metadata."""
    sources = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.get("lod_level", "LOD0") == "LOD0"
    ]
    lod_ratios = {"LOD1": 0.55, "LOD2": 0.30}
    lod_counts: dict[str, int] = {"LOD0": 0, "LOD1": 0, "LOD2": 0}
    for source in sources:
        source.data.calc_loop_triangles()
        lod_counts["LOD0"] += len(source.data.loop_triangles)
    for lod_name, ratio in lod_ratios.items():
        for source in sources:
            lod_object = source.copy()
            lod_object.data = source.data.copy()
            lod_object.name = f"{source.name}_{lod_name}"
            lod_object["lod_level"] = lod_name
            lod_object["lod_source"] = source.name
            lod_object["lod_ratio"] = ratio
            lod_object["lod_status"] = "GENERATED / REVIEW PENDING"
            bpy.context.collection.objects.link(lod_object)
            lod_object.hide_render = True
            lod_object.hide_set(True)

            for modifier in list(lod_object.modifiers):
                if modifier.type != "ARMATURE":
                    lod_object.modifiers.remove(modifier)
            decimate = lod_object.modifiers.new(name=f"CH101_{lod_name}_Simplify", type="DECIMATE")
            decimate.decimate_type = "COLLAPSE"
            decimate.ratio = ratio
            bpy.context.view_layer.objects.active = lod_object
            while lod_object.modifiers.find(decimate.name) > 0:
                bpy.ops.object.modifier_move_up(modifier=decimate.name)
            lod_object.select_set(True)
            try:
                bpy.ops.object.modifier_apply(modifier=decimate.name)
            except RuntimeError:
                lod_object["lod_status"] = "GENERATED / DECIMATE APPLY FAILED"
            lod_object.select_set(False)
            lod_object.data.calc_loop_triangles()
            lod_counts[lod_name] += len(lod_object.data.loop_triangles)
    root["lod_levels"] = "LOD0,LOD1,LOD2"
    root["lod_triangle_counts"] = json.dumps(lod_counts, sort_keys=True)
    root["lod_status"] = "LOD0/LOD1/LOD2 GENERATED / REVIEW PENDING"
    return {"lod_triangle_counts": lod_counts, "source_mesh_count": len(sources)}


def _reset_pose(armature: bpy.types.Object) -> None:
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
        pose_bone.location = (0.0, 0.0, 0.0)
        pose_bone.rotation_euler = (0.0, 0.0, 0.0)
        pose_bone.scale = (1.0, 1.0, 1.0)


def _create_motion_action(
    armature: bpy.types.Object,
    name: str,
    frame_end: int,
    keyframes: list[tuple[int, dict[str, tuple[float, float, float]]]],
) -> bpy.types.Action:
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action
    _reset_pose(armature)
    for frame, rotations in keyframes:
        for bone_name, rotation in rotations.items():
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone is None:
                continue
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = rotation
            pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone_name)
    action["review_frame_start"] = 1
    action["review_frame_end"] = frame_end
    return action


def prepare_rig_and_motion(root: bpy.types.Object) -> dict[str, object]:
    """Create an unweighted humanoid-aligned rig prototype and review actions."""
    armature_data = bpy.data.armatures.new("CH101_Rig_Armature")
    armature = bpy.data.objects.new("CH101_Rig_Armature", armature_data)
    bpy.context.collection.objects.link(armature)
    armature.parent = root
    armature["rig_revision"] = "v006"
    armature["rig_status"] = "PROTOTYPE / UNWEIGHTED"
    armature["deformation_status"] = "NOT WEIGHTED / PENDING SKINNING"
    armature["humanoid_mapping_status"] = "ROLE NAMES PREPARED / UNITY CHECK PENDING"
    armature["rest_pose_status"] = "NEUTRAL BLOCKOUT POSE / A-POSE CHECK ACTION INCLUDED"
    armature["motion_status"] = "IDLE RUN ATTACK REVIEW CLIPS"

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones: dict[str, bpy.types.EditBone] = {}
    for name, (head, tail, parent_name) in RIG_BONES.items():
        bone = armature_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent_name:
            bone.parent = edit_bones[parent_name]
            bone.use_connect = name not in {"LeftShoulder", "RightShoulder", "LeftUpperLeg", "RightUpperLeg"}
        edit_bones[name] = bone
    bpy.ops.object.mode_set(mode="OBJECT")

    humanoid_roles = {
        "Hips": "Hips", "Spine": "Spine", "Chest": "Chest", "Neck": "Neck", "Head": "Head",
        "LeftUpperArm": "LeftUpperArm", "LeftLowerArm": "LeftLowerArm", "LeftHand": "LeftHand",
        "RightUpperArm": "RightUpperArm", "RightLowerArm": "RightLowerArm", "RightHand": "RightHand",
        "LeftUpperLeg": "LeftUpperLeg", "LeftLowerLeg": "LeftLowerLeg", "LeftFoot": "LeftFoot",
        "RightUpperLeg": "RightUpperLeg", "RightLowerLeg": "RightLowerLeg", "RightFoot": "RightFoot",
    }
    for bone_name, role in humanoid_roles.items():
        armature_data.bones[bone_name]["humanoid_role"] = role

    for socket_name, bone_name in SOCKET_BONE_MAP.items():
        socket = bpy.data.objects.get(socket_name)
        if socket is None:
            continue
        world_matrix = socket.matrix_world.copy()
        socket.parent = armature
        socket.parent_type = "BONE"
        socket.parent_bone = bone_name
        socket.matrix_world = world_matrix
        socket["rig_parent_bone"] = bone_name

    idle = _create_motion_action(
        armature,
        "CH101_Idle",
        MOTION_CLIPS["CH101_Idle"],
        [
            (1, {"Chest": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)}),
            (24, {"Chest": (math.radians(-2.0), 0.0, 0.0), "Head": (math.radians(2.0), 0.0, 0.0)}),
            (48, {"Chest": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)}),
        ],
    )
    run = _create_motion_action(
        armature,
        "CH101_Run",
        MOTION_CLIPS["CH101_Run"],
        [
            (1, {"LeftUpperArm": (math.radians(-28), 0.0, 0.0), "RightUpperArm": (math.radians(28), 0.0, 0.0), "LeftUpperLeg": (math.radians(28), 0.0, 0.0), "RightUpperLeg": (math.radians(-28), 0.0, 0.0)}),
            (12, {"LeftUpperArm": (math.radians(28), 0.0, 0.0), "RightUpperArm": (math.radians(-28), 0.0, 0.0), "LeftUpperLeg": (math.radians(-28), 0.0, 0.0), "RightUpperLeg": (math.radians(28), 0.0, 0.0)}),
            (24, {"LeftUpperArm": (math.radians(-28), 0.0, 0.0), "RightUpperArm": (math.radians(28), 0.0, 0.0), "LeftUpperLeg": (math.radians(28), 0.0, 0.0), "RightUpperLeg": (math.radians(-28), 0.0, 0.0)}),
        ],
    )
    attack = _create_motion_action(
        armature,
        "CH101_Attack",
        MOTION_CLIPS["CH101_Attack"],
        [
            (1, {"RightUpperArm": (0.0, 0.0, 0.0), "RightLowerArm": (0.0, 0.0, 0.0)}),
            (8, {"RightUpperArm": (math.radians(-55), math.radians(-18), math.radians(-12)), "RightLowerArm": (math.radians(-70), 0.0, 0.0)}),
            (16, {"RightUpperArm": (math.radians(25), math.radians(12), math.radians(8)), "RightLowerArm": (math.radians(-30), 0.0, 0.0)}),
            (24, {"RightUpperArm": (0.0, 0.0, 0.0), "RightLowerArm": (0.0, 0.0, 0.0)}),
        ],
    )
    a_pose = _create_motion_action(
        armature,
        "CH101_A_Pose_Check",
        MOTION_CLIPS["CH101_A_Pose_Check"],
        [
            (1, {"LeftUpperArm": (math.radians(-42), 0.0, 0.0), "RightUpperArm": (math.radians(42), 0.0, 0.0)}),
            (2, {"LeftUpperArm": (math.radians(-42), 0.0, 0.0), "RightUpperArm": (math.radians(42), 0.0, 0.0)}),
        ],
    )
    armature.animation_data.action = idle
    _reset_pose(armature)
    bpy.ops.object.select_all(action="DESELECT")
    root["rig_prepared"] = True
    root["rig_status"] = "PROTOTYPE / UNWEIGHTED"
    root["deformation_status"] = "NOT WEIGHTED / PENDING SKINNING"
    root["motion_clip_names"] = ",".join((idle.name, run.name, attack.name, a_pose.name))
    root["socket_bone_parenting"] = "PASS"
    return {
        "armature_name": armature.name,
        "bone_count": len(armature_data.bones),
        "action_names": sorted(action.name for action in (idle, run, attack, a_pose)),
        "socket_bone_map": SOCKET_BONE_MAP,
        "deformation_status": armature["deformation_status"],
    }


def _skinning_bone_for_object(name: str) -> str:
    """Return a deliberate rigid-blockout bone assignment for a mesh part."""
    if name.startswith(("Hair_", "Face_", "Eye_")) or name in {"Body_Head"}:
        return "Head"
    if name == "Body_Neck":
        return "Neck"
    if name in {"Body_Pelvis", "Shorts_Waistband", "Shorts_Belt_Cyan"}:
        return "Hips"
    if name == "Body_Torso" or name.startswith(("Jacket_", "CropTop_", "SignalRibbon_")):
        return "Chest"
    if name.startswith("Saber_"):
        return "RightHand"
    if name.startswith("Sleeve_L_Upper"):
        return "LeftUpperArm"
    if name.startswith("Sleeve_L_Lower"):
        return "LeftLowerArm"
    if name.startswith(("Cuff_L", "Hand_L")):
        return "LeftHand"
    if name.startswith("Sleeve_R_Upper"):
        return "RightUpperArm"
    if name.startswith("Sleeve_R_Lower"):
        return "RightLowerArm"
    if name.startswith(("Cuff_R", "Hand_R")):
        return "RightHand"
    if name.startswith(("Shorts_L_", "Leg_L_Upper", "ThighStrap_L")):
        return "LeftUpperLeg"
    if name.startswith(("KneeGuard_L", "Leg_L_Lower")):
        return "LeftLowerLeg"
    if name.startswith("Boot_L"):
        return "LeftFoot"
    if name.startswith(("Shorts_R_", "Leg_R_Upper", "ThighStrap_R")):
        return "RightUpperLeg"
    if name.startswith(("KneeGuard_R", "Leg_R_Lower")):
        return "RightLowerLeg"
    if name.startswith("Boot_R"):
        return "RightFoot"
    return "Hips"


def prepare_blockout_skinning(root: bpy.types.Object) -> dict[str, object]:
    """Bind each blockout part rigidly to one rig bone for deformation review."""
    armature = bpy.data.objects.get("CH101_Rig_Armature")
    if armature is None:
        raise RuntimeError("CH101_Rig_Armature is required before skinning")
    weighted_meshes = 0
    assignment_counts: dict[str, int] = {}
    for obj in (item for item in bpy.context.scene.objects if item.type == "MESH"):
        bone_name = _skinning_bone_for_object(obj.name)
        if armature.data.bones.get(bone_name) is None:
            raise RuntimeError(f"Missing skinning bone {bone_name} for {obj.name}")
        group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.get("CH101_ArmatureDeform") or obj.modifiers.new(name="CH101_ArmatureDeform", type="ARMATURE")
        modifier.object = armature
        obj["skinning_revision"] = "v007"
        obj["skinning_mode"] = "RIGID BLOCKOUT WEIGHT"
        obj["skinning_bone"] = bone_name
        weighted_meshes += 1
        assignment_counts[bone_name] = assignment_counts.get(bone_name, 0) + 1
    armature["skinning_revision"] = "v007"
    armature["skinning_status"] = "RIGID BLOCKOUT WEIGHTS / DEFORMATION REVIEW"
    armature["deformation_status"] = "RIGID BLOCKOUT WEIGHTS / PROTOTYPE"
    armature["weighted_mesh_object_count"] = weighted_meshes
    armature["skinning_assignment_counts"] = json.dumps(assignment_counts, sort_keys=True)
    root["skinning_prepared"] = True
    root["skinning_status"] = "RIGID BLOCKOUT WEIGHTS / DEFORMATION REVIEW"
    root["deformation_status"] = "RIGID BLOCKOUT WEIGHTS / PROTOTYPE"
    root["weighted_mesh_object_count"] = weighted_meshes
    root["skinning_assignment_counts"] = json.dumps(assignment_counts, sort_keys=True)
    return {
        "weighted_mesh_object_count": weighted_meshes,
        "skinning_status": armature["skinning_status"],
        "assignment_counts": assignment_counts,
    }


def _production_weight_profile(name: str) -> list[tuple[str, float]]:
    """Return a small, deterministic influence profile for the review mesh.

    The generated blockout is made from separate rigid parts, so this is not a
    claim of final sculpt-quality deformation. It does, however, exercise the
    same two-bone transitions that the Unity import and pose review will use.
    """
    if name.startswith(("Hair_", "Face_", "Eye_")) or name in {"Body_Head"}:
        return [("Neck", 0.18), ("Head", 0.82)]
    if name == "Body_Neck":
        return [("Chest", 0.35), ("Neck", 0.65)]
    if name in {"Body_Pelvis", "Shorts_Waistband", "Shorts_Belt_Cyan"}:
        return [("Hips", 0.72), ("Spine", 0.28)]
    if name == "Body_Torso" or name.startswith(("Jacket_", "CropTop_", "SignalRibbon_")):
        return [("Spine", 0.30), ("Chest", 0.70)]
    if name.startswith("Saber_"):
        return [("RightLowerArm", 0.30), ("RightHand", 0.70)]
    if name.startswith("Sleeve_L_Upper"):
        return [("LeftShoulder", 0.30), ("LeftUpperArm", 0.70)]
    if name.startswith("Sleeve_L_Lower"):
        return [("LeftUpperArm", 0.30), ("LeftLowerArm", 0.70)]
    if name.startswith(("Cuff_L", "Hand_L")):
        return [("LeftLowerArm", 0.30), ("LeftHand", 0.70)]
    if name.startswith("Sleeve_R_Upper"):
        return [("RightShoulder", 0.30), ("RightUpperArm", 0.70)]
    if name.startswith("Sleeve_R_Lower"):
        return [("RightUpperArm", 0.30), ("RightLowerArm", 0.70)]
    if name.startswith(("Cuff_R", "Hand_R")):
        return [("RightLowerArm", 0.30), ("RightHand", 0.70)]
    if name.startswith(("Shorts_L_", "Leg_L_Upper", "ThighStrap_L")):
        return [("Hips", 0.25), ("LeftUpperLeg", 0.75)]
    if name.startswith(("KneeGuard_L", "Leg_L_Lower")):
        return [("LeftUpperLeg", 0.30), ("LeftLowerLeg", 0.70)]
    if name.startswith("Boot_L"):
        return [("LeftLowerLeg", 0.25), ("LeftFoot", 0.75)]
    if name.startswith(("Shorts_R_", "Leg_R_Upper", "ThighStrap_R")):
        return [("Hips", 0.25), ("RightUpperLeg", 0.75)]
    if name.startswith(("KneeGuard_R", "Leg_R_Lower")):
        return [("RightUpperLeg", 0.30), ("RightLowerLeg", 0.70)]
    if name.startswith("Boot_R"):
        return [("RightLowerLeg", 0.25), ("RightFoot", 0.75)]
    return [("Hips", 1.0)]


def prepare_production_skinning_review(root: bpy.types.Object) -> dict[str, object]:
    """Apply normalized two-bone review weights to the LOD0 blockout parts."""
    armature = bpy.data.objects.get("CH101_Rig_Armature")
    if armature is None:
        raise RuntimeError("CH101_Rig_Armature is required before production skinning review")
    weighted_meshes = 0
    assignment_counts: dict[str, int] = {}
    influence_counts: list[int] = []
    for obj in (
        item for item in bpy.context.scene.objects
        if item.type == "MESH" and item.get("lod_level", "LOD0") == "LOD0"
    ):
        profile = _production_weight_profile(obj.name)
        for group in list(obj.vertex_groups):
            obj.vertex_groups.remove(group)
        groups = []
        for bone_name, weight in profile:
            if armature.data.bones.get(bone_name) is None:
                raise RuntimeError(f"Missing production skinning bone {bone_name} for {obj.name}")
            groups.append((obj.vertex_groups.new(name=bone_name), weight))
            assignment_counts[bone_name] = assignment_counts.get(bone_name, 0) + 1
        vertices = list(obj.data.vertices)
        for vertex in vertices:
            for group, weight in groups:
                group.add([vertex.index], weight, "REPLACE")
            influence_counts.append(len(groups))
        modifier = obj.modifiers.get("CH101_ArmatureDeform") or obj.modifiers.new(
            name="CH101_ArmatureDeform", type="ARMATURE"
        )
        modifier.object = armature
        obj["skinning_revision"] = "v010"
        obj["skinning_mode"] = "BLENDED PRODUCTION REVIEW WEIGHTS"
        obj["skinning_profile"] = ",".join(f"{bone}:{weight:.2f}" for bone, weight in profile)
        weighted_meshes += 1
    average_influences = round(sum(influence_counts) / len(influence_counts), 3) if influence_counts else 0.0
    armature["skinning_revision"] = "v010"
    armature["skinning_status"] = "BLENDED WEIGHTS / PRODUCTION REVIEW"
    armature["deformation_status"] = "BLENDED WEIGHTS / PRODUCTION REVIEW"
    armature["max_influences_per_vertex"] = max(influence_counts, default=0)
    armature["average_influences_per_vertex"] = average_influences
    armature["weighted_mesh_object_count"] = weighted_meshes
    armature["skinning_assignment_counts"] = json.dumps(assignment_counts, sort_keys=True)
    root["skinning_prepared"] = True
    root["skinning_status"] = "BLENDED WEIGHTS / PRODUCTION REVIEW"
    root["deformation_status"] = "BLENDED WEIGHTS / PRODUCTION REVIEW"
    root["weighted_mesh_object_count"] = weighted_meshes
    root["max_influences_per_vertex"] = max(influence_counts, default=0)
    root["average_influences_per_vertex"] = average_influences
    root["skinning_assignment_counts"] = json.dumps(assignment_counts, sort_keys=True)
    return {
        "weighted_mesh_object_count": weighted_meshes,
        "skinning_status": armature["skinning_status"],
        "assignment_counts": assignment_counts,
        "max_influences_per_vertex": max(influence_counts, default=0),
        "average_influences_per_vertex": average_influences,
    }


def build_scene(args: argparse.Namespace) -> tuple[bpy.types.Object, Path]:
    output_dir = Path(args.output_dir).resolve()
    revision = "v010" if args.production_skinning_review else ("v009" if args.generate_lods else ("v008" if args.optimize_budget else "v007"))
    clear_scene()

    mats = {
        "skin": material("MAT_CH101_Skin", (0.72, 0.38, 0.28, 1.0), roughness=0.72),
        "white": material("MAT_CH101_White", (0.92, 0.92, 0.86, 1.0), roughness=0.68),
        "graphite": material("MAT_CH101_Graphite", (0.035, 0.045, 0.065, 1.0), roughness=0.48),
        "hair": material("MAT_CH101_Hair", (0.025, 0.032, 0.045, 1.0), roughness=0.42),
        "gold": material("MAT_CH101_Gold", (0.78, 0.46, 0.10, 1.0), metallic=0.55, roughness=0.34),
        "cyan": material("MAT_CH101_Cyan", (0.0, 0.55, 0.68, 1.0), metallic=0.12, roughness=0.38),
    }

    root = bpy.data.objects.new(f"{args.character}_Blockout_Root", None)
    root.empty_display_type = "PLAIN_AXES"
    root["character_id"] = args.character
    root["source_asset"] = args.source_asset
    root["source_commit"] = args.source_commit
    root["art_direction"] = "CH101 Route Sprint / white-black sport jacket / cyan-gold signal ribbon"
    root["blockout_revision"] = revision
    root["blockout_status"] = "DOCUMENTATION ONLY / NOT GATE B APPROVED"
    bpy.context.collection.objects.link(root)

    # Feminine runner proportions with a cropped jacket, shorts, and exposed legs.
    torso = add_cylinder_between("Body_Torso", (0, 0, 1.62), (0, 0, 2.42), 0.30, mats["graphite"])
    pelvis = add_uv_sphere("Body_Pelvis", (0, 0, 1.35), (0.37, 0.27, 0.23), mats["graphite"])
    neck = add_cylinder_between("Body_Neck", (0, 0, 2.40), (0, 0, 2.58), 0.13, mats["skin"])
    head = add_uv_sphere("Body_Head", (0, -0.01, 2.93), (0.36, 0.32, 0.43), mats["skin"])
    for obj in (torso, pelvis, neck, head):
        obj.parent = root

    # White cropped jacket, hood/collar, black sleeves, and gold zipper cue.
    jacket_panels = [
        ("Jacket_Panel_L", (-0.24, -0.27, 2.22), (0.11, 0.055, 0.30)),
        ("Jacket_Panel_R", (0.24, -0.27, 2.22), (0.11, 0.055, 0.30)),
        ("Jacket_Shoulder_L", (-0.34, -0.02, 2.38), (0.13, 0.15, 0.10)),
        ("Jacket_Shoulder_R", (0.34, -0.02, 2.38), (0.13, 0.15, 0.10)),
        ("Jacket_Hood", (0, 0.14, 2.50), (0.28, 0.13, 0.08)),
        ("Jacket_BackPanel", (0, 0.25, 2.22), (0.28, 0.05, 0.28)),
    ]
    for name, location, scale in jacket_panels:
        add_cube(name, location, scale, mats["white"], bevel=0.035).parent = root
    add_cube("Jacket_Zipper_Gold", (0, -0.335, 2.22), (0.018, 0.018, 0.27), mats["gold"], bevel=0.01).parent = root
    add_cube("CropTop_CyanBand", (0, -0.30, 1.91), (0.25, 0.045, 0.04), mats["cyan"], bevel=0.015).parent = root
    add_cube("Jacket_Hem_Cyan_L", (-0.22, -0.30, 1.95), (0.08, 0.018, 0.018), mats["cyan"], bevel=0.008).parent = root
    add_cube("Jacket_Hem_Cyan_R", (0.22, -0.30, 1.95), (0.08, 0.018, 0.018), mats["cyan"], bevel=0.008).parent = root
    add_cube("Jacket_Pocket_L", (-0.23, -0.335, 2.02), (0.07, 0.018, 0.045), mats["graphite"], bevel=0.012).parent = root
    add_cube("Jacket_Pocket_R", (0.23, -0.335, 2.02), (0.07, 0.018, 0.045), mats["graphite"], bevel=0.012).parent = root
    add_cube("Jacket_Back_CyanStripe", (0, 0.305, 2.25), (0.20, 0.018, 0.018), mats["cyan"], bevel=0.008).parent = root

    arms = [
        ("L", -1, (-0.31, 0, 2.31), (-0.64, -0.01, 1.99), (-0.80, -0.07, 1.72)),
        ("R", 1, (0.31, 0, 2.31), (0.64, -0.01, 1.99), (0.80, -0.07, 1.72)),
    ]
    for side, sign, shoulder, elbow, wrist in arms:
        upper = add_cylinder_between(f"Sleeve_{side}_Upper", shoulder, elbow, 0.115, mats["graphite"])
        lower = add_cylinder_between(f"Sleeve_{side}_Lower", elbow, wrist, 0.095, mats["graphite"])
        cuff = add_cube(f"Cuff_{side}_White", wrist, (0.11, 0.12, 0.08), mats["white"], bevel=0.03)
        hand = add_uv_sphere(f"Hand_{side}", (wrist[0] + 0.01 * sign, wrist[1] - 0.01, wrist[2] - 0.10), (0.09, 0.08, 0.11), mats["skin"])
        sleeve_piping = add_cylinder_between(f"Sleeve_{side}_CyanPiping", shoulder, elbow, 0.018, mats["cyan"])
        for obj in (upper, lower, cuff, hand, sleeve_piping):
            obj.parent = root

    # Shorts, exposed legs, thigh straps, knee guards, and the white/cyan boots.
    add_cube("Shorts_Waistband", (0, -0.02, 1.48), (0.34, 0.25, 0.10), mats["graphite"], bevel=0.04).parent = root
    add_cube("Shorts_Belt_Cyan", (0, -0.275, 1.49), (0.30, 0.018, 0.025), mats["cyan"], bevel=0.008).parent = root
    for side, x in (("L", -0.20), ("R", 0.20)):
        add_cube(f"Shorts_{side}_Leg", (x, -0.04, 1.28), (0.16, 0.22, 0.17), mats["graphite"], bevel=0.04).parent = root
        thigh = add_cylinder_between(f"Leg_{side}_Upper", (x, 0, 1.14), (x * 1.12, 0, 0.70), 0.12, mats["skin"])
        shin = add_cylinder_between(f"Leg_{side}_Lower", (x * 1.12, 0, 0.70), (x * 1.18, -0.04, 0.43), 0.10, mats["skin"])
        strap = add_cube(f"ThighStrap_{side}", (x * 1.05, -0.25, 1.05), (0.14, 0.035, 0.04), mats["white"], bevel=0.012)
        knee = add_cube(f"KneeGuard_{side}", (x * 1.12, -0.14, 0.64), (0.115, 0.07, 0.08), mats["graphite"], bevel=0.025)
        strap_buckle = add_cube(f"ThighStrap_{side}_GoldBuckle", (x * 1.05, -0.29, 1.05), (0.035, 0.012, 0.025), mats["gold"], bevel=0.008)
        for obj in (thigh, shin, strap, knee, strap_buckle):
            obj.parent = root
        add_boot(root, side, x * 1.18, mats)

    # High ponytail, loose bangs, cyan ends, and a gold tie cue.
    hair_main = add_uv_sphere("Hair_Main", (0, 0.08, 3.10), (0.42, 0.36, 0.36), mats["hair"])
    bangs = [(-0.18, -0.28, 3.12), (0.0, -0.31, 3.16), (0.18, -0.28, 3.12)]
    hair_tail = [
        (0.24, 0.10, 3.18, (0.18, 0.16, 0.27)),
        (0.42, 0.12, 2.98, (0.16, 0.14, 0.28)),
        (0.37, 0.08, 2.76, (0.13, 0.12, 0.22)),
    ]
    hair_main.parent = root
    for index, location in enumerate(bangs):
        add_uv_sphere(f"Hair_Bang_{index + 1}", location, (0.13, 0.08, 0.22), mats["hair"]).parent = root
    for index, (location_x, location_y, location_z, scale) in enumerate(hair_tail):
        add_uv_sphere(f"Hair_Ponytail_{index + 1}", (location_x, location_y, location_z), scale, mats["hair"]).parent = root
    add_uv_sphere("Hair_Ponytail_CyanTip", (0.30, 0.04, 2.58), (0.11, 0.10, 0.20), mats["cyan"]).parent = root
    add_torus("Hair_Tie_Gold", (0.25, 0.10, 3.20), 0.10, 0.025, mats["gold"], rotation=(math.pi / 2, 0, 0)).parent = root
    add_curve("Hair_Lock_L", [(-0.30, -0.20, 3.10), (-0.42, -0.18, 2.84), (-0.34, -0.16, 2.64)], 0.035, mats["hair"]).parent = root
    add_curve("Hair_Lock_R", [(0.30, -0.20, 3.10), (0.42, -0.18, 2.84), (0.34, -0.16, 2.64)], 0.035, mats["hair"]).parent = root
    for eye_x in (-0.13, 0.13):
        eye = add_uv_sphere("Eye_Cyan", (eye_x, -0.315, 2.98), (0.035, 0.018, 0.055), mats["cyan"])
        eye["emission_review"] = "CYAN EYE ACCENT / SHADER EMISSION PENDING"
        eye.parent = root
    add_uv_sphere("Face_Chin", (0, -0.25, 2.78), (0.19, 0.08, 0.11), mats["skin"]).parent = root
    add_cube("Face_Mouth", (0, -0.337, 2.84), (0.055, 0.008, 0.012), mats["graphite"], bevel=0.006).parent = root
    add_cube("Face_Brow_L", (-0.13, -0.332, 3.08), (0.065, 0.008, 0.012), mats["hair"], bevel=0.006).parent = root
    add_cube("Face_Brow_R", (0.13, -0.332, 3.08), (0.065, 0.008, 0.012), mats["hair"], bevel=0.006).parent = root
    add_curve("Hair_Ponytail_LongLock", [(0.36, 0.10, 3.06), (0.62, 0.12, 2.78), (0.52, 0.08, 2.48)], 0.045, mats["hair"]).parent = root
    add_curve("Hair_Ponytail_CyanLock", [(0.52, 0.08, 2.48), (0.46, 0.04, 2.30)], 0.028, mats["cyan"]).parent = root

    add_saber(root, mats)
    x, y, z = SOCKETS["Socket_Equipment_Primary"]
    for index, grip_z in enumerate((z - 0.30, z - 0.08), start=1):
        add_cube(f"Saber_Grip_GoldBand_{index}", (x, y - 0.06, grip_z), (0.07, 0.012, 0.018), mats["gold"], bevel=0.008).parent = root

    # One canonical signal ribbon: a cyan flowing path with a gold clasp.
    ribbon_points = [
        (-0.86, -0.22, 2.48),
        (-1.12, -0.18, 3.08),
        (-0.78, -0.16, 3.62),
        (0.0, -0.14, 3.80),
        (0.78, -0.16, 3.54),
        (1.04, -0.18, 2.94),
        (0.55, -0.22, 2.56),
    ]
    add_curve("SignalRibbon_Cyan_Path", ribbon_points, 0.055, mats["cyan"]).parent = root
    add_curve("SignalRibbon_Gold_Accent", ribbon_points[1:5], 0.014, mats["gold"]).parent = root
    add_cube("SignalRibbon_GoldClasp", (-0.86, -0.24, 2.48), (0.10, 0.04, 0.06), mats["gold"], bevel=0.025).parent = root
    add_cube("SignalRibbon_GoldLink_Upper", (-0.78, -0.20, 3.62), (0.045, 0.018, 0.018), mats["gold"], bevel=0.008).parent = root
    add_cube("SignalRibbon_GoldLink_Lower", (0.78, -0.20, 3.54), (0.045, 0.018, 0.018), mats["gold"], bevel=0.008).parent = root

    for socket_name, location in SOCKETS.items():
        add_socket(socket_name, location, root)

    scene = bpy.context.scene
    configure_render(scene, output_dir / "renders")
    add_area_light("Key_Light", (4.5, -6.0, 7.0), Vector((0, 0, 1.9)), 850.0, (1.0, 0.92, 0.82), 5.0)
    add_area_light("Fill_Light", (-4.0, -3.0, 4.0), Vector((0, 0, 1.8)), 500.0, (0.55, 0.75, 1.0), 4.0)
    add_area_light("Back_Light", (0.0, 4.0, 5.5), Vector((0, 0, 2.2)), 700.0, (0.15, 0.75, 0.95), 3.5)
    scene["re_camp_gate"] = "Gate B preflight only"
    scene["re_camp_source_commit"] = args.source_commit
    scene["re_camp_source_asset"] = args.source_asset
    scene["re_camp_technical_proof"] = "NOT TESTED"
    technical_stats = prepare_technical_asset(root)
    optimization_stats = optimize_lod0_budget(root) if args.optimize_budget else None
    if optimization_stats is not None:
        technical_stats["triangle_count"] = int(optimization_stats["triangle_count_after"])
    rig_stats = prepare_rig_and_motion(root)
    skinning_stats = (
        prepare_production_skinning_review(root)
        if args.production_skinning_review
        else prepare_blockout_skinning(root)
    )
    lod_stats = generate_lod_variants(root) if args.generate_lods else None
    scene["re_camp_blockout_revision"] = revision
    scene["re_camp_uv_status"] = "PASS" if technical_stats["uv_missing_after_prepare"] == 0 else "FAIL"
    scene["re_camp_lod_status"] = (
        "LOD0/LOD1/LOD2 GENERATED / REVIEW PENDING"
        if lod_stats
        else ("LOD0 OPTIMIZED / LOD1-2 PENDING" if args.optimize_budget else "LOD0 ONLY / LOD PENDING")
    )
    scene["re_camp_lod_triangle_counts"] = json.dumps(lod_stats["lod_triangle_counts"], sort_keys=True) if lod_stats else json.dumps({"LOD0": technical_stats["triangle_count"]}, sort_keys=True)
    scene["re_camp_triangle_count_before_optimization"] = int(optimization_stats["triangle_count_before"]) if optimization_stats else technical_stats["triangle_count"]
    scene["re_camp_triangle_count_after_optimization"] = int(optimization_stats["triangle_count_after"]) if optimization_stats else technical_stats["triangle_count"]
    scene["re_camp_triangle_budget_status"] = optimization_stats["triangle_budget_status"] if optimization_stats else "FAIL / SIMPLIFICATION REQUIRED"
    scene["re_camp_rig_status"] = (
        "PROTOTYPE / BLENDED PRODUCTION REVIEW WEIGHTS"
        if args.production_skinning_review
        else "PROTOTYPE / RIGID BLOCKOUT WEIGHTS"
    )
    scene["re_camp_deformation_status"] = skinning_stats["skinning_status"]
    scene["re_camp_motion_status"] = "IDLE RUN ATTACK REVIEW CLIPS"
    scene["re_camp_armature_name"] = rig_stats["armature_name"]
    scene["re_camp_bone_count"] = rig_stats["bone_count"]
    scene["re_camp_skinning_status"] = skinning_stats["skinning_status"]
    scene["re_camp_weighted_mesh_count"] = skinning_stats["weighted_mesh_object_count"]
    scene["re_camp_max_influences_per_vertex"] = skinning_stats.get("max_influences_per_vertex", 1)
    scene["re_camp_average_influences_per_vertex"] = skinning_stats.get("average_influences_per_vertex", 1.0)
    scene["re_camp_pose_review_status"] = "PENDING RENDER"

    blend_path = output_dir / f"{args.character}_Blockout_REVIEW_{revision}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    return root, blend_path


def add_torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
    rotation: tuple[float, float, float] = (0, 0, 0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=24,
        minor_segments=8,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    return smooth_mesh(apply_material(obj, mat))


def render_views(output_dir: Path) -> None:
    scene = bpy.context.scene
    target = Vector((0, 0, 1.85))
    views = {
        "front": (0, -11.4, 2.15),
        "side": (11.4, 0, 2.15),
        "back": (0, 11.4, 2.15),
    }
    for view, location in views.items():
        camera = add_camera(f"RenderCamera_{view}", location, target)
        scene.camera = camera
        scene.render.filepath = str(output_dir / "renders" / f"{view}.png")
        bpy.ops.render.render(write_still=True)


def render_pose_previews(output_dir: Path) -> None:
    """Render visible deformation checks for the generated review actions."""
    scene = bpy.context.scene
    armature = bpy.data.objects.get("CH101_Rig_Armature")
    if armature is None:
        raise RuntimeError("CH101_Rig_Armature is required for pose previews")
    target = Vector((0, 0, 1.85))
    camera = add_camera("RenderCamera_pose_review", (0, -11.4, 2.15), target)
    scene.camera = camera
    pose_frames = {
        "CH101_A_Pose_Check": 1,
        "CH101_Idle": 24,
        "CH101_Run": 12,
        "CH101_Attack": 16,
    }
    pose_dir = output_dir / "renders" / "poses"
    pose_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []
    for action_name, frame in pose_frames.items():
        action = bpy.data.actions.get(action_name)
        if action is None:
            continue
        armature.animation_data.action = action
        scene.frame_set(frame)
        scene.render.filepath = str(pose_dir / f"{action_name}.png")
        bpy.ops.render.render(write_still=True)
        rendered.append(action_name)
    idle = bpy.data.actions.get("CH101_Idle")
    if idle is not None:
        armature.animation_data.action = idle
    scene.frame_set(1)
    scene["re_camp_pose_review_status"] = "PASS" if len(rendered) == len(pose_frames) else "PARTIAL"
    scene["re_camp_pose_review_names"] = ",".join(rendered)


def export_fbx(output_dir: Path, character: str, revision: str) -> Path:
    fbx_path = output_dir / f"{character}_Blockout_REVIEW_{revision}.fbx"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=False,
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
        use_armature_deform_only=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
    )
    return fbx_path


def write_report(output_dir: Path, args: argparse.Namespace, blend_path: Path, fbx_path: Path | None) -> None:
    objects = list(bpy.data.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    report = {
        "character": args.character,
        "revision": bpy.context.scene.get("re_camp_blockout_revision", "v007"),
        "source_asset": args.source_asset,
        "source_commit": args.source_commit,
        "status": "DOCUMENTATION ONLY / NOT GATE B APPROVED",
        "technical_proof": "NOT TESTED",
        "blend": str(blend_path),
        "fbx": str(fbx_path) if fbx_path else None,
        "mesh_object_count": len(meshes),
        "object_count": len(objects),
        "triangle_count": sum(len(obj.data.loop_triangles) for obj in meshes),
        "triangle_count_total_all_lods": sum(len(obj.data.loop_triangles) for obj in meshes),
        "triangle_count_before_optimization": bpy.context.scene.get("re_camp_triangle_count_before_optimization", 0),
        "triangle_count_after_optimization": bpy.context.scene.get("re_camp_triangle_count_after_optimization", 0),
        "triangle_budget": {
            "body": BODY_TRIANGLE_BUDGET,
            "equipment": EQUIPMENT_TRIANGLE_BUDGET,
            "combined_review_limit": COMBINED_TRIANGLE_BUDGET,
        },
        "triangle_budget_status": bpy.context.scene.get("re_camp_triangle_budget_status", (
            "PASS"
            if sum(len(obj.data.loop_triangles) for obj in meshes) <= COMBINED_TRIANGLE_BUDGET
            else "FAIL / SIMPLIFICATION REQUIRED"
        )),
        "lod_triangle_counts": json.loads(bpy.context.scene.get("re_camp_lod_triangle_counts", "{}")),
        "lod_mesh_counts": {
            level: sum(1 for obj in meshes if obj.get("lod_level", "LOD0") == level)
            for level in ("LOD0", "LOD1", "LOD2")
        },
        "uv_missing": sorted(obj.name for obj in meshes if not obj.data.uv_layers),
        "materialless_meshes": sorted(obj.name for obj in meshes if not obj.data.materials),
        "lod_status": bpy.context.scene.get("re_camp_lod_status", "LOD0 ONLY / LOD PENDING"),
        "armature_name": bpy.context.scene.get("re_camp_armature_name", ""),
        "bone_count": bpy.context.scene.get("re_camp_bone_count", 0),
        "rig_status": bpy.context.scene.get("re_camp_rig_status", "NOT SET"),
        "deformation_status": bpy.context.scene.get("re_camp_deformation_status", "NOT SET"),
        "skinning_status": bpy.context.scene.get("re_camp_skinning_status", "NOT SET"),
        "weighted_mesh_object_count": bpy.context.scene.get("re_camp_weighted_mesh_count", 0),
        "max_influences_per_vertex": bpy.context.scene.get("re_camp_max_influences_per_vertex", 0),
        "average_influences_per_vertex": bpy.context.scene.get("re_camp_average_influences_per_vertex", 0.0),
        "pose_review_status": bpy.context.scene.get("re_camp_pose_review_status", "NOT RENDERED"),
        "pose_review_names": sorted(name for name in bpy.context.scene.get("re_camp_pose_review_names", "").split(",") if name),
        "motion_status": bpy.context.scene.get("re_camp_motion_status", "NOT SET"),
        "motion_clips": sorted(action.name for action in bpy.data.actions if action.name.startswith("CH101_")),
        "socket_bone_map": SOCKET_BONE_MAP,
        "socket_names": sorted(name for name in SOCKETS if bpy.data.objects.get(name)),
        "material_names": sorted(mat.name for mat in bpy.data.materials if mat.name.startswith("MAT_CH101_")),
        "material_slot_count": len([mat for mat in bpy.data.materials if mat.name.startswith("MAT_CH101_")]),
        "material_budget": {"combined_review_limit": 6},
        "material_budget_status": (
            "PASS"
            if len([mat for mat in bpy.data.materials if mat.name.startswith("MAT_CH101_")]) <= 6
            else "FAIL / MATERIAL CONSOLIDATION REQUIRED"
        ),
        "art_features": [
            "cropped white-black sport jacket",
            "black shorts and thigh straps",
            "high ponytail with cyan tip",
            "white graphite cyan boots",
            "single gold graphite cyan saber",
            "cyan signal ribbon with gold accent",
            "saber sheath and blade stripes",
            "jacket back panel and cyan piping",
            "review lighting rig",
            "face and brow readability cues",
            "jacket pockets and shorts belt",
            "strap buckles and saber grip bands",
            "extended ponytail locks and ribbon links",
            "applied transforms and bevel modifiers",
            "mesh conversion for procedural curves",
            "UV maps and technical material slots",
            "humanoid-aligned armature prototype",
            "idle run attack and A-pose review actions",
            "socket-to-bone parenting metadata",
            "blended production-review weights and armature modifiers",
            "A-pose idle run attack deformation previews",
        ],
        "render_views": ["front", "side", "back"] if args.render else [],
    }
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    revision = bpy.context.scene.get("re_camp_blockout_revision", "v007")
    (output_dir / "reports" / f"{args.character}_Blockout_REVIEW_{revision}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    root, blend_path = build_scene(args)
    del root
    if args.render:
        render_views(output_dir)
        render_pose_previews(output_dir)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    revision = bpy.context.scene.get("re_camp_blockout_revision", "v007")
    fbx_path = export_fbx(output_dir, args.character, revision) if args.export_fbx else None
    write_report(output_dir, args, blend_path, fbx_path)
    print(f"Blockout generated: {blend_path}")
    print(f"Revision: {revision} / skinned deformation review")
    print("Status: documentation-only / Gate B not approved / technical proof not tested")


if __name__ == "__main__":
    main()
