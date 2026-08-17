#!/usr/bin/env python3
"""Build a CH101 face/upper-body review WIP from the real MPFB body.

This pass deliberately limits scope to the face, hair, and chest silhouette.
It avoids the rejected full-body primitive outfit experiments so a reviewer can
judge the character anchor before any lower-body or equipment work begins.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_ch101_base_mesh_wip import clear, curve, mat, set_parent  # noqa: E402
from build_ch101_mpfb_base_wip import look_at, normalize_body  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def almond(name: str, center_x: float, center_z: float, width: float, height: float, y: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    vertices = [
        (center_x - width, y, center_z),
        (center_x - width * 0.55, y, center_z + height * 0.72),
        (center_x, y, center_z + height),
        (center_x + width * 0.55, y, center_z + height * 0.72),
        (center_x + width, y, center_z),
        (center_x + width * 0.55, y, center_z - height * 0.72),
        (center_x, y, center_z - height),
        (center_x - width * 0.55, y, center_z - height * 0.72),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], [tuple(range(8))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return set_parent(obj, root, material)


def surface_patch(name: str, body: bpy.types.Object, z_min: float, z_max: float, x_min: float, x_max: float, y_max: float, material: bpy.types.Material, root: bpy.types.Object, offset: float = 0.018) -> bpy.types.Object:
    """Copy only front-facing body polygons into a thin garment surface."""
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    index_map: dict[int, int] = {}
    for polygon in body.data.polygons:
        coords = [body.matrix_world @ body.data.vertices[index].co for index in polygon.vertices]
        if not coords:
            continue
        centroid = sum(coords, Vector()) / len(coords)
        if not (z_min <= centroid.z <= z_max and x_min <= centroid.x <= x_max and centroid.y <= y_max):
            continue
        face_indices = []
        for source_index, point in zip(polygon.vertices, coords):
            if source_index not in index_map:
                index_map[source_index] = len(vertices)
                vertices.append((point.x, point.y - offset, point.z))
            face_indices.append(index_map[source_index])
        faces.append(tuple(face_indices))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    solidify = obj.modifiers.new(name="GarmentThickness", type="SOLIDIFY")
    solidify.thickness = 0.018
    solidify.offset = 0.0
    bevel = obj.modifiers.new(name="GarmentEdge", type="BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    return obj


def hair_dome(root: bpy.types.Object, material: bpy.types.Material) -> bpy.types.Object:
    rings = [(3.15, 0.23, 0.20), (3.30, 0.39, 0.29), (3.52, 0.46, 0.31), (3.70, 0.38, 0.25), (3.78, 0.18, 0.13)]
    segments = 48
    vertices: list[tuple[float, float, float]] = []
    for z, rx, ry in rings:
        for index in range(segments):
            angle = math.tau * index / segments
            vertices.append((rx * math.cos(angle), 0.025 + ry * math.sin(angle), z))
    faces: list[tuple[int, ...]] = []
    for row in range(len(rings) - 1):
        start = row * segments
        next_start = (row + 1) * segments
        for index in range(segments):
            nxt = (index + 1) % segments
            faces.append((start + index, start + nxt, next_start + nxt, next_start + index))
    mesh = bpy.data.meshes.new("CH101_HairDomeMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("CH101_HairDome", mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    bevel = obj.modifiers.new(name="HairEdge", type="BEVEL")
    bevel.width = 0.012
    bevel.segments = 2
    return obj


def scene_setup(out: Path) -> None:
    scene = bpy.context.scene
    engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.008, 0.012, 0.025)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0.5, 1.45))
    backdrop = bpy.context.object
    backdrop.rotation_euler.x = math.radians(90.0)
    backdrop.data.materials.append(mat("CH101BustBackdrop", (0.012, 0.022, 0.045, 1.0), 0.6))
    bpy.ops.object.camera_add(location=(0.42, -5.25, 2.75))
    camera = bpy.context.object
    camera.data.lens = 68
    look_at(camera, Vector((0.0, -0.03, 2.78)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_FaceBust_WIP_3q.png")
    for location, energy, color in (((-3.5, -4.5, 5.5), 900, (1.0, 0.78, 0.68)), ((3.2, -2.5, 4.0), 560, (0.36, 0.58, 1.0)), ((0.0, 2.5, 4.5), 700, (0.08, 0.48, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 3.0
        look_at(light, Vector((0.0, 0.0, 2.6)))


def main() -> None:
    options = parse_args()
    base_obj = Path(options.base_obj).resolve()
    out = Path(options.output_dir).resolve()
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    clear()
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(base_obj), use_split_groups=True, import_vertex_groups=True, validate_meshes=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    body = next((obj for obj in imported if obj.name == "body"), None)
    if body is None:
        raise RuntimeError("MPFB base.obj import did not expose the body group")
    normalize_body(body, target_height=3.65)
    body.name = "CH101_A_MPFBody_CC0_WIP"
    root = bpy.data.objects.new("CH101_A_FaceBust_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    body.parent = root
    materials = {
        "skin": mat("MAT_CH101_BustSkin", (0.78, 0.42, 0.39, 1), 0.48),
        "skin_shadow": mat("MAT_CH101_BustSkinShadow", (0.55, 0.19, 0.22, 1), 0.58),
        "eye": mat("MAT_CH101_BustEyeWhite", (0.98, 0.98, 1.0, 1), 0.2),
        "iris": mat("MAT_CH101_BustIris", (0.02, 0.36, 0.62, 1), 0.18, metallic=0.05),
        "pupil": mat("MAT_CH101_BustPupil", (0.002, 0.004, 0.012, 1), 0.12),
        "highlight": mat("MAT_CH101_BustHighlight", (1.0, 1.0, 1.0, 1), 0.08, emission=True),
        "hair": mat("MAT_CH101_BustHair", (0.006, 0.010, 0.022, 1), 0.24),
        "hair_cyan": mat("MAT_CH101_BustHairCyan", (0.01, 0.38, 0.58, 1), 0.2, emission=True),
        "graphite": mat("MAT_CH101_BustGraphite", (0.014, 0.022, 0.044, 1), 0.38),
        "white": mat("MAT_CH101_BustWhite", (0.86, 0.87, 0.86, 1), 0.40),
        "gold": mat("MAT_CH101_BustGold", (0.76, 0.34, 0.06, 1), 0.25, metallic=0.68),
    }
    body.data.materials.append(materials["skin"])
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    for obj in imported:
        if obj != body:
            obj.hide_render = True
            obj.hide_viewport = True
    # Small, controlled face-shape delta: slightly wider adult anime cranium,
    # without replacing the real MPFB facial planes with a primitive mask.
    for vertex in body.data.vertices:
        world = body.matrix_world @ vertex.co
        if world.z > 2.96:
            vertex.co.x *= 1.07
            vertex.co.y *= 0.97
            vertex.co.z = (vertex.co.z - 1.56) * 1.04 + 1.56
    for side in (-1, 1):
        almond("CH101_BustEyeWhiteL" if side < 0 else "CH101_BustEyeWhiteR", side * 0.115, 3.22, 0.12, 0.085, -0.382, materials["eye"], root)
        almond("CH101_BustIrisL" if side < 0 else "CH101_BustIrisR", side * 0.115, 3.215, 0.056, 0.058, -0.397, materials["iris"], root)
        almond("CH101_BustPupilL" if side < 0 else "CH101_BustPupilR", side * 0.115, 3.212, 0.024, 0.036, -0.404, materials["pupil"], root)
        curve("CH101_BustBrowL" if side < 0 else "CH101_BustBrowR", [(side * 0.21, -0.385, 3.34), (side * 0.035, -0.398, 3.355)], 0.008, materials["hair"], root)
    almond("CH101_BustEyeHighlightL", -0.095, 3.25, 0.012, 0.014, -0.414, materials["highlight"], root)
    almond("CH101_BustEyeHighlightR", 0.095, 3.25, 0.012, 0.014, -0.414, materials["highlight"], root)
    hair_dome(root, materials["hair"])
    for index, dx in enumerate((-0.28, -0.18, -0.08, 0.08, 0.18, 0.28), start=1):
        curve(f"CH101_BustBang_{index}", [(dx * 0.7, -0.27, 3.57), (dx, -0.405, 3.36), (dx * 0.82, -0.33, 3.03)], 0.012, materials["hair"], root)
    curve("CH101_BustSideLockL", [(-0.36, -0.12, 3.47), (-0.46, -0.02, 3.14), (-0.37, 0.03, 2.78)], 0.026, materials["hair"], root)
    curve("CH101_BustSideLockR", [(0.36, -0.12, 3.47), (0.46, -0.02, 3.14), (0.37, 0.03, 2.78)], 0.026, materials["hair"], root)
    curve("CH101_BustCyanStreakL", [(-0.34, -0.14, 3.44), (-0.43, -0.04, 3.12), (-0.35, 0.01, 2.86)], 0.010, materials["hair_cyan"], root)
    curve("CH101_BustCyanStreakR", [(0.34, -0.14, 3.44), (0.43, -0.04, 3.12), (0.35, 0.01, 2.86)], 0.010, materials["hair_cyan"], root)
    # Body-surface garment patches: these are copied from the MPFB surface,
    # so they cannot float like the rejected blockout panels.
    surface_patch("CH101_BustInnerTop", body, 1.78, 2.18, -0.42, 0.42, -0.16, materials["graphite"], root)
    surface_patch("CH101_BustJacketFrontL", body, 2.02, 2.53, -0.58, -0.02, -0.12, materials["white"], root)
    surface_patch("CH101_BustJacketFrontR", body, 2.02, 2.53, 0.02, 0.58, -0.12, materials["white"], root)
    curve("CH101_BustJacketTrimL", [(-0.045, -0.34, 2.52), (-0.10, -0.40, 2.25), (-0.15, -0.34, 2.02)], 0.010, materials["hair_cyan"], root)
    curve("CH101_BustJacketTrimR", [(0.045, -0.34, 2.52), (0.10, -0.40, 2.25), (0.15, -0.34, 2.02)], 0.010, materials["hair_cyan"], root)
    root["status"] = "WIP / FACE-BUST STYLE ANCHOR / NOT APPROVED"
    root["source_license"] = "CC0 1.0 Universal (MPFB base asset)"
    root["target_heads"] = "5.3-5.4"
    root["next"] = "human review before lower-body and equipment styling"
    scene_setup(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / FACE-BUST STYLE ANCHOR / NOT APPROVED"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    blend = out / "CH101_A_FaceBust_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {"status": "WIP / FACE-BUST STYLE ANCHOR / NOT APPROVED", "blend": str(blend), "source_obj": str(base_obj), "source_license": "CC0 1.0 Universal", "body_vertices": len(body.data.vertices), "style_layers": ["controlled head delta", "layered anime eyes", "hair dome and locks", "body-surface chest patches"], "gate_a": "PENDING", "gate_b": "BLOCKED", "notes": ["Human visual review required before expanding scope", "This is not a final game asset"]}
    (out / "reports" / "CH101_A_FaceBust_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / face-bust style anchor / not approved")


if __name__ == "__main__":
    main()
