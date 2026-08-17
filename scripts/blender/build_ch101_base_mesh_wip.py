#!/usr/bin/env python3
"""Build a smooth CH101 common-base A/B visual modelling WIP.

The scene is a modelling reference, not a final rigged asset. It intentionally
uses continuous ring meshes for the body and restrained rounded garment parts so
the result can be judged as a character model rather than a primitive blockout.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for group in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(group):
            if item.users == 0:
                group.remove(item)


def mat(name: str, rgba: tuple[float, float, float, float], roughness: float, metallic: float = 0.0, emission: bool = False) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = rgba
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = metallic
        if emission and "Emission Color" in shader.inputs:
            shader.inputs["Emission Color"].default_value = rgba
            shader.inputs["Emission Strength"].default_value = 2.0
    return material


def set_parent(obj: bpy.types.Object, root: bpy.types.Object, material: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.append(material)
    obj.parent = root
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def add_subdivision(obj: bpy.types.Object, levels: int = 1) -> None:
    modifier = obj.modifiers.new(name="VisualSubdivision", type="SUBSURF")
    modifier.levels = levels
    modifier.render_levels = levels


def ring_mesh(name: str, offset_x: float, rings: list[tuple[float, float, float]], material: bpy.types.Material, root: bpy.types.Object, segments: int = 32) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    for z, radius_x, radius_y in rings:
        for index in range(segments):
            angle = (math.tau * index) / segments
            vertices.append((offset_x + radius_x * math.cos(angle), radius_y * math.sin(angle), z))
    faces: list[tuple[int, ...]] = []
    for row in range(len(rings) - 1):
        start = row * segments
        next_start = (row + 1) * segments
        for index in range(segments):
            nxt = (index + 1) % segments
            faces.append((start + index, start + nxt, next_start + nxt, next_start + index))
    faces.append(tuple(range(segments - 1, -1, -1)))
    faces.append(tuple((len(rings) - 1) * segments + index for index in range(segments)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    add_subdivision(obj, 1)
    return obj


def sphere(name: str, loc: tuple[float, float, float], scale: tuple[float, float, float], material: bpy.types.Material, root: bpy.types.Object, segments: int = 48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=32, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    set_parent(obj, root, material)
    add_subdivision(obj, 1)
    return obj


def rounded_cube(name: str, loc: tuple[float, float, float], scale: tuple[float, float, float], material: bpy.types.Material, root: bpy.types.Object, bevel: float = 0.05) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel_modifier = obj.modifiers.new(name="RoundedPanel", type="BEVEL")
    bevel_modifier.width = bevel
    bevel_modifier.segments = 6
    bevel_modifier.limit_method = "ANGLE"
    set_parent(obj, root, material)
    return obj


def panel(name: str, loc: tuple[float, float, float], top_width: float, bottom_width: float, height: float, depth: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    """Create a tapered clothing panel with real front/back surfaces.

    Using a shallow tapered mesh keeps the jacket readable as fabric instead
    of a rectangular toy block while still being cheap enough for a WIP.
    """
    cx, cy, cz = loc
    half_top = top_width * 0.5
    half_bottom = bottom_width * 0.5
    half_h = height * 0.5
    front_y = cy - depth * 0.5
    back_y = cy + depth * 0.5
    outline = [(-half_top, half_h), (half_top, half_h), (half_bottom, -half_h), (-half_bottom, -half_h)]
    vertices = [(cx + dx, front_y, cz + dz) for dx, dz in outline] + [(cx + dx, back_y, cz + dz) for dx, dz in outline]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    bevel = obj.modifiers.new(name="SoftFabricEdge", type="BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    return obj


def capsule(name: str, a: tuple[float, float, float], b: tuple[float, float, float], radius: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    start = Vector(a)
    end = Vector(b)
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=direction.length, location=(start + end) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    bevel_modifier = obj.modifiers.new(name="SoftJoint", type="BEVEL")
    bevel_modifier.width = radius * 0.30
    bevel_modifier.segments = 6
    set_parent(obj, root, material)
    return obj


def curve(name: str, points: list[tuple[float, float, float]], radius: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 16
    data.bevel_depth = radius
    data.bevel_resolution = 5
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coord in zip(spline.bezier_points, points):
        point.co = coord
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return set_parent(obj, root, material)


def face(x: float, root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    # Tapered anime head instead of a single spherical primitive.  The lower
    # rings pull into a small chin while the upper rings keep the mature
    # stylized face plane readable at a gameplay camera distance.
    ring_mesh(
        "Face",
        x,
        [
            (2.63, 0.10, 0.095),
            (2.70, 0.23, 0.20),
            (2.86, 0.31, 0.265),
            (3.08, 0.34, 0.285),
            (3.25, 0.28, 0.235),
            (3.34, 0.15, 0.14),
        ],
        m["skin"],
        root,
        segments=40,
    )
    for side in (-1, 1):
        sphere("EyeWhite", (x + side * 0.12, -0.268, 3.02), (0.082, 0.022, 0.064), m["eye"], root, segments=36)
        sphere("Iris", (x + side * 0.12, -0.291, 3.015), (0.043, 0.012, 0.050), m["iris"], root, segments=36)
        sphere("Pupil", (x + side * 0.12, -0.302, 3.015), (0.019, 0.008, 0.032), m["pupil"], root, segments=24)
        sphere("EyeHighlight", (x + side * 0.105, -0.311, 3.043), (0.009, 0.005, 0.012), m["eye_highlight"], root, segments=20)
        capsule("Brow", (x + side * 0.19, -0.284, 3.135), (x + side * 0.055, -0.292, 3.15), 0.010, m["hair"], root)
    sphere("Nose", (x, -0.302, 2.91), (0.020, 0.018, 0.032), m["skin_shadow"], root, segments=24)
    curve("Mouth", [(x - 0.045, -0.300, 2.845), (x, -0.308, 2.835), (x + 0.045, -0.300, 2.845)], 0.006, m["lip"], root)


def hair(x: float, root: bpy.types.Object, m: dict[str, bpy.types.Material], hood: bool) -> None:
    sphere("HairCap", (x, 0.045, 3.18), (0.36, 0.31, 0.30), m["hair"], root)
    for index, dx in enumerate((-0.24, -0.15, -0.05, 0.06, 0.16, 0.25), start=1):
        curve(
            f"Bang_{index}",
            [(x + dx * 0.68, -0.245, 3.27), (x + dx, -0.304, 3.10), (x + dx * 0.82, -0.20, 2.86)],
            0.036,
            m["hair"],
            root,
        )
    curve("SideLockL", [(x - 0.28, -0.10, 3.18), (x - 0.40, -0.03, 2.85), (x - 0.33, 0.02, 2.52)], 0.070, m["hair"], root)
    curve("SideLockR", [(x + 0.28, -0.10, 3.18), (x + 0.40, -0.03, 2.85), (x + 0.33, 0.02, 2.52)], 0.070, m["hair"], root)
    curve("Ponytail", [(x + 0.25, 0.10, 3.22), (x + 0.50, 0.16, 3.05), (x + 0.51, 0.12, 2.76), (x + 0.40, 0.04, 2.48)], 0.085, m["hair"], root)
    curve("PonytailCyan", [(x + 0.44, 0.10, 2.93), (x + 0.52, 0.05, 2.67), (x + 0.42, 0.01, 2.46)], 0.027, m["cyan"], root)
    if hood:
        rounded_cube("CourierHood", (x, 0.15, 2.57), (0.30, 0.10, 0.14), m["graphite"], root, 0.08)


def equipment(x: float, root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    capsule("SaberGrip", (x + 0.68, -0.24, 1.54), (x + 0.68, -0.24, 1.84), 0.040, m["graphite"], root)
    rounded_cube("SaberGuard", (x + 0.68, -0.24, 1.88), (0.13, 0.025, 0.022), m["gold"], root, 0.015)
    rounded_cube("SaberBlade", (x + 0.68, -0.24, 2.22), (0.028, 0.014, 0.32), m["cyan"], root, 0.014)
    curve("SignalRibbon", [(x - 0.40, -0.18, 2.38), (x - 0.72, -0.08, 2.84), (x - 0.48, 0.0, 3.26), (x + 0.18, 0.0, 3.40), (x + 0.72, -0.12, 2.77), (x + 0.45, -0.17, 2.32)], 0.040, m["cyan"], root)
    curve("RibbonAccent", [(x - 0.40, -0.20, 2.38), (x - 0.48, -0.01, 3.26), (x + 0.18, -0.01, 3.40)], 0.010, m["gold"], root)


def character(x: float, variant: str, m: dict[str, bpy.types.Material]) -> bpy.types.Object:
    root = bpy.data.objects.new(f"CH101_{variant}_CommonBase_WIP_Root", None)
    root["character_id"] = "CH101"
    root["variant"] = variant
    root["status"] = "WIP / NOT APPROVED"
    root["target_heads"] = "5.3-5.4"
    bpy.context.collection.objects.link(root)
    # Continuous base body with a readable bust/waist/hip rhythm.  Clothing
    # sits over this surface; it is intentionally not a set of cubes.
    ring_mesh("BodyBase", x, [(1.30, 0.34, 0.22), (1.45, 0.38, 0.24), (1.70, 0.29, 0.19), (1.98, 0.285, 0.19), (2.20, 0.33, 0.20), (2.37, 0.17, 0.14)], m["skin"], root)
    ring_mesh("LegBaseL", x - 0.18, [(1.25, 0.125, 0.12), (1.05, 0.115, 0.105), (0.68, 0.092, 0.085), (0.35, 0.078, 0.075)], m["skin"], root, segments=24)
    ring_mesh("LegBaseR", x + 0.18, [(1.25, 0.125, 0.12), (1.05, 0.115, 0.105), (0.68, 0.092, 0.085), (0.35, 0.078, 0.075)], m["skin"], root, segments=24)
    capsule("Neck", (x, 0.0, 2.28), (x, 0.0, 2.58), 0.105, m["skin"], root)
    ring_mesh("ShortsWaist", x, [(1.28, 0.35, 0.23), (1.40, 0.36, 0.23), (1.53, 0.31, 0.20)], m["graphite"], root, segments=36)
    for side in (-1, 1):
        ring_mesh("ShortsLeg", x + side * 0.18, [(1.18, 0.14, 0.17), (1.30, 0.16, 0.18), (1.42, 0.14, 0.17)], m["graphite"], root, segments=24)
        rounded_cube("ThighStrap", (x + side * 0.19, -0.19, 1.03), (0.105, 0.022, 0.027), m["gold"], root, 0.012)
        capsule("ArmUpper", (x + side * 0.30, 0.0, 2.24), (x + side * 0.54, -0.01, 1.96), 0.095, m["graphite"], root)
        capsule("ArmLower", (x + side * 0.54, -0.01, 1.96), (x + side * 0.66, -0.05, 1.70), 0.078, m["graphite"], root)
        rounded_cube("Cuff", (x + side * 0.66, -0.05, 1.68), (0.085, 0.095, 0.06), m["white"], root, 0.025)
        sphere("Hand", (x + side * 0.66, -0.07, 1.57), (0.065, 0.06, 0.085), m["skin"], root, segments=32)
        capsule("BootUpper", (x + side * 0.18, -0.08, 0.15), (x + side * 0.18, -0.08, 0.40), 0.13, m["graphite"], root)
        sphere("BootToe", (x + side * 0.18, -0.24, 0.12), (0.16, 0.25, 0.11), m["white"], root, segments=36)
        rounded_cube("BootSole", (x + side * 0.18, -0.22, 0.045), (0.18, 0.27, 0.032), m["cyan"], root, 0.028)
    sphere("BustL", (x - 0.135, -0.165, 2.12), (0.16, 0.125, 0.16), m["skin"], root)
    sphere("BustR", (x + 0.135, -0.165, 2.12), (0.16, 0.125, 0.16), m["skin"], root)
    ring_mesh("CropTop", x, [(1.92, 0.25, 0.16), (2.10, 0.31, 0.18), (2.27, 0.28, 0.17)], m["graphite"], root, segments=36)
    panel("JacketPanelL", (x - 0.23, -0.235, 2.16), 0.13, 0.20, 0.58, 0.075, m["white"], root)
    panel("JacketPanelR", (x + 0.23, -0.235, 2.16), 0.13, 0.20, 0.58, 0.075, m["white"], root)
    rounded_cube("JacketHem", (x, -0.22, 1.91), (0.28, 0.032, 0.025), m["cyan"], root, 0.012)
    if variant == "B":
        rounded_cube("CourierCollar", (x, 0.03, 2.40), (0.25, 0.11, 0.09), m["white"], root, 0.05)
        rounded_cube("CourierPouchL", (x - 0.31, -0.22, 1.94), (0.075, 0.05, 0.12), m["graphite"], root, 0.03)
        rounded_cube("CourierPouchR", (x + 0.31, -0.22, 1.94), (0.075, 0.05, 0.12), m["graphite"], root, 0.03)
    else:
        rounded_cube("SprintShoulderL", (x - 0.31, 0.0, 2.34), (0.12, 0.12, 0.075), m["white"], root, 0.035)
        rounded_cube("SprintShoulderR", (x + 0.31, 0.0, 2.34), (0.12, 0.12, 0.075), m["white"], root, 0.035)
    face(x, root, m)
    hair(x, root, m, hood=variant == "B")
    equipment(x, root, m)
    # The source proportion target is 5.3–5.4 heads.  The guide meshes are
    # authored in a compact local scale, so stretch the connected character
    # vertically rather than enlarging the head and creating a chibi read.
    root.scale.z = 1.15
    root["proportion_review"] = "vertical scale 1.15 / target 5.3-5.4 heads"
    return root


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def scene_setup(out: Path, m: dict[str, bpy.types.Material]) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.02, 0.025, 0.04)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.5, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("ReviewFloor", (0.025, 0.035, 0.055, 1.0), 0.60))
    bpy.ops.object.camera_add(location=(0, -12.2, 2.28))
    camera = bpy.context.object
    camera.data.lens = 58
    look_at(camera, Vector((0, 0, 1.95)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_CommonBase_AB_WIP_front.png")
    for name, loc, energy, color in (("Key", (-4.5, -6, 6), 1050, (1.0, 0.82, 0.72)), ("Fill", (4, -3, 4), 700, (0.50, 0.70, 1.0)), ("Rim", (0, 3.5, 5), 900, (0.12, 0.64, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.7)))


def main() -> None:
    options = args()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    clear()
    materials = {
        "skin": mat("MAT_HF2_Skin", (0.86, 0.58, 0.54, 1), 0.58),
        "skin_shadow": mat("MAT_HF2_SkinShadow", (0.68, 0.34, 0.34, 1), 0.72),
        "eye": mat("MAT_HF2_EyeWhite", (0.95, 0.98, 1.0, 1), 0.25),
        "iris": mat("MAT_HF2_Iris", (0.04, 0.38, 0.62, 1), 0.20, metallic=0.05),
        "pupil": mat("MAT_HF2_Pupil", (0.004, 0.008, 0.016, 1), 0.12),
        "eye_highlight": mat("MAT_HF2_EyeHighlight", (1.0, 1.0, 1.0, 1), 0.08, emission=True),
        "lip": mat("MAT_HF2_Lip", (0.45, 0.07, 0.10, 1), 0.32),
        "hair": mat("MAT_HF2_Hair", (0.012, 0.018, 0.030, 1), 0.25),
        "white": mat("MAT_HF2_Cream", (0.88, 0.87, 0.81, 1), 0.46),
        "graphite": mat("MAT_HF2_Graphite", (0.022, 0.030, 0.048, 1), 0.38),
        "gold": mat("MAT_HF2_Gold", (0.78, 0.38, 0.065, 1), 0.25, metallic=0.72),
        "cyan": mat("MAT_HF2_Cyan", (0.01, 0.42, 0.62, 1), 0.28, metallic=0.12, emission=True),
    }
    character(-1.15, "A", materials)
    character(1.15, "B", materials)
    scene_setup(out, materials)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / COMMON BASE MESH REVIEW / NOT APPROVED"
    scene["re_camp_character"] = "CH101"
    scene["re_camp_variants"] = "A Route Sprint / B Signal Courier"
    scene["re_camp_target_heads"] = "5.3-5.4"
    scene["re_camp_source_commit"] = "183b0f0983969937d779f70b2ac51e53fc976203"
    blend = out / "CH101_CommonBase_AB_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "character": "CH101",
        "variants": ["A Route Sprint", "B Signal Courier"],
        "status": "WIP / COMMON BASE MESH REVIEW / NOT APPROVED",
        "blend": str(blend),
        "target_heads": "5.3-5.4",
        "body_strategy": "continuous ring meshes with subdivision review surface",
        "shared_identity": ["face", "hair family", "body proportions", "saber", "signal ribbon"],
        "review_notes": ["Visual WIP only", "No rig, animation, UV, LOD or Unity proof", "User Gate A approval required"],
    }
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "reports" / "CH101_CommonBase_AB_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / common base mesh review / not approved")


if __name__ == "__main__":
    main()
