#!/usr/bin/env python3
"""Style the CC0 MPFB body into a CH101-A visual WIP."""

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

from build_ch101_base_mesh_wip import (  # noqa: E402
    capsule,
    clear,
    curve,
    face,
    hair,
    mat,
    panel,
    ring_mesh,
    rounded_cube,
    set_parent,
    sphere,
)
from build_ch101_mpfb_base_wip import look_at, normalize_body  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-obj", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    return parser.parse_args(raw)


def collection(name: str) -> bpy.types.Collection:
    value = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(value)
    return value


def shift_new_objects(before: set[bpy.types.Object], dz: float) -> None:
    for obj in bpy.data.objects:
        if obj not in before:
            obj.location.z += dz


def body_shell(name: str, body: bpy.types.Object, z_min: float, z_max: float, x_min: float, x_max: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    index_map: dict[int, int] = {}
    for polygon in body.data.polygons:
        coords = [body.matrix_world @ body.data.vertices[index].co for index in polygon.vertices]
        if not coords:
            continue
        centroid = sum(coords, Vector()) / len(coords)
        if not (z_min <= centroid.z <= z_max and x_min <= centroid.x <= x_max):
            continue
        face_indices = []
        for source_index, point in zip(polygon.vertices, coords):
            if source_index not in index_map:
                index_map[source_index] = len(vertices)
                vertices.append((point.x, point.y, point.z))
            face_indices.append(index_map[source_index])
        faces.append(tuple(face_indices))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, root, material)
    solidify = obj.modifiers.new(name="GarmentThickness", type="SOLIDIFY")
    solidify.thickness = 0.025
    solidify.offset = 0.0
    bevel = obj.modifiers.new(name="GarmentEdge", type="BEVEL")
    bevel.width = 0.012
    bevel.segments = 2
    return obj


def add_outfit(root: bpy.types.Object, body: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    # The MPFB body is the continuous surface.  Earlier attempts selected
    # arbitrary source polygons for clothing.  That produced detached shards
    # because the base topology is not laid out as garment panels.  This pass
    # uses low-profile lofted shells that follow the measured torso/hip
    # envelope, keeping the real body underneath while reading as clothing.
    ring_mesh(
        "CH101_CropTopShell",
        0.0,
        [(1.70, 0.32, 0.255), (1.78, 0.39, 0.295), (2.04, 0.43, 0.305), (2.22, 0.46, 0.285)],
        m["graphite"],
        root,
        segments=40,
    )
    # High-waisted shorts are split into two legs so the inner-thigh gap and
    # the user's preferred leg exposure remain visible in the silhouette.
    for side in (-1, 1):
        ring_mesh(
            "CH101_ShortsShellL" if side < 0 else "CH101_ShortsShellR",
            side * 0.215,
            [(0.92, 0.205, 0.235), (1.12, 0.235, 0.255), (1.49, 0.245, 0.270), (1.59, 0.225, 0.255)],
            m["graphite"],
            root,
            segments=32,
        )
        # A slim cuff and thigh strap give the lower silhouette a designed
        # edge without the old detached rectangular blocks.
        ring_mesh(
            "CH101_ThighCuffL" if side < 0 else "CH101_ThighCuffR",
            side * 0.215,
            [(1.02, 0.235, 0.255), (1.07, 0.245, 0.265)],
            m["cyan"],
            root,
            segments=32,
        )
    # One continuous torso shell gives the jacket a believable cloth volume;
    # the zip/trim lines below preserve the open-front reading without the
    # old floating rectangular slabs.
    ring_mesh(
        "CH101_JacketTorsoShell",
        0.0,
        [(1.92, 0.45, 0.315), (2.08, 0.53, 0.345), (2.38, 0.56, 0.34), (2.57, 0.48, 0.295)],
        m["white"],
        root,
        segments=40,
    )
    curve("CH101_JacketZipL", [(-0.045, -0.355, 2.54), (-0.09, -0.395, 2.28), (-0.13, -0.35, 1.96)], 0.012, m["cyan"], root)
    curve("CH101_JacketZipR", [(0.045, -0.355, 2.54), (0.09, -0.395, 2.28), (0.13, -0.35, 1.96)], 0.012, m["cyan"], root)
    for side in (-1, 1):
        capsule("CH101_JacketSleeve", (side * 0.30, 0.0, 2.20), (side * 0.47, -0.02, 1.91), 0.115, m["graphite"], root)
        capsule("CH101_JacketForeSleeve", (side * 0.47, -0.02, 1.91), (side * 0.59, -0.06, 1.68), 0.085, m["graphite"], root)
        rounded_cube("CH101_ThighStrap", (side * 0.215, -0.255, 1.05), (0.17, 0.018, 0.022), m["gold"], root, 0.012)
        ring_mesh(
            "CH101_BootUpperL" if side < 0 else "CH101_BootUpperR",
            side * 0.18,
            [(0.08, 0.15, 0.17), (0.22, 0.145, 0.16), (0.48, 0.125, 0.14)],
            m["graphite"],
            root,
            segments=28,
        )
        rounded_cube("CH101_BootToe", (side * 0.18, -0.285, 0.10), (0.17, 0.19, 0.075), m["white"], root, 0.045)
        rounded_cube("CH101_BootSole", (side * 0.18, -0.27, 0.045), (0.18, 0.205, 0.025), m["cyan"], root, 0.018)
    curve("CH101_JacketHem", [(-0.28, -0.24, 1.91), (0.0, -0.25, 1.88), (0.28, -0.24, 1.91)], 0.018, m["cyan"], root)


def add_equipment(root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    rounded_cube("CH101_SaberGrip", (0.69, -0.24, 1.67), (0.035, 0.035, 0.16), m["graphite"], root, 0.018)
    panel("CH101_SaberBlade", (0.69, -0.24, 2.05), 0.075, 0.045, 0.60, 0.025, m["cyan"], root)
    curve("CH101_SignalRibbon", [(-0.39, -0.18, 2.36), (-0.72, -0.08, 2.84), (-0.46, 0.0, 3.27), (0.20, 0.0, 3.42), (0.72, -0.12, 2.78), (0.46, -0.17, 2.30)], 0.038, m["cyan"], root)
    curve("CH101_RibbonAccent", [(-0.39, -0.20, 2.36), (-0.46, -0.01, 3.27), (0.20, -0.01, 3.42)], 0.009, m["gold"], root)
    rounded_cube("CH101_PouchL", (-0.32, -0.22, 1.79), (0.075, 0.05, 0.12), m["graphite"], root, 0.025)
    rounded_cube("CH101_PouchR", (0.32, -0.22, 1.79), (0.075, 0.05, 0.12), m["graphite"], root, 0.025)


def almond(name: str, center_x: float, center_z: float, width: float, height: float, y: float, material: bpy.types.Material, root: bpy.types.Object) -> bpy.types.Object:
    """Make a thin graphic almond plane facing the review camera.

    The previous spherical eye overlays read as toy googly eyes on the human
    head.  A layered almond plane preserves anime readability while keeping
    the MPFB facial planes visible for later sculpt/texture work.
    """
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


def add_anime_face(root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    # Keep the real MPFB head planes and add only the readable anime eye and
    # brow language.  Replacing the whole head with a primitive overlay caused
    # the previous WIP to read as a toy mask.
    for side in (-1, 1):
        almond("CH101_EyeWhiteL" if side < 0 else "CH101_EyeWhiteR", side * 0.115, 3.22, 0.12, 0.09, -0.382, m["eye"], root)
        almond("CH101_IrisL" if side < 0 else "CH101_IrisR", side * 0.115, 3.215, 0.058, 0.060, -0.395, m["iris"], root)
        almond("CH101_PupilL" if side < 0 else "CH101_PupilR", side * 0.115, 3.212, 0.025, 0.038, -0.402, m["pupil"], root)
        sphere("CH101_EyeHighlight", (side * 0.095, -0.412, 3.25), (0.010, 0.004, 0.014), m["eye_highlight"], root, segments=20)
        capsule("CH101_Brow", (side * 0.22, -0.385, 3.34), (side * 0.035, -0.396, 3.355), 0.008, m["hair"], root)
    sphere("CH101_Nose", (0.0, -0.398, 3.10), (0.022, 0.018, 0.035), m["skin_shadow"], root, segments=24)
    curve("CH101_Mouth", [(-0.055, -0.400, 3.02), (0.0, -0.408, 3.01), (0.055, -0.400, 3.02)], 0.007, m["lip"], root)


def add_styled_hair(root: bpy.types.Object, m: dict[str, bpy.types.Material]) -> None:
    sphere("CH101_HairCap", (0.0, 0.04, 3.48), (0.47, 0.34, 0.25), m["hair"], root)
    for index, dx in enumerate((-0.25, -0.15, -0.05, 0.06, 0.16, 0.25), start=1):
        curve(f"CH101_Bang_{index}", [(dx * 0.72, -0.34, 3.55), (dx, -0.405, 3.36), (dx * 0.82, -0.30, 3.04)], 0.012, m["hair"], root)
    curve("CH101_SideLockL", [(-0.39, -0.12, 3.45), (-0.48, -0.02, 3.15), (-0.38, 0.02, 2.84)], 0.028, m["hair"], root)
    curve("CH101_SideLockR", [(0.39, -0.12, 3.45), (0.48, -0.02, 3.15), (0.38, 0.02, 2.84)], 0.028, m["hair"], root)
    curve("CH101_Ponytail", [(0.28, 0.11, 3.52), (0.56, 0.16, 3.30), (0.54, 0.11, 2.95), (0.42, 0.04, 2.66)], 0.052, m["hair"], root)
    curve("CH101_PonytailCyan", [(0.48, 0.10, 3.18), (0.56, 0.05, 2.92), (0.42, 0.01, 2.68)], 0.016, m["cyan"], root)


def scene_setup(out: Path) -> None:
    scene = bpy.context.scene
    # Blender 4.x exposes EEVEE_NEXT while Blender 5.x renamed the enum to
    # EEVEE.  Keep the WIP reproducible on both local/CI installations.
    available_engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available_engines else "BLENDER_EEVEE"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.012, 0.016, 0.028)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.5, 0.0))
    floor = bpy.context.object
    floor.data.materials.append(mat("CH101ReviewFloor", (0.018, 0.025, 0.045, 1.0), 0.56))
    bpy.ops.object.camera_add(location=(0.50, -7.6, 2.05))
    camera = bpy.context.object
    camera.data.lens = 58
    look_at(camera, Vector((0, 0, 1.90)))
    scene.camera = camera
    scene.render.filepath = str(out / "renders" / "CH101_A_MPFStyled_WIP_3q.png")
    for location, energy, color in (((-4.0, -5.0, 6.0), 1200, (1.0, 0.80, 0.70)), ((4.0, -3.0, 4.0), 700, (0.45, 0.68, 1.0)), ((0.0, 3.5, 5.0), 950, (0.10, 0.60, 1.0))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = 4
        look_at(light, Vector((0, 0, 1.8)))


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
    for obj in imported:
        if obj != body:
            obj.hide_render = True
            obj.hide_viewport = True
    normalize_body(body, target_height=3.65)
    root = bpy.data.objects.new("CH101_A_MPFStyled_WIP_Root", None)
    bpy.context.collection.objects.link(root)
    body.parent = root
    body.name = "CH101_A_MPFBody_CC0_WIP"
    body.data.materials.append(mat("MAT_CH101_Skin", (0.82, 0.50, 0.47, 1), 0.54))
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    materials = {
        "skin": body.data.materials[0],
        "skin_shadow": mat("MAT_CH101_SkinShadow", (0.65, 0.30, 0.30, 1), 0.64),
        "eye": mat("MAT_CH101_EyeWhite", (0.96, 0.98, 1.0, 1), 0.22),
        "iris": mat("MAT_CH101_Iris", (0.03, 0.40, 0.62, 1), 0.18, metallic=0.05),
        "pupil": mat("MAT_CH101_Pupil", (0.004, 0.006, 0.015, 1), 0.10),
        "eye_highlight": mat("MAT_CH101_Highlight", (1.0, 1.0, 1.0, 1), 0.06, emission=True),
        "lip": mat("MAT_CH101_Lip", (0.46, 0.08, 0.12, 1), 0.30),
        "hair": mat("MAT_CH101_Hair", (0.008, 0.012, 0.025, 1), 0.22),
        "white": mat("MAT_CH101_White", (0.88, 0.88, 0.84, 1), 0.42),
        "graphite": mat("MAT_CH101_Graphite", (0.018, 0.026, 0.046, 1), 0.36),
        "gold": mat("MAT_CH101_Gold", (0.78, 0.38, 0.06, 1), 0.25, metallic=0.7),
        "cyan": mat("MAT_CH101_Cyan", (0.01, 0.42, 0.64, 1), 0.24, metallic=0.12, emission=True),
    }
    add_outfit(root, body, materials)
    add_anime_face(root, materials)
    add_styled_hair(root, materials)
    add_equipment(root, materials)
    root["status"] = "WIP / MPFB-STYLED BASE / NOT APPROVED"
    root["source_license"] = "CC0 1.0 Universal (MPFB base asset)"
    root["target_heads"] = "5.3-5.4"
    root["next"] = "replace WIP outfit/hair panels with production meshes; retopo; rig bind"
    scene_setup(out)
    scene = bpy.context.scene
    scene["re_camp_status"] = "WIP / MPFB-STYLED BASE / NOT APPROVED"
    scene["re_camp_character"] = "CH101-A Route Sprint"
    scene["re_camp_gate"] = "Gate A pending / Gate B blocked"
    scene["re_camp_source_license"] = "CC0 1.0 Universal"
    blend = out / "CH101_A_MPFStyledBase_WIP_v001.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if options.render:
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    body.data.calc_loop_triangles()
    report = {
        "status": "WIP / MPFB-STYLED BASE / NOT APPROVED",
        "blend": str(blend),
        "source_obj": str(base_obj),
        "source_license": "CC0 1.0 Universal",
        "body_vertices": len(body.data.vertices),
        "body_triangles": len(body.data.loop_triangles),
        "style_layers": ["CH101 face WIP", "hair WIP", "outfit WIP", "equipment WIP"],
        "gate_a": "PENDING",
        "gate_b": "BLOCKED / retopology and rig binding required",
        "notes": ["Human topology source", "CH101 styling still WIP", "Human visual review required"],
    }
    (out / "reports" / "CH101_A_MPFStyledBase_WIP_v001.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Generated {blend}")
    print("Status: WIP / MPFB-styled base / not approved")


if __name__ == "__main__":
    main()
